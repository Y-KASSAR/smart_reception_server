"""
Guest Enrollment Routes (SDD §3.4.2 / §4.3.7, FR-1.11)
======================================================
Two-step enrollment flow used by the React dashboard:

    POST /api/enrollment/capture   → preview a single face from a base64
                                     image, return the detected crop and
                                     quality score so the receptionist can
                                     retake before submitting.

    POST /api/enrollment/complete  → atomic "create guest + attach up to
                                     N face embeddings" operation. Validates
                                     consent_given (NFR-2.10).

The existing ``POST /api/guests/{id}/embed`` route (guests.py) handles
*adding* embeddings to an existing guest; enrollment.py is for first-time
enrollment in a single round-trip.
"""
import base64
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.schemas import GuestCreate, GuestResponse
from config.logging_config import get_logger
from database.connection import get_db
from database.repositories import FaceEmbeddingRepository, GuestRepository
from utils.security_utils import get_current_staff

logger = get_logger(__name__)
router = APIRouter()


# ----------------------------------------------------------------------------
# Pydantic payloads
# ----------------------------------------------------------------------------
class CapturePayload(BaseModel):
    frame_b64: str   # base64-encoded JPEG/PNG from the dashboard webcam


class CaptureResponse(BaseModel):
    face_detected: bool
    face_count: int
    bbox: Optional[List[int]] = None    # [x, y, w, h]
    quality_score: Optional[float] = None
    face_image_b64: Optional[str] = None   # cropped face for preview, base64-encoded JPEG
    message: Optional[str] = None


class CompletePayload(BaseModel):
    guest: GuestCreate
    face_images_b64: List[str]    # 1..max_embeddings_per_guest base64 frames
    consent_given: bool = False   # NFR-2.10 — must be True to proceed


class CompleteResponse(BaseModel):
    guest: GuestResponse
    embeddings_stored: int
    embeddings_failed: int


# ----------------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------------
def _decode_frame(frame_b64: str):
    """Base64 → numpy BGR ndarray. Raises HTTPException on bad input."""
    try:
        import numpy as np
    except ImportError:
        raise HTTPException(status_code=503, detail="numpy not installed on server")
    try:
        import cv2
    except ImportError:
        raise HTTPException(status_code=503, detail="OpenCV not installed on server")

    try:
        raw = base64.b64decode(frame_b64)
        arr = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid frame data: {e}")

    if frame is None:
        raise HTTPException(status_code=400, detail="Could not decode frame image")
    return frame


def _encode_jpeg(frame) -> Optional[str]:
    """Encode a numpy BGR frame back to base64 JPEG (for preview returns)."""
    try:
        import cv2
    except ImportError:
        return None
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        return None
    return base64.b64encode(buf.tobytes()).decode("ascii")


# ----------------------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------------------
@router.post("/capture", response_model=CaptureResponse)
def capture_face(
    payload: CapturePayload,
    _=Depends(get_current_staff),
):
    """
    Detect a face in the supplied frame and return a preview + quality score.

    The frontend calls this before ``/complete`` so the receptionist can
    review (or retake) each shot. No database write happens here.
    """
    from modules.recognition import face_engine

    frame = _decode_frame(payload.frame_b64)
    faces = face_engine.detect_faces(frame)
    if not faces:
        return CaptureResponse(
            face_detected=False,
            face_count=0,
            message="No face detected — try better lighting or face the camera.",
        )

    # Largest face = closest to camera
    face = max(faces, key=lambda f: f.bbox[2] * f.bbox[3])
    x, y, w, h = face.bbox
    # Crop with a small padding for nicer preview
    pad = int(0.15 * max(w, h))
    h_img, w_img = frame.shape[:2]
    x0 = max(0, x - pad)
    y0 = max(0, y - pad)
    x1 = min(w_img, x + w + pad)
    y1 = min(h_img, y + h + pad)
    crop = frame[y0:y1, x0:x1]

    return CaptureResponse(
        face_detected=True,
        face_count=len(faces),
        bbox=[x, y, w, h],
        quality_score=round(float(face.confidence), 4),
        face_image_b64=_encode_jpeg(crop),
        message=None
        if face.confidence >= 0.9
        else "Face detected but quality is low — consider retaking.",
    )


@router.post("/complete", response_model=CompleteResponse, status_code=201)
def complete_enrollment(
    payload: CompletePayload,
    db: Session = Depends(get_db),
    _=Depends(get_current_staff),
):
    """
    Create a new guest and enroll up to N face embeddings in one atomic call.

    Steps:
        1. Validate consent_given (NFR-2.10).
        2. Reject duplicate emails (matches POST /api/guests/).
        3. Create the Guest row.
        4. For each base64 face image, run face_engine.enroll() — best-effort:
           failures are counted but do not roll back the whole enrollment.
    """
    if not payload.consent_given:
        raise HTTPException(
            status_code=400,
            detail="consent_given must be True to enroll a guest's facial data (NFR-2.10).",
        )

    if not payload.face_images_b64:
        raise HTTPException(
            status_code=400,
            detail="At least one face image is required for enrollment.",
        )

    from config.settings import settings
    max_emb = int(settings.recognition.max_embeddings_per_guest)
    if len(payload.face_images_b64) > max_emb:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_emb} face images per guest (FR-1.12).",
        )

    if payload.guest.email:
        existing = GuestRepository.get_by_email(db, payload.guest.email)
        if existing:
            raise HTTPException(
                status_code=409, detail="Guest with this email already exists"
            )

    guest = GuestRepository.create(db, **payload.guest.model_dump())

    from modules.recognition import face_engine

    stored = 0
    failed = 0
    for frame_b64 in payload.face_images_b64:
        try:
            frame = _decode_frame(frame_b64)
            result = face_engine.enroll(frame, guest_id=guest.id, db=db)
            if result is not None:
                stored += 1
            else:
                failed += 1
        except HTTPException:
            failed += 1
        except Exception as e:
            logger.error(f"enroll exception: {e}", exc_info=True)
            failed += 1

    if stored == 0:
        # No usable embeddings — keep the guest (admin may add later via
        # POST /api/guests/{id}/embed) but warn the caller.
        logger.warning(
            f"Guest #{guest.id} created without any usable face embeddings"
        )

    return CompleteResponse(
        guest=GuestResponse.model_validate(guest),
        embeddings_stored=stored,
        embeddings_failed=failed,
    )
