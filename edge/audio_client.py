"""
Audio Edge Client (Raspberry Pi)
================================
Continuously captures audio from the USB webcam's microphone and POSTs
fixed-size WAV chunks to the laptop's ``/api/audio/chunk`` endpoint. The
laptop only fires Whisper inference when at least one dashboard client
is subscribed to the translation feed, so streaming when nobody's
listening is cheap (just buffered + discarded).

Designed to run alongside edge_client.py as a separate systemd service.

Required env vars (defaulted):
    SERVER_URL              http://192.168.99.1:5000
    API_KEY                 (same key used by edge_client.py)
    CAMERA_ID               main
    AUDIO_DEVICE            -1 = default input
    AUDIO_CHUNK_SECONDS     5
    AUDIO_SAMPLE_RATE       16000

Install (Pi):
    sudo apt install -y portaudio19-dev python3-pyaudio
    pip install pyaudio requests   # if not already in venv
"""
from __future__ import annotations

import base64
import io
import logging
import os
import time
import wave
from dataclasses import dataclass

logger = logging.getLogger("audio_client")
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s.%(funcName)s - %(message)s",
)


@dataclass
class AudioConfig:
    server_url: str
    api_key: str
    camera_id: str = "main"
    device_index: int = -1            # -1 = use system default mic
    chunk_seconds: float = 8.0   # 8s gives Whisper enough context for dialect
    sample_rate: int = 16000
    channels: int = 1                  # mono — Whisper handles mono best
    sample_width: int = 2              # int16


def _load_config() -> AudioConfig:
    return AudioConfig(
        server_url=os.environ.get("SERVER_URL", "http://192.168.99.1:5000").rstrip("/"),
        api_key=os.environ.get("API_KEY", ""),
        camera_id=os.environ.get("CAMERA_ID", "main"),
        device_index=int(os.environ.get("AUDIO_DEVICE", "-1")),
        chunk_seconds=float(os.environ.get("AUDIO_CHUNK_SECONDS", "8.0")),
        sample_rate=int(os.environ.get("AUDIO_SAMPLE_RATE", "16000")),
    )


def _frames_to_wav_bytes(frames: bytes, cfg: AudioConfig) -> bytes:
    """Wrap raw PCM frames in a WAV container so the server can decode."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(cfg.channels)
        wf.setsampwidth(cfg.sample_width)
        wf.setframerate(cfg.sample_rate)
        wf.writeframes(frames)
    return buf.getvalue()


def _send_chunk(wav_bytes: bytes, cfg: AudioConfig) -> dict:
    import requests
    url = f"{cfg.server_url}/api/audio/chunk"
    body = {
        "audio_b64": base64.b64encode(wav_bytes).decode("ascii"),
        "camera_id": cfg.camera_id,
    }
    headers = {"X-API-Key": cfg.api_key}
    backoff = 1.0
    for attempt in range(3):
        try:
            r = requests.post(url, json=body, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"audio upload attempt {attempt + 1} failed: {e}")
            time.sleep(backoff)
            backoff *= 2
    return {"ok": False}


def main() -> None:
    cfg = _load_config()
    if not cfg.api_key:
        logger.error("API_KEY env var is required")
        return

    try:
        import pyaudio
    except ImportError:
        logger.error(
            "pyaudio not installed. Run: sudo apt install portaudio19-dev "
            "python3-pyaudio && pip install pyaudio"
        )
        return

    pa = pyaudio.PyAudio()
    chunk_frames = int(cfg.sample_rate * cfg.chunk_seconds)
    fmt = pyaudio.paInt16

    device_kwargs = {}
    if cfg.device_index >= 0:
        device_kwargs["input_device_index"] = cfg.device_index

    try:
        stream = pa.open(
            format=fmt,
            channels=cfg.channels,
            rate=cfg.sample_rate,
            input=True,
            frames_per_buffer=1024,
            **device_kwargs,
        )
    except Exception as e:
        logger.error(f"Failed to open audio input: {e}")
        pa.terminate()
        return

    logger.info(
        f"Audio capture started: sr={cfg.sample_rate} chunk={cfg.chunk_seconds}s "
        f"device={cfg.device_index} -> {cfg.server_url}"
    )

    try:
        while True:
            # Read one chunk worth of audio
            raw = stream.read(chunk_frames, exception_on_overflow=False)
            wav_bytes = _frames_to_wav_bytes(raw, cfg)
            resp = _send_chunk(wav_bytes, cfg)
            if resp.get("translated"):
                logger.debug(
                    f"chunk uploaded -> translated "
                    f"(listeners={resp.get('translation_listeners')})"
                )
    except KeyboardInterrupt:
        logger.info("Audio client interrupted")
    finally:
        try: stream.stop_stream(); stream.close()
        except Exception: pass
        pa.terminate()


if __name__ == "__main__":
    main()
