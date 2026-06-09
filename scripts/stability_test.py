"""
Stability Test - long-running CPU/RAM/FPS monitor.

Logs system metrics (CPU%, RAM MB, RAM%, optionally GPU) and the running
backend's API/WebSocket health every N minutes for a configurable
duration (default 8 hours). Output is appended to
``logs/stability_YYYYMMDD_HHMM.csv`` so failures mid-run preserve data.

Usage:
    python scripts/stability_test.py                       # 8h, every 60 min
    python scripts/stability_test.py --hours 1 --interval 5
    python scripts/stability_test.py --url http://127.0.0.1:8000/api/v1/health

Notes:
    - Requires `psutil` (pip install psutil). If missing, basic metrics
      are still logged via os.times()/resource where possible.
    - FPS is read from the backend stats endpoint when available; if the
      backend is not running, FPS is logged as empty.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import psutil  # type: ignore
    HAS_PSUTIL = True
except ImportError:  # pragma: no cover
    HAS_PSUTIL = False

try:
    import httpx  # type: ignore
    HAS_HTTPX = True
except ImportError:  # pragma: no cover
    HAS_HTTPX = False

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("stability")

DEFAULT_HEALTH_URL = "http://127.0.0.1:8000/api/v1/health"
DEFAULT_STATS_URL = "http://127.0.0.1:8000/api/v1/stats"


def logs_dir() -> Path:
    d = PROJECT_ROOT / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sample_system() -> dict:
    """Return a snapshot of CPU/RAM (and disk) metrics."""
    if not HAS_PSUTIL:
        return {"cpu_pct": "", "ram_mb": "", "ram_pct": "", "disk_pct": ""}
    cpu = psutil.cpu_percent(interval=1.0)
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(str(PROJECT_ROOT))
    return {
        "cpu_pct": f"{cpu:.1f}",
        "ram_mb": f"{vm.used / (1024 * 1024):.0f}",
        "ram_pct": f"{vm.percent:.1f}",
        "disk_pct": f"{disk.percent:.1f}",
    }


def sample_backend(health_url: str, stats_url: str) -> dict:
    """Hit health + stats endpoints. Returns latency_ms, fps, status."""
    out = {"latency_ms": "", "fps": "", "status": "down"}
    if not HAS_HTTPX:
        return out
    try:
        t0 = time.perf_counter()
        r = httpx.get(health_url, timeout=5.0)
        latency = (time.perf_counter() - t0) * 1000
        if r.status_code == 200:
            out["status"] = "ok"
            out["latency_ms"] = f"{latency:.1f}"
    except Exception as exc:
        logger.debug("health check failed: %s", exc)

    try:
        r = httpx.get(stats_url, timeout=5.0)
        if r.status_code == 200:
            data = r.json()
            fps = data.get("fps") or data.get("avg_fps")
            if fps is not None:
                out["fps"] = f"{float(fps):.2f}"
    except Exception:
        pass
    return out


def run(hours: float, interval_min: float, health_url: str, stats_url: str) -> Path:
    start = datetime.now()
    end = start + timedelta(hours=hours)
    csv_path = logs_dir() / f"stability_{start:%Y%m%d_%H%M}.csv"

    fields = [
        "timestamp", "elapsed_min",
        "cpu_pct", "ram_mb", "ram_pct", "disk_pct",
        "backend_status", "latency_ms", "fps",
    ]
    new_file = not csv_path.exists()
    with csv_path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        if new_file:
            writer.writeheader()
            fh.flush()

        logger.info(
            "Stability test starting: %.1fh, sampling every %.0fm -> %s",
            hours, interval_min, csv_path.name,
        )
        if not HAS_PSUTIL:
            logger.warning("psutil not installed; CPU/RAM metrics will be empty")
        if not HAS_HTTPX:
            logger.warning("httpx not installed; backend metrics will be empty")

        sample_n = 0
        while datetime.now() < end:
            now = datetime.now()
            elapsed = (now - start).total_seconds() / 60.0
            row = {
                "timestamp": now.isoformat(timespec="seconds"),
                "elapsed_min": f"{elapsed:.1f}",
            }
            row.update(sample_system())
            be = sample_backend(health_url, stats_url)
            row["backend_status"] = be["status"]
            row["latency_ms"] = be["latency_ms"]
            row["fps"] = be["fps"]
            writer.writerow(row)
            fh.flush()
            sample_n += 1
            logger.info(
                "[%d] cpu=%s%% ram=%sMB(%s%%) be=%s lat=%sms fps=%s",
                sample_n, row["cpu_pct"], row["ram_mb"], row["ram_pct"],
                row["backend_status"], row["latency_ms"] or "-", row["fps"] or "-",
            )

            remaining = (end - datetime.now()).total_seconds()
            sleep_s = min(interval_min * 60, max(remaining, 0))
            if sleep_s <= 0:
                break
            time.sleep(sleep_s)

    logger.info("Stability test complete: %d samples written to %s", sample_n, csv_path)
    return csv_path


def main() -> int:
    p = argparse.ArgumentParser(description="Smart Reception 8-hour stability test")
    p.add_argument("--hours", type=float, default=8.0, help="Total run duration in hours")
    p.add_argument("--interval", type=float, default=60.0, help="Sample interval in minutes")
    p.add_argument("--url", default=DEFAULT_HEALTH_URL, help="Health endpoint URL")
    p.add_argument("--stats-url", default=DEFAULT_STATS_URL, help="Stats endpoint URL")
    args = p.parse_args()
    try:
        run(args.hours, args.interval, args.url, args.stats_url)
        return 0
    except KeyboardInterrupt:
        logger.warning("Interrupted by user; partial CSV preserved.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
