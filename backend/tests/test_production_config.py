from __future__ import annotations

from app.settings import Settings, validate_production_settings


def _settings(**overrides: object) -> Settings:
    data: dict[str, object] = {
        "database_url": "postgresql+asyncpg://user:pass@db.example.com/app",
        "app_secret": "x" * 48,
        "app_env": "production",
        "oidc_issuer": "https://idp.example.com",
        "oidc_audience": "pg-erd-cloud",
        "cors_origins": "https://erd.example.com",
        "db_introspection_allowed_hosts": "db.example.com",
    }
    data.update(overrides)
    return Settings(**data)  # type: ignore[arg-type]


def test_validate_production_settings_accepts_hardened_config() -> None:
    assert validate_production_settings(_settings()) == []


def test_validate_production_settings_is_inactive_for_development() -> None:
    config = _settings(
        app_env="development",
        oidc_issuer=None,
        oidc_audience=None,
        app_secret="short",
        cors_origins="http://localhost:5173",
        db_introspection_allowed_hosts="",
    )

    assert validate_production_settings(config) == []


def test_validate_production_settings_reports_missing_release_gates() -> None:
    errors = validate_production_settings(
        _settings(
            oidc_issuer=None,
            oidc_audience=None,
            app_secret="short",
            cors_origins="http://localhost:5173",
            db_introspection_allowed_hosts="",
            share_link_default_ttl_hours=0,
        )
    )

    assert "OIDC_ISSUER is required when APP_ENV=production" in errors
    assert "OIDC_AUDIENCE is required when APP_ENV=production" in errors
    assert "APP_SECRET must be at least 32 characters in production" in errors
    assert "DB_INTROSPECTION_ALLOWED_HOSTS must allow explicit target DB hosts" in errors
    assert "CORS_ORIGINS must include at least one public HTTPS origin" in errors
    assert "SHARE_LINK_DEFAULT_TTL_HOURS must be greater than 0" in errors


def test_validate_production_settings_requires_llm_provider_when_shared_drafts_enabled() -> None:
    errors = validate_production_settings(_settings(share_link_llm_draft_enabled=True))

    assert (
        "LLM_API_BASE_URL, LLM_API_KEY, and LLM_MODEL are required when "
        "SHARE_LINK_LLM_DRAFT_ENABLED=true"
    ) in errors
