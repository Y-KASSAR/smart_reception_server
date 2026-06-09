"""
Image Utilities
===============
Helpers for encoding/decoding frames for transmission and storage.
"""
import numpy as np
from typing import Optional, Tuple


def encode_frame_to_jpeg(frame: np.ndarray, quality: int = 80) -> Optional[bytes]:
    """
    Encode a BGR numpy frame to JPEG bytes.

    Args:
        frame: BGR numpy array (OpenCV format)
        quality: JPEG quality 1-100

    Returns:
        JPEG bytes or None if encoding failed
    """
    try:
        import cv2
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        success, buffer = cv2.imencode(".jpg", frame, encode_params)
        if success:
            return buffer.tobytes()
        return None
    except ImportError:
        return None
    except Exception:
        return None


def decode_jpeg_to_frame(jpeg_bytes: bytes) -> Optional[np.ndarray]:
    """
    Decode JPEG bytes to a BGR numpy frame.

    Args:
        jpeg_bytes: Raw JPEG bytes

    Returns:
        BGR numpy array or None if decoding failed
    """
    try:
        import cv2
        arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame
    except ImportError:
        return None
    except Exception:
        return None


def crop_face(frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    """
    Crop a face region from a frame.

    Args:
        frame: BGR numpy array
        bbox: (x, y, w, h) bounding box

    Returns:
        Cropped face numpy array or None
    """
    try:
        x, y, w, h = bbox
        if w <= 0 or h <= 0:
            return None
        return frame[y:y + h, x:x + w].copy()
    except Exception:
        return None