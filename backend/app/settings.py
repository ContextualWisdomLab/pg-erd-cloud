from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    # Optional: a read-only endpoint/replica DSN.
    database_read_only_url: str | None = None

    # Optional: pooler kind hint. If set, probing is skipped.
    db_pooler_kind: Literal["pgbouncer", "pgcat", "unknown", "none"] | None = (
        None
    )

    # Read routing mode. In auto mode, read-only DSN is used only when a pooler
    # is detected (or hinted via db_pooler_kind).
    db_read_routing: Literal["off", "auto", "on"] = "auto"

    # Best-effort pooler probe timeout. Keep it small to avoid blocking request
    # paths.
    db_pooler_probe_timeout_seconds: float = Field(0.7, ge=0.0)
    app_secret: str

    cors_origins: str = "http://localhost:5173"

    # Rate limiting (FastAPI app layer, applied to /api/*)
    api_rate_limit_enabled: bool = True
    api_rate_limit_requests: int = Field(120, ge=1)
    api_rate_limit_window_seconds: float = Field(60.0, gt=0.0)
    api_rate_limit_trust_x_forwarded_for: bool = False
    api_rate_limit_max_keys: int = Field(10_000, ge=1)

    # Observability (MVP)
    observability_request_logging_enabled: bool = True
    # Metrics exposure must be opt-in.
    observability_metrics_enabled: bool = False
    # Optional shared token for /metrics when OIDC isn't configured.
    observability_metrics_token: str | None = None

    # Optional OIDC (Casdoor). If set, JWTs are verified.
    oidc_issuer: str | None = None
    oidc_audience: str | None = None

    # Allowed JWT signing algorithms for OIDC verification.
    # Comma-separated string (env: OIDC_ALGORITHMS). Default is RS256.
    # NOTE: Do not trust the token header's alg; only accept algorithms from
    # this allowlist.
    oidc_algorithms: str = "RS256"


settings = Settings()  # type: ignore[call-arg]
