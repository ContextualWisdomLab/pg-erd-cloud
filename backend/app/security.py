from __future__ import annotations

import os
import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.settings import settings


def _derive_key(salt: bytes | None = None) -> bytes:
    """Derive a stable 32-byte key from APP_SECRET using HKDF."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"pg-erd-cloud-db-connection",
    )
    return hkdf.derive(settings.app_secret.encode("utf-8"))


@dataclass(frozen=True)
class EncryptedBlob:
    """Encrypted bytes plus nonce for AES-GCM."""

    ciphertext: bytes
    nonce: bytes


def encrypt_text(plaintext: str) -> EncryptedBlob:
    """Encrypt a UTF-8 string using AES-256-GCM."""
    salt = os.urandom(16)
    key = _derive_key(salt)
    aes = AESGCM(key)

    nonce = os.urandom(12)
    # prepend salt to ciphertext to allow decryption
    ciphertext = salt + aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return EncryptedBlob(ciphertext=ciphertext, nonce=nonce)


def decrypt_text(ciphertext: bytes, nonce: bytes) -> str:
    """Decrypt a blob produced by encrypt_text."""
    # salt is the first 16 bytes
    salt = ciphertext[:16]
    actual_ciphertext = ciphertext[16:]

    # Fallback to old behavior for backward compatibility if the ciphertext isn't long enough
    # or if we can't decrypt it. The old behavior used no salt and a simple SHA256.
    try:
        key = _derive_key(salt)
        aes = AESGCM(key)
        plaintext = aes.decrypt(nonce, actual_ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception:
        old_key = hashlib.sha256(settings.app_secret.encode("utf-8")).digest()
        aes = AESGCM(old_key)
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
