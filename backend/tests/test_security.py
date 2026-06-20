from __future__ import annotations

import pytest

from app.security import redact_dsn, encrypt_text, decrypt_text


@pytest.mark.parametrize(
    ("dsn", "expected"),
    [
        # Happy path - typical format
        ("postgresql://user:password@localhost:5432/dbname", "postgresql://***@localhost:5432/dbname"),

        # Missing @
        ("postgresql://localhost:5432/dbname", "***"),

        # Missing ://
        ("user:password@localhost:5432/dbname", "***"),

        # No credentials or host
        ("invalid", "***"),

        # Empty string
        ("", "***"),

        # Username only (no password)
        ("postgresql://user@localhost:5432/dbname", "postgresql://***@localhost:5432/dbname"),

        # Special characters in password
        ("postgresql://user:p@ssw0rd!@localhost:5432/dbname", "postgresql://***@localhost:5432/dbname"),

        # Multiple @ symbols (e.g. in password)
        ("postgresql://user:p@ssw@rd!@localhost:5432/dbname", "postgresql://***@localhost:5432/dbname"),

        # Different scheme
        ("mysql://user:password@host:3306/db", "mysql://***@host:3306/db"),
    ]
)
def test_redact_dsn(dsn: str, expected: str) -> None:
    assert redact_dsn(dsn) == expected


def test_encrypt_decrypt_roundtrip() -> None:
    plaintext = "super secret database password"
    blob = encrypt_text(plaintext)

    assert blob.ciphertext != plaintext.encode("utf-8")

    decrypted = decrypt_text(blob.ciphertext, blob.nonce)
    assert decrypted == plaintext
