from __future__ import annotations

import pytest
from unittest.mock import patch
from cryptography.exceptions import InvalidTag

from app.security import decrypt_text, encrypt_text, redact_dsn


@pytest.mark.parametrize(
    ("dsn", "expected"),
    [
        (
            "postgresql://user:password@localhost:5432/dbname",
            "postgresql://***@localhost:5432/dbname",
        ),
        ("postgresql://localhost:5432/dbname", "***"),
        ("user:password@localhost:5432/dbname", "***"),
        ("invalid", "***"),
        ("", "***"),
        (
            "postgresql://user@localhost:5432/dbname",
            "postgresql://***@localhost:5432/dbname",
        ),
        (
            "postgresql://user:p@ssw0rd!@localhost:5432/dbname",
            "postgresql://***@localhost:5432/dbname",
        ),
        (
            "postgresql://user:p@ssw@rd!@localhost:5432/dbname",
            "postgresql://***@localhost:5432/dbname",
        ),
        ("postgresql://user:pass@word@localhost/db", "postgresql://***@localhost/db"),
        ("mysql://user:password@host:3306/db", "mysql://***@host:3306/db"),
        ("mysql://user:pass@remote.host:3306/db", "mysql://***@remote.host:3306/db"),
        ("user@pass://localhost", "***"),
    ],
)
def test_redact_dsn(dsn: str, expected: str) -> None:
    assert redact_dsn(dsn) == expected


def test_encrypt_decrypt_text() -> None:
    plaintext = "super secret password 123"
    blob = encrypt_text(plaintext)

    assert blob.ciphertext != plaintext.encode("utf-8")
    assert decrypt_text(blob.ciphertext, blob.nonce) == plaintext


def test_encrypt_decrypt_empty_string() -> None:
    plaintext = ""
    blob = encrypt_text(plaintext)

    assert decrypt_text(blob.ciphertext, blob.nonce) == plaintext


def test_encrypt_text_nonces_are_unique() -> None:
    plaintext = "test"
    blob1 = encrypt_text(plaintext)
    blob2 = encrypt_text(plaintext)

    assert blob1.nonce != blob2.nonce
    assert blob1.ciphertext != blob2.ciphertext


def test_encrypt_decrypt_with_mocked_secret() -> None:
    plaintext = "mocked secret test"

    with patch("app.security.settings.app_secret", "secret-key-1"):
        blob = encrypt_text(plaintext)
        assert decrypt_text(blob.ciphertext, blob.nonce) == plaintext

    with patch("app.security.settings.app_secret", "secret-key-2"):
        with pytest.raises(InvalidTag):
            decrypt_text(blob.ciphertext, blob.nonce)
