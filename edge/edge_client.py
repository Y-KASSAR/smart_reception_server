"""
Edge Client (Raspberry Pi)
==========================
Implements SDD §4.1 components:

    C1 VideoCapture       — capture frames from a USB webcam (OpenCV)
    C2 MotionDetector     — REMOVED (PIR module taken out; camera is always-on)
    C3 FrameStreamer      — JPEG-compress frames into a bounded queue
    C4 EdgeNetworkClient  — POST frames + heartbeat to the AI server

NOTE: The PIR motion sensor (C2 MotionDetector) has been removed. The
camera now streams continuously at the full configured FPS (30) with no
idle/downtime — every loop iteration captures and uploads a frame.

Run on a Raspberry Pi 4 (Raspberry Pi OS 64-bit, Python 3.9+) as a
systemd service. The companion AI server must be reachable at the URL
configured via the SERVER_URL environment variable.
"""
from __future__ import annotations

import base64
import logging
import os
import platform
import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("edge_client")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s.%(funcName)s - %(message)s",
)


# ---------------------------------------------------------------
# C1: Video Capture (SDD §4.1.1)
# ---------------------------------------------------------------

class VideoCapture:
    """Capture video frames from a USB webcam via OpenCV."""

    def __init__(self, device_id: int = 0, resolution=(1920, 1080), fps: int = 30):
        self.device_id = device_id
        self.resolution = resolution
        self.fps = fps
        self.cap = None
        self.is_active = False

    def start(self) -> None:
        import cv2
        backend = cv2.CAP_V4L2 if platform.system() == "Linux" else cv2.CAP_DSHOW
        self.cap = cv2.VideoCapture(self.device_id, backend)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        # Minimize the driver's frame buffer so reads return the FRESHEST frame
        # instead of a stale queued one — critical for low end-to-end latency.
        try:
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        except Exception:
            pass
        self.is_active = self.cap.isOpened()
        if not self.is_active:
            logger.error(f"VideoCapture: failed to open device {self.device_id}")
        else:
            logger.info(
                f"VideoCapture started: device={self.device_id}, "
                f"res={self.resolution}, fps={self.fps}"
            )

    def stop(self) -> None:
        if self.cap is not None:
            self.cap.release()
        self.cap = None
        self.is_active = False
        logger.info("VideoCapture stopped")

    def capture_frame(self):
        if not self.is_active or self.cap is None:
            return None
        ok, frame = self.cap.read()
        return frame if ok else None

    def is_running(self) -> bool:
        return self.is_active


# ---------------------------------------------------------------
# C2: Motion Detector (SDD §4.1.2) -- REMOVED
# ---------------------------------------------------------------
# The PIR motion sensor module has been removed from the project. The
# camera now runs always-on at full FPS with no motion gating. The original
# MotionDetector implementation is kept here, commented out, for reference.
#
# class MotionDetector:
#     """PIR motion detector wired on Raspberry Pi GPIO (BCM)."""
#
#     def __init__(self, gpio_pin: int = 17, debounce_ms: int = 2000, idle_timeout_s: int = 60):
#         self.gpio_pin = gpio_pin
#         self.debounce_ms = debounce_ms
#         self.idle_timeout_s = idle_timeout_s
#         self.last_trigger: float = 0.0
#         self._gpio = None
#
#     def setup(self) -> None:
#         try:
#             import RPi.GPIO as GPIO
#             GPIO.setmode(GPIO.BCM)
#             GPIO.setup(self.gpio_pin, GPIO.IN)
#             self._gpio = GPIO
#             logger.info(f"MotionDetector ready on GPIO BCM {self.gpio_pin}")
#         except Exception as e:
#             logger.warning(f"MotionDetector: GPIO unavailable ({e}); running in stub mode")
#             self._gpio = None
#
#     def is_detected(self) -> bool:
#         now = time.time() * 1000.0
#         if (now - self.last_trigger) < self.debounce_ms:
#             return False
#         if self._gpio is None:
#             return False
#         try:
#             if self._gpio.input(self.gpio_pin):
#                 self.last_trigger = now
#                 return True
#         except Exception as e:
#             logger.error(f"MotionDetector read error: {e}")
#         return False
#
#     def get_state(self) -> dict:
#         return {
#             "gpio_pin": self.gpio_pin,
#             "last_trigger": self.last_trigger,
#             "idle": (time.time() * 1000.0 - self.last_trigger) > self.idle_timeout_s * 1000,
#         }
#
#     def cleanup(self) -> None:
#         if self._gpio is not None:
#             try:
#                 self._gpio.cleanup()
#             except Exception:
#                 pass


# ---------------------------------------------------------------
# C3: Frame Streamer (SDD §4.1.3)
# ---------------------------------------------------------------

class FrameStreamer:
    """JPEG-compress frames and queue them for transmission."""

    def __init__(self, jpeg_quality: int = 80, max_queue_size: int = 50):
        self.jpeg_quality = jpeg_quality
        self.max_queue_size = max_queue_size
        self.queue: "queue.Queue[bytes]" = queue.Queue(maxsize=max_queue_size)

    def compress(self, frame) -> bytes:
        import cv2
        ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality])
        if not ok:
            raise RuntimeError("JPEG encode failed")
        return buf.tobytes()

    def queue_frame(self, frame_bytes: bytes) -> None:
        # Drop-oldest strategy
        if self.queue.full():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
        try:
            self.queue.put_nowait(frame_bytes)
        except queue.Full:
            pass

    def get_next_frame(self) -> Optional[bytes]:
        try:
            return self.queue.get_nowait()
        except queue.Empty:
            return None


# ---------------------------------------------------------------
# C4: Edge Network Client (SDD §4.1.4)
# ---------------------------------------------------------------

class EdgeNetworkClient:
    """Transmit frames + heartbeats to the AI server with retry/backoff."""

    def __init__(self, server_url: str, api_key: str, camera_id: str = "main"):
        self.server_url = server_url.rstrip("/")
        self.api_key = api_key
        self.camera_id = camera_id
        self._buffer: list = []
        self._max_buffer = 200  # NFR-3.5: local buffer on network loss

    def _headers(self) -> dict:
        return {"X-API-Key": self.api_key}

    def upload_frame(self, frame_bytes: bytes) -> dict:
        import requests
        url = f"{self.server_url}/api/edge/frame"
        body = {
            "frame_b64": base64.b64encode(frame_bytes).decode("ascii"),
            "camera_id": self.camera_id,
        }
        backoff = 1.0
        for attempt in range(4):
            try:
                r = requests.post(url, json=body, headers=self._headers(), timeout=10)
                r.raise_for_status()
                # On success, flush local buffer best-effort
                self._flush_buffer()
                return r.json()
            except Exception as e:
                logger.warning(f"upload_frame attempt {attempt+1} failed: {e}")
                time.sleep(backoff)
                backoff *= 2
        # Buffer locally
        if len(self._buffer) >= self._max_buffer:
            self._buffer.pop(0)
        self._buffer.append(frame_bytes)
        return {"buffered": True, "buffer_size": len(self._buffer)}

    def _flush_buffer(self) -> None:
        if not self._buffer:
            return
        import requests
        url = f"{self.server_url}/api/edge/frame"
        flushed = 0
        while self._buffer:
            fb = self._buffer[0]
            try:
                body = {
                    "frame_b64": base64.b64encode(fb).decode("ascii"),
                    "camera_id": self.camera_id,
                }
                r = requests.post(url, json=body, headers=self._headers(), timeout=5)
                if r.ok:
                    self._buffer.pop(0)
                    flushed += 1
                else:
                    break
            except Exception:
                break
        if flushed:
            logger.info(f"Flushed {flushed} buffered frames")

    def send_heartbeat(self) -> dict:
        import requests
        url = f"{self.server_url}/api/edge/heartbeat"
        try:
            r = requests.get(url, headers=self._headers(), timeout=5)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"send_heartbeat failed: {e}")
            return {"status": "error", "error": str(e)}

    def handle_response(self, response: dict) -> None:
        if not response:
            return
        if response.get("buffered"):
            return
        n = response.get("persons_detected", 0)
        if n:
            logger.debug(f"Server detected {n} persons in last frame")


# ---------------------------------------------------------------
# Main loop (entrypoint for systemd)
# ---------------------------------------------------------------

@dataclass
class EdgeConfig:
    server_url: str
    api_key: str
    camera_id: str = "main"
    device_id: int = 0
    # PIR module removed — sensor pin no longer used.
    # pir_pin: int = 17
    fps: int = 30
    heartbeat_interval_s: int = 30
    # PIR module removed — camera always streams continuously at the configured
    # FPS with no motion gating and no downtime (was SysRS FR-7.8 "always-on
    # override", now the only mode). Flag kept commented for reference.
    # pir_disabled: bool = True
    # Capture resolution + JPEG quality — lower these to relieve server-side
    # MTCNN/FaceNet CPU pressure when the ingest pipeline is the bottleneck.
    res_width: int = 1920
    res_height: int = 1080
    jpeg_quality: int = 80


def _truthy(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes", "on")


def _load_config() -> EdgeConfig:
    return EdgeConfig(
        server_url=os.environ.get("SERVER_URL", "http://localhost:5000"),
        api_key=os.environ.get("API_KEY", ""),
        camera_id=os.environ.get("CAMERA_ID", "main"),
        device_id=int(os.environ.get("DEVICE_ID", "0")),
        # PIR module removed — PIR_PIN / PIR_DISABLED env vars no longer read.
        # pir_pin=int(os.environ.get("PIR_PIN", "17")),
        fps=int(os.environ.get("FPS", "30")),
        heartbeat_interval_s=int(os.environ.get("HEARTBEAT_INTERVAL_S", "30")),
        # pir_disabled=_truthy(os.environ.get("PIR_DISABLED", "false")),
        res_width=int(os.environ.get("RES_WIDTH", "1920")),
        res_height=int(os.environ.get("RES_HEIGHT", "1080")),
        jpeg_quality=int(os.environ.get("JPEG_QUALITY", "80")),
    )


def main() -> None:
    cfg = _load_config()
    if not cfg.api_key:
        logger.error("API_KEY environment variable is required")
        return

    capture = VideoCapture(
        device_id=cfg.device_id,
        resolution=(cfg.res_width, cfg.res_height),
        fps=cfg.fps,
    )
    # PIR module removed — no motion detector is instantiated.
    # motion = MotionDetector(gpio_pin=cfg.pir_pin)
    streamer = FrameStreamer(jpeg_quality=cfg.jpeg_quality)
    client = EdgeNetworkClient(server_url=cfg.server_url, api_key=cfg.api_key, camera_id=cfg.camera_id)

    capture.start()
    logger.info(
        f"PIR removed — always-on capture at {cfg.fps} fps; "
        f"latest-frame streaming for low latency (near real-time)"
    )

    stop_event = threading.Event()

    def heartbeat_loop():
        while not stop_event.wait(cfg.heartbeat_interval_s):
            client.send_heartbeat()

    hb_thread = threading.Thread(target=heartbeat_loop, name="hb", daemon=True)
    hb_thread.start()

    # ---- Latest-frame capture thread -----------------------------------
    # A dedicated thread continuously grabs frames at the camera's FPS and
    # keeps only the most recent one. The upload loop below always sends that
    # newest frame and discards anything captured while a (slower) server
    # round-trip was in flight. This decouples capture from processing so we
    # stream the freshest possible frame — the key to "near real-time".
    latest = {"frame": None}
    latest_lock = threading.Lock()

    def capture_loop():
        frame_interval = 1.0 / max(1, cfg.fps)
        while not stop_event.is_set():
            frame = capture.capture_frame()
            if frame is not None:
                with latest_lock:
                    latest["frame"] = frame
            time.sleep(frame_interval)

    cap_thread = threading.Thread(target=capture_loop, name="capture", daemon=True)
    cap_thread.start()

    try:
        while not stop_event.is_set():
            # Grab-and-consume the freshest frame (drop-stale, latest wins).
            with latest_lock:
                frame = latest["frame"]
                latest["frame"] = None
            if frame is None:
                time.sleep(0.002)
                continue
            try:
                jpeg = streamer.compress(frame)
                # Upload is blocking on the full server pipeline, so it self-
                # paces the loop; no fixed FPS sleep is added here to keep
                # latency minimal.
                resp = client.upload_frame(jpeg)
                client.handle_response(resp)
            except Exception as e:
                logger.error(f"frame pipeline error: {e}")
    except KeyboardInterrupt:
        logger.info("Edge client interrupted")
    finally:
        stop_event.set()
        capture.stop()
        # PIR module removed — no motion sensor cleanup required.
        # motion.cleanup()


if __name__ == "__main__":
    main()
