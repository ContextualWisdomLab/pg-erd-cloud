from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import usage_quotas
from app.settings import settings


class FakeResult:
    def __init__(self, value: int) -> None:
        self.value = value

    def scalar_one(self) -> int:
        return self.value


class FakeSession:
    def __init__(self, value: int | list[int]) -> None:
        self.values = value if isinstance(value, list) else [value]
        self.execute_count = 0

    async def execute(self, stmt: object) -> FakeResult:
        del stmt
        value = self.values[min(self.execute_count, len(self.values) - 1)]
        self.execute_count += 1
        return FakeResult(value)


@pytest.mark.asyncio
async def test_project_quota_is_skipped_when_unlimited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(999)
    monkeypatch.setattr(settings, "billing_max_projects_per_user", 0)

    await usage_quotas.enforce_project_quota(session, uuid.uuid4())

    assert session.execute_count == 0


@pytest.mark.asyncio
async def test_project_quota_rejects_when_limit_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(2)
    monkeypatch.setattr(settings, "billing_max_projects_per_user", 2)

    with pytest.raises(HTTPException) as exc_info:
        await usage_quotas.enforce_project_quota(session, uuid.uuid4())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "project quota exceeded"


@pytest.mark.asyncio
async def test_connection_quota_rejects_when_limit_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(3)
    monkeypatch.setattr(settings, "billing_max_connections_per_project", 3)

    with pytest.raises(HTTPException) as exc_info:
        await usage_quotas.enforce_connection_quota(session, uuid.uuid4())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "connection quota exceeded"


@pytest.mark.asyncio
async def test_snapshot_quota_rejects_when_limit_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(4)
    monkeypatch.setattr(settings, "billing_max_snapshots_per_project", 4)

    with pytest.raises(HTTPException) as exc_info:
        await usage_quotas.enforce_snapshot_quota(session, uuid.uuid4())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "snapshot quota exceeded"


@pytest.mark.asyncio
async def test_share_link_quota_rejects_when_limit_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession(5)
    monkeypatch.setattr(settings, "billing_max_share_links_per_project", 5)

    with pytest.raises(HTTPException) as exc_info:
        await usage_quotas.enforce_share_link_quota(session, uuid.uuid4())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "share link quota exceeded"


@pytest.mark.asyncio
async def test_seat_quota_is_skipped_when_no_contract_seat_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([999, 0])

    async def fake_latest_entitlement(session: object, subject: str) -> object:
        del session, subject
        return SimpleNamespace(seat_count=None)

    monkeypatch.setattr(
        usage_quotas,
        "latest_billing_entitlement_for_subject",
        fake_latest_entitlement,
    )

    await usage_quotas.enforce_seat_quota(
        session,
        owner_user_account_uuid=uuid.uuid4(),
        owner_subject="customer-owner",
        candidate_user_account_uuid=uuid.uuid4(),
    )

    assert session.execute_count == 0


@pytest.mark.asyncio
async def test_seat_quota_rejects_new_member_when_contract_limit_reached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([2, 0])

    async def fake_latest_entitlement(session: object, subject: str) -> object:
        del session, subject
        return SimpleNamespace(seat_count=2)

    monkeypatch.setattr(
        usage_quotas,
        "latest_billing_entitlement_for_subject",
        fake_latest_entitlement,
    )

    with pytest.raises(HTTPException) as exc_info:
        await usage_quotas.enforce_seat_quota(
            session,
            owner_user_account_uuid=uuid.uuid4(),
            owner_subject="customer-owner",
            candidate_user_account_uuid=uuid.uuid4(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "seat quota exceeded"
    assert session.execute_count == 2


@pytest.mark.asyncio
async def test_seat_quota_allows_existing_member_role_update_at_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = FakeSession([2, 1])

    async def fake_latest_entitlement(session: object, subject: str) -> object:
        del session, subject
        return SimpleNamespace(seat_count=2)

    monkeypatch.setattr(
        usage_quotas,
        "latest_billing_entitlement_for_subject",
        fake_latest_entitlement,
    )

    await usage_quotas.enforce_seat_quota(
        session,
        owner_user_account_uuid=uuid.uuid4(),
        owner_subject="customer-owner",
        candidate_user_account_uuid=uuid.uuid4(),
    )

    assert session.execute_count == 2
