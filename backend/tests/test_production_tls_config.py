"""Regression tests for the fail-closed production TLS deployment contract."""

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_production_compose_exposes_only_tls_to_external_clients() -> None:
    """Require a dedicated HTTPS entry point, redirect, and certificate secrets."""

    compose = (REPOSITORY_ROOT / "compose.prod.yaml").read_text(encoding="utf-8")

    assert "--entryPoints.websecure.address=:8443" in compose
    assert "--entryPoints.web.http.redirections.entryPoint.to=websecure" in compose
    assert "--entryPoints.web.http.redirections.entryPoint.scheme=https" in compose
    assert "${TRAEFIK_HTTPS_PORT:-443}:8443" in compose
    assert "tls_certificate" in compose
    assert "tls_private_key" in compose
    assert "CORS_ORIGINS: ${PUBLIC_ORIGIN:?" in compose


def test_traefik_dynamic_config_terminates_tls_with_hsts() -> None:
    """Require TLS-only routers, mounted certificates, and strict transport policy."""

    dynamic = (REPOSITORY_ROOT / "deploy/traefik/dynamic.yaml").read_text(
        encoding="utf-8"
    )

    assert dynamic.count("- websecure") == 3
    assert dynamic.count("options: hardened") == 3
    assert "certFile: /run/secrets/tls_certificate" in dynamic
    assert "keyFile: /run/secrets/tls_private_key" in dynamic
    assert "minVersion: VersionTLS12" in dynamic
    assert "sniStrict: true" in dynamic
    assert "stsSeconds: 31536000" in dynamic
    assert "stsIncludeSubdomains: true" in dynamic
    assert "stsPreload: true" in dynamic
