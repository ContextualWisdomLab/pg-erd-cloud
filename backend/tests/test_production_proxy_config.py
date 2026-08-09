from __future__ import annotations

from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _service_block(compose: str, service: str, next_service: str) -> str:
    return compose.split(f"  {service}:\n", 1)[1].split(
        f"\n  {next_service}:\n", 1
    )[0]


def _list_values(block: str, section: str, next_section: str) -> set[str]:
    body = block.split(f"    {section}:\n", 1)[1].split(
        f"\n    {next_section}:", 1
    )[0]
    return {
        line.strip().removeprefix("- ").strip('"')
        for line in body.splitlines()
        if line.strip().startswith("- ")
    }


def _mapping_values(block: str, section: str, next_section: str) -> dict[str, str]:
    body = block.split(f"    {section}:\n", 1)[1].split(
        f"\n    {next_section}:", 1
    )[0]
    entries: dict[str, str] = {}
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        entries[key] = value.strip().strip('"')
    return entries


def test_production_proxy_preserves_real_client_ip_for_rate_limits() -> None:
    compose = (REPOSITORY_ROOT / "compose.prod.yaml").read_text(encoding="utf-8")
    env_example = (REPOSITORY_ROOT / ".env.example").read_text(encoding="utf-8")
    traefik = _service_block(compose, "traefik", "postgres")
    backend = _service_block(compose, "backend", "frontend")
    commands = _list_values(traefik, "command", "depends_on")
    ports = _list_values(traefik, "ports", "volumes")
    backend_environment = _mapping_values(backend, "environment", "secrets")

    assert "image: traefik:v3.5.4@sha256:" in traefik
    assert "--entryPoints.web.forwardedHeaders.insecure=false" in commands
    assert (
        "--entryPoints.web.forwardedHeaders.trustedIPs="
        "${TRAEFIK_TRUSTED_PROXY_CIDRS:?set TRAEFIK_TRUSTED_PROXY_CIDRS}"
    ) in commands
    # Traefik 3.5 does not expose notAppendXForwardedFor. Its default behavior
    # already appends the direct peer to X-Forwarded-For, and passing the newer
    # option would prevent this pinned image from starting.
    assert not any("notAppendXForwardedFor" in command for command in commands)
    assert "127.0.0.1:${TRAEFIK_HTTP_PORT:-8080}:8080" in ports
    assert backend_environment["API_RATE_LIMIT_TRUST_X_FORWARDED_FOR"] == "true"
    assert backend_environment["API_RATE_LIMIT_TRUSTED_PROXY_HOPS"] == "2"
    # Copying the example must fail closed until the operator replaces this
    # empty value with the actual TLS-terminator source CIDR(s).
    assert "TRAEFIK_TRUSTED_PROXY_CIDRS=\n" in env_example
