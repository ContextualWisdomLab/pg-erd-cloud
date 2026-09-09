"""Tests for :mod:`app.spec.waiver_record` — signed, tamper-evident waivers."""

from __future__ import annotations

import json
from typing import Any

import pytest

from app.spec.waiver_record import (
    WAIVER_SIGNATURE_ALGO,
    sign_waiver,
    verify_waiver_signature,
)

_KEY = b"unit-test-secret-key-0123456789ab"
_OTHER_KEY = b"a-different-secret-key-0123456789"


def _waiver() -> dict[str, Any]:
    """Return a representative waiver body (matches the assessment-module shape)."""

    return {
        "scope": {"relation": "sales.invoice_line", "kind": "candidate_3nf_split"},
        "owner": "data-architecture-guild",
        "reason": "denormalized on purpose for the reporting read model",
        "review_date": "2026-09-01",
        "expiry": "2027-03-01",
    }


def _sign(waiver: dict[str, Any] | None = None) -> dict[str, Any]:
    """Sign ``waiver`` (or the default) with fixed metadata for reuse in tests."""

    return sign_waiver(
        waiver if waiver is not None else _waiver(),
        signer="reviewer@example.test",
        signed_at="2026-09-02T10:00:00Z",
        key_id="waiver-key-2026-09",
        key=_KEY,
    )


def test_round_trip_verifies_true() -> None:
    """A freshly signed record verifies against the same key."""

    record = _sign()
    assert record["signature"]["algo"] == WAIVER_SIGNATURE_ALGO
    assert verify_waiver_signature(record, key=_KEY) is True


def test_signing_does_not_mutate_caller_waiver() -> None:
    """The caller's dict is deep-copied, not referenced, by the signed record."""

    original = _waiver()
    record = _sign(original)
    original["reason"] = "changed after signing"
    assert record["waiver"]["reason"] == "denormalized on purpose for the reporting read model"
    assert verify_waiver_signature(record, key=_KEY) is True


@pytest.mark.parametrize("field", ["owner", "reason", "review_date", "expiry"])
def test_tampering_a_waiver_field_fails_verification(field: str) -> None:
    """Editing any waiver body field after signing is detected."""

    record = _sign()
    record["waiver"][field] = "tampered"
    assert verify_waiver_signature(record, key=_KEY) is False


def test_tampering_nested_scope_fails_verification() -> None:
    """Editing a nested waiver value is detected too."""

    record = _sign()
    record["waiver"]["scope"]["relation"] = "sales.something_else"
    assert verify_waiver_signature(record, key=_KEY) is False


@pytest.mark.parametrize("field", ["signer", "signed_at", "key_id"])
def test_tampering_signature_metadata_fails_verification(field: str) -> None:
    """Changing who/when/which-key without re-signing is detected."""

    record = _sign()
    record["signature"][field] = "tampered"
    assert verify_waiver_signature(record, key=_KEY) is False


def test_tampering_signature_value_fails_verification() -> None:
    """A doctored HMAC digest does not verify."""

    record = _sign()
    record["signature"]["value"] = "0" * 64
    assert verify_waiver_signature(record, key=_KEY) is False


def test_wrong_key_fails_verification() -> None:
    """Verification with a different secret key returns False, not an error."""

    record = _sign()
    assert verify_waiver_signature(record, key=_OTHER_KEY) is False


def test_missing_signature_raises_value_error() -> None:
    """A record without a signature is a programming error, not a False."""

    with pytest.raises(ValueError, match="signature"):
        verify_waiver_signature({"waiver": _waiver()}, key=_KEY)


def test_unsupported_algo_raises_value_error() -> None:
    """Only HMAC-SHA256 is accepted; anything else is rejected loudly."""

    record = _sign()
    record["signature"]["algo"] = "hmac-sha1"
    with pytest.raises(ValueError, match="algo"):
        verify_waiver_signature(record, key=_KEY)


@pytest.mark.parametrize("bad", ["", None, 0])
def test_blank_metadata_is_rejected_at_signing(bad: object) -> None:
    """signer / signed_at / key_id must each be a non-empty string."""

    for field in ("signer", "signed_at", "key_id"):
        kwargs: dict[str, Any] = {
            "signer": "s",
            "signed_at": "t",
            "key_id": "k",
            "key": _KEY,
        }
        kwargs[field] = bad
        with pytest.raises(ValueError, match=field):
            sign_waiver(_waiver(), **kwargs)


def test_empty_key_is_rejected_at_signing() -> None:
    """An empty signing key is refused."""

    with pytest.raises(ValueError, match="key"):
        sign_waiver(
            _waiver(),
            signer="s",
            signed_at="t",
            key_id="k",
            key=b"",
        )


def test_canonical_form_is_key_order_independent() -> None:
    """Two waivers equal as dicts but built in different key order verify alike."""

    a = {"alpha": 1, "beta": {"x": 1, "y": 2}}
    b = {"beta": {"y": 2, "x": 1}, "alpha": 1}
    record_a = _sign(a)
    # Swap in the differently-ordered but equal body; signature must still hold.
    record_a["waiver"] = b
    assert verify_waiver_signature(record_a, key=_KEY) is True


def test_record_survives_json_round_trip() -> None:
    """Serializing and reloading the record does not break verification."""

    record = _sign()
    reloaded = json.loads(json.dumps(record))
    assert verify_waiver_signature(reloaded, key=_KEY) is True


def test_signing_is_deterministic() -> None:
    """Signing the same inputs twice yields the same digest."""

    assert _sign()["signature"]["value"] == _sign()["signature"]["value"]
