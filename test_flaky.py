import time
from unittest import mock
import pytest
from fastapi.testclient import TestClient

from app import main as main_app
from app.csrf import CSRF_HEADER_NAME, generate_csrf_token
from app.settings import settings

def test_flaky():
    main_app._rate_limiter._buckets.clear()
    main_app._share_link_rate_limiter._buckets.clear()
    main_app._revoke_rate_limiter._buckets.clear()

    client = TestClient(main_app.app)
    headers = {CSRF_HEADER_NAME: generate_csrf_token(settings.app_secret)}

    # Simulate crossing the boundary
    with mock.patch("app.rate_limit.time.monotonic") as mock_time:
        # Before boundary
        mock_time.return_value = 59.9
        for _ in range(10):
            assert client.post("/api/auth/logout", headers=headers).status_code != 429

        # Cross boundary
        mock_time.return_value = 60.1
        response = client.post("/api/auth/logout", headers=headers)
        print("Response after crossing boundary:", response.status_code)

test_flaky()
