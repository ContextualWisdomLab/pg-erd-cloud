import pytest
from app import auth
from app.settings import settings
import httpx

@pytest.mark.asyncio
async def test_ssrf_protection_oidc_issuer(monkeypatch):
    monkeypatch.setattr(settings, "oidc_issuer", "https://127.0.0.1/")
    monkeypatch.setattr(auth, "_oidc_config", None)
    with pytest.raises(RuntimeError, match="restricted IP"):
        await auth._get_oidc_config()

@pytest.mark.asyncio
async def test_ssrf_protection_jwks_uri(monkeypatch):
    async def fake_config():
        return {"jwks_uri": "https://localhost/jwks"}
    monkeypatch.setattr(auth, "_get_oidc_config", fake_config)
    monkeypatch.setattr(auth, "_oidc_jwks", None)
    with pytest.raises(RuntimeError, match="restricted IP"):
        await auth._get_jwks()
