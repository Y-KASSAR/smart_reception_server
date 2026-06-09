"""
WebSocket Routes
================
Real-time event streaming for the dashboard (SDD §3.4.3).

Clients connect to:
    /ws                  (SDD canonical path)
    /api/ws/alerts       (legacy path, kept for backwards compatibility)

Server-to-client message types (SDD §3.4.3):
    live_feed             {camera_id, frame_b64, detections, ts}
    detection_update      {persons, faces, tracks, ts}
    alert_push            {alert_id, type, severity, title, ts}
    guest_identified      {guest_id, name, confidence, ts}
    recommendation_update {guest_id, recommendations, ts}
    heartbeat             {ts, active_tracks, camera_status}
    frame_ack             {frame_id, processed, ts}
"""
import json
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from config.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

_connected_clients: Set[WebSocket] = set()

# Clients that have opted into receiving live translation events.
# The audio ingest route gates expensive Whisper inference on this count.
_translation_subscribers: Set[WebSocket] = set()


def translation_subscriber_count() -> int:
    return len(_translation_subscribers)


# Reference to the main asyncio event loop, captured at app startup.
# Sync FastAPI route handlers run in a threadpool worker where
# `asyncio.get_event_loop()` does NOT see the main loop. Use
# `broadcast_from_thread()` instead to dispatch coroutines safely.
_main_loop: "asyncio.AbstractEventLoop | None" = None


def set_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Capture the main event loop reference. Called from the app lifespan."""
    global _main_loop
    _main_loop = loop
    logger.info("WebSocket main loop reference captured")


def broadcast_from_thread(coro) -> None:
    """Schedule a coroutine onto the main event loop from any thread.

    Safe to call from sync FastAPI route handlers (e.g. `api/routes/edge.py`'s
    `ingest_frame`) which run in the threadpool. Without this helper the
    `asyncio.ensure_future()` calls from a worker thread silently no-op
    because the worker thread has no running event loop.
    """
    if _main_loop is None or not _main_loop.is_running():
        return
    try:
        asyncio.run_coroutine_threadsafe(coro, _main_loop)
    except Exception as e:
        logger.debug(f"broadcast_from_thread failed: {e}")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _broadcast(payload: Dict[str, Any]) -> None:
    """Send a JSON payload to every connected WebSocket client."""
    if not _connected_clients:
        return
    message = json.dumps(payload)
    disconnected = set()
    for ws in list(_connected_clients):
        try:
            await ws.send_text(message)
        except Exception:
            disconnected.add(ws)
    _connected_clients.difference_update(disconnected)


# ---------------------------------------------------------------
# SDD §3.4.3 typed broadcast helpers
# ---------------------------------------------------------------

async def broadcast_alert(data: dict) -> None:
    """Broadcast an alert event (alert_push). Accepts legacy 'alert_created' shape."""
    payload = dict(data)
    payload.setdefault("event", "alert_push")
    payload.setdefault("ts", _now_iso())
    await _broadcast(payload)


async def broadcast_live_feed(camera_id: str, frame_b64: str, detections: list) -> None:
    await _broadcast({
        "event": "live_feed",
        "camera_id": camera_id,
        "frame_b64": frame_b64,
        "detections": detections,
        "ts": _now_iso(),
    })


async def broadcast_detection_update(persons: list, faces: list, tracks: list) -> None:
    await _broadcast({
        "event": "detection_update",
        "persons": persons,
        "faces": faces,
        "tracks": tracks,
        "ts": _now_iso(),
    })


async def broadcast_guest_identified(guest_id: int, name: str, confidence: float) -> None:
    await _broadcast({
        "event": "guest_identified",
        "guest_id": guest_id,
        "name": name,
        "confidence": float(confidence),
        "ts": _now_iso(),
    })


async def broadcast_recommendation_update(guest_id: int, recommendations: list) -> None:
    await _broadcast({
        "event": "recommendation_update",
        "guest_id": guest_id,
        "recommendations": recommendations,
        "ts": _now_iso(),
    })


async def broadcast_heartbeat(active_tracks: int, camera_status: str = "online") -> None:
    await _broadcast({
        "event": "heartbeat",
        "ts": _now_iso(),
        "active_tracks": active_tracks,
        "camera_status": camera_status,
    })


async def broadcast_frame_ack(frame_id: str, processed: bool) -> None:
    await _broadcast({
        "event": "frame_ack",
        "frame_id": frame_id,
        "processed": processed,
        "ts": _now_iso(),
    })


async def broadcast_translation(
    camera_id: str,
    source_lang: str,
    text: str,
    duration_s: float,
) -> None:
    """Emit a translation transcript event to every client. The audio route
    only invokes this when at least one client has subscribed via the
    /ws/translation socket."""
    await _broadcast({
        "event": "translation",
        "camera_id": camera_id,
        "source_lang": source_lang,
        "text": text,
        "duration_s": round(float(duration_s), 2),
        "ts": _now_iso(),
    })


async def _serve_websocket(websocket: WebSocket) -> None:
    """Shared WebSocket handler used by both /ws and /api/ws/alerts."""
    await websocket.accept()
    _connected_clients.add(websocket)
    logger.info(f"WebSocket client connected. Total: {len(_connected_clients)}")
    try:
        await websocket.send_text(json.dumps({
            "event": "connected",
            "message": "Real-time stream active",
            "ts": _now_iso(),
        }))
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text(json.dumps({"event": "pong", "ts": _now_iso()}))
            except asyncio.TimeoutError:
                await websocket.send_text(json.dumps({
                    "event": "heartbeat",
                    "ts": _now_iso(),
                }))
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        _connected_clients.discard(websocket)
        logger.info(f"WebSocket clients remaining: {len(_connected_clients)}")


@router.websocket("/alerts")
async def websocket_alerts(websocket: WebSocket):
    """Legacy WebSocket endpoint mounted under /api/ws/alerts."""
    await _serve_websocket(websocket)


# Top-level /ws router (SDD canonical), mounted directly on the app.
ws_router = APIRouter()


@ws_router.websocket("/ws")
async def websocket_root(websocket: WebSocket):
    """SDD §3.4 canonical WebSocket endpoint at /ws."""
    await _serve_websocket(websocket)


@ws_router.websocket("/ws/translation")
async def websocket_translation(websocket: WebSocket):
    """Subscriber-only WebSocket. Adds the connection to
    ``_translation_subscribers`` so the audio route knows to engage Whisper
    inference, and removes it on disconnect. Receives the same translation
    events the main /ws would (we just need the membership signal)."""
    await websocket.accept()
    _connected_clients.add(websocket)
    _translation_subscribers.add(websocket)
    logger.info(f"Translation subscriber connected. Total: {len(_translation_subscribers)}")
    try:
        await websocket.send_text(json.dumps({
            "event": "translation_ready",
            "message": "Whisper pipeline engaged for this client.",
            "ts": _now_iso(),
        }))
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                if data == "ping":
                    await websocket.send_text(json.dumps({"event": "pong", "ts": _now_iso()}))
            except asyncio.TimeoutError:
                # Idle keepalive
                await websocket.send_text(json.dumps({"event": "heartbeat", "ts": _now_iso()}))
    except WebSocketDisconnect:
        logger.info("Translation subscriber disconnected")
    except Exception as e:
        logger.error(f"Translation WS error: {e}", exc_info=True)
    finally:
        _translation_subscribers.discard(websocket)
        _connected_clients.discard(websocket)
        logger.info(f"Translation subscribers remaining: {len(_translation_subscribers)}")
