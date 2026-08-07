from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.permissions import require_project_member


class FakeResult:
    def __init__(self, role: str | None) -> None:
        self.role = role

    def scalar_one_or_none(self) -> str | None:
        return self.role


class FakeSession:
    def __init__(self, role: str | None) -> None:
        self.role = role

    async def execute(self, _: object) -> FakeResult:
        return FakeResult(self.role)


@pytest.mark.asyncio
async def test_require_project_member_allows_sufficient_role() -> None:
    role = await require_project_member(
        FakeSession("editor"), uuid.uuid4(), uuid.uuid4(), minimum_role="editor"
    )

    assert role == "editor"


@pytest.mark.asyncio
async def test_require_project_member_rejects_insufficient_role() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await require_project_member(
            FakeSession("viewer"), uuid.uuid4(), uuid.uuid4(), minimum_role="editor"
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "insufficient project role"


@pytest.mark.asyncio
async def test_require_project_member_rejects_non_member() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await require_project_member(FakeSession(None), uuid.uuid4(), uuid.uuid4())

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "project access denied"
