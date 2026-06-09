"""
modules.recognition
===================
Face recognition engine (SDD §4.2.3, FR-1).

Public exports:
    FaceRecognitionEngine — the class (see face_recognizer.py)
    FaceDetection          — dataclass for a detected face
    RecognitionResult      — dataclass for a recognition outcome
    face_engine            — process-wide singleton used by API routes
"""
from modules.recognition.face_recognizer import (
    FaceDetection,
    FaceRecognitionEngine,
    RecognitionResult,
    face_engine,
)

__all__ = [
    "FaceDetection",
    "FaceRecognitionEngine",
    "RecognitionResult",
    "face_engine",
]
