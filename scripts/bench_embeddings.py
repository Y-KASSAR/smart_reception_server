"""
NFR-1.10 benchmark — 1000-embedding recognition latency
=========================================================
Seeds the in-memory embedding cache with N synthetic 512-D vectors and
times :meth:`FaceRecognitionEngine._find_best_match` over a fresh query
vector ``REPS`` times. Reports min / p50 / p95 / mean / max latency.

The SysRS target is **< 2000 ms per match at N >= 1000**. With the
vectorised embedding matrix, we expect single-digit milliseconds on the
RTX 3050 Ti laptop (CPU side; matching itself doesn't need the GPU).

Usage::

    python scripts/bench_embeddings.py
    python scripts/bench_embeddings.py --n 5000 --reps 200
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from modules.recognition.face_recognizer import FaceRecognitionEngine


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=1000, help="Synthetic embeddings to load")
    p.add_argument("--reps", type=int, default=500, help="Match calls to time")
    p.add_argument("--threshold", type=float, default=0.8)
    args = p.parse_args()

    rng = np.random.default_rng(seed=42)

    fre = FaceRecognitionEngine()
    # Skip model load; we only need the matcher path.
    fre._threshold = args.threshold

    # Seed: N synthetic L2-normalised 512-D vectors, one per "guest"
    embeddings: dict = {}
    for gid in range(1, args.n + 1):
        v = rng.normal(size=512).astype(np.float32)
        v /= np.linalg.norm(v) or 1.0
        embeddings[gid] = [v]
    fre._guest_embeddings = embeddings
    fre._guest_names = {gid: f"Synthetic #{gid}" for gid in embeddings}
    # Trigger the vectorised matrix build (if your face_recognizer caches one)
    fre._emb_matrix = None
    fre._emb_guest_ids = []

    # Time the matcher
    print(f"Benchmarking: N={args.n} embeddings, reps={args.reps}, threshold={args.threshold}")
    times_ms: list[float] = []
    for _ in range(args.reps):
        q = rng.normal(size=512).astype(np.float32)
        q /= np.linalg.norm(q) or 1.0
        t0 = time.perf_counter()
        gid, sim = fre._find_best_match(q)
        times_ms.append((time.perf_counter() - t0) * 1000.0)

    times_ms.sort()
    p50 = times_ms[len(times_ms) // 2]
    p95 = times_ms[int(len(times_ms) * 0.95)]

    print()
    print(f"  min   {min(times_ms):8.3f} ms")
    print(f"  mean  {statistics.fmean(times_ms):8.3f} ms")
    print(f"  p50   {p50:8.3f} ms")
    print(f"  p95   {p95:8.3f} ms")
    print(f"  max   {max(times_ms):8.3f} ms")
    print()
    target_ms = 2000.0
    if p95 < target_ms:
        print(f"[PASS] p95 ({p95:.2f} ms) < SysRS target ({target_ms:.0f} ms)")
    else:
        print(f"[FAIL] p95 ({p95:.2f} ms) >= SysRS target ({target_ms:.0f} ms)")


if __name__ == "__main__":
    main()
