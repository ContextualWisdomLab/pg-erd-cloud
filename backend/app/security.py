from __future__ import annotations

import hashlib
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.settings import settings


def _derive_key() -> bytes:
    # MVP key derivation: stable 32-bytes from APP_SECRET.
    # In production prefer KMS/HKDF with rotation.
    return hashlib.sha256(settings.app_secret.encode("utf-8")).digest()


@dataclass(frozen=True)
class EncryptedBlob:
    ciphertext: bytes
    nonce: bytes


def encrypt_text(plaintext: str) -> EncryptedBlob:
    key = _derive_key()
    aes = AESGCM(key)
    import os

    nonce = os.urandom(12)
    ciphertext = aes.encrypt(nonce, plaintext.encode("utf-8"), None)
    return EncryptedBlob(ciphertext=ciphertext, nonce=nonce)


def decrypt_text(ciphertext: bytes, nonce: bytes) -> str:
    key = _derive_key()
    aes = AESGCM(key)
    plaintext = aes.decrypt(nonce, ciphertext, None)
    return plaintext.decode("utf-8")


def redact_dsn(dsn: str) -> str:
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
