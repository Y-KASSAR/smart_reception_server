"""
Person Detection Package (SDD C5)
==================================
Server-side person detection module per SDD Section 4 (C5).
Provides YOLOv8/MobileNet-SSD detection with graceful fallback,
plus a lightweight centroid-IoU tracker for stable track IDs.
"""
from detection.person_detector import (
    PersonDetector,
    PersonDetection,
    CentroidTracker,
    person_detector,
    person_tracker,
)

__all__ = [
    "PersonDetector",
    "PersonDetection",
    "CentroidTracker",
    "person_detector",
    "person_tracker",
]
