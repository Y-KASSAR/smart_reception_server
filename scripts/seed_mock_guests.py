r"""
Mock guest population for full-system testing
=============================================

Registers **100 realistic guests** in the database so the dashboard, guest
search, reservations, alerts and the upselling engine can all be exercised
against a populated catalogue — *without* touching the face-recognition path.

Deliberately NOT mocked
-----------------------
* **Face embeddings.** We never fabricate FaceEmbedding rows: the recognition
  model is only meaningful against real faces, so fake 512-d vectors would add
  noise and could be mistaken for enrolled identities. These guests are
  "registered" (profile + history) but not face-enrolled.

What it does seed
-----------------
1. 100 guests with varied titles, nationalities, languages, VIP flags,
   dietary/room preferences and statuses (a few watch-listed for security
   testing).
2. Recommendation interaction history across the service catalogue, with a
   per-service hidden "appeal" so accept/decline outcomes differ between
   services. This is what makes the statistics-driven popularity meaningful.
3. A final ``ServiceRepository.recompute_popularity`` pass so each service's
   ``popularity_score`` reflects the seeded statistics (the same code path the
   live server runs when a guest responds to a recommendation).

Idempotent: guests use the ``@mock.example.com`` domain and are skipped if a
matching e-mail already exists, so re-running tops up to 100 without dupes.

Usage:
    .\venv\Scripts\python.exe -m scripts.seed_mock_guests
    .\venv\Scripts\python.exe -m scripts.seed_mock_guests --count 100 --reset-interactions
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import get_db_session, init_db
from database.models import (
    Guest,
    GuestStatus,
    Recommendation,
    RecommendationStatus,
    Service,
    Title,
)
from database.repositories import ServiceRepository

MOCK_DOMAIN = "mock.example.com"
SEED = 20260620  # fixed seed → reproducible test population

# --- name & locale pools ---------------------------------------------------
# (nationality, language, [first names], [last names])
_LOCALES = [
    ("LB", "ar", ["Ali", "Hassan", "Maya", "Rana", "Karim", "Layla", "Omar", "Nour", "Ziad", "Dana"],
                  ["Haddad", "Khoury", "Saab", "Aoun", "Nasr", "Fares", "Salameh", "Chamoun"]),
    ("SY", "ar", ["Yara", "Tarek", "Lina", "Samer", "Hala", "Wael", "Rima", "Bassel"],
                  ["Aljabi", "Othman", "Kassar", "Darwish", "Hamwi", "Sayegh"]),
    ("AE", "ar", ["Saeed", "Fatima", "Khalid", "Mariam", "Hamdan", "Aisha"],
                  ["Al Maktoum", "Al Nahyan", "Al Qasimi", "Al Suwaidi"]),
    ("SA", "ar", ["Abdullah", "Norah", "Faisal", "Sara", "Turki", "Reem"],
                  ["Al Saud", "Al Ghamdi", "Al Qahtani", "Al Harbi"]),
    ("EG", "ar", ["Mostafa", "Heba", "Ahmed", "Salma", "Tamer", "Yasmin"],
                  ["Mansour", "Fahmy", "Abdelrahman", "Saleh"]),
    ("US", "en", ["John", "Emily", "Michael", "Jessica", "David", "Ashley", "Robert", "Sarah"],
                  ["Smith", "Johnson", "Williams", "Brown", "Davis", "Miller"]),
    ("GB", "en", ["Oliver", "Amelia", "Harry", "Charlotte", "George", "Emma", "Jack"],
                  ["Taylor", "Wilson", "Evans", "Roberts", "Thompson"]),
    ("FR", "fr", ["Lucas", "Camille", "Hugo", "Léa", "Louis", "Manon", "Jules"],
                  ["Martin", "Bernard", "Dubois", "Moreau", "Laurent"]),
    ("DE", "de", ["Lukas", "Hannah", "Felix", "Mia", "Paul", "Lena", "Jonas"],
                  ["Müller", "Schmidt", "Schneider", "Fischer", "Weber"]),
    ("ES", "es", ["Hugo", "Lucía", "Pablo", "Sofía", "Mateo", "Martina"],
                  ["García", "Fernández", "Rodríguez", "López", "Martínez"]),
    ("IT", "it", ["Leonardo", "Giulia", "Francesco", "Aurora", "Alessandro"],
                  ["Rossi", "Russo", "Ferrari", "Esposito", "Bianchi"]),
    ("JP", "en", ["Haruto", "Yui", "Sota", "Aoi", "Riku", "Hina"],
                  ["Sato", "Suzuki", "Takahashi", "Tanaka", "Watanabe"]),
]

_TITLES = [Title.MR, Title.MRS, Title.MS, Title.MISS, Title.DR, Title.ENGR]
_ID_TYPES = ["passport", "civil_id", "driving_license"]
_ROOM_TYPES = ["standard", "Superior", "Exacutive", "junior suite"]
_DIETARY = ["halal", "vegan", "vegetarian", "gluten-free", "kosher"]
_PILLOWS = ["soft", "firm", "memory foam", "hypoallergenic"]

# Status mix — mostly active/checked-out, a sprinkle of due-in/out & blacklist.
_STATUS_WEIGHTS = [
    (GuestStatus.ACTIVE, 0.40),
    (GuestStatus.CHECKED_OUT, 0.35),
    (GuestStatus.DUE_IN, 0.10),
    (GuestStatus.DUE_OUT, 0.10),
    (GuestStatus.BLACKLISTED, 0.05),
]


def _weighted_choice(rng: random.Random, weighted):
    r = rng.random()
    cum = 0.0
    for value, w in weighted:
        cum += w
        if r <= cum:
            return value
    return weighted[-1][0]


def _make_guest(rng: random.Random, n: int) -> Guest:
    nationality, language, firsts, lasts = rng.choice(_LOCALES)
    first = rng.choice(firsts)
    last = rng.choice(lasts)
    # Unique e-mail regardless of name collisions.
    email = f"{first}.{last}.{n}".lower().replace(" ", "") + f"@{MOCK_DOMAIN}"

    is_vip = rng.random() < 0.15
    prefs: dict = {}
    if rng.random() < 0.5:
        prefs["room_type"] = rng.choice(_ROOM_TYPES)
    if rng.random() < 0.35:
        prefs["dietary"] = rng.choice(_DIETARY)
    if rng.random() < 0.3:
        prefs["pillow"] = rng.choice(_PILLOWS)

    is_watched = rng.random() < 0.04  # ~4 watch-listed guests for security tests

    return Guest(
        title=rng.choice(_TITLES),
        full_name=f"{first} {last}",
        email=email,
        phone=f"+961{rng.randint(70, 81)}{rng.randint(100000, 999999)}",
        nationality=nationality,
        id_type=rng.choice(_ID_TYPES),
        id_number=str(rng.randint(10**7, 10**9)),
        language_preference=language,
        vip_status=is_vip,
        status=_weighted_choice(rng, _STATUS_WEIGHTS),
        preferences=json.dumps(prefs) if prefs else None,
        notes=rng.choice([None, "Repeat guest", "Late arrival expected",
                          "Allergic to nuts", "Prefers high floor"]),
        is_watched=is_watched,
        watch_reason="Flagged during prior stay" if is_watched else None,
    )


def _seed_interactions(db, guests, services, rng: random.Random) -> int:
    """Create recommendation accept/decline history with per-service appeal."""
    # Hidden "true appeal" per service so popularity ends up differentiated.
    appeal = {svc.id: rng.uniform(0.15, 0.9) for svc in services}
    created = 0
    base_time = datetime.now() - timedelta(days=120)
    for guest in guests:
        # Each guest interacts with a random handful of services.
        for svc in rng.sample(services, k=min(len(services), rng.randint(2, 6))):
            responded = base_time + timedelta(
                days=rng.randint(0, 119), hours=rng.randint(0, 23)
            )
            accepted = rng.random() < appeal[svc.id]
            status = RecommendationStatus.ACCEPTED if accepted else RecommendationStatus.DECLINED
            db.add(Recommendation(
                guest_id=guest.id,
                service_id=svc.id,
                score=round(appeal[svc.id], 3),
                reasoning="Seeded interaction for statistics testing",
                status=status,
                presented_at=responded - timedelta(minutes=rng.randint(1, 30)),
                responded_at=responded,
                created_at=responded - timedelta(minutes=rng.randint(31, 120)),
            ))
            created += 1
    db.flush()
    return created


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed mock guests for system testing.")
    parser.add_argument("--count", type=int, default=100, help="Target number of mock guests (default 100)")
    parser.add_argument("--reset-interactions", action="store_true",
                        help="Delete existing recommendation history before reseeding it")
    args = parser.parse_args()

    rng = random.Random(SEED)
    init_db()

    with get_db_session() as db:
        # --- services must exist for interactions / popularity ---
        services = db.query(Service).all()
        if not services:
            print("No services found — seeding the catalogue first via seed_services...")
            from scripts import seed_services
            seed_services.main()
            services = db.query(Service).all()
        if not services:
            print("[ABORT] could not seed services; cannot build recommendation statistics.")
            return 1

        # --- guests (idempotent top-up to --count) ---
        existing = (
            db.query(Guest).filter(Guest.email.like(f"%@{MOCK_DOMAIN}")).count()
        )
        to_create = max(0, args.count - existing)
        print(f"Mock guests present: {existing}; creating {to_create} more...")

        new_guests = []
        n = existing
        while len(new_guests) < to_create:
            n += 1
            guest = _make_guest(rng, n)
            if db.query(Guest).filter(Guest.email == guest.email).first():
                continue  # extremely unlikely, but stay safe on the unique key
            db.add(guest)
            new_guests.append(guest)
        db.flush()  # assign ids
        print(f"✓ Created {len(new_guests)} guests.")

        # --- recommendation interactions / popularity statistics ---
        if args.reset_interactions:
            deleted = db.query(Recommendation).delete()
            print(f"  cleared {deleted} existing recommendations.")
            db.flush()

        all_mock_guests = (
            db.query(Guest).filter(Guest.email.like(f"%@{MOCK_DOMAIN}")).all()
        )
        interaction_guests = new_guests if not args.reset_interactions else all_mock_guests
        n_interactions = _seed_interactions(db, interaction_guests, services, rng)
        print(f"✓ Seeded {n_interactions} recommendation interactions.")

        # --- derive popularity from the statistics we just created ---
        scores = ServiceRepository.recompute_popularity(db)
        print("✓ Recomputed popularity from statistics:")
        for svc in sorted(services, key=lambda s: scores.get(s.id, 0), reverse=True):
            print(f"    {scores.get(svc.id, 0):.3f}  {svc.name} ({svc.category})")

        total_guests = db.query(Guest).count()
        print(f"\n✅ Done. Total guests in DB: {total_guests}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
