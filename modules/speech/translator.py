"""
Speech Translator (faster-whisper)
==================================
Transcribes + translates short audio chunks (WAV bytes) to English using
``faster-whisper``. The model is loaded lazily on first use so import-time
cost stays cheap; once warm it sticks around at module scope.

Whisper's built-in ``task="translate"`` covers both cases for us:

    * Foreign-language input  →  English translation
    * English input           →  English transcription (passthrough)

Auto-detected source language is returned in each TranscriptSegment so the
dashboard can show "FR → EN", "RU → EN", etc.

Gracefully degrades: if faster-whisper / CUDA / a model is unavailable, the
module loads in stub mode and ``transcribe_chunk()`` returns ``None`` so the
rest of the app still boots.
"""
from __future__ import annotations

import io
import threading
import wave
from dataclasses import dataclass
from typing import Optional

import numpy as np

from config.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)


@dataclass
class TranscriptSegment:
    """One chunk's worth of transcription output."""
    text: str                  # English (Whisper task=translate)
    source_lang: str           # auto-detected source ISO code (e.g. "fr", "ar")
    duration_s: float          # audio duration of this chunk
    avg_logprob: float = 0.0   # rough confidence proxy (Whisper internal)


class SpeechTranslator:
    """Singleton-style Whisper wrapper. Loads the model on first call."""

    def __init__(self):
        # Resolved at construction so config tweaks take effect on import.
        sp = getattr(settings, "speech", None)
        # Upgraded default: 'small' (244M) handles dialectal Arabic
        # (Lebanese / Levantine), French, and other non-English inputs
        # FAR better than 'base'. Still real-time on a 3050 Ti.
        self._model_size: str = getattr(sp, "whisper_model", "small")
        self._device: str = getattr(sp, "device", "auto")
        self._compute_type: str = getattr(sp, "compute_type", "int8_float16")
        self._min_audio_s: float = float(getattr(sp, "min_audio_seconds", 0.4))
        # Beam search > greedy on noisy or dialectal speech; small cost on GPU.
        self._beam_size: int = int(getattr(sp, "beam_size", 5))
        # Conversational primer steers the decoder toward natural phrasing.
        self._initial_prompt: str = getattr(
            sp, "initial_prompt",
            "Hotel reception conversation. Guest speaks colloquial Lebanese "
            "Arabic, French, or English. Translate naturally."
        )

        self._model = None
        self._lock = threading.RLock()
        self.backend: str = self._detect_backend()

    # ------------------------------------------------------------------
    def _detect_backend(self) -> str:
        try:
            import faster_whisper  # noqa: F401
            return "faster-whisper"
        except ImportError:
            logger.warning(
                "SpeechTranslator stub mode: install faster-whisper to enable."
            )
            return "stub"

    def _resolve_device(self) -> str:
        if self._device != "auto":
            return self._device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _ensure_model(self) -> bool:
        if self.backend != "faster-whisper":
            return False
        if self._model is not None:
            return True
        with self._lock:
            if self._model is not None:
                return True
            try:
                from faster_whisper import WhisperModel
                dev = self._resolve_device()
                # int8_float16 on GPU is fast + lower VRAM. Fallback for CPU is
                # plain int8 which is supported by all CTranslate2 builds.
                ct = self._compute_type if dev == "cuda" else "int8"
                self._model = WhisperModel(self._model_size, device=dev, compute_type=ct)
                logger.info(
                    f"Whisper model '{self._model_size}' loaded "
                    f"(device={dev}, compute={ct})"
                )
                return True
            except Exception as e:
                logger.error(f"Failed to load Whisper model: {e}", exc_info=True)
                self.backend = "stub"
                return False

    # ------------------------------------------------------------------
    @staticmethod
    def _wav_bytes_to_float32(wav_bytes: bytes) -> Optional[np.ndarray]:
        """Decode a WAV byte payload into a mono float32 numpy array at 16kHz.

        Returns None if the WAV is malformed or empty.
        """
        try:
            with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
                sr = wf.getframerate()
                n_channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                n_frames = wf.getnframes()
                raw = wf.readframes(n_frames)
            if n_frames <= 0:
                return None
            # Convert raw PCM to float32 in [-1.0, 1.0]
            if sample_width == 2:
                arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            elif sample_width == 4:
                arr = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
            elif sample_width == 1:
                arr = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
            else:
                return None
            if n_channels > 1:
                arr = arr.reshape(-1, n_channels).mean(axis=1)
            # Resample to 16kHz if needed — Whisper expects 16kHz.
            if sr != 16000:
                arr = _linear_resample(arr, src_sr=sr, dst_sr=16000)
            return arr
        except Exception as e:
            logger.debug(f"WAV decode failed: {e}")
            return None

    # ------------------------------------------------------------------
    def transcribe_chunk(self, wav_bytes: bytes) -> Optional[TranscriptSegment]:
        """Translate a single WAV chunk to English. Returns None on no-speech /
        stub mode / decode failure.

        Thread-safe: holds the model lock around inference because
        CTranslate2 sessions are not concurrent-safe.
        """
        if not self._ensure_model():
            return None
        audio = self._wav_bytes_to_float32(wav_bytes)
        if audio is None:
            return None
        duration_s = audio.shape[0] / 16000.0
        if duration_s < self._min_audio_s:
            return None
        try:
            with self._lock:
                segs, info = self._model.transcribe(
                    audio,
                    task="translate",                # always -> English
                    vad_filter=True,                 # skip silent stretches
                    beam_size=self._beam_size,       # 5 = much better dialect handling
                    no_speech_threshold=0.6,
                    # Conversational primer biases the decoder toward natural,
                    # colloquial phrasing instead of formal news Arabic.
                    initial_prompt=self._initial_prompt,
                    # Lower temperature = less hallucination on short chunks.
                    temperature=0.0,
                    # Word-level timestamps not needed; saves work.
                    word_timestamps=False,
                )
                pieces = []
                lp_total, lp_count = 0.0, 0
                for s in segs:
                    pieces.append(s.text.strip())
                    if getattr(s, "avg_logprob", None) is not None:
                        lp_total += s.avg_logprob
                        lp_count += 1
            text = " ".join(p for p in pieces if p).strip()
            if not text:
                return None
            return TranscriptSegment(
                text=text,
                source_lang=(info.language or "?").lower(),
                duration_s=duration_s,
                avg_logprob=(lp_total / lp_count) if lp_count else 0.0,
            )
        except Exception as e:
            logger.error(f"transcribe_chunk failed: {e}", exc_info=True)
            return None


def _linear_resample(arr: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """Cheap linear resample. Adequate for speech where Whisper does its own
    feature extraction at 16kHz internally."""
    if src_sr == dst_sr or arr.shape[0] == 0:
        return arr
    new_len = int(round(arr.shape[0] * (dst_sr / src_sr)))
    if new_len <= 0:
        return arr.astype(np.float32)
    x_old = np.linspace(0.0, 1.0, num=arr.shape[0], endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=new_len, endpoint=False)
    return np.interp(x_new, x_old, arr).astype(np.float32)


# Module-level singleton — imported by api/routes/audio.py
speech_translator = SpeechTranslator()
