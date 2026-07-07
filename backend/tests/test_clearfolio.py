from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from app.integrations import clearfolio as cf


SECRET = "gateway-shared-secret"
PERMS = "job:create,job:read,job:retry,viewer:read,artifact-link:create,analytics:read"


def test_sign_tenant_claims_matches_golden_vector():
    # Golden value computed from the documented recipe:
    #   base64url(HMAC_SHA256(secret, tenant\nsubject\nperms\nissuedAt)), no padding
    sig = cf.sign_tenant_claims(SECRET, "pg-erd-cloud", "dev:alice", PERMS, 1782995100)
    assert sig == "TVdcjfzpR30SJmpCMrliK4gjuj6UY7zi2zGXBHzRlvc"
    assert "=" not in sig  # unpadded
    assert "+" not in sig and "/" not in sig  # base64URL alphabet


def test_signature_binds_every_claim():
    base = cf.sign_tenant_claims(SECRET, "t", "s", "p", 100)
    assert base != cf.sign_tenant_claims(SECRET, "t2", "s", "p", 100)
    assert base != cf.sign_tenant_claims(SECRET, "t", "s2", "p", 100)
    assert base != cf.sign_tenant_claims(SECRET, "t", "s", "p2", 100)
    assert base != cf.sign_tenant_claims(SECRET, "t", "s", "p", 101)
    assert base != cf.sign_tenant_claims("other", "t", "s", "p", 100)


def test_build_headers_sends_full_signed_set_and_self_verifies():
    cfg = cf.ClearfolioConfig(
        gateway_url="https://cf.example.com", hmac_secret=SECRET,
        tenant_id="pg-erd-cloud", permissions=PERMS, timeout_seconds=10.0,
    )
    headers = cf.build_tenant_headers(cfg, "dev:alice", issued_at=1782995100)
    assert headers["X-Clearfolio-Tenant-Id"] == "pg-erd-cloud"
    assert headers["X-Clearfolio-Subject-Id"] == "dev:alice"
    assert headers["X-Clearfolio-Permissions"] == PERMS
    assert headers["X-Clearfolio-Claims-Issued-At"] == "1782995100"
    # the signature header must equal an independent re-sign of the sent claims
    assert headers["X-Clearfolio-Claims-Signature"] == cf.sign_tenant_claims(
        SECRET,
        headers["X-Clearfolio-Tenant-Id"],
        headers["X-Clearfolio-Subject-Id"],
        headers["X-Clearfolio-Permissions"],
        int(headers["X-Clearfolio-Claims-Issued-At"]),
    )


@pytest.mark.asyncio
async def test_not_configured_raises():
    with patch.object(cf.settings, "clearfolio_gateway_url", None):
        with pytest.raises(cf.ClearfolioNotConfigured):
            await cf.submit_conversion_job("dev:alice", b"pdf", "spec.pdf")


@pytest.mark.asyncio
async def test_submit_signs_and_posts_multipart(monkeypatch):
    monkeypatch.setattr(cf.settings, "clearfolio_gateway_url", "https://cf.example.com")
    monkeypatch.setattr(cf.settings, "clearfolio_tenant_claims_hmac_secret", SECRET)
    monkeypatch.setattr(cf.settings, "clearfolio_tenant_id", "pg-erd-cloud")
    captured = {}

    async def fake_validate(config):
        return None

    async def fake_request(self, method, url, headers=None, files=None):
        captured.update(method=method, url=url, headers=headers, files=files)
        return httpx.Response(202, json={"jobId": "j-1", "statusUrl": "/x"})

    monkeypatch.setattr(cf, "_validate_gateway", fake_validate)
    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    out = await cf.submit_conversion_job("dev:alice", b"%PDF-1.7", "spec.pdf")
    assert out["jobId"] == "j-1"
    assert captured["method"] == "POST"
    assert captured["url"] == "https://cf.example.com/api/v1/convert/jobs"
    assert captured["headers"]["X-Clearfolio-Claims-Signature"]  # signed
    assert captured["files"]["file"][0] == "spec.pdf"


@pytest.mark.asyncio
async def test_http_error_becomes_clearfolio_error(monkeypatch):
    monkeypatch.setattr(cf.settings, "clearfolio_gateway_url", "https://cf.example.com")
    monkeypatch.setattr(cf.settings, "clearfolio_tenant_claims_hmac_secret", SECRET)

    async def fake_validate(config):
        return None

    async def fake_request(self, method, url, headers=None, files=None):
        return httpx.Response(403, json={"error": "forbidden"})

    monkeypatch.setattr(cf, "_validate_gateway", fake_validate)
    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    with pytest.raises(cf.ClearfolioError):
        await cf.get_viewer_bootstrap("dev:alice", "doc-1")
