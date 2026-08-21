from __future__ import annotations

import os
import stat
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_SECRETS_DIR = Path("/run/secrets")


def _read_secret_file(
    path: Path,
    *,
    allowed_base: Path = _SECRETS_DIR,
) -> str:
    """Read one direct-child secret without a path-check/read race."""

    if not path.is_absolute() or path.parent != allowed_base:
        raise ValueError(
            f"APP_SECRET_FILE must be a direct child of {allowed_base}"
        )

    required_flags = ("O_CLOEXEC", "O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
    if any(not hasattr(os, flag) for flag in required_flags):
        raise ValueError("APP_SECRET_FILE secure loading is unsupported")

    directory_fd = -1
    secret_fd = -1
    try:
        directory_fd = os.open(
            allowed_base,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
        )
        secret_fd = os.open(
            path.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
            dir_fd=directory_fd,
        )
        if not stat.S_ISREG(os.fstat(secret_fd).st_mode):
            raise ValueError("APP_SECRET_FILE must be a regular file")

        with os.fdopen(secret_fd, "r", encoding="utf-8", closefd=True) as handle:
            secret_fd = -1
            secret = handle.read().rstrip("\r\n")
    except (OSError, UnicodeError):
        raise ValueError("APP_SECRET_FILE could not be opened securely") from None
    finally:
        if secret_fd >= 0:
            os.close(secret_fd)
        if directory_fd >= 0:
            os.close(directory_fd)

    if secret == "":
        raise ValueError("APP_SECRET_FILE is empty")
    return secret


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Optional: a read-only endpoint/replica DSN.
    database_read_only_url: str | None = None

    # Optional: pooler kind hint. If set, probing is skipped.
    db_pooler_kind: Literal["pgbouncer", "pgcat", "unknown", "none"] | None = None

    # Read routing mode. In auto mode, read-only DSN is used only when a pooler
    # is detected (or hinted via db_pooler_kind).
    db_read_routing: Literal["off", "auto", "on"] = "auto"

    # Best-effort pooler probe timeout. Keep it small to avoid blocking request
    # paths.
    db_pooler_probe_timeout_seconds: float = Field(0.7, ge=0.0)
    # Required encryption key material.
    #
    # Supports the Docker/Podman *_FILE pattern (e.g. /run/secrets/app_secret)
    # to avoid putting secrets directly into environment variables.
    app_secret: str
    app_secret_file: str | None = Field(
        default=None, validation_alias="APP_SECRET_FILE"
    )

    @model_validator(mode="before")
    @classmethod
    def _load_app_secret_from_file(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        secret_file = data.get("APP_SECRET_FILE") or data.get("app_secret_file")
        if not secret_file:
            return data

        secret = _read_secret_file(Path(str(secret_file)))

        # If APP_SECRET_FILE is provided, prefer it deterministically.
        new_data = dict(data)
        new_data["app_secret"] = secret
        return new_data

    cors_origins: str = "http://localhost:5173"

    # Rate limiting (FastAPI app layer, applied to /api/*)
    api_rate_limit_enabled: bool = True
    api_rate_limit_requests: int = Field(120, ge=1)
    api_rate_limit_window_seconds: float = Field(60.0, gt=0.0)
    api_rate_limit_trust_x_forwarded_for: bool = False
    api_rate_limit_max_keys: int = Field(10_000, ge=1)
    share_link_rate_limit_enabled: bool = True
    share_link_rate_limit_requests: int = Field(30, ge=1)
    share_link_rate_limit_window_seconds: float = Field(60.0, gt=0.0)
    share_link_rate_limit_max_keys: int = Field(10_000, ge=1)

    # Observability (MVP)
    observability_request_logging_enabled: bool = True
    # Metrics exposure must be opt-in.
    observability_metrics_enabled: bool = False
    # Optional shared token for /metrics when OIDC isn't configured.
    observability_metrics_token: str | None = None

    # Optional Valkey-backed queue signal path. The relational job_queue table
    # remains the source of truth; Valkey reduces polling/lock pressure by
    # carrying due job IDs for workers to claim.
    job_queue_backend: Literal["database", "valkey"] = "database"
    valkey_url: str | None = None
    valkey_sentinel_hosts: str | None = None
    valkey_sentinel_master: str | None = None
    valkey_queue_key: str = "pg-erd-cloud:job-queue"
    valkey_lock_ttl_seconds: int = Field(300, ge=1)

    # Optional OIDC (Casdoor). If set, JWTs are verified.
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    # Optional single-tenant Keyverse profile. When set, verified tokens must
    # carry the exact opaque ``org`` claim; the deployment database is the
    # tenant boundary for every project lookup.
    oidc_organization: str | None = None

    @field_validator("oidc_organization")
    @classmethod
    def _validate_oidc_organization(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip() or value != value.strip():
            raise ValueError(
                "OIDC_ORGANIZATION must be non-empty and have no surrounding whitespace"
            )
        return value

    # Optional allowlist for reverse-engineering database targets.
    # Comma-separated exact hostnames/IPs or wildcard domains like *.example.com.
    db_introspection_allowed_hosts: str = ""

    # Optional OpenAI-compatible chat-completions provider for live reversing
    # spec drafts. Leave unset to keep all reversing spec generation local.
    llm_api_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(30.0, gt=0.0, le=120.0)

    # Clearfolio reference-document viewer connector (buyer gateway).
    clearfolio_gateway_url: str | None = None
    clearfolio_tenant_claims_hmac_secret: str | None = None
    clearfolio_tenant_id: str = "pg-erd-cloud"
    clearfolio_permissions: str = (
        "job:create,job:read,job:retry,viewer:read,artifact-link:create,analytics:read"
    )
    clearfolio_timeout_seconds: float = Field(30.0, gt=0.0, le=120.0)

    # Allowed JWT signing algorithms for OIDC verification.
    # Comma-separated string (env: OIDC_ALGORITHMS). Default is RS256.
    # NOTE: Do not trust the token header's alg; only accept algorithms from
    # this allowlist.
    oidc_algorithms: str = "RS256"


settings = Settings()  # type: ignore[call-arg]
