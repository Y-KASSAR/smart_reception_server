"""
Tests for AlertNotifier's cooldown gating, memory-bounded pruning, and the
event handlers that turn detection events into dispatch calls.

`_create_and_dispatch` is monkeypatched to a recording spy in every test so
these stay pure unit tests against the in-memory cooldown/dispatch logic —
no real database session or SMTP/Twilio call is ever touched here (those are
covered separately by the send_real_test_*.py scripts).
"""
import pytest

from modules.alerts.alert_notifier import AlertNotifier


@pytest.fixture
def notifier(monkeypatch):
    n = AlertNotifier.__new__(AlertNotifier)  # bypass __init__'s event_bus.subscribe()
    import threading
    n._lock = threading.RLock()
    n._last_fire = {}
    n._checks_since_prune = 0
    n._subscribed = True
    calls = []
    monkeypatch.setattr(n, "_create_and_dispatch", lambda **kw: calls.append(kw))
    n.calls = calls
    return n


# ----------------------------------------------------------------------
# Cooldown gating
# ----------------------------------------------------------------------
class TestCooldownCheck:
    def test_first_call_passes(self, notifier):
        assert notifier._cooldown_check(("wanted", 1)) is True

    def test_immediate_repeat_blocked(self, notifier):
        notifier._cooldown_check(("wanted", 1))
        assert notifier._cooldown_check(("wanted", 1)) is False

    def test_different_keys_independent(self, notifier):
        assert notifier._cooldown_check(("wanted", 1)) is True
        assert notifier._cooldown_check(("wanted", 2)) is True
        assert notifier._cooldown_check(("vip", 1)) is True

    def test_expired_cooldown_passes_again(self, notifier, monkeypatch):
        import sys
        import modules.alerts.alert_notifier  # noqa: F401 - ensure imported
        mod = sys.modules["modules.alerts.alert_notifier"]
        t = [1000.0]
        monkeypatch.setattr(mod, "_COOLDOWN_SECONDS", 10.0)
        monkeypatch.setattr("time.monotonic", lambda: t[0])
        assert notifier._cooldown_check(("wanted", 1)) is True
        t[0] += 5.0
        assert notifier._cooldown_check(("wanted", 1)) is False
        t[0] += 6.0  # total 11s elapsed > 10s cooldown
        assert notifier._cooldown_check(("wanted", 1)) is True


# ----------------------------------------------------------------------
# Opportunistic pruning — bounds _last_fire's memory growth
# ----------------------------------------------------------------------
class TestPruning:
    def test_prune_removes_expired_entries_after_threshold_checks(self, notifier, monkeypatch):
        import sys
        import modules.alerts.alert_notifier  # noqa: F401 - ensure imported
        mod = sys.modules["modules.alerts.alert_notifier"]
        t = [1000.0]  # nonzero start — 0.0 collides with the "never fired" sentinel
        monkeypatch.setattr(mod, "_COOLDOWN_SECONDS", 1.0)
        monkeypatch.setattr("time.monotonic", lambda: t[0])
        notifier._PRUNE_EVERY = 5

        # Seed one entry, then let it expire.
        assert notifier._cooldown_check(("unknown", 999)) is True
        assert ("unknown", 999) in notifier._last_fire
        t[0] += 2.0  # past the 1s cooldown — now prunable

        # Drive _PRUNE_EVERY more checks (different keys) to trigger a sweep.
        for i in range(5):
            notifier._cooldown_check(("unknown", i))

        assert ("unknown", 999) not in notifier._last_fire

    def test_prune_keeps_fresh_entries(self, notifier, monkeypatch):
        import sys
        import modules.alerts.alert_notifier  # noqa: F401 - ensure imported
        mod = sys.modules["modules.alerts.alert_notifier"]
        t = [1000.0]  # nonzero start — 0.0 collides with the "never fired" sentinel
        monkeypatch.setattr(mod, "_COOLDOWN_SECONDS", 100.0)
        monkeypatch.setattr("time.monotonic", lambda: t[0])
        notifier._PRUNE_EVERY = 3

        notifier._cooldown_check(("wanted", 1))
        for i in range(3):
            notifier._cooldown_check(("unknown", i))

        assert ("wanted", 1) in notifier._last_fire

    def test_last_fire_does_not_grow_unbounded_over_many_distinct_keys(self, notifier, monkeypatch):
        """Simulates long-running track_id churn: many distinct, short-lived
        keys should not accumulate forever once they've expired."""
        import sys
        import modules.alerts.alert_notifier  # noqa: F401 - ensure imported
        mod = sys.modules["modules.alerts.alert_notifier"]
        t = [1000.0]  # nonzero start — 0.0 collides with the "never fired" sentinel
        monkeypatch.setattr(mod, "_COOLDOWN_SECONDS", 1.0)
        monkeypatch.setattr("time.monotonic", lambda: t[0])
        notifier._PRUNE_EVERY = 50

        for i in range(500):
            notifier._cooldown_check(("unknown", i))
            t[0] += 0.01  # 5s of simulated time over 500 distinct track_ids
        assert len(notifier._last_fire) < 500  # pruning kept it bounded


# ----------------------------------------------------------------------
# Event handlers — now-reachable vip_arrival + existing watchlist_match
# ----------------------------------------------------------------------
class TestEventHandlers:
    def test_vip_arrival_dispatches(self, notifier):
        notifier._on_vip_arrival(guest_id=7, guest_name="Ada Guest", confidence=0.91)
        assert len(notifier.calls) == 1
        assert notifier.calls[0]["guest_id"] == 7
        assert "Ada Guest" in notifier.calls[0]["title"]

    def test_vip_arrival_respects_cooldown(self, notifier):
        notifier._on_vip_arrival(guest_id=7, guest_name="Ada Guest")
        notifier._on_vip_arrival(guest_id=7, guest_name="Ada Guest")
        assert len(notifier.calls) == 1  # second call suppressed

    def test_watchlist_match_dispatches(self, notifier):
        notifier._on_watchlist_match(guest_id=3, guest_name="Wanted Guy", watch_reason="theft")
        assert len(notifier.calls) == 1
        assert notifier.calls[0]["guest_id"] == 3
