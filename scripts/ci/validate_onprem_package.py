#!/usr/bin/env python3
"""Static smoke checks for the on-premises commercial package."""

from __future__ import annotations

import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parents[2]

REQUIRED_FILES = (
    "compose.prod.yaml",
    ".env.example",
    "backend/Dockerfile",
    "frontend/Dockerfile.prod",
    "deploy/traefik/dynamic.yaml",
    "docs/legal/license-billing.md",
    "docs/operations/backup-restore.md",
    "docs/operations/migration-rollback.md",
    "docs/operations/on-premises-package.md",
)

COMPOSE_REQUIRED_SNIPPETS = (
    "traefik:v3.5.4@sha256:",
    "postgres:16-alpine@sha256:",
    "APP_ENV: production",
    "APP_SECRET_FILE: /run/secrets/app_secret",
    "secrets:",
    "file: ./secrets/app_secret",
    "alembic upgrade head",
    "127.0.0.1:${TRAEFIK_HTTP_PORT:-8080}:8080",
    "127.0.0.1:${POSTGRES_PORT:-54321}:5432",
)

ENV_REQUIRED_SNIPPETS = (
    "LICENSE_MODE=off",
    "LICENSE_PUBLIC_KEY=",
    "LICENSE_REVOKED_TOKEN_IDS=",
    "LICENSE_REVOKED_SUBJECTS=",
    "BILLING_WEBHOOK_SECRET=",
    "BILLING_WEBHOOK_SIGNATURE_SECRET=",
    "BILLING_SUPPORT_URL=",
    "ACCOUNT_REACTIVATION_URL=",
    "ACCOUNT_DEACTIVATED_SUBJECTS=",
    "SUPPORT_OPERATOR_SUBJECTS=",
    "DB_INTROSPECTION_ALLOWED_HOSTS=",
)

LICENSE_DOC_REQUIRED_SNIPPETS = (
    "python -m app.license_tokens generate-keypair",
    "python -m app.license_tokens issue",
    "LICENSE_REVOKED_TOKEN_IDS",
    "LICENSE_REVOKED_SUBJECTS",
    "POST /api/billing/events",
    "BILLING_WEBHOOK_SIGNATURE_SECRET",
    "GET /api/billing/support/account",
    "support_operator: true",
)

BACKUP_DOC_REQUIRED_SNIPPETS = (
    "APP_SECRET",
    "Restore Drill",
    "/healthz",
    "alembic current",
    "docker run --rm --name pg-erd-restore-drill",
)

ROLLBACK_DOC_REQUIRED_SNIPPETS = (
    "alembic current",
    "alembic downgrade",
    "compose.prod.yaml",
    "/healthz",
)

ONPREM_DOC_REQUIRED_SNIPPETS = (
    "Offline license",
    "Secret material",
    "Revocation update",
    "Restore drill",
    "Rollback drill",
    "Support bundle",
    "Air-gapped",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read(relative_path: str) -> str:
    path = ROOT / relative_path
    require(path.is_file(), f"missing required file: {relative_path}")
    return path.read_text(encoding="utf-8")


def require_snippets(text: str, snippets: tuple[str, ...], source: str) -> None:
    for snippet in snippets:
        require(snippet in text, f"{source} must contain {snippet!r}")


def main() -> int:
    for relative_path in REQUIRED_FILES:
        require((ROOT / relative_path).is_file(), f"missing required file: {relative_path}")

    require_snippets(read("compose.prod.yaml"), COMPOSE_REQUIRED_SNIPPETS, "compose.prod.yaml")
    require_snippets(read(".env.example"), ENV_REQUIRED_SNIPPETS, ".env.example")
    require_snippets(
        read("docs/legal/license-billing.md"),
        LICENSE_DOC_REQUIRED_SNIPPETS,
        "docs/legal/license-billing.md",
    )
    require_snippets(
        read("docs/operations/backup-restore.md"),
        BACKUP_DOC_REQUIRED_SNIPPETS,
        "docs/operations/backup-restore.md",
    )
    require_snippets(
        read("docs/operations/migration-rollback.md"),
        ROLLBACK_DOC_REQUIRED_SNIPPETS,
        "docs/operations/migration-rollback.md",
    )
    require_snippets(
        read("docs/operations/on-premises-package.md"),
        ONPREM_DOC_REQUIRED_SNIPPETS,
        "docs/operations/on-premises-package.md",
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"validate_onprem_package.py: {exc}", file=sys.stderr)
        raise SystemExit(1)
