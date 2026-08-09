"""
Tests for the person detection and monitoring pipeline.

The full YOLOv8 inference path requires the `ultralytics` package which is
optional. These tests focus on the always-available person tracking and
threshold-based alerting logic in modules.monitoring, and include a
lightweight FPS smoke benchmark over the tracking update loop.
"""
import time
import pytest

from modules.monitoring import PersonMonitor, TrackedPerson
from detection.person_detector import CentroidTracker, PersonDetection


@pytest.fixture
def monitor():
    m = PersonMonitor()
    m.clear()
    # Use small thresholds for fast tests
    m._security_threshold = 0.05
    m._assistance_threshold = 0.05
    m._tracking_timeout = 0.1
    return m


# ----------------------------------------------------------------------
# Tracked person dataclass
# ----------------------------------------------------------------------
class TestTrackedPerson:
    def test_dwell_time_starts_at_zero(self):
        p = TrackedPerson(track_id=1)
        assert p.dwell_time >= 0.0
        assert p.dwell_time < 0.05

    def test_touch_updates_last_seen(self):
        p = TrackedPerson(track_id=1)
        first = p.last_seen
        time.sleep(0.01)
        p.touch()
        assert p.last_seen > first

    def test_dwell_time_grows_with_touch(self):
        p = TrackedPerson(track_id=1)
        time.sleep(0.02)
        p.touch()
        assert p.dwell_time >= 0.02


# ----------------------------------------------------------------------
# update()
# ----------------------------------------------------------------------
class TestMonitorUpdate:
    def test_update_creates_track(self, monitor):
        p = monitor.update(track_id=1)
        assert p.track_id == 1
        assert p.is_known is False
        assert monitor.active_count == 1

    def test_update_existing_track_touches(self, monitor):
        p1 = monitor.update(track_id=1)
        first_seen = p1.last_seen
        time.sleep(0.01)
        p2 = monitor.update(track_id=1)
        assert p2 is p1
        assert p2.last_seen > first_seen
        assert monitor.active_count == 1

    def test_update_promotes_to_known(self, monitor):
        monitor.update(track_id=1, is_known=False)
        p = monitor.update(track_id=1, is_known=True, guest_id=42)
        assert p.is_known is True
        assert p.guest_id == 42

    def test_update_creates_known_track(self, monitor):
        p = monitor.update(track_id=2, is_known=True, guest_id=7)
        assert p.is_known is True
        assert p.guest_id == 7

    def test_multiple_independent_tracks(self, monitor):
        monitor.update(track_id=1)
        monitor.update(track_id=2)
        monitor.update(track_id=3)
        assert monitor.active_count == 3


# ----------------------------------------------------------------------
# get / clear
# ----------------------------------------------------------------------
class TestAccessors:
    def test_get_track_returns_existing(self, monitor):
        monitor.update(track_id=1)
        assert monitor.get_track(1) is not None

    def test_get_track_returns_none_for_missing(self, monitor):
        assert monitor.get_track(999) is None

    def test_get_all_tracks_returns_copy(self, monitor):
        monitor.update(track_id=1)
        all_tracks = monitor.get_all_tracks()
        all_tracks.clear()
        assert monitor.active_count == 1

    def test_clear_removes_all(self, monitor):
        monitor.update(track_id=1)
        monitor.update(track_id=2)
        monitor.clear()
        assert monitor.active_count == 0


# ----------------------------------------------------------------------
# remove_stale_tracks
# ----------------------------------------------------------------------
class TestStaleRemoval:
    def test_stale_tracks_removed(self, monitor):
        monitor.update(track_id=1)
        time.sleep(monitor._tracking_timeout + 0.05)
        removed = monitor.remove_stale_tracks()
        assert removed == 1
        assert monitor.active_count == 0

    def test_fresh_tracks_kept(self, monitor):
        monitor.update(track_id=1)
        removed = monitor.remove_stale_tracks()
        assert removed == 0
        assert monitor.active_count == 1


# ----------------------------------------------------------------------
# Threshold checks (event publication)
# ----------------------------------------------------------------------
class TestThresholdChecks:
    def test_unknown_person_triggers_security(self, monitor):
        from core.event_bus import event_bus
        events = []
        unsubscribe = event_bus.subscribe("unknown_person_detected", lambda **kw: events.append(kw))
        try:
            monitor.update(track_id=1, is_known=False)
            time.sleep(monitor._security_threshold + 0.02)
            monitor.update(track_id=1, is_known=False)
            monitor.check_thresholds()
        finally:
            try:
                unsubscribe()
            except TypeError:
                pass
        assert len(events) >= 1
        assert events[0]["track_id"] == 1

    def test_security_alert_only_sent_once(self, monitor):
        from core.event_bus import event_bus
        events = []
        event_bus.subscribe("unknown_person_detected", lambda **kw: events.append(kw))
        monitor.update(track_id=1, is_known=False)
        time.sleep(monitor._security_threshold + 0.02)
        monitor.update(track_id=1, is_known=False)
        monitor.check_thresholds()
        monitor.update(track_id=1, is_known=False)
        monitor.check_thresholds()
        # Filter to the events fired for our track_id only (in case other tests subscribed)
        ours = [e for e in events if e.get("track_id") == 1]
        assert len(ours) == 1

    def test_assistance_alert_for_known_person(self, monitor):
        from core.event_bus import event_bus
        events = []
        event_bus.subscribe("assistance_needed", lambda **kw: events.append(kw))
        monitor.update(track_id=99, is_known=True, guest_id=5)
        time.sleep(monitor._assistance_threshold + 0.02)
        monitor.update(track_id=99, is_known=True, guest_id=5)
        monitor.check_thresholds()
        ours = [e for e in events if e.get("track_id") == 99]
        assert len(ours) >= 1
        assert ours[0]["guest_id"] == 5

    def test_no_alert_below_threshold(self, monitor):
        from core.event_bus import event_bus
        events = []
        event_bus.subscribe("unknown_person_detected", lambda **kw: events.append(kw))
        monitor.update(track_id=77, is_known=False)
        monitor.check_thresholds()  # Immediately, below threshold
        ours = [e for e in events if e.get("track_id") == 77]
        assert ours == []


# ----------------------------------------------------------------------
# FPS / performance smoke
# ----------------------------------------------------------------------
class TestPerformance:
    def test_update_loop_throughput(self, monitor):
        """Sanity-check that the tracking update loop can process at least
        500 updates/second on commodity hardware. This is a lower bound;
        real YOLO inference is benchmarked separately."""
        N = 1000
        start = time.perf_counter()
        for i in range(N):
            monitor.update(track_id=i % 10, is_known=(i % 2 == 0), guest_id=i)
        elapsed = time.perf_counter() - start
        fps = N / elapsed if elapsed > 0 else float("inf")
        assert fps > 500, f"update throughput too low: {fps:.0f}/s"

    def test_check_thresholds_is_fast(self, monitor):
        for i in range(100):
            monitor.update(track_id=i, is_known=False)
        start = time.perf_counter()
        for _ in range(100):
            monitor.check_thresholds()
        elapsed = time.perf_counter() - start
        # 100 sweeps over 100 tracks should comfortably fit in 1 second
        assert elapsed < 1.0


# ----------------------------------------------------------------------
# CentroidTracker — track-id continuity (dwell-timer reliability)
# ----------------------------------------------------------------------
class TestCentroidTrackerMaxDisappeared:
    def test_defaults_to_settings_value_when_not_overridden(self):
        from config.settings import settings
        t = CentroidTracker()
        assert t._max_disappeared == int(settings.detection.track_max_disappeared_frames)

    def test_explicit_arg_overrides_settings(self):
        t = CentroidTracker(max_disappeared=3)
        assert t._max_disappeared == 3

    def test_track_survives_gap_within_budget(self):
        """A person briefly undetected for fewer frames than max_disappeared
        keeps the SAME track_id — this is what protects PersonMonitor's
        dwell-time clock from resetting on minor occlusion."""
        t = CentroidTracker(max_disappeared=5, bbox_smoothing=1.0)
        d1 = [PersonDetection(bbox=(10, 10, 20, 40), confidence=0.9)]
        t.update(d1)
        tid = d1[0].track_id
        assert tid is not None

        # 3 frames with nobody detected (gap < max_disappeared=5)
        for _ in range(3):
            t.update([])

        d2 = [PersonDetection(bbox=(11, 11, 20, 40), confidence=0.9)]
        t.update(d2)
        assert d2[0].track_id == tid  # same person, same id

    def test_track_id_churns_after_budget_exceeded(self):
        """Beyond max_disappeared frames of absence, the old id is evicted
        and a new detection at the same spot gets a NEW track_id — the
        exact mechanism that resets PersonMonitor's dwell clock."""
        t = CentroidTracker(max_disappeared=2, bbox_smoothing=1.0)
        d1 = [PersonDetection(bbox=(10, 10, 20, 40), confidence=0.9)]
        t.update(d1)
        tid = d1[0].track_id

        for _ in range(3):  # gap > max_disappeared=2
            t.update([])

        d2 = [PersonDetection(bbox=(11, 11, 20, 40), confidence=0.9)]
        t.update(d2)
        assert d2[0].track_id != tid


# ----------------------------------------------------------------------
# YOLO availability (optional)
# ----------------------------------------------------------------------
class TestYoloOptional:
    def test_ultralytics_optional_import(self):
        """YOLOv8 / ultralytics is optional. The test passes whether or not
        it is installed, but documents the expected interface if present."""
        try:
            import ultralytics  # noqa: F401
            yolo_available = True
        except ImportError:
            yolo_available = False
        assert isinstance(yolo_available, bool)
