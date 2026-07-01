from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

        path = Path(str(secret_file))
        try:
            resolved = path.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ValueError(f"APP_SECRET_FILE does not exist: {path}") from exc

        # Security hardening: avoid symlink tricks and restrict secret files to
        # the expected secrets mount.
        #
        # Docker/Podman secrets are typically mounted under /run/secrets.
        allowed_base = Path("/run/secrets").resolve()
        if path.is_symlink():
            raise ValueError("APP_SECRET_FILE must not be a symlink")
        if not resolved.is_relative_to(allowed_base):
            raise ValueError(
                f"APP_SECRET_FILE must be under {allowed_base}: {resolved}"
            )
        if not resolved.is_file():
            raise ValueError(
                f"APP_SECRET_FILE does not exist or is not a file: {resolved}"
            )

        # Important: secret files commonly include a trailing newline.
        secret = resolved.read_text(encoding="utf-8").rstrip("\r\n")
        if secret == "":
            raise ValueError("APP_SECRET_FILE is empty")

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

    # Optional allowlist for reverse-engineering database targets.
    # Comma-separated exact hostnames/IPs or wildcard domains like *.example.com.
    db_introspection_allowed_hosts: str = ""

    # Optional OpenAI-compatible chat-completions provider for live reversing
    # spec drafts. Leave unset to keep all reversing spec generation local.
    llm_api_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(30.0, gt=0.0, le=120.0)

    # Allowed JWT signing algorithms for OIDC verification.
    # Comma-separated string (env: OIDC_ALGORITHMS). Default is RS256.
    # NOTE: Do not trust the token header's alg; only accept algorithms from
    # this allowlist.
    oidc_algorithms: str = "RS256"


settings = Settings()  # type: ignore[call-arg]
