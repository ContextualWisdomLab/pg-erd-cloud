from __future__ import annotations

import argparse
import base64
import binascii
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Sequence

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
    load_pem_private_key,
)

LICENSE_TOKEN_VERSION = "v1"


@dataclass(frozen=True)
class LicenseKeyPair:
    private_key: str
    public_key: str


def _b64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    try:
        return base64.b64decode(
            (value + padding).encode("ascii"),
            altchars=b"-_",
            validate=True,
        )
    except (binascii.Error, UnicodeEncodeError, ValueError) as exc:
        raise ValueError("key must be base64url encoded") from exc


def generate_license_key_pair() -> LicenseKeyPair:
    private_key = Ed25519PrivateKey.generate()
    raw_private_key = private_key.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    raw_public_key = private_key.public_key().public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )
    return LicenseKeyPair(
        private_key=_b64url_encode(raw_private_key),
        public_key=_b64url_encode(raw_public_key),
    )


def _load_private_key(value: str) -> Ed25519PrivateKey:
    key_text = value.strip().replace("\\n", "\n")
    if not key_text:
        raise ValueError("private key is required")

    if "-----BEGIN" in key_text:
        loaded_key = load_pem_private_key(key_text.encode("utf-8"), password=None)
        if not isinstance(loaded_key, Ed25519PrivateKey):
            raise ValueError("private key must be an Ed25519 private key")
        return loaded_key

    try:
        return Ed25519PrivateKey.from_private_bytes(_b64url_decode(key_text))
    except ValueError as exc:
        raise ValueError("private key must be an Ed25519 private key") from exc


def _clean_claim(value: str, claim: str) -> str:
    if not value.strip() or value != value.strip():
        raise ValueError(f"{claim} must be a non-empty string without edge whitespace")
    return value


def _validate_positive_epoch(value: int, claim: str) -> int:
    if value <= 0:
        raise ValueError(f"{claim} must be a positive Unix epoch seconds value")
    return value


def issue_license_token(
    *,
    private_key: str,
    subject: str,
    plan: str,
    expires_at: int,
    token_id: str | None = None,
    not_before: int | None = None,
    seats: int | None = None,
) -> str:
    payload: dict[str, object] = {
        "sub": _clean_claim(subject, "sub"),
        "plan": _clean_claim(plan, "plan"),
        "exp": _validate_positive_epoch(expires_at, "exp"),
    }
    if token_id is not None:
        payload["jti"] = _clean_claim(token_id, "jti")
    if not_before is not None:
        payload["nbf"] = _validate_positive_epoch(not_before, "nbf")
    if seats is not None:
        if seats <= 0:
            raise ValueError("seats must be a positive integer")
        payload["seats"] = seats

    encoded_payload = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    )
    signing_input = f"{LICENSE_TOKEN_VERSION}.{encoded_payload}".encode("ascii")
    signature = _load_private_key(private_key).sign(signing_input)
    return f"{LICENSE_TOKEN_VERSION}.{encoded_payload}.{_b64url_encode(signature)}"


def _parse_epoch_or_iso(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        pass

    try:
        if len(value) == 10:
            parsed_date = date.fromisoformat(value)
            parsed_datetime = datetime.combine(
                parsed_date,
                time.min,
                tzinfo=timezone.utc,
            )
        else:
            parsed_datetime = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed_datetime.tzinfo is None:
                parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)
        return int(parsed_datetime.timestamp())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "expected Unix epoch seconds, YYYY-MM-DD, or ISO-8601 datetime"
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate and issue pg-erd-cloud offline license tokens."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    keypair_parser = subparsers.add_parser(
        "generate-keypair",
        help="Generate an Ed25519 key pair for offline license issuance.",
    )
    keypair_parser.add_argument(
        "--format",
        choices=("env", "json"),
        default="env",
        help="Output format. The private key must remain outside runtime deployments.",
    )

    issue_parser = subparsers.add_parser(
        "issue",
        help="Issue a signed offline license token for X-LICENSE-KEY.",
    )
    issue_parser.add_argument("--private-key", required=True)
    issue_parser.add_argument("--sub", required=True, dest="subject")
    issue_parser.add_argument("--plan", required=True)
    issue_parser.add_argument("--exp", required=True, type=_parse_epoch_or_iso)
    issue_parser.add_argument("--jti", dest="token_id")
    issue_parser.add_argument("--nbf", type=_parse_epoch_or_iso, dest="not_before")
    issue_parser.add_argument("--seats", type=int)
    return parser


def _coalesce_private_key_arg(argv: Sequence[str] | None) -> list[str]:
    args = list(sys.argv[1:] if argv is None else argv)
    normalized: list[str] = []
    index = 0
    while index < len(args):
        # Base64url Ed25519 private keys can start with "-", which argparse
        # otherwise treats as the next option instead of the option value.
        if (
            args[index] == "--private-key"
            and index + 1 < len(args)
            and args[index + 1].startswith("-")
        ):
            normalized.append(f"--private-key={args[index + 1]}")
            index += 2
            continue
        normalized.append(args[index])
        index += 1
    return normalized


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(_coalesce_private_key_arg(argv))

    if args.command == "generate-keypair":
        key_pair = generate_license_key_pair()
        if args.format == "json":
            print(json.dumps(key_pair.__dict__, sort_keys=True))
        else:
            print(f"LICENSE_PRIVATE_KEY={key_pair.private_key}")
            print(f"LICENSE_PUBLIC_KEY={key_pair.public_key}")
        return 0

    if args.command == "issue":
        print(
            issue_license_token(
                private_key=args.private_key,
                subject=args.subject,
                plan=args.plan,
                expires_at=args.exp,
                token_id=args.token_id,
                not_before=args.not_before,
                seats=args.seats,
            )
        )
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
