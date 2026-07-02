from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.billing import router
from app.auth import CurrentUser, get_current_user
from app.db import get_read_session
from app.settings import settings

app = FastAPI()
app.include_router(router)


class FakeResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class FakeSession:
    def __init__(self, counts: list[int]) -> None:
        self.counts = counts
        self.statement_count = 0

    async def execute(self, stmt: object) -> FakeResult:
        del stmt
        value = self.counts[self.statement_count]
        self.statement_count += 1
        return FakeResult(value)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def fake_get_current_user() -> CurrentUser:
    return CurrentUser(
        user_account_uuid=uuid.uuid4(),
        subject="customer-owner",
        display_name="Customer Owner",
    )


def test_billing_usage_returns_owned_project_scope_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([2, 5, 3, 8, 4, 1])
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", "x" * 44)
    monkeypatch.setattr(settings, "billing_max_projects_per_user", 10)
    monkeypatch.setattr(settings, "billing_max_connections_per_project", 20)
    monkeypatch.setattr(settings, "billing_max_snapshots_per_project", 30)
    monkeypatch.setattr(settings, "billing_max_share_links_per_project", 40)
    monkeypatch.setattr(settings, "billing_portal_url", "https://billing.example.com")
    monkeypatch.setattr(settings, "billing_support_url", "https://support.example.com")
    monkeypatch.setattr(
        settings,
        "account_reactivation_url",
        "https://billing.example.com/reactivate",
    )

    app.dependency_overrides[get_current_user] = fake_get_current_user
    app.dependency_overrides[get_read_session] = lambda: session

    response = TestClient(app).get("/api/billing/usage")

    assert response.status_code == 200
    assert response.json() == {
        "scope": "owned_projects",
        "license_mode": "required",
        "license_verifier": "signed_token",
        "project_count": 2,
        "seat_count": 5,
        "connection_count": 3,
        "snapshot_count": 8,
        "share_link_count": 4,
        "active_share_link_count": 1,
        "project_limit": 10,
        "connection_limit": 20,
        "snapshot_limit": 30,
        "share_link_limit": 40,
        "account_status": "active",
        "billing_portal_url": "https://billing.example.com",
        "billing_support_url": "https://support.example.com",
        "account_reactivation_url": "https://billing.example.com/reactivate",
    }
    assert session.statement_count == 6


def test_billing_usage_reports_no_license_verifier_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([0, 0, 0, 0, 0, 0])
    monkeypatch.setattr(settings, "license_mode", "off")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", None)
    monkeypatch.setattr(settings, "billing_max_projects_per_user", 0)
    monkeypatch.setattr(settings, "billing_max_connections_per_project", 0)
    monkeypatch.setattr(settings, "billing_max_snapshots_per_project", 0)
    monkeypatch.setattr(settings, "billing_max_share_links_per_project", 0)
    monkeypatch.setattr(settings, "billing_portal_url", None)
    monkeypatch.setattr(settings, "billing_support_url", None)
    monkeypatch.setattr(settings, "account_reactivation_url", None)

    app.dependency_overrides[get_current_user] = fake_get_current_user
    app.dependency_overrides[get_read_session] = lambda: session

    response = TestClient(app).get("/api/billing/usage")

    assert response.status_code == 200
    assert response.json()["license_verifier"] == "none"
    assert response.json()["project_count"] == 0
    assert response.json()["account_status"] == "active"
    assert response.json()["billing_portal_url"] is None
    assert response.json()["billing_support_url"] is None
    assert response.json()["account_reactivation_url"] is None


def test_billing_plan_change_returns_portal_url_with_target_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "billing_portal_url",
        "https://billing.example.com/portal?source=pg-erd",
    )
    monkeypatch.setattr(settings, "billing_support_url", "https://support.example.com")

    app.dependency_overrides[get_current_user] = fake_get_current_user

    response = TestClient(app).post(
        "/api/billing/plan-change",
        json={"target_plan": "enterprise-plus"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "action": "portal_redirect",
        "target_plan": "enterprise-plus",
        "billing_portal_url": (
            "https://billing.example.com/portal?"
            "source=pg-erd&target_plan=enterprise-plus"
        ),
        "billing_support_url": "https://support.example.com",
        "message": "Open the billing portal to request or complete this plan change.",
    }


def test_billing_plan_change_falls_back_to_support_when_portal_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "billing_portal_url", None)
    monkeypatch.setattr(settings, "billing_support_url", "https://support.example.com")

    app.dependency_overrides[get_current_user] = fake_get_current_user

    response = TestClient(app).post(
        "/api/billing/plan-change",
        json={"target_plan": "team"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "action": "contact_support",
        "target_plan": "team",
        "billing_portal_url": None,
        "billing_support_url": "https://support.example.com",
        "message": "Contact billing support to request or complete this plan change.",
    }


def test_billing_plan_change_requires_portal_or_support_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "billing_portal_url", None)
    monkeypatch.setattr(settings, "billing_support_url", None)

    app.dependency_overrides[get_current_user] = fake_get_current_user

    response = TestClient(app).post(
        "/api/billing/plan-change",
        json={"target_plan": "team"},
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "billing plan change path is not configured"
