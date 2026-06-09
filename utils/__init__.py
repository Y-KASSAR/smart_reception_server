"""
Utility Functions
=================
Shared helper utilities used across the Smart Reception Assistant.

Includes:
- image_utils: Frame encoding/decoding helpers
- time_utils: Timestamp formatting
- security_utils: Token validation helpers
"""
from utils.time_utils import utcnow_str, seconds_to_human
from utils.security_utils import decode_jwt_token, require_role

try:
    from utils.image_utils import encode_frame_to_jpeg, decode_jpeg_to_frame
    _image_utils_available = True
except ImportError:
    _image_utils_available = False
    encode_frame_to_jpeg = None
    decode_jpeg_to_frame = None

__all__ = [
    "encode_frame_to_jpeg",
    "decode_jpeg_to_frame",
    "utcnow_str",
    "seconds_to_human",
    "decode_jwt_token",
    "require_role",
]