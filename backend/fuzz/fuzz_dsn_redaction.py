#!/usr/bin/env python3
"""Atheris harness for ``app.dsn_redaction.redact_dsn_error_message``.

Untrusted-input surface: driver error messages are built from a user-supplied
DSN (which carries a password) and are then surfaced back to the user. The
redactor must (1) never raise on arbitrary input and (2) never let the
DSN-derived password survive verbatim in the redacted message -- otherwise a
crafted connection string turns an error banner into a secret-exfiltration
channel.

CodeGraph pointed here via:
    codegraph explore "DSN redaction parse sanitize identifier untrusted input"

Run locally (Python 3.10-3.12, where Atheris wheels exist):
    python backend/fuzz/fuzz_dsn_redaction.py -atheris_runs=200000
    python backend/fuzz/fuzz_dsn_redaction.py backend/fuzz/corpus/dsn_redaction
"""

from __future__ import annotations

import sys

import atheris

with atheris.instrument_imports():
    from app.dsn_redaction import redact_dsn_error_message

# Password alphabet with no DSN-structural characters, so the password we embed
# survives urlsplit verbatim and the leak check stays a true positive.
_SAFE_PW = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-.~"


def test_one_input(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    # Path A -- crash safety on fully arbitrary error message + DSN.
    error_message = fdp.ConsumeUnicodeNoSurrogates(256)
    dsn = fdp.ConsumeUnicodeNoSurrogates(256)
    redact_dsn_error_message(error_message, dsn)

    # Path B -- secret must not leak. Build a well-formed DSN with a known,
    # structurally-safe password and force it into the error text.
    pw_len = fdp.ConsumeIntInRange(1, 40)
    pw = "".join(
        _SAFE_PW[b % len(_SAFE_PW)] for b in fdp.ConsumeBytes(pw_len)
    )
    if not pw:
        return
    host = "db.example.com"
    structured_dsn = f"postgresql://user:{pw}@{host}:5432/app?sslmode=require"
    noise = fdp.ConsumeUnicodeNoSurrogates(120)
    structured_message = (
        f"connection failed: {noise} password={pw} authenticating to {structured_dsn}"
    )
    redacted = redact_dsn_error_message(structured_message, structured_dsn)
    if pw in redacted:
        raise AssertionError(
            f"password leaked through redaction: pw={pw!r} redacted={redacted!r}"
        )


def main() -> None:
    atheris.Setup(sys.argv, test_one_input)
    atheris.Fuzz()


if __name__ == "__main__":
    main()
