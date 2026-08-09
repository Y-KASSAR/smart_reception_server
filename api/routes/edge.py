"""
Frame Ingestion Route
=====================
Accepts base64-encoded camera frames from Raspberry Pi edge devices.
Runs person detection (SDD C5), face recognition, and dwell-time
monitoring on each frame.
"""
import base64
import time
from collections import deque
try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    np = None
    _NUMPY_AVAILABLE = False
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from database.connection import get_db
from modules.recognition import face_engine
from modules.monitoring import person_monitor
from detection import person_detector, person_tracker
from config.settings import settings
from config.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Real-time tuning state (see settings.recognition.recognize_every_n_frames).
# Person detection + tracking runs on every frame; the expensive face
# recognition pass runs only every Nth frame, and the last known identity per
# track is carried forward on the in-between frames via this cache.
_frame_counter = 0
_recent_recognitions: dict = {}   # track_id -> recognition_output entry
# Wall-clock of the last live-feed (full JPEG) broadcast, used to throttle the
# heavy video preview independently of the lightweight detection_update stream.
_last_live_feed_t = 0.0

# ---------------------------------------------------------------------------
# Per-stage timing instrumentation. Rolling windows so avg/p95/max stay cheap
# to compute and reflect recent behaviour, not the whole process lifetime.
# Exposed via GET /api/edge/status and periodically summarized to the log —
# without this, tuning recognize_every_n_frames / inference_width / detection
# thresholds is a guess about which stage (YOLO vs MTCNN+FaceNet) dominates.
# ---------------------------------------------------------------------------
_TIMING_WINDOW = 200
_LOG_EVERY_N_FRAMES = 200
_detection_ms: deque = deque(maxlen=_TIMING_WINDOW)
_recognition_ms: deque = deque(maxlen=_TIMING_WINDOW)


def _percentile(values: list, pct: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, int(len(s) * pct))
    return s[idx]


def _stage_stats(samples: deque) -> dict:
    vals = list(samples)
    if not vals:
        return {"avg_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0, "samples": 0}
    return {
        "avg_ms": round(sum(vals) / len(vals), 1),
        "p95_ms": round(_percentile(vals, 0.95), 1),
        "max_ms": round(max(vals), 1),
        "samples": len(vals),
    }


def _timing_snapshot() -> dict:
    return {
        "person_detection": _stage_stats(_detection_ms),
        "face_recognition": _stage_stats(_recognition_ms),
    }


class FramePayload(BaseModel):
    frame_b64: str
    camera_id: str = "main"
    track_ids: Optional[list] = None


class FrameResult(BaseModel):
    camera_id: str
    persons_detected: int
    faces_detected: int
    faces_recognized: int
    active_tracks: int
    person_detections: list
    recognition_results: list


def _verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    if x_api_key != settings.secrets.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


def _bbox_iou(a, b) -> float:
    """IoU between two (x,y,w,h) bboxes."""
    ax1, ay1, aw, ah = a
    bx1, by1, bw, bh = b
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


@router.post("/frame", response_model=FrameResult)
def ingest_frame(
    payload: FramePayload,
    db: Session = Depends(get_db),
    _: str = Depends(_verify_api_key),
):
    """
    Accept a camera frame from a Raspberry Pi edge device.

    Pipeline:
        1. Decode the base64 JPEG/PNG into a numpy frame.
        2. Detect persons (SDD C5) and assign stable track IDs.
        3. Run face recognition (SDD C6).
        4. Match recognized faces back to person tracks (highest IoU).
        5. Update the dwell-time monitor (SDD C10) and check thresholds.
    """
    try:
        if not _NUMPY_AVAILABLE:
            raise HTTPException(status_code=503, detail="numpy not installed; edge processing unavailable")
        frame_bytes = base64.b64decode(payload.frame_b64)
        frame_array = np.frombuffer(frame_bytes, dtype=np.uint8)
        try:
            import cv2
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
        except ImportError:
            frame = frame_array.reshape((1, -1, 3))
    except Exception as e:
        logger.error(f"Frame decode error: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid frame data: {e}")

    # 1. Person detection + tracking (every frame — cheap on GPU)
    t_detect0 = time.perf_counter()
    person_dets = person_detector.detect(frame)
    _detection_ms.append((time.perf_counter() - t_detect0) * 1000.0)
    person_tracker.update(person_dets)
    current_track_ids = {p.track_id for p in person_dets if p.track_id is not None}

    # 2. Face recognition — only every Nth frame (the expensive FaceNet pass).
    #    On the in-between frames we carry forward the last known identity per
    #    track so the dashboard keeps showing recognized guests continuously.
    global _frame_counter
    _frame_counter += 1
    if _frame_counter % _LOG_EVERY_N_FRAMES == 0:
        snap = _timing_snapshot()
        logger.info(
            "Timing (last %d samples) — detection avg=%.1fms p95=%.1fms | "
            "recognition avg=%.1fms p95=%.1fms",
            _TIMING_WINDOW,
            snap["person_detection"]["avg_ms"], snap["person_detection"]["p95_ms"],
            snap["face_recognition"]["avg_ms"], snap["face_recognition"]["p95_ms"],
        )
    recognize_every = max(1, int(getattr(settings.recognition, "recognize_every_n_frames", 1)))
    # Only run the expensive FaceNet pass on the Nth frame AND only when YOLO
    # actually saw a person — no point detecting faces in an empty lobby.
    do_recognize = (_frame_counter % recognize_every == 0) and len(person_dets) > 0

    recognition_output = []
    faces_detected = 0
    faces_recognized = 0

    if do_recognize:
        # 3. Map each recognized face to the best-overlapping person track
        t_recognize0 = time.perf_counter()
        face_results = face_engine.recognize(frame, db=db)
        _recognition_ms.append((time.perf_counter() - t_recognize0) * 1000.0)
        faces_detected = len(face_results)
        faces_recognized = sum(1 for r in face_results if r.is_recognized)
        for r in face_results:
            face_box = r.face.bbox
            track_id = None
            best_iou = 0.0
            for p in person_dets:
                iou = _bbox_iou(face_box, p.bbox)
                if iou > best_iou:
                    best_iou = iou
                    track_id = p.track_id
            # Fallback when no person detection overlapped this face (YOLO
            # missed the body but MTCNN saw the face). Use a STABLE synthetic
            # ID derived from guest_id so successive frames hit the same track
            # entry — the previous hash-of-bbox approach minted a fresh phantom
            # every frame because face bboxes shift by a pixel or two.
            if track_id is None:
                if r.guest_id is not None:
                    track_id = 100_000 + int(r.guest_id)  # known-guest bucket
                else:
                    # Anonymous face with no body — drop it; tracker will
                    # catch them when YOLO sees the body on a later frame.
                    continue

            person_monitor.update(
                track_id=track_id,
                is_known=r.is_recognized,
                guest_id=r.guest_id,
            )
            entry = {
                "track_id": track_id,
                "is_recognized": r.is_recognized,
                "guest_id": r.guest_id,
                "guest_name": r.guest_name,
                "similarity": round(r.similarity, 3),
                "bbox": list(face_box),
            }
            recognition_output.append(entry)
            # Cache identity for carry-forward on skipped frames
            _recent_recognitions[track_id] = entry
    else:
        # Carry forward cached identities for tracks still on screen.
        for tid in current_track_ids:
            cached = _recent_recognitions.get(tid)
            if cached is None:
                continue
            recognition_output.append(cached)
            person_monitor.update(
                track_id=tid,
                is_known=cached.get("is_recognized", False),
                guest_id=cached.get("guest_id"),
            )

    # Also update the monitor for unmatched person tracks (unknown persons)
    matched_track_ids = {r["track_id"] for r in recognition_output}
    for p in person_dets:
        if p.track_id is None or p.track_id in matched_track_ids:
            continue
        person_monitor.update(track_id=p.track_id, is_known=False)

    # Map each person track to its recognized guest (if any) so the dashboard
    # can colour the bbox by status (red=watched, green=known, gold=unknown).
    # Works on both real recognition frames and carry-forward frames because
    # _recent_recognitions repopulates recognition_output above.
    track_guest_map: dict = {}
    recognized_gids: set = set()
    for r in recognition_output:
        if (
            r.get("is_recognized")
            and r.get("guest_id") is not None
            and r.get("track_id") is not None
        ):
            gid = int(r["guest_id"])
            track_guest_map[r["track_id"]] = gid
            recognized_gids.add(gid)

    # Bulk-check watched + staff-badge + active-reservation status for any
    # recognized guests. The in_house set drives FR-3.5's 3-state
    # classification on the dashboard (in_house / known_non_guest / unknown).
    # IMPORTANT: must run BEFORE check_thresholds() so staff-badge marking
    # below propagates to the monitor's per-track gate.
    watched_gids: set = set()
    staff_badge_gids: set = set()
    vip_gids: set = set()
    in_house_gids: set = set()
    if recognized_gids:
        try:
            from database.models import Guest, Reservation, ReservationStatus
            rows = db.query(
                Guest.id, Guest.is_watched, Guest.is_staff_badge, Guest.vip_status
            ).filter(
                Guest.id.in_(recognized_gids)
            ).all()
            for gid, is_watched, is_staff, is_vip in rows:
                if is_watched:
                    watched_gids.add(gid)
                if is_staff:
                    staff_badge_gids.add(gid)
                if is_vip:
                    vip_gids.add(gid)

            # FR-3.5 — guest is "in-house" only if they have an active
            # CHECKED_IN reservation right now. Otherwise they're a known
            # non-guest (recognized face, not currently staying).
            in_rows = db.query(Reservation.guest_id).filter(
                Reservation.guest_id.in_(recognized_gids),
                Reservation.status == ReservationStatus.CHECKED_IN,
            ).all()
            in_house_gids = {r[0] for r in in_rows}
        except Exception as e:
            logger.debug(f"watchlist/staff/in-house lookup failed: {e}")

    # Stamp the staff-badge bit onto matched tracks so check_thresholds()
    # skips them entirely (no security/assistance/VIP pings for staff).
    for tid, gid in track_guest_map.items():
        if gid in staff_badge_gids:
            person_monitor.update(track_id=tid, is_staff_badge=True)

    person_monitor.check_thresholds()
    person_monitor.remove_stale_tracks()

    # Prune the carry-forward cache so it doesn't grow unbounded.
    for tid in list(_recent_recognitions.keys()):
        if tid not in current_track_ids:
            _recent_recognitions.pop(tid, None)

    # NOTE: is_watched reflects the EFFECTIVE alert-triggering state, not
    # the raw DB flag. When a guest carries a staff badge, watchlist is
    # suppressed entirely (badge wins) — so we mark is_watched=False in
    # the payload so the dashboard's red banner + bbox color stay in sync
    # with the actual alert pipeline.
    # FR-3.5 — derive 3-state guest classification per track
    def _classify(p) -> str:
        gid = track_guest_map.get(p.track_id) if p.track_id is not None else None
        if gid is None:
            return "unknown"
        return "in_house" if gid in in_house_gids else "known_non_guest"

    # FR-3.6 — pull live dwell seconds from PersonMonitor for each track so
    # the canvas overlay can show "00:42" beside the track ID/guest name.
    def _dwell(p) -> float:
        if p.track_id is None:
            return 0.0
        tp = person_monitor.get_track(p.track_id)
        return round(tp.dwell_time, 1) if tp is not None else 0.0

    person_output = [
        {
            "track_id": p.track_id,
            "bbox": list(p.bbox),
            "confidence": round(p.confidence, 3),
            "guest_id": track_guest_map.get(p.track_id),
            "guest_status": _classify(p),           # FR-3.5
            "dwell_seconds": _dwell(p),             # FR-3.6
            "is_watched": (
                p.track_id is not None
                and track_guest_map.get(p.track_id) in watched_gids
                and track_guest_map.get(p.track_id) not in staff_badge_gids
            ),
            "is_staff_badge": (
                p.track_id is not None
                and track_guest_map.get(p.track_id) in staff_badge_gids
            ),
        }
        for p in person_dets
    ]

    # Broadcast detection update + per-guest identification events (SDD §3.4.3).
    # This route is sync (def, not async def) so it runs in the FastAPI
    # threadpool. The previous `asyncio.ensure_future(...)` calls silently
    # no-op'd because the worker thread has no running event loop.
    # `broadcast_from_thread()` schedules each coroutine onto the main loop
    # via `asyncio.run_coroutine_threadsafe()`.
    try:
        from api.routes.websocket import (
            broadcast_from_thread,
            broadcast_detection_update,
            broadcast_guest_identified,
            broadcast_live_feed,
        )
        broadcast_from_thread(broadcast_detection_update(
            persons=person_output,
            faces=[r["bbox"] for r in recognition_output],
            tracks=list({r["track_id"] for r in recognition_output if r["track_id"] is not None}),
        ))
        # Throttle the heavy live-feed (full base64 JPEG) to live_feed_fps so we
        # don't JSON-encode a ~1-2MB string on the event loop every frame. The
        # lightweight detection_update above still streams at full rate.
        global _last_live_feed_t
        lf_fps = int(getattr(settings.edge, "live_feed_fps", 0) or 0)
        now_t = time.perf_counter()
        if lf_fps <= 0 or (now_t - _last_live_feed_t) >= (1.0 / lf_fps):
            _last_live_feed_t = now_t
            broadcast_from_thread(broadcast_live_feed(
                camera_id=payload.camera_id,
                frame_b64=payload.frame_b64,
                detections=person_output,
            ))
        # Fire guest-identified events only on real recognition frames, not on
        # carry-forward frames — otherwise each identity would re-broadcast
        # every frame and spam dashboard toasts / alert triggers.
        if do_recognize:
            from core.event_bus import event_bus
            # Hydrate guest objects only for watched IDs (the rest are just
            # broadcast_guest_identified — name/confidence already in payload).
            watched_lookup: dict = {}
            if watched_gids:
                try:
                    from database.models import Guest
                    watched_lookup = {
                        g.id: g
                        for g in db.query(Guest).filter(Guest.id.in_(watched_gids)).all()
                    }
                except Exception as e:
                    logger.debug(f"watched lookup failed: {e}")

            for r in recognition_output:
                if r["is_recognized"] and r.get("guest_id"):
                    gid = int(r["guest_id"])
                    broadcast_from_thread(broadcast_guest_identified(
                        guest_id=gid,
                        name=r.get("guest_name") or "",
                        confidence=r.get("similarity", 0.0),
                    ))
                    # Watchlist hook: WANTED alert when a flagged guest is
                    # identified. AlertNotifier listens on the event_bus and
                    # the cooldown on person_monitor prevents per-track spam.
                    if gid in watched_gids and gid not in staff_badge_gids:
                        watched = watched_lookup.get(gid)
                        if watched is not None:
                            # Publish to the dedicated topic so AlertNotifier
                            # persists it (via AlertRepository.create) and
                            # broadcasts the WS payload through the standard
                            # alert pipeline. The previous "alert_created"
                            # topic only fired the WS toast — no DB row.
                            event_bus.publish(
                                "watchlist_match",
                                guest_id=gid,
                                guest_name=watched.full_name,
                                watch_reason=watched.watch_reason or "",
                                confidence=r.get("similarity", 0.0),
                                track_id=r.get("track_id"),
                            )
                    # VIP arrival hook: AlertNotifier already subscribes to
                    # this topic and has a full dispatch handler
                    # (_on_vip_arrival), but until now nothing ever published
                    # it — VIP recognitions were silently never alerted.
                    # guest_name comes straight from the recognition cache
                    # (no extra DB round trip needed, unlike the watchlist
                    # case above which also needs watch_reason).
                    if gid in vip_gids and gid not in staff_badge_gids:
                        event_bus.publish(
                            "vip_arrival",
                            guest_id=gid,
                            guest_name=r.get("guest_name") or "",
                            confidence=r.get("similarity", 0.0),
                        )
    except Exception as e:
        logger.debug(f"WS broadcast skipped: {e}")

    return FrameResult(
        camera_id=payload.camera_id,
        persons_detected=len(person_dets),
        faces_detected=faces_detected,
        faces_recognized=faces_recognized,
        active_tracks=person_monitor.active_count,
        person_detections=person_output,
        recognition_results=recognition_output,
    )


@router.get("/status")
def edge_status(_: str = Depends(_verify_api_key)):
    """Return current edge processing status, including a rolling window of
    per-stage timing (person detection vs face recognition) so bottlenecks
    can be diagnosed live instead of guessed at."""
    return {
        "active_tracks": person_monitor.active_count,
        "person_detection_backend": person_detector.backend,
        "recognition_backend": face_engine.backend,
        "guest_embeddings_loaded": face_engine.guest_count,
        "timing": _timing_snapshot(),
    }


@router.get("/heartbeat")
def edge_heartbeat(_: str = Depends(_verify_api_key)):
    """
    Edge heartbeat endpoint (SDD §3.4.5, NFR-3.4).

    Returns the server liveness signal used by the Raspberry Pi
    EdgeNetworkClient (C4) to verify connectivity.
    """
    from datetime import datetime, timezone
    return {
        "status": "ok",
        "ts": datetime.now(timezone.utc).isoformat(),
        "active_tracks": person_monitor.active_count,
        "camera_status": "online",
    }