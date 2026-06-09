"""
Laptop Edge Simulator
=====================
Emulates the Raspberry Pi edge device on a laptop so the whole pipeline
(frame -> server -> detection -> recognition -> dwell monitor -> alerts
-> WebSocket broadcast) can be exercised without real hardware.

Frame source priority:
    1. Laptop webcam via OpenCV (DSHOW on Windows, V4L2 on Linux)
    2. Directory of test images (--images-dir)
    3. Synthetic gradient frame (last resort)

Heartbeat is sent every N seconds. (The PIR module has been removed; the
camera streams continuously at full FPS with no motion gating or downtime.)

Usage:
    python scripts/laptop_edge.py
    python scripts/laptop_edge.py --fps 5 --duration 30
    python scripts/laptop_edge.py --images-dir tests/test_images
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


def _try_open_webcam(device_id: int):
    try:
        import cv2
        import platform
        backend = cv2.CAP_DSHOW if platform.system() == "Windows" else cv2.CAP_ANY
        cap = cv2.VideoCapture(device_id, backend)
        if cap.isOpened():
            ok, _ = cap.read()
            if ok:
                return cap
        cap.release()
    except Exception:
        pass
    return None


def _load_images(images_dir: Path):
    import cv2
    images = []
    if not images_dir.exists():
        return images
    for p in sorted(images_dir.iterdir()):
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
            img = cv2.imread(str(p))
            if img is not None:
                images.append(img)
    return images


def _synthetic_frame(i: int):
    import numpy as np
    h, w = 480, 640
    frame = np.zeros((h, w, 3), dtype=np.uint8)
    frame[:, :, 0] = (i * 7) % 256
    frame[:, :, 1] = (i * 13) % 256
    frame[:, :, 2] = (i * 19) % 256
    # Add a rectangle that vaguely resembles a person silhouette
    import cv2
    cx = (i * 5) % (w - 60) + 30
    cv2.rectangle(frame, (cx - 30, 100), (cx + 30, 380), (200, 200, 200), -1)
    cv2.circle(frame, (cx, 140), 30, (220, 200, 180), -1)
    return frame


def _encode_jpeg(frame) -> bytes:
    import cv2
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
    if not ok:
        raise RuntimeError("JPEG encode failed")
    return buf.tobytes()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=os.environ.get("SERVER_URL", "http://localhost:5000"))
    parser.add_argument("--api-key", default=os.environ.get("API_KEY", ""))
    parser.add_argument("--device-id", type=int, default=0)
    parser.add_argument("--fps", type=float, default=2.0)
    parser.add_argument("--duration", type=float, default=20.0, help="seconds; 0 = forever")
    parser.add_argument("--images-dir", default=str(PROJECT_ROOT / "tests" / "test_images"))
    parser.add_argument("--heartbeat-interval", type=float, default=10.0)
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: API_KEY missing. Set in .env or pass --api-key")
        sys.exit(1)

    import requests

    print(f"[edge] server={args.server} fps={args.fps} duration={args.duration}s")

    # Try webcam first
    cap = _try_open_webcam(args.device_id)
    images = []
    if cap is not None:
        print(f"[edge] using webcam device {args.device_id}")
        source = "webcam"
    else:
        images = _load_images(Path(args.images_dir))
        if images:
            print(f"[edge] webcam unavailable; using {len(images)} images from {args.images_dir}")
            source = "images"
        else:
            print(f"[edge] webcam unavailable and no images in {args.images_dir}; using synthetic frames")
            source = "synthetic"

    frame_url = f"{args.server.rstrip('/')}/api/edge/frame"
    hb_url = f"{args.server.rstrip('/')}/api/edge/heartbeat"
    headers = {"X-API-Key": args.api_key}

    start = time.time()
    last_hb = 0.0
    interval = 1.0 / max(args.fps, 0.1)
    i = 0
    sent = 0
    errors = 0

    try:
        while True:
            if args.duration > 0 and (time.time() - start) >= args.duration:
                break

            if source == "webcam":
                ok, frame = cap.read()
                if not ok:
                    print("[edge] webcam read failed; retrying...")
                    time.sleep(0.5)
                    continue
            elif source == "images":
                frame = images[i % len(images)]
            else:
                frame = _synthetic_frame(i)

            try:
                jpeg = _encode_jpeg(frame)
                payload = {"frame_b64": base64.b64encode(jpeg).decode("ascii"), "camera_id": "laptop"}
                r = requests.post(frame_url, json=payload, headers=headers, timeout=15)
                if r.ok:
                    data = r.json()
                    sent += 1
                    if sent % 5 == 1:
                        print(
                            f"[edge] frame {sent}: persons={data.get('persons_detected')} "
                            f"faces={data.get('faces_detected')} recognized={data.get('faces_recognized')} "
                            f"tracks={data.get('active_tracks')}"
                        )
                else:
                    errors += 1
                    print(f"[edge] HTTP {r.status_code}: {r.text[:200]}")
            except Exception as e:
                errors += 1
                print(f"[edge] request failed: {e}")

            now = time.time()
            if now - last_hb >= args.heartbeat_interval:
                try:
                    requests.get(hb_url, headers=headers, timeout=5)
                    last_hb = now
                except Exception as e:
                    print(f"[edge] heartbeat failed: {e}")

            i += 1
            time.sleep(interval)
    except KeyboardInterrupt:
        print("[edge] interrupted")
    finally:
        if cap is not None:
            cap.release()
        elapsed = time.time() - start
        print(f"[edge] done: sent={sent} errors={errors} elapsed={elapsed:.1f}s")


if __name__ == "__main__":
    main()
