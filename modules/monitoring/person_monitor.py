"""
Lobby Person Monitor (SDD §4.2.7, FR-3 / FR-4)
==============================================

Tracks every person currently visible in the lobby (one entry per stable
track_id assigned by the person_tracker), accumulates their dwell time, and
publishes detection-level events on threshold breaches:

    "unknown_person_detected"  — payload: {track_id, dwell_time}
        Fired once when an unknown person has lingered longer than
        ``settings.monitoring.security_dwell_threshold`` (FR-4.1).

    "assistance_needed"        — payload: {track_id, guest_id, dwell_time}
        Fired once when a *known* in-house guest has lingered longer than
        ``settings.monitoring.assistance_dwell_threshold`` (FR-4.2).

Conversion of these detection events into stored Alert rows + email/SMS
delivery is the AlertNotifier's job (see modules/alerts/), keeping the
monitor pure and easy to unit-test.

Stale tracks (not touched within ``tracking_timeout`` seconds) are evicted
by ``remove_stale_tracks()``, called by the frame-ingest pipeline after
every recognition pass.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from config.logging_config import get_logger
from config.settings import settings
from core.event_bus import event_bus

logger = get_logger(__name__)


# ----------------------------------------------------------------------------
# Tracked-person dataclass
# ----------------------------------------------------------------------------
@dataclass
class TrackedPerson:
    """One person currently visible in the lobby.

    ``first_seen`` and ``last_seen`` are monotonic seconds (``time.perf_counter``)
    so that wall-clock changes don't corrupt dwell-time math.
    """
    track_id: int
    is_known: bool = False
    guest_id: Optional[int] = None
    # True when this person carries an admin-assigned staff badge — the
    # threshold checker will skip alert firing for them entirely.
    is_staff_badge: bool = False
    first_seen: float = field(default_factory=time.perf_counter)
    last_seen: float = field(default_factory=time.perf_counter)
    # alerts_fired[event_name] = True once that event has been published for
    # this track, providing per-track cooldown.
    alerts_fired: dict = field(default_factory=dict)

    @property
    def dwell_time(self) -> float:
        """Seconds elapsed between first sighting and last sighting."""
        return max(0.0, self.last_seen - self.first_seen)

    def touch(self) -> None:
        """Mark the person as seen again — refresh ``last_seen``."""
        self.last_seen = time.perf_counter()


# ----------------------------------------------------------------------------
# Monitor
# ----------------------------------------------------------------------------
class PersonMonitor:
    """Thread-safe in-memory registry of tracked persons.

    The frame-ingest pipeline calls:

        person_monitor.update(track_id=..., is_known=..., guest_id=...)
        person_monitor.check_thresholds()
        person_monitor.remove_stale_tracks()

    on every processed frame.
    """

    def __init__(self):
        self._tracks: dict[int, TrackedPerson] = {}
        self._lock = threading.RLock()
        # Thresholds (seconds) — overridable in tests
        self._security_threshold: float = float(
            settings.monitoring.security_dwell_threshold
        )
        self._assistance_threshold: float = float(
            settings.monitoring.assistance_dwell_threshold
        )
        self._tracking_timeout: float = float(settings.monitoring.tracking_timeout)

    # ------------------------------------------------------------------
    # Core lifecycle
    # ------------------------------------------------------------------
    def update(
        self,
        track_id: int,
        is_known: bool = False,
        guest_id: Optional[int] = None,
        is_staff_badge: bool = False,
    ) -> TrackedPerson:
        """Register a sighting of ``track_id`` — creates or refreshes the entry.

        If an existing unknown track is later recognized, this call promotes
        it (sets is_known + guest_id) without resetting dwell time.
        ``is_staff_badge=True`` exempts the track from all alert thresholds.
        """
        with self._lock:
            tp = self._tracks.get(track_id)
            if tp is None:
                tp = TrackedPerson(
                    track_id=track_id, is_known=is_known, guest_id=guest_id,
                    is_staff_badge=is_staff_badge,
                )
                self._tracks[track_id] = tp
            else:
                tp.touch()
                # Promote unknown → known when recognition succeeds later
                if is_known and not tp.is_known:
                    tp.is_known = True
                if guest_id is not None and tp.guest_id is None:
                    tp.guest_id = guest_id
                if is_staff_badge:
                    tp.is_staff_badge = True
            return tp

    @property
    def active_count(self) -> int:
        with self._lock:
            return len(self._tracks)

    def get_track(self, track_id: int) -> Optional[TrackedPerson]:
        with self._lock:
            return self._tracks.get(track_id)

    def get_all_tracks(self) -> list[TrackedPerson]:
        """Snapshot of current tracks — safe to mutate the returned list."""
        with self._lock:
            return list(self._tracks.values())

    def clear(self) -> None:
        with self._lock:
            self._tracks.clear()

    # ------------------------------------------------------------------
    # Threshold checks (publish detection events on first breach)
    # ------------------------------------------------------------------
    def check_thresholds(self) -> list[dict]:
        """Inspect every tracked person; fire detection events on first breach.

        Returns the list of events fired this call (useful for logging /
        tests). Each entry is `{event, track_id, ...}`.
        """
        fired: list[dict] = []
        with self._lock:
            for tp in self._tracks.values():
                # Staff-badged tracks are alert-exempt by design (off-duty
                # managers shouldn't trigger security/assistance pings).
                if tp.is_staff_badge:
                    continue
                dwell = tp.dwell_time

                if (
                    not tp.is_known
                    and dwell >= self._security_threshold
                    and not tp.alerts_fired.get("unknown_person_detected")
                ):
                    payload = {
                        "track_id": tp.track_id,
                        "dwell_time": dwell,
                    }
                    tp.alerts_fired["unknown_person_detected"] = True
                    fired.append({"event": "unknown_person_detected", **payload})
                    event_bus.publish("unknown_person_detected", **payload)
                    logger.info(
                        f"Security threshold breached: track={tp.track_id} dwell={dwell:.1f}s"
                    )

                elif (
                    tp.is_known
                    and dwell >= self._assistance_threshold
                    and not tp.alerts_fired.get("assistance_needed")
                ):
                    payload = {
                        "track_id": tp.track_id,
                        "guest_id": tp.guest_id,
                        "dwell_time": dwell,
                    }
                    tp.alerts_fired["assistance_needed"] = True
                    fired.append({"event": "assistance_needed", **payload})
                    event_bus.publish("assistance_needed", **payload)
                    logger.info(
                        f"Assistance threshold breached: track={tp.track_id} "
                        f"guest_id={tp.guest_id} dwell={dwell:.1f}s"
                    )
        return fired

    # ------------------------------------------------------------------
    # Stale eviction
    # ------------------------------------------------------------------
    def remove_stale_tracks(self) -> int:
        """Drop tracks whose ``last_seen`` is older than ``tracking_timeout``.

        Returns the number of tracks evicted. Called once per processed frame.
        """
        cutoff = time.perf_counter() - self._tracking_timeout
        with self._lock:
            stale = [tid for tid, tp in self._tracks.items() if tp.last_seen < cutoff]
            for tid in stale:
                del self._tracks[tid]
        if stale:
            logger.debug(f"Evicted {len(stale)} stale track(s)")
        return len(stale)


# Module-level singleton (api/routes/edge.py:21 imports this directly)
person_monitor = PersonMonitor()
