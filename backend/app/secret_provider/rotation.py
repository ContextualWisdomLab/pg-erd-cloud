"""Pure `APP_SECRET` dual-read / single-write rotation core.

`docs/doctoring/credential-provider-contract.md` describes the rotation
design: the crypto layer takes an ordered key set ``[active, *previous]``,
decryption tries every key (**dual-read**), encryption always uses the
active key (**single-write**), and a bounded resumable job re-encrypts
stored rows so every ciphertext ends up under the active key.

This module is the *pure* core of that job — no database, no `Settings`, no
I/O. It offers:

* :func:`dual_read_decrypt` — decrypt one AES-256-GCM blob by trying each
  candidate ``APP_SECRET`` in order (HKDF-derived key first, then the legacy
  raw-SHA-256 key, matching :mod:`app.security`);
* :func:`plan_key_rotation` — walk a batch of stored ciphertexts, decrypt
  each with whichever key in the set works, and re-encrypt under the active
  key. A row already under the active key is left alone; a row no key in the
  set can decrypt is surfaced as ``needs_key_recovery`` (design step 5),
  never silently dropped and never re-encrypted from a guess.

The planner never returns plaintext: its result is ciphertext/nonce bytes,
counts, and structural reason codes only.

References (APA 7th):

Barker, E. (2020). *Recommendation for key management: Part 1 — General*
(NIST Special Publication 800-57 Part 1 Revision 5). National Institute of
Standards and Technology. https://doi.org/10.6028/NIST.SP.800-57pt1r5
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.secret_provider.contract import SecretResolutionError

#: Contract version for the :func:`plan_key_rotation` result shape.
ROTATION_PLAN_VERSION = "1"

#: AES-GCM nonce length in bytes (must match :mod:`app.security`).
NONCE_LENGTH = 12

# ponytail: these three HKDF parameters MUST stay in sync with
# app/security._derive_key. test_app_secret_rotation round-trips a real
# app.security.encrypt_text blob through this module, so a drift fails loudly.
_HKDF_SALT = b"pg-erd-cloud-v1"
_HKDF_INFO = b"aes-gcm-encryption"
_KEY_LENGTH = 32


def _hkdf_key(app_secret: str) -> bytes:
    """Derive the 32-byte AES key from ``app_secret`` via HKDF-SHA256."""
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=_KEY_LENGTH,
        salt=_HKDF_SALT,
        info=_HKDF_INFO,
    )
    return hkdf.derive(app_secret.encode("utf-8"))


def _legacy_key(app_secret: str) -> bytes:
    """Derive the legacy raw-SHA-256 AES key (older ciphertexts)."""
    return hashlib.sha256(app_secret.encode("utf-8")).digest()


def _try_one_secret(app_secret: str, ciphertext: bytes, nonce: bytes) -> bytes | None:
    """Return the plaintext if ``app_secret`` decrypts the blob, else ``None``."""
    for key in (_hkdf_key(app_secret), _legacy_key(app_secret)):
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, None)
        except InvalidTag:
            continue
    return None


def dual_read_decrypt(
    key_set: Sequence[str], ciphertext: bytes, nonce: bytes
) -> bytes:
    """Decrypt one blob by trying every ``APP_SECRET`` in ``key_set`` in order.

    Args:
        key_set: Ordered candidate secrets, active first, then previous keys.
        ciphertext: The AES-256-GCM ciphertext (with the GCM tag appended, as
            :func:`app.security.encrypt_text` produces).
        nonce: The 12-byte nonce stored alongside the ciphertext.

    Returns:
        The decrypted UTF-8 plaintext bytes.

    Raises:
        SecretResolutionError: If ``key_set`` is empty or no key decrypts the
            blob. The message never contains a key or any plaintext.
    """
    if not key_set:
        raise SecretResolutionError("empty key set: no APP_SECRET to try")
    for app_secret in key_set:
        plaintext = _try_one_secret(app_secret, ciphertext, nonce)
        if plaintext is not None:
            return plaintext
    raise SecretResolutionError("no key in the set decrypts this ciphertext")


def _encrypt(app_secret: str, plaintext: bytes, nonce: bytes) -> bytes:
    """Encrypt ``plaintext`` under the HKDF key for ``app_secret``."""
    return AESGCM(_hkdf_key(app_secret)).encrypt(nonce, plaintext, None)


def plan_key_rotation(
    active_key: str,
    previous_keys: Sequence[str],
    records: Iterable[Mapping[str, Any]],
    *,
    nonce_source: Callable[[int], bytes] = os.urandom,
) -> dict[str, Any]:
    """Plan the re-encryption of a batch of stored ciphertexts under ``active_key``.

    Args:
        active_key: The current ``APP_SECRET`` -- every output ciphertext is
            encrypted with this (**single-write**).
        previous_keys: Older secrets still accepted for decryption, newest
            first (**dual-read**).
        records: Iterable of ``{"ciphertext": bytes, "nonce": bytes}`` mappings.
            An optional ``"id"`` is passed through to the result so a caller
            can map an outcome back to its row.
        nonce_source: Callable returning ``n`` random bytes; overridable in
            tests for deterministic output. Defaults to :func:`os.urandom`.

    Returns:
        A dict with:

        ``version``
            :data:`ROTATION_PLAN_VERSION`.
        ``total``
            Number of records seen.
        ``re_encrypted``
            ``[{"id"?, "ciphertext": bytes, "nonce": bytes}]`` for rows that
            decrypted with a *previous* key and were re-encrypted under
            ``active_key``.
        ``already_active``
            Count of rows that already decrypt with ``active_key`` (nothing to
            do).
        ``needs_key_recovery``
            ``[{"index": int, "id"?, "reason": str}]`` for rows that no key in
            the set decrypts (``"no_key_decrypts"``) or that are malformed
            (``"malformed_record"``). These are never re-encrypted.

        The result contains no plaintext and no key material.
    """
    key_set = [active_key, *previous_keys]
    re_encrypted: list[dict[str, Any]] = []
    needs_recovery: list[dict[str, Any]] = []
    already_active = 0
    total = 0

    for index, record in enumerate(records):
        total += 1
        ciphertext = record.get("ciphertext")
        nonce = record.get("nonce")
        entry_id = record.get("id")
        if not isinstance(ciphertext, (bytes, bytearray)) or not isinstance(
            nonce, (bytes, bytearray)
        ):
            miss: dict[str, Any] = {"index": index, "reason": "malformed_record"}
            if entry_id is not None:
                miss["id"] = entry_id
            needs_recovery.append(miss)
            continue

        ciphertext = bytes(ciphertext)
        nonce = bytes(nonce)

        if _try_one_secret(active_key, ciphertext, nonce) is not None:
            already_active += 1
            continue

        plaintext: bytes | None = None
        for app_secret in previous_keys:
            plaintext = _try_one_secret(app_secret, ciphertext, nonce)
            if plaintext is not None:
                break

        if plaintext is None:
            miss = {"index": index, "reason": "no_key_decrypts"}
            if entry_id is not None:
                miss["id"] = entry_id
            needs_recovery.append(miss)
            continue

        new_nonce = nonce_source(NONCE_LENGTH)
        rotated: dict[str, Any] = {
            "ciphertext": _encrypt(active_key, plaintext, new_nonce),
            "nonce": new_nonce,
        }
        if entry_id is not None:
            rotated["id"] = entry_id
        re_encrypted.append(rotated)

    return {
        "version": ROTATION_PLAN_VERSION,
        "total": total,
        "re_encrypted": re_encrypted,
        "already_active": already_active,
        "needs_key_recovery": needs_recovery,
    }
