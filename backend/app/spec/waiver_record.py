"""Tamper-evident signing for normalization-assessment waiver records.

The assessment modules in this package (:mod:`app.spec.normalization_assessment`
and :mod:`app.spec.transitive_dependency_assessment`) accept caller-supplied
*waivers*: small records that say "this finding is a deliberate, reviewed
exception, not a defect". Today those waivers are trusted as-is. For an audit
trail an enterprise buyer can rely on, a waiver needs to be **tamper-evident**:
a reviewer signs it once, and anyone can later check that neither the waiver
body nor the "who signed it / when / with which key" metadata was altered
afterwards.

This module does exactly that and nothing more:

* :func:`sign_waiver` takes a waiver ``dict`` plus the signer identity, an
  ISO-8601 timestamp, a key id, and the secret key bytes. It returns a new
  record ``{"waiver": <deep copy>, "signature": {...}}`` whose ``signature``
  carries an HMAC-SHA256 over the canonical JSON of the waiver *with the
  signature metadata folded in*, so changing the signer or the timestamp
  invalidates the signature just as changing the waiver body would.
* :func:`verify_waiver_signature` recomputes that HMAC from ``record["waiver"]``
  and ``record["signature"]`` and compares it in constant time.

The secret key never leaves the caller: this module neither stores it, logs
it, nor puts it (or any plaintext derived from it) into the returned record.
It is a pure function pair with no database, network, or filesystem access.

References (APA 7th):

* National Institute of Standards and Technology. (2008). *The keyed-hash
  message authentication code (HMAC)* (FIPS PUB 198-1).
  https://doi.org/10.6028/NIST.FIPS.198-1
* Rundgren, A., Jordan, B., & Erdtman, S. (2020). *JSON Canonicalization
  Scheme (JCS)* (RFC 8785). RFC Editor.
  https://doi.org/10.17487/RFC8785
"""

from __future__ import annotations

import hashlib
import hmac
import json
from copy import deepcopy
from typing import Any

WAIVER_SIGNATURE_ALGO = "hmac-sha256"
"""Identifier stored in every signature; the only algorithm this module accepts."""

_META_FIELDS = ("signer", "signed_at", "key_id")


def _canonical(waiver: dict[str, Any]) -> bytes:
    """Return a deterministic byte string for ``waiver``.

    Keys are sorted at every level and separators are tight, so two dicts that
    are equal as Python objects produce identical bytes regardless of the order
    their keys were inserted. ``default=str`` lets values such as ``datetime``
    or ``Decimal`` serialize instead of raising; the same Python value always
    stringifies the same way, which is all a signature needs.
    """

    return json.dumps(
        waiver, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _require_non_empty_str(value: object, field: str) -> str:
    """Return ``value`` unchanged, or raise :class:`ValueError` naming ``field``."""

    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _expected_value(waiver: dict[str, Any], meta: dict[str, str], key: bytes) -> str:
    """Compute the HMAC-SHA256 hex digest over the waiver plus its signature meta."""

    return hmac.new(
        key, _canonical({**waiver, "_meta": meta}), hashlib.sha256
    ).hexdigest()


def sign_waiver(
    waiver: dict[str, Any],
    *,
    signer: str,
    signed_at: str,
    key_id: str,
    key: bytes,
) -> dict[str, Any]:
    """Return a signed, tamper-evident copy of ``waiver``.

    Args:
        waiver: The waiver body to sign. It is deep-copied into the result, so
            the caller's dict is never mutated and later edits to it do not
            affect the signed record.
        signer: Who approved the waiver (a person or system identity). Required,
            non-empty.
        signed_at: When it was approved, as an ISO-8601 string. Required,
            non-empty; this module records it verbatim and does not parse it.
        key_id: Which signing key was used, so a verifier can pick the right
            secret without trial and error. Required, non-empty.
        key: The secret key bytes for the HMAC. Required, non-empty. Never
            stored, logged, or echoed back in the result.

    Returns:
        ``{"waiver": <deep copy of waiver>, "signature": {"algo", "signer",
        "signed_at", "key_id", "value"}}`` where ``value`` is the HMAC-SHA256
        hex digest binding the waiver body to the three metadata fields.

    Raises:
        ValueError: If ``signer``, ``signed_at``, or ``key_id`` is not a
            non-empty string, or if ``key`` is empty / not ``bytes``.
    """

    meta = {
        "signer": _require_non_empty_str(signer, "signer"),
        "signed_at": _require_non_empty_str(signed_at, "signed_at"),
        "key_id": _require_non_empty_str(key_id, "key_id"),
    }
    if not isinstance(key, (bytes, bytearray)) or not key:
        raise ValueError("key must be non-empty bytes")

    return {
        "waiver": deepcopy(waiver),
        "signature": {
            "algo": WAIVER_SIGNATURE_ALGO,
            **meta,
            "value": _expected_value(waiver, meta, bytes(key)),
        },
    }


def verify_waiver_signature(record: dict[str, Any], *, key: bytes) -> bool:
    """Return ``True`` iff ``record``'s signature matches its waiver body.

    Recomputes the HMAC-SHA256 from ``record["waiver"]`` and the ``signer`` /
    ``signed_at`` / ``key_id`` inside ``record["signature"]``, then compares it
    to the stored ``value`` with :func:`hmac.compare_digest` (constant time).
    Any change to the waiver body or to a signature metadata field makes this
    return ``False``; a wrong ``key`` also returns ``False``.

    Args:
        record: A record produced by :func:`sign_waiver` (or one claiming to
            be). Must have a ``waiver`` dict and a ``signature`` dict whose
            ``algo`` is :data:`WAIVER_SIGNATURE_ALGO`.
        key: The secret key bytes to verify against.

    Raises:
        ValueError: If ``record`` is missing ``waiver`` or ``signature``, if
            either is not a dict, or if the signature's ``algo`` is not
            :data:`WAIVER_SIGNATURE_ALGO`.
    """

    if not isinstance(record, dict) or "signature" not in record:
        raise ValueError("record must contain a 'signature'")
    waiver = record.get("waiver")
    signature = record["signature"]
    if not isinstance(waiver, dict) or not isinstance(signature, dict):
        raise ValueError("record 'waiver' and 'signature' must both be objects")
    if signature.get("algo") != WAIVER_SIGNATURE_ALGO:
        raise ValueError(f"unsupported signature algo: {signature.get('algo')!r}")

    meta = {field: str(signature.get(field, "")) for field in _META_FIELDS}
    expected = _expected_value(waiver, meta, bytes(key))
    return hmac.compare_digest(expected, str(signature.get("value", "")))
