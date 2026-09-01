"""Tests for :mod:`app.secret_provider.rotation`.

The planner must re-encrypt only rows under a previous key, leave
active-key rows alone, surface undecryptable and malformed rows as
``needs_key_recovery`` without dropping them, never emit plaintext, and
produce ciphertexts the production :mod:`app.security` path can decrypt.
"""

from __future__ import annotations

import pytest

from app.secret_provider.contract import SecretResolutionError
from app.secret_provider.rotation import (
    NONCE_LENGTH,
    ROTATION_PLAN_VERSION,
    dual_read_decrypt,
    plan_key_rotation,
)

_OLD = "old-app-secret-value-0001"
_NEW = "new-app-secret-value-0002"
_PLAINTEXT = "postgresql://user:pw@db.example:5432/app"


def _encrypt_with(monkeypatch: pytest.MonkeyPatch, app_secret: str, text: str) -> dict:
    """Encrypt ``text`` through the real app.security path under ``app_secret``."""
    from app import security

    monkeypatch.setattr(security.settings, "app_secret", app_secret)
    blob = security.encrypt_text(text)
    return {"ciphertext": blob.ciphertext, "nonce": blob.nonce}


def test_row_under_a_previous_key_is_re_encrypted_under_the_active_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _encrypt_with(monkeypatch, _OLD, _PLAINTEXT)
    fixed_nonce = b"\x01" * NONCE_LENGTH
    plan = plan_key_rotation(
        _NEW, [_OLD], [dict(record, id="conn-1")], nonce_source=lambda n: fixed_nonce
    )
    assert plan["version"] == ROTATION_PLAN_VERSION
    assert plan["total"] == 1
    assert plan["already_active"] == 0
    assert plan["needs_key_recovery"] == []
    assert len(plan["re_encrypted"]) == 1
    rotated = plan["re_encrypted"][0]
    assert rotated["id"] == "conn-1"
    assert rotated["nonce"] == fixed_nonce
    # The re-encrypted blob decrypts under the NEW key through production code.
    from app import security

    monkeypatch.setattr(security.settings, "app_secret", _NEW)
    assert security.decrypt_text(rotated["ciphertext"], rotated["nonce"]) == _PLAINTEXT


def test_row_already_under_the_active_key_is_left_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _encrypt_with(monkeypatch, _NEW, _PLAINTEXT)
    plan = plan_key_rotation(_NEW, [_OLD], [record])
    assert plan["already_active"] == 1
    assert plan["re_encrypted"] == []
    assert plan["needs_key_recovery"] == []


def test_undecryptable_row_is_flagged_not_dropped_or_guessed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _encrypt_with(monkeypatch, "a-third-unrelated-secret", _PLAINTEXT)
    plan = plan_key_rotation(_NEW, [_OLD], [dict(record, id="conn-x")])
    assert plan["re_encrypted"] == []
    assert plan["already_active"] == 0
    assert plan["needs_key_recovery"] == [
        {"index": 0, "id": "conn-x", "reason": "no_key_decrypts"}
    ]


def test_malformed_record_is_flagged_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good = _encrypt_with(monkeypatch, _OLD, _PLAINTEXT)
    plan = plan_key_rotation(
        _NEW,
        [_OLD],
        [
            {"ciphertext": "not-bytes", "nonce": b"x" * NONCE_LENGTH},
            {"nonce": b"x" * NONCE_LENGTH},
            good,
        ],
    )
    assert plan["total"] == 3
    reasons = [m["reason"] for m in plan["needs_key_recovery"]]
    assert reasons == ["malformed_record", "malformed_record"]
    assert len(plan["re_encrypted"]) == 1


def test_no_op_rotation_when_active_equals_the_only_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _encrypt_with(monkeypatch, _NEW, _PLAINTEXT)
    plan = plan_key_rotation(_NEW, [], [record])
    assert plan["already_active"] == 1
    assert plan["re_encrypted"] == []


def test_result_contains_no_plaintext(monkeypatch: pytest.MonkeyPatch) -> None:
    record = _encrypt_with(monkeypatch, _OLD, _PLAINTEXT)
    plan = plan_key_rotation(_NEW, [_OLD], [record])
    blob = repr(plan)
    assert _PLAINTEXT not in blob
    assert "user:pw" not in blob
    assert _OLD not in blob and _NEW not in blob


def test_dual_read_decrypt_tries_keys_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _encrypt_with(monkeypatch, _OLD, _PLAINTEXT)
    got = dual_read_decrypt(
        [_NEW, _OLD], record["ciphertext"], record["nonce"]
    )
    assert got.decode("utf-8") == _PLAINTEXT


def test_dual_read_decrypt_raises_on_empty_key_set() -> None:
    with pytest.raises(SecretResolutionError):
        dual_read_decrypt([], b"x", b"y")


def test_dual_read_decrypt_raises_when_no_key_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _encrypt_with(monkeypatch, "secret-nobody-has", _PLAINTEXT)
    with pytest.raises(SecretResolutionError):
        dual_read_decrypt([_NEW, _OLD], record["ciphertext"], record["nonce"])


def test_rotation_is_reproducible_with_a_fixed_nonce_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _encrypt_with(monkeypatch, _OLD, _PLAINTEXT)
    src = lambda n: b"\x07" * n
    a = plan_key_rotation(_NEW, [_OLD], [dict(record)], nonce_source=src)
    b = plan_key_rotation(_NEW, [_OLD], [dict(record)], nonce_source=src)
    assert a == b
