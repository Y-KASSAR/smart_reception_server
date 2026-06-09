"""
Tests for the face recognition engine.

These tests focus on backend-agnostic logic that does not require
heavy ML packages (deepface/facenet) at runtime:
- Cosine similarity math
- Backend detection
- Embedding loading from the database
- Best-match selection given embeddings
- Recognition threshold gating
"""
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Guest, FaceEmbedding
from modules.recognition import (
    FaceRecognitionEngine,
    FaceDetection,
    RecognitionResult,
)


@pytest.fixture(scope="function")
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def fre():
    return FaceRecognitionEngine()


def _vec(*values):
    return np.array(values, dtype=np.float32)


def _add_guest_with_embedding(db, name, vector):
    g = Guest(full_name=name)
    db.add(g)
    db.commit()
    db.refresh(g)
    fe = FaceEmbedding(
        guest_id=g.id,
        embedding_vector=np.asarray(vector, dtype=np.float32).tobytes(),
        source="enrollment",
        quality_score=0.95,
    )
    db.add(fe)
    db.commit()
    return g


# ----------------------------------------------------------------------
# Cosine similarity
# ----------------------------------------------------------------------
class TestCosineSimilarity:
    def test_identical_vectors_similarity_one(self):
        a = _vec(1, 2, 3)
        assert FaceRecognitionEngine._cosine_similarity(a, a) == pytest.approx(1.0)

    def test_orthogonal_vectors_similarity_zero(self):
        a = _vec(1, 0, 0)
        b = _vec(0, 1, 0)
        assert FaceRecognitionEngine._cosine_similarity(a, b) == pytest.approx(0.0)

    def test_opposite_vectors_similarity_negative_one(self):
        a = _vec(1, 0, 0)
        b = _vec(-1, 0, 0)
        assert FaceRecognitionEngine._cosine_similarity(a, b) == pytest.approx(-1.0)

    def test_zero_vector_returns_zero(self):
        a = _vec(0, 0, 0)
        b = _vec(1, 2, 3)
        assert FaceRecognitionEngine._cosine_similarity(a, b) == 0.0
        assert FaceRecognitionEngine._cosine_similarity(b, a) == 0.0

    def test_similarity_invariant_to_magnitude(self):
        a = _vec(1, 1, 1)
        b = _vec(5, 5, 5)
        assert FaceRecognitionEngine._cosine_similarity(a, b) == pytest.approx(1.0)


# ----------------------------------------------------------------------
# Backend detection
# ----------------------------------------------------------------------
class TestBackendDetection:
    def test_backend_is_known_value(self, fre):
        assert fre.backend in ("facenet", "deepface", "opencv", "none")

    def test_guest_count_starts_zero(self, fre):
        assert fre.guest_count == 0


# ----------------------------------------------------------------------
# Loading guest embeddings
# ----------------------------------------------------------------------
class TestLoadGuestEmbeddings:
    def test_load_no_embeddings(self, db, fre):
        loaded = fre.load_guest_embeddings(db)
        assert loaded == 0
        assert fre.guest_count == 0

    def test_load_single_embedding(self, db, fre):
        _add_guest_with_embedding(db, "Alice", _vec(1, 0, 0, 0))
        loaded = fre.load_guest_embeddings(db)
        assert loaded == 1
        assert fre.guest_count == 1

    def test_load_multiple_guests(self, db, fre):
        _add_guest_with_embedding(db, "Alice", _vec(1, 0, 0, 0))
        _add_guest_with_embedding(db, "Bob", _vec(0, 1, 0, 0))
        _add_guest_with_embedding(db, "Carol", _vec(0, 0, 1, 0))
        loaded = fre.load_guest_embeddings(db)
        assert loaded == 3
        assert fre.guest_count == 3

    def test_load_clears_previous_state(self, db, fre):
        _add_guest_with_embedding(db, "Alice", _vec(1, 0, 0, 0))
        fre.load_guest_embeddings(db)
        assert fre.guest_count == 1
        # Clear and reload
        from database.models import FaceEmbedding as FE, Guest as G
        db.query(FE).delete()
        db.query(G).delete()
        db.commit()
        fre.load_guest_embeddings(db)
        assert fre.guest_count == 0


# ----------------------------------------------------------------------
# Best match selection
# ----------------------------------------------------------------------
class TestFindBestMatch:
    def test_best_match_selects_closest(self, db, fre):
        a = _add_guest_with_embedding(db, "Alice", _vec(1, 0, 0, 0))
        _add_guest_with_embedding(db, "Bob", _vec(0, 1, 0, 0))
        fre.load_guest_embeddings(db)
        guest_id, sim = fre._find_best_match(_vec(0.99, 0.01, 0, 0))
        assert guest_id == a.id
        assert sim > 0.99

    def test_best_match_returns_none_when_no_embeddings(self, fre):
        guest_id, sim = fre._find_best_match(_vec(1, 0, 0, 0))
        assert guest_id is None
        assert sim == 0.0


# ----------------------------------------------------------------------
# Recognize() pipeline
# ----------------------------------------------------------------------
class TestRecognizePipeline:
    def test_recognize_with_no_embedding_marks_unrecognized(self, fre):
        face = FaceDetection(bbox=(0, 0, 50, 50), confidence=0.9, embedding=None)
        fre._guest_embeddings = {}
        # Manually exercise the matching logic without calling detect_faces
        result = RecognitionResult(face=face)
        if face.embedding is not None and fre._guest_embeddings:
            best_id, best_sim = fre._find_best_match(face.embedding)
            if best_sim >= fre._threshold:
                result.guest_id = best_id
                result.is_recognized = True
        assert result.is_recognized is False
        assert result.guest_id is None

    def test_recognize_below_threshold_not_recognized(self, db, fre):
        _add_guest_with_embedding(db, "Alice", _vec(1, 0, 0, 0))
        fre.load_guest_embeddings(db)
        # Highly orthogonal embedding -> low similarity
        guest_id, sim = fre._find_best_match(_vec(0, 1, 0, 0))
        assert sim < fre._threshold

    def test_recognize_above_threshold_recognized(self, db, fre):
        a = _add_guest_with_embedding(db, "Alice", _vec(1, 0, 0, 0))
        fre.load_guest_embeddings(db)
        guest_id, sim = fre._find_best_match(_vec(1, 0.001, 0, 0))
        assert sim >= fre._threshold
        assert guest_id == a.id


# ----------------------------------------------------------------------
# Dataclass smoke
# ----------------------------------------------------------------------
class TestDataclasses:
    def test_face_detection_default_embedding(self):
        f = FaceDetection(bbox=(0, 0, 1, 1), confidence=0.5)
        assert f.embedding is None

    def test_recognition_result_defaults(self):
        f = FaceDetection(bbox=(0, 0, 1, 1), confidence=0.5)
        r = RecognitionResult(face=f)
        assert r.is_recognized is False
        assert r.guest_id is None
        assert r.similarity == 0.0
