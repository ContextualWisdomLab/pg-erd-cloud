from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main as main_app
from app.csrf import CSRF_HEADER_NAME, generate_csrf_token
from app.settings import settings


def test_logout_route_uses_tighter_revocation_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    main_app._rate_limiter._buckets.clear()
    main_app._share_link_rate_limiter._buckets.clear()
    main_app._revoke_rate_limiter._buckets.clear()

    # Avoid hitting OIDC configuration error by allowing no authorization
    monkeypatch.setattr(settings, "oidc_issuer", "https://example.com/oidc")

    client = TestClient(main_app.app)
    headers = {CSRF_HEADER_NAME: generate_csrf_token(settings.app_secret)}

    for _ in range(10):
        res = client.post("/api/auth/logout", headers=headers)
        assert res.status_code != 429
        assert res.status_code == 401

    response = client.post("/api/auth/logout", headers=headers)

    assert response.status_code == 429
    assert response.json() == {"detail": "rate limit exceeded"}
