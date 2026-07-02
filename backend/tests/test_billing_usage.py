from __future__ import annotations

import datetime as dt
import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.billing import router
from app.auth import CurrentUser, get_current_user
from app.db import get_read_session, get_session
from app.models import BillingEvent, UserAccount
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


class FakeBillingEventResult:
    def __init__(self, event: BillingEvent | None) -> None:
        self.event = event

    def scalar_one_or_none(self) -> BillingEvent | None:
        return self.event


class FakeBillingEventSession:
    def __init__(self, existing_event: BillingEvent | None = None) -> None:
        self.existing_event = existing_event
        self.added_event: BillingEvent | None = None
        self.committed = False
        self.rolled_back = False

    async def execute(self, stmt: object) -> FakeBillingEventResult:
        del stmt
        return FakeBillingEventResult(self.existing_event)

    def add(self, event: BillingEvent) -> None:
        self.added_event = event

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeScalars:
    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values


class FakeSupportResult:
    def __init__(
        self,
        value: object | None = None,
        values: list[object] | None = None,
    ) -> None:
        self.value = value
        self.values = values or []

    def scalar_one(self) -> object:
        return self.value

    def scalar_one_or_none(self) -> object | None:
        return self.value

    def scalars(self) -> FakeScalars:
        return FakeScalars(self.values)


class FakeSupportSession:
    def __init__(
        self,
        account: UserAccount | None,
        counts: list[int],
        events: list[BillingEvent],
    ) -> None:
        self.account = account
        self.counts = counts
        self.events = events
        self.statement_count = 0

    async def execute(self, stmt: object) -> FakeSupportResult:
        del stmt
        self.statement_count += 1
        if self.statement_count == 1:
            return FakeSupportResult(self.account)
        if 2 <= self.statement_count <= 7:
            return FakeSupportResult(self.counts[self.statement_count - 2])
        return FakeSupportResult(values=list(self.events))


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


def fake_get_support_operator() -> CurrentUser:
    return CurrentUser(
        user_account_uuid=uuid.uuid4(),
        subject="support-operator",
        display_name="Support Operator",
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


def test_billing_event_requires_configured_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "billing_webhook_secret", None)
    app.dependency_overrides[get_session] = lambda: FakeBillingEventSession()

    response = TestClient(app).post(
        "/api/billing/events",
        headers={"X-BILLING-WEBHOOK-SECRET": "provider-secret"},
        json={
            "provider": "stripe",
            "provider_event_id": "evt_1",
            "event_type": "subscription.updated",
            "subject": "customer-owner",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "billing webhook secret is not configured"


def test_billing_event_rejects_invalid_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "billing_webhook_secret", "provider-secret")
    app.dependency_overrides[get_session] = lambda: FakeBillingEventSession()

    response = TestClient(app).post(
        "/api/billing/events",
        headers={"X-BILLING-WEBHOOK-SECRET": "wrong-secret"},
        json={
            "provider": "stripe",
            "provider_event_id": "evt_1",
            "event_type": "subscription.updated",
            "subject": "customer-owner",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "invalid billing webhook secret"


def test_billing_event_records_and_redacts_sensitive_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeBillingEventSession()
    monkeypatch.setattr(settings, "billing_webhook_secret", "provider-secret")
    app.dependency_overrides[get_session] = lambda: session

    response = TestClient(app).post(
        "/api/billing/events",
        headers={"X-BILLING-WEBHOOK-SECRET": "provider-secret"},
        json={
            "provider": "stripe",
            "provider_event_id": "evt_1",
            "event_type": "subscription.updated",
            "subject": "customer-owner",
            "target_plan": "enterprise",
            "occurred_at": "2026-07-02T01:02:03Z",
            "metadata": {
                "invoice_id": "in_123",
                "api_key": "sk_live_secret",
                "nested": {"client_secret": "seti_secret"},
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "recorded"
    assert payload["provider"] == "stripe"
    assert payload["provider_event_id"] == "evt_1"
    assert payload["event_type"] == "subscription.updated"
    assert payload["subject"] == "customer-owner"
    assert payload["target_plan"] == "enterprise"
    assert payload["status"] == "recorded"
    assert session.committed is True
    assert session.added_event is not None
    assert session.added_event.metadata_json == {
        "invoice_id": "in_123",
        "api_key": "[redacted]",
        "nested": {"client_secret": "[redacted]"},
    }


def test_billing_event_ignores_duplicate_provider_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_event = BillingEvent(
        billing_event_uuid=uuid.uuid4(),
        provider="stripe",
        provider_event_id="evt_1",
        event_type="subscription.updated",
        subject="customer-owner",
        target_plan="enterprise",
        event_status="recorded",
        occurred_at=dt.datetime(2026, 7, 2, tzinfo=dt.timezone.utc),
        received_at=dt.datetime(2026, 7, 2, 1, tzinfo=dt.timezone.utc),
        metadata_json={},
    )
    session = FakeBillingEventSession(existing_event=existing_event)
    monkeypatch.setattr(settings, "billing_webhook_secret", "provider-secret")
    app.dependency_overrides[get_session] = lambda: session

    response = TestClient(app).post(
        "/api/billing/events",
        headers={"X-BILLING-WEBHOOK-SECRET": "provider-secret"},
        json={
            "provider": "stripe",
            "provider_event_id": "evt_1",
            "event_type": "subscription.updated",
            "subject": "customer-owner",
            "target_plan": "enterprise",
        },
    )

    assert response.status_code == 200
    assert response.json()["action"] == "duplicate"
    assert uuid.UUID(response.json()["billing_event_uuid"]) == (
        existing_event.billing_event_uuid
    )
    assert session.added_event is None
    assert session.committed is False


def test_support_account_billing_requires_support_operator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "support_operator_subjects", "support-operator")
    app.dependency_overrides[get_current_user] = fake_get_current_user
    app.dependency_overrides[get_read_session] = lambda: FakeSupportSession(
        account=None,
        counts=[],
        events=[],
    )

    response = TestClient(app).get(
        "/api/billing/support/account",
        params={"subject": "customer-owner"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "support operator role required"


def test_support_account_billing_returns_read_only_account_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_uuid = uuid.uuid4()
    account = UserAccount(
        user_account_uuid=customer_uuid,
        oidc_subject="customer-owner",
        display_name="Customer Owner",
    )
    event = BillingEvent(
        billing_event_uuid=uuid.uuid4(),
        provider="stripe",
        provider_event_id="evt_1",
        event_type="subscription.updated",
        subject="customer-owner",
        target_plan="enterprise",
        event_status="recorded",
        occurred_at=dt.datetime(2026, 7, 2, tzinfo=dt.timezone.utc),
        received_at=dt.datetime(2026, 7, 2, 1, tzinfo=dt.timezone.utc),
        metadata_json={"api_key": "[redacted]"},
    )
    session = FakeSupportSession(
        account=account,
        counts=[2, 5, 3, 8, 4, 1],
        events=[event],
    )
    monkeypatch.setattr(settings, "support_operator_subjects", "support-operator")
    monkeypatch.setattr(settings, "account_deactivated_subjects", "")
    monkeypatch.setattr(settings, "license_mode", "required")
    monkeypatch.setattr(settings, "license_key", None)
    monkeypatch.setattr(settings, "license_public_key", "x" * 44)
    monkeypatch.setattr(settings, "billing_portal_url", "https://billing.example.com")
    monkeypatch.setattr(settings, "billing_support_url", "https://support.example.com")
    monkeypatch.setattr(
        settings,
        "account_reactivation_url",
        "https://billing.example.com/reactivate",
    )
    app.dependency_overrides[get_current_user] = fake_get_support_operator
    app.dependency_overrides[get_read_session] = lambda: session

    response = TestClient(app).get(
        "/api/billing/support/account",
        params={"subject": "customer-owner"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["subject"] == "customer-owner"
    assert payload["user_account_uuid"] == str(customer_uuid)
    assert payload["account_status"] == "active"
    assert payload["license_mode"] == "required"
    assert payload["license_verifier"] == "signed_token"
    assert payload["billing_portal_url"] == "https://billing.example.com"
    assert payload["billing_support_url"] == "https://support.example.com"
    assert payload["account_reactivation_url"] == (
        "https://billing.example.com/reactivate"
    )
    assert payload["project_count"] == 2
    assert payload["seat_count"] == 5
    assert payload["connection_count"] == 3
    assert payload["snapshot_count"] == 8
    assert payload["share_link_count"] == 4
    assert payload["active_share_link_count"] == 1
    assert payload["recent_billing_events"] == [
        {
            "billing_event_uuid": str(event.billing_event_uuid),
            "provider": "stripe",
            "provider_event_id": "evt_1",
            "event_type": "subscription.updated",
            "target_plan": "enterprise",
            "status": "recorded",
            "occurred_at": "2026-07-02T00:00:00Z",
            "received_at": "2026-07-02T01:00:00Z",
        }
    ]
    assert session.statement_count == 8
