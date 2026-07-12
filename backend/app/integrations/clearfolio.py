"""Buyer-gateway connector for Clearfolio (reference-document viewer platform).

pg-erd-cloud acts as the *buyer gateway*: it authenticates its own user
(OIDC / API key), maps that principal to Clearfolio tenant claims, signs those
claims with the shared HMAC secret, and proxies to the Clearfolio connector API
(submit → status → viewer bootstrap → artifact link).

Signing contract (from Clearfolio's buyer-deployment playbook — must match its
verifier exactly):

    payload    = "\\n".join([tenantId, subjectId, canonicalPermissions, issuedAt])
    signature  = base64url( HMAC_SHA256(secret, payload) )   # no padding

Sent as the header set ``X-Clearfolio-{Tenant-Id,Subject-Id,Permissions,
Claims-Issued-At,Claims-Signature}``. The gateway host is SSRF-validated (it is
admin-configured, not per-request user input, but validated for defense in
depth).
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.pg_introspect.dsn_guard import _validated_ip_hosts
from app.settings import settings

def _sanitize(value: str) -> str:
    """Match Clearfolio's claim sanitizer: drop NUL, strip surrounding space."""
    return value.replace("\x00", "").strip()


def canonicalize_permissions(raw: str) -> str:
    """Reduce a permission string to Clearfolio's canonical form.

    Clearfolio verifies the signature against ``canonicalPermissions`` — the
    header split on ``,``, each entry sanitized, empties dropped, de-duplicated
    preserving order, re-joined with ``,``. The gateway must sign (and send)
    this exact form or every request 401s, so we canonicalize identically.
    """
    seen: dict[str, None] = {}
    for part in raw.split(","):
        cleaned = _sanitize(part)
        if cleaned:
            seen.setdefault(cleaned, None)
    return ",".join(seen)


def _path_segment(value: str) -> str:
    return quote(value, safe="")


_H_TENANT = "X-Clearfolio-Tenant-Id"
_H_SUBJECT = "X-Clearfolio-Subject-Id"
_H_PERMS = "X-Clearfolio-Permissions"
_H_ISSUED = "X-Clearfolio-Claims-Issued-At"
_H_SIG = "X-Clearfolio-Claims-Signature"


class ClearfolioNotConfigured(RuntimeError):
    """Raised when the Clearfolio connector is called without configuration."""


class ClearfolioError(RuntimeError):
    """A Clearfolio API call failed (status text is safe to surface)."""


@dataclass(frozen=True)
class ClearfolioConfig:
    gateway_url: str
    hmac_secret: str
    tenant_id: str
    permissions: str
    timeout_seconds: float

    @classmethod
    def from_settings(cls) -> "ClearfolioConfig":
        if not settings.clearfolio_gateway_url or not settings.clearfolio_tenant_claims_hmac_secret:
            raise ClearfolioNotConfigured(
                "CLEARFOLIO_GATEWAY_URL and CLEARFOLIO_TENANT_CLAIMS_HMAC_SECRET must be set"
            )
        return cls(
            gateway_url=settings.clearfolio_gateway_url.rstrip("/"),
            hmac_secret=settings.clearfolio_tenant_claims_hmac_secret,
            tenant_id=settings.clearfolio_tenant_id,
            permissions=settings.clearfolio_permissions,
            timeout_seconds=settings.clearfolio_timeout_seconds,
        )


def sign_tenant_claims(
    secret: str,
    tenant_id: str,
    subject_id: str,
    canonical_permissions: str,
    issued_at: int,
) -> str:
    """Base64URL (unpadded) HMAC-SHA256 of the newline-joined claim payload."""
    payload = "\n".join([tenant_id, subject_id, canonical_permissions, str(issued_at)])
    digest = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def build_tenant_headers(
    config: ClearfolioConfig, subject_id: str, issued_at: int | None = None
) -> dict[str, str]:
    """Build the full signed Clearfolio tenant header set for a subject."""
    if issued_at is None:
        issued_at = int(dt.datetime.now(dt.timezone.utc).timestamp())
    # Sign and send the exact canonical values Clearfolio re-derives on verify,
    # otherwise a config with spaces/duplicates would 401.
    tenant_id = _sanitize(config.tenant_id)
    subject = _sanitize(subject_id)
    permissions = canonicalize_permissions(config.permissions)
    signature = sign_tenant_claims(
        config.hmac_secret, tenant_id, subject, permissions, issued_at
    )
    return {
        _H_TENANT: tenant_id,
        _H_SUBJECT: subject,
        _H_PERMS: permissions,
        _H_ISSUED: str(issued_at),
        _H_SIG: signature,
    }


async def _validate_gateway(config: ClearfolioConfig) -> None:
    """SSRF defense-in-depth: reject an internal/loopback gateway host."""
    parsed = urlparse(config.gateway_url)
    if not parsed.hostname:
        raise ClearfolioError("invalid CLEARFOLIO_GATEWAY_URL")
    await _validated_ip_hosts(parsed.hostname, is_hostaddr=False, port=parsed.port or 443)


async def _request(
    config: ClearfolioConfig,
    method: str,
    path: str,
    subject_id: str,
    *,
    files: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    await _validate_gateway(config)
    headers = build_tenant_headers(config, subject_id)
    if extra_headers:
        headers.update(extra_headers)
    async with httpx.AsyncClient(timeout=config.timeout_seconds) as client:
        resp = await client.request(
            method, f"{config.gateway_url}{path}", headers=headers, files=files
        )
    if resp.status_code >= 400:
        raise ClearfolioError(f"clearfolio {method} {path} -> {resp.status_code}")
    return resp.json() if resp.content else {}


async def submit_conversion_job(
    subject_id: str, file_bytes: bytes, filename: str
) -> dict[str, Any]:
    """POST /api/v1/convert/jobs — submit a document for preview conversion."""
    config = ClearfolioConfig.from_settings()
    return await _request(
        config,
        "POST",
        "/api/v1/convert/jobs",
        subject_id,
        files={"file": (filename, file_bytes)},
    )


async def get_job_status(subject_id: str, job_id: str) -> dict[str, Any]:
    """GET /api/v1/convert/jobs/{jobId} — read conversion lifecycle status."""
    config = ClearfolioConfig.from_settings()
    return await _request(
        config, "GET", f"/api/v1/convert/jobs/{_path_segment(job_id)}", subject_id
    )


async def get_viewer_bootstrap(subject_id: str, doc_id: str) -> dict[str, Any]:
    """GET /api/v1/viewer/{docId} — viewer bootstrap (signed previewResourcePath)."""
    config = ClearfolioConfig.from_settings()
    return await _request(
        config, "GET", f"/api/v1/viewer/{_path_segment(doc_id)}", subject_id
    )


async def create_artifact_link(subject_id: str, doc_id: str) -> dict[str, Any]:
    """POST /api/v1/viewer/{docId}/artifact-links — short-lived signed artifact URL."""
    config = ClearfolioConfig.from_settings()
    return await _request(
        config,
        "POST",
        f"/api/v1/viewer/{_path_segment(doc_id)}/artifact-links",
        subject_id,
    )
