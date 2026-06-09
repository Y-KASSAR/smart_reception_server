"""
Recognition Accuracy Harness — TPR / FPR / latency
==================================================
Streams the server's WebSocket events and tallies recognition outcomes
during a manual benchmark.

A background asyncio reader drains the WebSocket continuously so the
TCP buffer doesn't fill while the operator is staging the next attempt.
Without this, the server's `await ws.send_text()` would block on a full
client buffer and the connection silently dies after the first window.

Usage::

    python scripts/accuracy_test.py --target-guest "Youssef Kassar" --tpr 20 --fpr 10
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

try:
    import websockets  # type: ignore
except ImportError:
    sys.exit("Install websockets first: pip install websockets")


@dataclass
class Attempt:
    kind: str           # "TPR" or "FPR"
    matched: bool
    similarity: float
    latency_ms: float
    detections_seen: int
    identifications_seen: int


@dataclass
class Report:
    target_guest: str
    tpr_attempts: list[Attempt] = field(default_factory=list)
    fpr_attempts: list[Attempt] = field(default_factory=list)

    def tpr(self) -> float:
        if not self.tpr_attempts:
            return 0.0
        return sum(1 for a in self.tpr_attempts if a.matched) / len(self.tpr_attempts)

    def fpr(self) -> float:
        if not self.fpr_attempts:
            return 0.0
        return sum(1 for a in self.fpr_attempts if a.matched) / len(self.fpr_attempts)

    def avg_latency_ms(self) -> float:
        hits = [a.latency_ms for a in self.tpr_attempts if a.matched and a.latency_ms > 0]
        return sum(hits) / len(hits) if hits else 0.0


async def reader_task(ws, queue: asyncio.Queue):
    """Continuously drain the WebSocket into a queue. Runs forever until cancelled."""
    while True:
        try:
            raw = await ws.recv()
        except Exception:
            return
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        try:
            queue.put_nowait((time.monotonic(), msg))
        except asyncio.QueueFull:
            # Should be unbounded, but guard anyway
            pass


async def drain_queue(queue: asyncio.Queue) -> None:
    while not queue.empty():
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return


async def watch_window(queue: asyncio.Queue, target_guest: str, window_s: float) -> Attempt:
    """Consume events from the queue for `window_s` seconds and tally outcomes."""
    await drain_queue(queue)  # discard backlog from before the window
    start = time.monotonic()
    matched = False
    best_sim = 0.0
    latency_ms = 0.0
    det_count = 0
    ident_count = 0
    target_lc = target_guest.lower().strip()

    while time.monotonic() - start < window_s:
        remaining = window_s - (time.monotonic() - start)
        try:
            ts, msg = await asyncio.wait_for(queue.get(), timeout=max(0.05, remaining))
        except asyncio.TimeoutError:
            continue
        ev = msg.get("event") or msg.get("type")
        if ev == "detection_update":
            det_count += 1
        elif ev == "guest_identified":
            ident_count += 1
            name = (msg.get("name") or "").lower().strip()
            sim = float(msg.get("confidence") or 0.0)
            if sim > best_sim:
                best_sim = sim
            if name == target_lc and not matched:
                matched = True
                latency_ms = (ts - start) * 1000.0

    return Attempt(kind="?", matched=matched, similarity=best_sim,
                   latency_ms=latency_ms, detections_seen=det_count,
                   identifications_seen=ident_count)


async def prompt(text: str) -> None:
    """Blocking input() pushed to a thread so the reader keeps running."""
    await asyncio.to_thread(input, text)


async def main(args):
    uri = args.ws_url
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri, max_size=None, ping_interval=20, ping_timeout=20) as ws:
        queue: asyncio.Queue = asyncio.Queue()
        reader = asyncio.create_task(reader_task(ws, queue))
        print("Connected. Press Enter on each prompt to start a 5-second capture window.\n")

        report = Report(target_guest=args.target_guest)

        try:
            print("=" * 70)
            print(f"PHASE 1 - TPR ({args.tpr} attempts)")
            print("Walk into the camera view. The system should recognise you.")
            print("=" * 70)
            for i in range(1, args.tpr + 1):
                await prompt(f"[TPR {i}/{args.tpr}] Position yourself, then press Enter...")
                print(f"  [watching for {args.window}s...]")
                a = await watch_window(queue, args.target_guest, window_s=args.window)
                a.kind = "TPR"
                report.tpr_attempts.append(a)
                verdict = "MATCH " if a.matched else "MISS  "
                print(f"  {verdict} sim={a.similarity:.3f} latency={a.latency_ms:.0f}ms dets={a.detections_seen} idents={a.identifications_seen}\n")

            print("=" * 70)
            print(f"PHASE 2 - FPR ({args.fpr} attempts)")
            print("Hold up a phone photo of someone else. System should NOT match.")
            print("=" * 70)
            for i in range(1, args.fpr + 1):
                await prompt(f"[FPR {i}/{args.fpr}] Hold up a stranger's photo, then press Enter...")
                print(f"  [watching for {args.window}s...]")
                a = await watch_window(queue, args.target_guest, window_s=args.window)
                a.kind = "FPR"
                report.fpr_attempts.append(a)
                verdict = "FALSE+" if a.matched else "OK    "
                print(f"  {verdict} sim={a.similarity:.3f} dets={a.detections_seen} idents={a.identifications_seen}\n")
        finally:
            reader.cancel()
            try:
                await reader
            except asyncio.CancelledError:
                pass

        # Summary
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        tpr_hits = sum(1 for a in report.tpr_attempts if a.matched)
        fpr_hits = sum(1 for a in report.fpr_attempts if a.matched)
        print(f"  Target guest        : {report.target_guest}")
        print(f"  TPR (True Positive) : {report.tpr() * 100:.1f}%  ({tpr_hits}/{len(report.tpr_attempts)})")
        print(f"  FPR (False Positive): {report.fpr() * 100:.1f}%  ({fpr_hits}/{len(report.fpr_attempts)})")
        print(f"  Avg recognition lat : {report.avg_latency_ms():.0f} ms (TPR hits only)")
        print(f"  SysRS targets       : TPR >= 85%, FPR < 5%, latency <= 2000ms")

        out = {
            "target_guest": report.target_guest,
            "tpr_percent": report.tpr() * 100,
            "fpr_percent": report.fpr() * 100,
            "avg_latency_ms": report.avg_latency_ms(),
            "tpr_attempts": [asdict(a) for a in report.tpr_attempts],
            "fpr_attempts": [asdict(a) for a in report.fpr_attempts],
        }
        ts = int(time.time())
        path = Path("docs") / f"accuracy_{ts}.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(out, indent=2))
        print(f"\nReport saved: {path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--ws-url", default="ws://localhost:5000/ws")
    p.add_argument("--target-guest", required=True, help="Guest name as stored")
    p.add_argument("--tpr", type=int, default=20)
    p.add_argument("--fpr", type=int, default=10)
    p.add_argument("--window", type=float, default=5.0, help="Seconds per attempt")
    args = p.parse_args()
    asyncio.run(main(args))
