"""
Face Recognition Engine (SDD §4.2.3, FR-1)
==========================================

Pipeline per FR-1.1 → FR-1.7:

    raw frame  →  face detection (MTCNN)
               →  alignment + crop to 160x160
               →  embedding extraction (FaceNet, 512-D, L2-normalized)
               →  cosine-similarity match against cached guest embeddings
               →  RecognitionResult with guest_id when similarity ≥ threshold

The module is designed to **load cleanly without ML dependencies installed**
(mirrors the lazy-import pattern in `api/routes/edge.py`). When
`facenet-pytorch` is unavailable, `backend` is reported as ``"none"`` and
`recognize()` returns an empty list — the rest of the system still boots,
tests still pass, and installing the library later activates full inference.

Backends, in priority order:

    1. ``"facenet"``  — facenet-pytorch (MTCNN + InceptionResnetV1, GPU optional)
    2. ``"none"``     — passthrough stub (no detection, no recognition)

Heavier alternatives (DeepFace) can be added later by extending
``_init_backend()`` without touching the public API.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from sqlalchemy.orm import Session

from config.logging_config import get_logger
from config.settings import settings
from database.models import FaceEmbedding
from database.repositories.face_embedding_repository import FaceEmbeddingRepository
from utils.crypto_utils import decrypt_embedding, encrypt_embedding

logger = get_logger(__name__)


# ----------------------------------------------------------------------------
# Public dataclasses
# ----------------------------------------------------------------------------
@dataclass
class FaceDetection:
    """A single face detected in a frame (FR-1.2)."""
    bbox: tuple                       # (x, y, w, h)
    confidence: float
    embedding: Optional[np.ndarray] = None   # 512-D when extraction succeeds


@dataclass
class RecognitionResult:
    """Outcome of matching a detected face against the embedding cache (FR-1.5/1.7)."""
    face: FaceDetection
    guest_id: Optional[int] = None
    guest_name: Optional[str] = None     # populated by recognize() when matched
    similarity: float = 0.0
    is_recognized: bool = False


# ----------------------------------------------------------------------------
# Engine
# ----------------------------------------------------------------------------
class FaceRecognitionEngine:
    """Singleton-style face recognition pipeline.

    Heavy ML models are loaded once on first detection call and cached.
    Embedding lookups go through an in-memory dict keyed by guest_id; reload
    after every enrollment to keep the cache hot.
    """

    def __init__(self):
        self._threshold: float = float(settings.recognition.similarity_threshold)
        self._max_per_guest: int = int(settings.recognition.max_embeddings_per_guest)
        self._guest_embeddings: dict[int, list[np.ndarray]] = {}
        self._guest_names: dict[int, str] = {}
        # Flattened, L2-normalized embedding matrix for vectorized matching.
        # _emb_matrix: (N, D) float32; _emb_guest_ids[i] is the guest for row i.
        self._emb_matrix: Optional[np.ndarray] = None
        self._emb_guest_ids: list[int] = []
        self._lock = threading.RLock()

        # Model handles (initialized lazily)
        self._mtcnn = None
        self._resnet = None
        self._device: str = "cpu"
        self.backend: str = self._detect_backend()

        if self.backend == "facenet":
            logger.info(
                f"FaceRecognitionEngine ready (backend=facenet, "
                f"threshold={self._threshold:.2f}, device={self._device})"
            )
        else:
            logger.warning(
                "FaceRecognitionEngine running in stub mode (backend=none). "
                "Install facenet-pytorch + torch to enable recognition."
            )

    # ------------------------------------------------------------------
    # Backend detection / lazy model load
    # ------------------------------------------------------------------
    def _detect_backend(self) -> str:
        try:
            import facenet_pytorch   # noqa: F401
            import torch             # noqa: F401
            try:
                import torch as _t
                self._device = "cuda" if _t.cuda.is_available() else "cpu"
            except Exception:
                self._device = "cpu"
            return "facenet"
        except ImportError:
            self._device = "cpu"
            return "none"

    def _ensure_models(self) -> bool:
        """Initialize MTCNN + FaceNet on first use. Returns True on success."""
        if self.backend != "facenet":
            return False
        if self._mtcnn is not None and self._resnet is not None:
            return True
        with self._lock:
            if self._mtcnn is not None and self._resnet is not None:
                return True
            try:
                # Patch the off-by-N bug in facenet_pytorch.detect_face's
                # stage-2 / stage-3 loops. Must run BEFORE the MTCNN constructor
                # because the class's __init__ binds to the original `detect_face`
                # at module import time.
                from modules.recognition import _facenet_patch
                _facenet_patch.apply()
                from facenet_pytorch import MTCNN, InceptionResnetV1
                # Pose-tolerance knobs (FR-1): a smaller min_face_size and
                # relaxed cascade thresholds keep faces turned ~30–45° that the
                # stricter defaults would drop. Embedding matching still gates
                # recognition, so looser detection alone can't cause a false ID.
                min_face_size = int(getattr(settings.recognition, "min_face_size", 20) or 20)
                thresholds = list(getattr(settings.recognition, "detection_thresholds", None)
                                  or [0.6, 0.7, 0.7])
                self._mtcnn = MTCNN(
                    image_size=160,
                    margin=14,
                    keep_all=True,
                    post_process=True,
                    min_face_size=min_face_size,
                    thresholds=thresholds,
                    device=self._device,
                )
                self._resnet = (
                    InceptionResnetV1(pretrained="vggface2").eval().to(self._device)
                )
                logger.info(f"FaceNet models loaded on {self._device}")
                return True
            except Exception as e:
                logger.error(f"Failed to load FaceNet models: {e}", exc_info=True)
                self.backend = "none"
                return False

    # ------------------------------------------------------------------
    # Cosine similarity (FR-1.5) — staticmethod so tests can invoke without
    # constructing the engine
    # ------------------------------------------------------------------
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity in [-1, 1]. Returns 0.0 if either vector is zero."""
        a = np.asarray(a, dtype=np.float32).ravel()
        b = np.asarray(b, dtype=np.float32).ravel()
        na = float(np.linalg.norm(a))
        nb = float(np.linalg.norm(b))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    # ------------------------------------------------------------------
    # Embedding cache management
    # ------------------------------------------------------------------
    @property
    def guest_count(self) -> int:
        return len(self._guest_embeddings)

    def load_guest_embeddings(self, db: Session) -> int:
        """Reload every guest's embeddings from the DB into the in-memory cache.

        Called at startup and after every enrollment. Returns the number of
        distinct guests now in the cache.
        """
        from database.models import Guest

        with self._lock:
            self._guest_embeddings.clear()
            self._guest_names.clear()
            embeddings = db.query(FaceEmbedding).all()
            for fe in embeddings:
                vec = self._deserialize(fe.embedding_vector)
                if vec is None:
                    continue
                self._guest_embeddings.setdefault(fe.guest_id, []).append(vec)

            # Cache display names so the recognize() result can include them
            # without an extra query per recognition call.
            guest_ids = list(self._guest_embeddings.keys())
            if guest_ids:
                for g in db.query(Guest).filter(Guest.id.in_(guest_ids)).all():
                    self._guest_names[g.id] = (
                        g.full_name or f"{g.first_name or ''} {g.last_name or ''}".strip()
                        or f"Guest #{g.id}"
                    )

            # Build the flattened, L2-normalized matrix for vectorized matching.
            rows: list[np.ndarray] = []
            ids: list[int] = []
            for gid, vectors in self._guest_embeddings.items():
                for v in vectors:
                    n = float(np.linalg.norm(v))
                    rows.append((v / n) if n else v)
                    ids.append(gid)
            self._emb_matrix = np.vstack(rows).astype(np.float32) if rows else None
            self._emb_guest_ids = ids

        logger.info(
            f"Embedding cache reloaded: {self.guest_count} guest(s), "
            f"{sum(len(v) for v in self._guest_embeddings.values())} embedding(s)"
        )
        return self.guest_count

    @staticmethod
    def _deserialize(blob: bytes) -> Optional[np.ndarray]:
        """Convert a DB-stored embedding blob → numpy float32 vector.

        Handles both the encrypted blobs written by FaceEmbeddingRepository
        and raw `.tobytes()` writes used in tests (decrypt is transparent
        passthrough when key is unset or blob isn't encrypted).
        """
        if blob is None:
            return None
        try:
            raw = decrypt_embedding(blob)
            vec = np.frombuffer(raw, dtype=np.float32)
            if vec.size == 0:
                return None
            return vec
        except Exception as e:
            logger.warning(f"Failed to deserialize embedding: {e}")
            return None

    # ------------------------------------------------------------------
    # Matching (FR-1.6)
    # ------------------------------------------------------------------
    def _find_best_match(self, embedding: np.ndarray) -> tuple[Optional[int], float]:
        """Return (best_guest_id, best_similarity) across cached embeddings.

        Uses best-match strategy (FR-1.12): for guests with multiple stored
        embeddings, picks the highest per-guest similarity.
        """
        if embedding is None:
            return None, 0.0

        # Fast path: single matrix-vector product. Rows of _emb_matrix are
        # already L2-normalized, so normalizing the query makes each dot
        # product an exact cosine similarity.
        mat = self._emb_matrix
        if mat is not None and mat.shape[0] > 0:
            q = np.asarray(embedding, dtype=np.float32).ravel()
            nq = float(np.linalg.norm(q))
            if nq == 0.0:
                return None, 0.0
            sims = mat @ (q / nq)
            idx = int(np.argmax(sims))
            return self._emb_guest_ids[idx], float(sims[idx])

        # Fallback (matrix not built yet): original per-vector loop.
        best_id: Optional[int] = None
        best_sim: float = 0.0
        for guest_id, vectors in self._guest_embeddings.items():
            for v in vectors:
                sim = self._cosine_similarity(embedding, v)
                if sim > best_sim:
                    best_sim = sim
                    best_id = guest_id
        return best_id, best_sim

    # ------------------------------------------------------------------
    # Detection + recognition pipeline
    # ------------------------------------------------------------------
    def detect_faces(self, frame: np.ndarray) -> list[FaceDetection]:
        """Detect every face in a BGR frame and attach its 512-D embedding.

        Returns an empty list when no backend is available or no face is found.

        We deliberately bypass ``self._mtcnn(pil)``'s combined detect+extract
        path because facenet-pytorch occasionally surfaces degenerate boxes
        (post-bbreg ``x2 < x1`` / ``y2 < y1``) that crash ``PIL.Image.crop``
        with "Coordinate 'right' is less than 'left'". Instead we run detect,
        clamp + filter the boxes to sane bounds, then extract manually.
        """
        if not self._ensure_models() or frame is None:
            return []
        try:
            from PIL import Image
            from facenet_pytorch.models.utils.detect_face import extract_face
            import torch
            rgb = frame[..., ::-1] if frame.ndim == 3 else frame
            pil_full = Image.fromarray(rgb)
            img_w, img_h = pil_full.size

            # Downscale for face DETECTION only (big MTCNN speedup → lower
            # latency). Crops for embedding extraction are still taken from the
            # full-resolution image, so recognition accuracy is preserved.
            infer_w = int(getattr(settings.recognition, "inference_width", 0) or 0)
            if infer_w and img_w > infer_w:
                det_scale = infer_w / float(img_w)
                pil_det = pil_full.resize((infer_w, max(1, int(img_h * det_scale))))
            else:
                det_scale = 1.0
                pil_det = pil_full

            with self._lock:
                boxes, probs = self._mtcnn.detect(pil_det)
            if boxes is None or len(boxes) == 0:
                return []

            inv = 1.0 / det_scale  # map detection-scale boxes back to full res
            valid: list[tuple[tuple[float, float, float, float], float]] = []
            for box, prob in zip(boxes, probs):
                if box is None or prob is None:
                    continue
                x1, y1 = float(box[0]) * inv, float(box[1]) * inv
                x2, y2 = float(box[2]) * inv, float(box[3]) * inv
                x1 = max(0.0, min(x1, img_w - 1))
                y1 = max(0.0, min(y1, img_h - 1))
                x2 = max(0.0, min(x2, img_w))
                y2 = max(0.0, min(y2, img_h))
                if x2 - x1 < 20 or y2 - y1 < 20:
                    continue
                valid.append(((x1, y1, x2, y2), float(prob)))
            if not valid:
                return []

            face_tensors = []
            with self._lock:
                for (x1, y1, x2, y2), _ in valid:
                    try:
                        face = extract_face(pil_full, (x1, y1, x2, y2), self._mtcnn.image_size, self._mtcnn.margin)
                    except Exception as ex:
                        logger.debug(f"extract_face skipped invalid box ({x1},{y1},{x2},{y2}): {ex}")
                        continue
                    if face is None:
                        continue
                    # Match the post_process step the wrapper would have done
                    face = (face - 127.5) / 128.0
                    face_tensors.append(face)
            if not face_tensors:
                return []

            aligned = torch.stack(face_tensors).to(self._device)
            with torch.no_grad():
                # FP16 autocast on GPU ~doubles FaceNet throughput with
                # negligible accuracy loss; plain FP32 path on CPU.
                if self._device != "cpu":
                    with torch.autocast(device_type="cuda", dtype=torch.float16):
                        embeddings = self._resnet(aligned).float().cpu().numpy()
                else:
                    embeddings = self._resnet(aligned).cpu().numpy()
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            embeddings = embeddings / norms

            results: list[FaceDetection] = []
            for ((x1, y1, x2, y2), prob), emb in zip(valid, embeddings):
                bbox = (int(x1), int(y1), int(max(1, x2 - x1)), int(max(1, y2 - y1)))
                results.append(
                    FaceDetection(
                        bbox=bbox,
                        confidence=prob,
                        embedding=emb.astype(np.float32),
                    )
                )
            return results
        except Exception as e:
            logger.error(f"detect_faces failed: {e}", exc_info=True)
            return []

    def guest_embedding_vectors(self, db: Session, guest_id: int) -> list[np.ndarray]:
        """Read a guest's stored face vectors straight from the DB (decrypted).

        Reads from the database rather than the in-memory cache so verification
        is correct even if the cache hasn't been reloaded since the last change.
        """
        rows = FaceEmbeddingRepository.get_by_guest(db, guest_id)
        out: list[np.ndarray] = []
        for fe in rows:
            v = self._deserialize(fe.embedding_vector)
            if v is not None:
                out.append(v)
        return out

    def verify_match(
        self,
        frame: np.ndarray,
        guest_id: int,
        db: Session,
        threshold: Optional[float] = None,
    ) -> dict:
        """Quick "is this the same person?" check before adding a face.

        Compares the largest face in ``frame`` against the guest's existing
        embeddings. Returns a dict:
            face_found  : a face was detected in the frame
            no_baseline : guest has no existing embeddings (nothing to compare)
            similarity  : best cosine similarity to the guest's stored faces
            is_match    : similarity >= threshold (or True when no baseline)
        """
        thr = float(threshold if threshold is not None
                    else getattr(settings.recognition, "enroll_verify_threshold", 0.5))
        faces = self.detect_faces(frame)
        if not faces:
            return {"face_found": False, "no_baseline": False,
                    "similarity": 0.0, "is_match": False, "threshold": thr}
        face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
        existing = self.guest_embedding_vectors(db, guest_id)
        if not existing:
            return {"face_found": True, "no_baseline": True,
                    "similarity": 0.0, "is_match": True, "threshold": thr}
        best = max(self._cosine_similarity(face.embedding, v) for v in existing)
        return {"face_found": True, "no_baseline": False,
                "similarity": round(float(best), 4), "is_match": best >= thr,
                "threshold": thr}

    def recognize(self, frame: np.ndarray, db: Optional[Session] = None) -> list[RecognitionResult]:
        """End-to-end: detect every face in the frame and match each one.

        ``db`` is accepted for API symmetry with the route layer
        (`api/routes/edge.py:101`) but the matcher works off the in-memory
        cache, so the DB is only used to refresh display names lazily.
        """
        faces = self.detect_faces(frame)
        results: list[RecognitionResult] = []
        for face in faces:
            result = RecognitionResult(face=face)
            if face.embedding is not None and self._guest_embeddings:
                best_id, best_sim = self._find_best_match(face.embedding)
                result.similarity = best_sim
                if best_sim >= self._threshold and best_id is not None:
                    result.is_recognized = True
                    result.guest_id = best_id
                    result.guest_name = self._guest_names.get(best_id)
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Enrollment (FR-1.11)
    # ------------------------------------------------------------------
    def enroll(
        self,
        frame: np.ndarray,
        guest_id: int,
        db: Session,
        source: str = "enrollment",
    ) -> Optional[FaceEmbedding]:
        """Detect the largest face in ``frame``, extract its embedding, and
        store it for ``guest_id``. Enforces ``max_embeddings_per_guest``
        (FR-1.12) by evicting the oldest record once the limit is reached.

        Returns the persisted FaceEmbedding row, or None on failure.
        """
        faces = self.detect_faces(frame)
        if not faces:
            logger.info(f"enroll: no face detected for guest_id={guest_id}")
            return None
        # Pick the largest face (closest to camera) — same heuristic the SDD
        # recommends for enrollment UX.
        face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
        if face.embedding is None:
            return None

        # Enforce per-guest cap before insertion
        existing = FaceEmbeddingRepository.get_by_guest(db, guest_id)
        if len(existing) >= self._max_per_guest:
            oldest = min(existing, key=lambda e: e.created_at)
            FaceEmbeddingRepository.delete(db, oldest.id)

        raw_bytes = face.embedding.astype(np.float32).tobytes()
        stored = FaceEmbeddingRepository.create(
            db,
            guest_id=guest_id,
            embedding_bytes=raw_bytes,
            source=source,
            quality_score=face.confidence,
        )

        # Refresh the in-memory cache so the new face is recognized immediately
        self.load_guest_embeddings(db)
        return stored


# Module-level singleton (required by api/routes/edge.py:20 and others)
face_engine = FaceRecognitionEngine()
