from __future__ import annotations

from app.security import decrypt_text, encrypt_text, redact_dsn


def test_encrypt_decrypt_text() -> None:
    plaintext = "super secret password 123 🚀"
    blob = encrypt_text(plaintext)

    # Ciphertext shouldn't be plain
    assert blob.ciphertext != plaintext.encode("utf-8")

    # Decrypt should restore original
    decrypted = decrypt_text(blob.ciphertext, blob.nonce)
    assert decrypted == plaintext


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


def test_redact_dsn() -> None:
    assert redact_dsn("postgresql://user:password@localhost:5432/db") == "postgresql://***@localhost:5432/db"
    assert redact_dsn("postgresql://user:pass@word@localhost/db") == "postgresql://***@localhost/db"
    assert redact_dsn("mysql://user:pass@remote.host:3306/db") == "mysql://***@remote.host:3306/db"
    # No @ or ://
    assert redact_dsn("invalid") == "***"
    assert redact_dsn("postgresql://localhost/db") == "***"
