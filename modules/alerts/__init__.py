"""
modules.alerts
==============
Detection-event → Alert-row dispatcher with email + SMS fan-out
(SDD §4.2.6, FR-4).

Public exports:
    AlertNotifier   — the class (see alert_notifier.py)
    alert_notifier  — process-wide singleton (auto-subscribes on import)
"""
from modules.alerts.alert_notifier import AlertNotifier, alert_notifier

__all__ = ["AlertNotifier", "alert_notifier"]
