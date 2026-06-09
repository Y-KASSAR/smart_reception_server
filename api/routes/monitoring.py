"""
Lobby Monitoring Routes (SDD §3.4.5, FR-3)
==========================================
Surfaces the current state of PersonMonitor for the dashboard's
"Lobby Overview" widget.

    GET /api/monitoring/status   → counts + per-track breakdown
"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from config.logging_config import get_logger
from utils.security_utils import get_current_staff

logger = get_logger(__name__)
router = APIRouter()


class TrackSnapshot(BaseModel):
    track_id: int
    is_known: bool
    guest_id: Optional[int] = None
    dwell_seconds: float
    alerts_fired: List[str] = []


class MonitoringStatusResponse(BaseModel):
    total_persons: int
    in_house_count: int
    unknown_count: int
    flagged_count: int    # tracks that have already fired at least one alert
    tracks: List[TrackSnapshot]


@router.get("/status", response_model=MonitoringStatusResponse)
def get_monitoring_status(_=Depends(get_current_staff)):
    """Snapshot of every person currently tracked in the lobby."""
    from modules.monitoring import person_monitor

    tracks = person_monitor.get_all_tracks()
    snapshots: List[TrackSnapshot] = []
    in_house = 0
    unknown = 0
    flagged = 0

    for tp in tracks:
        if tp.is_known:
            in_house += 1
        else:
            unknown += 1
        if tp.alerts_fired:
            flagged += 1
        snapshots.append(
            TrackSnapshot(
                track_id=tp.track_id,
                is_known=tp.is_known,
                guest_id=tp.guest_id,
                dwell_seconds=round(tp.dwell_time, 2),
                alerts_fired=sorted(tp.alerts_fired.keys()),
            )
        )

    return MonitoringStatusResponse(
        total_persons=len(tracks),
        in_house_count=in_house,
        unknown_count=unknown,
        flagged_count=flagged,
        tracks=snapshots,
    )
