"""
Seed the services catalog with a realistic hotel offering so the
RecommendationPanel has something to recommend.

Categories mirror SDD §7.4 and the recommendation engine's rule keys:
``spa``, ``dining``, ``activities``, ``room_service``.

Idempotent: skips any service whose ``name`` already exists.
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import SessionLocal
from database.models import Service

SERVICES = [
    # spa
    {"name": "Signature Spa Ritual",        "category": "spa",          "price": 120.0, "popularity_score": 0.85,
     "description": "90-minute full-body massage with aromatherapy oils."},
    {"name": "Hammam & Steam Experience",   "category": "spa",          "price":  65.0, "popularity_score": 0.70,
     "description": "Traditional Lebanese hammam ritual and steam room access."},
    {"name": "Couples Wellness Package",    "category": "spa",          "price": 220.0, "popularity_score": 0.55,
     "description": "Side-by-side couples massage and private jacuzzi."},

    # dining
    {"name": "Rooftop Dinner Reservation",  "category": "dining",       "price":  85.0, "popularity_score": 0.90,
     "description": "Three-course tasting menu at the rooftop restaurant."},
    {"name": "Mediterranean Mezze Brunch",  "category": "dining",       "price":  40.0, "popularity_score": 0.78,
     "description": "Saturday brunch with live oud music."},
    {"name": "Private Wine Tasting",        "category": "dining",       "price": 110.0, "popularity_score": 0.45,
     "description": "Curated wine tasting with the head sommelier."},

    # activities
    {"name": "Beirut Heritage Walking Tour","category": "activities",   "price":  35.0, "popularity_score": 0.60,
     "description": "Guided 2-hour walking tour of downtown Beirut."},
    {"name": "Day-Trip to Byblos",          "category": "activities",   "price":  95.0, "popularity_score": 0.65,
     "description": "Half-day private driver excursion to Byblos and the cedars."},
    {"name": "Sunset Yacht Charter",        "category": "activities",   "price": 350.0, "popularity_score": 0.40,
     "description": "Two-hour sunset cruise along the Beirut coastline."},

    # room_service
    {"name": "Late Checkout (4pm)",         "category": "room_service", "price":  25.0, "popularity_score": 0.92,
     "description": "Extended checkout to 4:00pm, subject to availability."},
    {"name": "In-Room Breakfast Service",   "category": "room_service", "price":  18.0, "popularity_score": 0.80,
     "description": "Continental breakfast delivered to your room."},
    {"name": "Pillow Menu Selection",       "category": "room_service", "price":   0.0, "popularity_score": 0.30,
     "description": "Complimentary pillow upgrade (memory foam / hypoallergenic / lavender)."},
    {"name": "Airport Transfer",            "category": "room_service", "price":  55.0, "popularity_score": 0.75,
     "description": "Private car service to/from Beirut International Airport."},
]


def main() -> None:
    db = SessionLocal()
    existing = {s.name for s in db.query(Service).all()}
    created = 0
    skipped = 0
    for cfg in SERVICES:
        if cfg["name"] in existing:
            skipped += 1
            continue
        db.add(Service(
            name=cfg["name"],
            category=cfg["category"],
            description=cfg["description"],
            price=cfg["price"],
            is_active=True,
            popularity_score=cfg["popularity_score"],
        ))
        created += 1
    db.commit()
    total = db.query(Service).count()
    db.close()
    print(f"Seeded services: created={created} skipped={skipped} total_now={total}")


if __name__ == "__main__":
    main()
