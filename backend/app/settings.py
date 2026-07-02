from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    app_env: Literal["development", "production"] = "development"
    production_config_checks_enabled: bool = True
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
    share_link_default_ttl_hours: int = Field(168, ge=0)

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

    # Optional commercial/on-prem licensing gate.
    #
    # Set LICENSE_MODE=required to reject API usage without a valid
    # X-LICENSE-KEY header when running paid/on-prem distribution.
    license_mode: Literal["off", "required"] = "off"
    license_key: str | None = None
    # Optional Ed25519 public key for offline signed on-prem license tokens.
    license_public_key: str | None = None
    # Comma-separated signed license token IDs (jti) or customer subjects (sub)
    # that must be rejected before their natural expiry.
    license_revoked_token_ids: str = ""
    license_revoked_subjects: str = ""

    # Optional billing/license usage limits. A value of 0 means unlimited.
    billing_max_projects_per_user: int = Field(0, ge=0)
    billing_max_connections_per_project: int = Field(0, ge=0)
    billing_max_snapshots_per_project: int = Field(0, ge=0)
    billing_max_share_links_per_project: int = Field(0, ge=0)
    billing_portal_url: str | None = None
    billing_support_url: str | None = None
    account_reactivation_url: str | None = None
    # Comma-separated OIDC subjects that must be denied before DB access.
    account_deactivated_subjects: str = ""

    # Optional OpenAI-compatible chat-completions provider for live reversing
    # spec drafts. Leave unset to keep all reversing spec generation local.
    llm_api_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None
    llm_timeout_seconds: float = Field(30.0, gt=0.0, le=120.0)
    llm_max_prompt_chars: int = Field(120_000, ge=1_000)
    llm_max_output_tokens: int = Field(1_200, ge=1, le=8_192)
    share_link_llm_draft_enabled: bool = False

    # Allowed JWT signing algorithms for OIDC verification.
    # Comma-separated string (env: OIDC_ALGORITHMS). Default is RS256.
    # NOTE: Do not trust the token header's alg; only accept algorithms from
    # this allowlist.
    oidc_algorithms: str = "RS256"


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _is_public_https_origin(origin: str) -> bool:
    parsed = urlparse(origin)
    host = parsed.hostname or ""
    return (
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and host not in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
    )


def validate_production_settings(config: Settings) -> list[str]:
    """Return startup-blocking configuration errors for production deployments."""
    if config.app_env != "production" or not config.production_config_checks_enabled:
        return []

    errors: list[str] = []
    if not config.oidc_issuer:
        errors.append("OIDC_ISSUER is required when APP_ENV=production")
    if not config.oidc_audience:
        errors.append("OIDC_AUDIENCE is required when APP_ENV=production")
    if len(config.app_secret) < 32:
        errors.append("APP_SECRET must be at least 32 characters in production")
    if not _split_csv(config.db_introspection_allowed_hosts):
        errors.append(
            "DB_INTROSPECTION_ALLOWED_HOSTS must allow explicit target DB hosts"
        )
    if not any(_is_public_https_origin(origin) for origin in _split_csv(config.cors_origins)):
        errors.append("CORS_ORIGINS must include at least one public HTTPS origin")
    if config.share_link_default_ttl_hours == 0:
        errors.append("SHARE_LINK_DEFAULT_TTL_HOURS must be greater than 0")
    if config.share_link_llm_draft_enabled and not (
        config.llm_api_base_url and config.llm_api_key and config.llm_model
    ):
        errors.append(
            "LLM_API_BASE_URL, LLM_API_KEY, and LLM_MODEL are required when "
            "SHARE_LINK_LLM_DRAFT_ENABLED=true"
        )
    if config.license_mode == "required":
        if not (config.license_key or config.license_public_key):
            errors.append(
                "LICENSE_KEY or LICENSE_PUBLIC_KEY is required when LICENSE_MODE=required"
            )
        if config.license_key and len(config.license_key) < 24:
            errors.append("LICENSE_KEY must be at least 24 characters")
    if _split_csv(config.account_deactivated_subjects) and not (
        config.account_reactivation_url or config.billing_support_url
    ):
        errors.append(
            "ACCOUNT_DEACTIVATED_SUBJECTS requires ACCOUNT_REACTIVATION_URL or "
            "BILLING_SUPPORT_URL in production"
        )
    return errors


settings = Settings()  # type: ignore[call-arg]
