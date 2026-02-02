from __future__ import annotations

from typing import Literal

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
    db_pooler_probe_timeout_seconds: float = 0.7
    app_secret: str

    cors_origins: str = "http://localhost:5173"

    # Optional OIDC (Casdoor). If set, JWTs are verified.
    oidc_issuer: str | None = None
    oidc_audience: str | None = None


settings = Settings()  # type: ignore[call-arg]
