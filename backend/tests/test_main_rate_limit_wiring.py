from __future__ import annotations

from fastapi.testclient import TestClient

from app import main as main_app
from app.csrf import CSRF_HEADER_NAME, generate_csrf_token
from app.settings import settings


def test_logout_route_uses_tighter_revocation_rate_limit() -> None:
    main_app._rate_limiter._buckets.clear()
    main_app._share_link_rate_limiter._buckets.clear()
    main_app._revoke_rate_limiter._buckets.clear()

    client = TestClient(main_app.app)
    headers = {CSRF_HEADER_NAME: generate_csrf_token(settings.app_secret)}

    probe_path = "/api/auth/logout/rate-limit-probe"
    for _ in range(10):
        assert client.post(probe_path, headers=headers).status_code != 429

    response = client.post(probe_path, headers=headers)

    assert response.status_code == 429
    assert response.json() == {"detail": "rate limit exceeded"}
