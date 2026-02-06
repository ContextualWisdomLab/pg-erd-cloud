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
    db_pooler_kind: Literal["pgbouncer", "pgcat", "unknown", "none"] | None = (
        None
    )

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
        if not path.is_file():
            raise ValueError(
                f"APP_SECRET_FILE does not exist or is not a file: {path}"
            )

        # Important: secret files commonly include a trailing newline.
        secret = path.read_text(encoding="utf-8").rstrip("\r\n")
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

    # Observability (MVP)
    observability_request_logging_enabled: bool = True
    # Metrics exposure must be opt-in.
    observability_metrics_enabled: bool = False
    # Optional shared token for /metrics when OIDC isn't configured.
    observability_metrics_token: str | None = None

    # Optional OIDC (Casdoor). If set, JWTs are verified.
    oidc_issuer: str | None = None
    oidc_audience: str | None = None


settings = Settings()  # type: ignore[call-arg]
