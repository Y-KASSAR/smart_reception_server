"""
modules.monitoring
==================
Lobby dwell-time tracking + threshold-based alert event publication
(SDD §4.2.7, FR-3 / FR-4).

Public exports:
    PersonMonitor     — the class (see person_monitor.py)
    TrackedPerson     — dataclass for a single tracked person
    person_monitor    — process-wide singleton used by API routes
"""
from modules.monitoring.person_monitor import (
    PersonMonitor,
    TrackedPerson,
    person_monitor,
)

__all__ = [
    "PersonMonitor",
    "TrackedPerson",
    "person_monitor",
]
