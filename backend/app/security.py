from __future__ import annotations

import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from app.settings import settings


def _derive_key() -> bytes:
    """Derive a stable 32-byte key from APP_SECRET using HKDF.

    HKDF ensures optimal entropy distribution for the derived key,
    mitigating weaknesses if the application secret is sub-optimal.
    """
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"pg-erd-cloud-v1",
        info=b"aes-gcm-encryption",
    )
    return hkdf.derive(settings.app_secret.encode("utf-8"))


def _derive_legacy_key() -> bytes:
    """Legacy key derivation (raw SHA256) for backward compatibility."""
    return hashlib.sha256(settings.app_secret.encode("utf-8")).digest()


@dataclass(frozen=True)
class EncryptedBlob:
    """Encrypted bytes plus nonce for AES-GCM."""

    ciphertext: bytes
    nonce: bytes


def encrypt_text(plaintext: str) -> EncryptedBlob:
    """Encrypt a UTF-8 string using AES-256-GCM."""
    key = _derive_key()
    aes = AESGCM(key)
    import os

    nonce = os.urandom(12)
    ciphertext = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return EncryptedBlob(ciphertext=ciphertext, nonce=nonce)


def decrypt_text(ciphertext: bytes, nonce: bytes) -> str:
    """Decrypt a blob produced by encrypt_text (with legacy fallback)."""
    from cryptography.exceptions import InvalidTag

    try:
        # Attempt to decrypt with the secure HKDF key
        key = _derive_key()
        aes = AESGCM(key)
        plaintext = aes.decrypt(nonce, ciphertext, None)
    except InvalidTag:
        # Fallback to legacy raw SHA-256 derivation for older ciphertexts
        legacy_key = _derive_legacy_key()
        aes = AESGCM(legacy_key)
        plaintext = aes.decrypt(nonce, ciphertext, None)

    return plaintext.decode("utf-8")


def redact_dsn(dsn: str) -> str:
    """Redact credentials from a DSN for safe logging."""

    # Avoid leaking credentials in logs.
    # Best-effort: remove password in typical URI formats.
    # If unsure, return a constant to avoid partial leaks.
    if "@" not in dsn or "://" not in dsn:
        return "***"
    scheme, rest = dsn.split("://", 1)
    if "@" not in rest:
        return "***"
    _, hostpart = rest.rsplit("@", 1)
    return f"{scheme}://***@{hostpart}"
