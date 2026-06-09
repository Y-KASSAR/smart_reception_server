"""
Audio ingest + live translation (Whisper)
==========================================
The Pi POSTs WAV chunks to ``/api/audio/chunk``. We always store the latest
chunks in an in-memory ring buffer (small — bounded), and only fire the
expensive Whisper inference path when the dashboard's Live Translation page
is open (tracked via the ``translation`` WebSocket event subscription).

Output is broadcast as a ``translation`` event with the source language and
the English transcript so the frontend can render a live transcript log.
"""
from __future__ import annotations

import base64
import time
from collections import deque
from typing import Optional, Deque

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException
from pydantic import BaseModel

from config.logging_config import get_logger
from config.settings import settings
from modules.speech import speech_translator

logger = get_logger(__name__)
router = APIRouter()

# -----------------------------------------------------------------
# Ring buffer of the most-recent audio chunks (bounded for memory).
# Each entry: (timestamp_perf_counter, wav_bytes).
# -----------------------------------------------------------------
_BUFFER_SIZE = 30
_audio_buffer: Deque[tuple[float, bytes]] = deque(maxlen=_BUFFER_SIZE)
_last_translated_ts: float = 0.0


class AudioChunkPayload(BaseModel):
    audio_b64: str            # base64-encoded WAV bytes (16kHz mono is ideal)
    camera_id: str = "main"


def _verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    if x_api_key != settings.secrets.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key


def _translation_subscribers() -> int:
    """How many dashboard clients are currently subscribed to the
    translation feed. We use this to gate expensive Whisper inference —
    nobody listening = no work."""
    try:
        from api.routes.websocket import translation_subscriber_count
        return translation_subscriber_count()
    except Exception:
        return 0


def _process_chunk_inline(wav_bytes: bytes, camera_id: str) -> None:
    """Run Whisper on the chunk and broadcast the transcript. Called by a
    BackgroundTask so the HTTP POST returns immediately to the Pi."""
    global _last_translated_ts
    seg = speech_translator.transcribe_chunk(wav_bytes)
    if seg is None:
        return
    _last_translated_ts = time.perf_counter()
    try:
        from api.routes.websocket import broadcast_from_thread, broadcast_translation
        broadcast_from_thread(broadcast_translation(
            camera_id=camera_id,
            source_lang=seg.source_lang,
            text=seg.text,
            duration_s=seg.duration_s,
        ))
    except Exception as e:
        logger.debug(f"translation broadcast skipped: {e}")


@router.post("/chunk")
def ingest_audio_chunk(
    payload: AudioChunkPayload,
    background: BackgroundTasks,
    _: str = Depends(_verify_api_key),
):
    """Receive one audio chunk. Always buffered; only translated when at
    least one dashboard client is listening on the ``translation`` event."""
    try:
        wav_bytes = base64.b64decode(payload.audio_b64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64: {e}")

    _audio_buffer.append((time.perf_counter(), wav_bytes))

    listeners = _translation_subscribers()
    triggered = False
    if listeners > 0:
        triggered = True
        # Defer the heavy inference so the Pi gets a quick 200 OK back.
        background.add_task(_process_chunk_inline, wav_bytes, payload.camera_id)

    return {
        "buffered": len(_audio_buffer),
        "translation_listeners": listeners,
        "translated": triggered,
    }


@router.get("/status")
def audio_status(_: str = Depends(_verify_api_key)):
    return {
        "buffer_size": len(_audio_buffer),
        "buffer_capacity": _BUFFER_SIZE,
        "translation_listeners": _translation_subscribers(),
        "speech_backend": speech_translator.backend,
        "seconds_since_last_translation": (
            round(time.perf_counter() - _last_translated_ts, 1)
            if _last_translated_ts > 0 else None
        ),
    }
