"""
modules.upselling
=================
Rule-based service recommendation engine (SDD §4.2.5, FR-2).

Public exports:
    RecommendationEngine    — the class (see recommendation_engine.py)
    recommendation_engine   — process-wide singleton used by API routes
"""
from modules.upselling.recommendation_engine import (
    RecommendationEngine,
    recommendation_engine,
)

__all__ = [
    "RecommendationEngine",
    "recommendation_engine",
]
