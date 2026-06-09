"""
Embedding-at-rest Encryption (NFR-2.1)
=======================================
Authenticated AES-256-GCM encryption for the face-embedding column.

Storage format for new writes:

    [1 byte version=0x01] [12 byte nonce] [ciphertext + 16 byte GCM tag]

The total is base64-encoded so it round-trips cleanly through SQLite's
``LargeBinary`` columns. AES-256-GCM gives authenticated encryption with
12-byte nonces (NIST-recommended). The 256-bit key comes from the
``ENCRYPTION_KEY`` env var — must be 32 raw bytes, or 64 hex chars, or 44
base64 chars. A legacy Fernet decoder is also instantiated when the key
shape allows it, so rows written by earlier deployments still decrypt
transparently. Plaintext rows from before encryption was enabled also
pass through unchanged.

Generate a new key for production:

    python -c "import secrets; print(secrets.token_hex(32))"

Or via the bundled helper:

    python -c "from utils.crypto_utils import generate_key; print(generate_key())"
"""
from __future__ import annotations

import base64
import secrets as _secrets
from typing import Optional

from config.logging_config import get_logger
from config.settings import settings

logger = get_logger(__name__)

_VERSION_GCM_V1 = 0x01
_NONCE_BYTES = 12
_GCM_TAG_BYTES = 16

_AESGCM = None             # lazy-loaded cryptography.hazmat.AESGCM instance
_LEGACY_FERNET = None      # kept for one-way back-compat reads
_INITIALIZED = False


# ----------------------------------------------------------------------------
# Key parsing — accepts 32-byte raw / 64-char hex / 44-char base64
# ----------------------------------------------------------------------------
def _key_bytes_from_env(raw: str) -> Optional[bytes]:
    raw = raw.strip()
    if not raw:
        return None
    # Hex?
    if len(raw) == 64 and all(c in "0123456789abcdefABCDEF" for c in raw):
        try:
            return bytes.fromhex(raw)
        except Exception:
            pass
    # base64 url-safe (Fernet-style, 44 chars + optional padding)?
    try:
        b = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        if len(b) == 32:
            return b
    except Exception:
        pass
    # base64 standard?
    try:
        b = base64.b64decode(raw)
        if len(b) == 32:
            return b
    except Exception:
        pass
    # Raw 32 bytes (unusual but supported)
    if len(raw.encode()) == 32:
        return raw.encode()
    return None


def _init() -> None:
    """Initialise AESGCM + legacy Fernet exactly once."""
    global _AESGCM, _LEGACY_FERNET, _INITIALIZED
    if _INITIALIZED:
        return
    _INITIALIZED = True
    env_key = settings.secrets.encryption_key or ""
    if not env_key:
        logger.info("Embedding encryption disabled (no ENCRYPTION_KEY set)")
        return
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        logger.warning("cryptography not installed, embedding encryption disabled")
        return

    key_bytes = _key_bytes_from_env(env_key)
    if key_bytes is None or len(key_bytes) != 32:
        logger.error(
            "ENCRYPTION_KEY invalid for AES-256 (need 32 raw bytes / 64 hex / "
            "44 base64 chars); encryption disabled"
        )
        return

    _AESGCM = AESGCM(key_bytes)
    logger.info("Embedding encryption enabled (AES-256-GCM, 12B nonce, 128b tag)")

    # Legacy reader — try to construct a Fernet from the same key if it
    # happens to be a valid Fernet base64 key (44 chars). Lets existing
    # rows decrypt cleanly during migration.
    try:
        from cryptography.fernet import Fernet
        if len(env_key.strip()) == 44:
            _LEGACY_FERNET = Fernet(env_key.encode() if isinstance(env_key, str) else env_key)
            logger.info("Legacy Fernet reader also enabled for backward-compat decrypts")
    except Exception:
        _LEGACY_FERNET = None


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------
def encrypt_embedding(raw: bytes) -> bytes:
    """Encrypt embedding bytes with AES-256-GCM. Pass-through if disabled."""
    _init()
    if _AESGCM is None or raw is None:
        return raw
    try:
        nonce = _secrets.token_bytes(_NONCE_BYTES)
        ct = _AESGCM.encrypt(nonce, raw, associated_data=None)
        # Frame: version || nonce || ciphertext+tag, base64-encoded for portability
        framed = bytes([_VERSION_GCM_V1]) + nonce + ct
        return base64.b64encode(framed)
    except Exception as e:
        logger.error(f"Embedding encrypt failed: {e}")
        return raw


def decrypt_embedding(stored: bytes) -> bytes:
    """Decrypt embedding bytes. Transparent to plaintext + legacy Fernet rows.

    Detection order:
      1. AES-256-GCM v1 framing (our new format)
      2. Legacy Fernet ciphertext (rows written by earlier deployments)
      3. Plaintext passthrough (rows written before encryption was enabled)
    """
    _init()
    if stored is None:
        return stored

    # Try AES-256-GCM v1
    try:
        framed = base64.b64decode(stored)
        if (
            _AESGCM is not None
            and len(framed) >= 1 + _NONCE_BYTES + _GCM_TAG_BYTES
            and framed[0] == _VERSION_GCM_V1
        ):
            nonce = framed[1:1 + _NONCE_BYTES]
            ct = framed[1 + _NONCE_BYTES:]
            return _AESGCM.decrypt(nonce, ct, associated_data=None)
    except Exception:
        pass

    # Try legacy Fernet (gAAAAA… prefix)
    if _LEGACY_FERNET is not None:
        try:
            return _LEGACY_FERNET.decrypt(stored)
        except Exception:
            pass

    # Plaintext passthrough — legacy unencrypted row
    return stored


def generate_key() -> str:
    """Generate a fresh 32-byte AES-256 key, hex-encoded."""
    return _secrets.token_hex(32)
