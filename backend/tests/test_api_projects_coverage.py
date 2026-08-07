"""Behavioral coverage for project and membership API orchestration."""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from app.api import projects
from app.auth import CurrentUser
from app.schemas import ProjectCreateIn, ProjectMemberAddIn


class _Scalars:
    """Small scalar collection compatible with SQLAlchemy result use."""

    def __init__(self, values: list[object]) -> None:
        self.values = values

    def all(self) -> list[object]:
        return self.values

    def first(self) -> object | None:
        return self.values[0] if self.values else None


class _Result:
    """Configurable SQLAlchemy-like result for project tests."""

    def __init__(
        self,
        *,
        scalar: object | None = None,
        scalar_required: object | None = None,
        scalars: list[object] | None = None,
        rows: list[object] | None = None,
    ) -> None:
        self._scalar = scalar
        self._scalar_required = scalar_required
        self._scalars = scalars or []
        self._rows = rows or []

    def scalar_one_or_none(self) -> object | None:
        return self._scalar

    def scalar_one(self) -> object:
        if self._scalar_required is None:
            raise AssertionError("required scalar was not configured")
        return self._scalar_required

    def scalars(self) -> _Scalars:
        return _Scalars(self._scalars)

    def all(self) -> list[object]:
        return self._rows


class _Session:
    """Async session double with queued query results and mutation receipts."""

    def __init__(self, *results: _Result) -> None:
        self.results = list(results)
        self.added: list[object] = []
        self.flush_calls = 0
        self.commit_calls = 0

    async def execute(self, _statement: object) -> _Result:
        if not self.results:
            raise AssertionError("unexpected database execute")
        return self.results.pop(0)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        self.flush_calls += 1

    async def commit(self) -> None:
        self.commit_calls += 1


def _user() -> CurrentUser:
    """Return one authenticated project caller."""
    return CurrentUser(
        user_account_uuid=uuid.uuid4(),
        subject="oidc|project-user",
        display_name="Project User",
    )


@pytest.mark.asyncio
async def test_list_projects_maps_member_projects() -> None:
    """Return only the public project identity fields from query rows."""
    first_uuid = uuid.uuid4()
    second_uuid = uuid.uuid4()
    session = _Session(
        _Result(
            scalars=[
                SimpleNamespace(project_space_uuid=first_uuid, project_name="Alpha"),
                SimpleNamespace(project_space_uuid=second_uuid, project_name="Beta"),
            ]
        )
    )

    result = await projects.list_projects(user=_user(), session=session)  # type: ignore[arg-type]

    assert [(item.project_space_uuid, item.project_name) for item in result] == [
        (first_uuid, "Alpha"),
        (second_uuid, "Beta"),
    ]


@pytest.mark.asyncio
async def test_create_project_adds_project_and_owner() -> None:
    """Persist the new project before its owner membership and commit once."""
    user = _user()
    session = _Session()

    result = await projects.create_project(
        ProjectCreateIn(project_name="Buyer Workspace"),
        user=user,
        session=session,  # type: ignore[arg-type]
    )

    assert result.project_name == "Buyer Workspace"
    assert result.project_space_uuid == session.added[0].project_space_uuid  # type: ignore[attr-defined]
    assert session.added[1].project_role == "owner"  # type: ignore[attr-defined]
    assert session.added[1].user_account_uuid == user.user_account_uuid  # type: ignore[attr-defined]
    assert session.flush_calls == 1
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_list_project_members_requires_editor_and_maps_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authorize the caller before exposing project membership identities."""
    project_uuid = uuid.uuid4()
    caller = _user()
    member_uuid = uuid.uuid4()
    authorizations: list[tuple[uuid.UUID, uuid.UUID, str | None]] = []

    async def require_member(
        _session: object,
        project_space_uuid: uuid.UUID,
        user_account_uuid: uuid.UUID,
        minimum_role: str | None = None,
    ) -> str:
        authorizations.append((project_space_uuid, user_account_uuid, minimum_role))
        return "editor"

    monkeypatch.setattr(projects, "require_project_member", require_member)
    session = _Session(
        _Result(
            rows=[
                (
                    SimpleNamespace(project_role="viewer"),
                    SimpleNamespace(
                        user_account_uuid=member_uuid,
                        oidc_subject="oidc|member",
                    ),
                )
            ]
        )
    )

    result = await projects.list_project_members(
        project_uuid,
        user=caller,
        session=session,  # type: ignore[arg-type]
    )

    assert authorizations == [(project_uuid, caller.user_account_uuid, "editor")]
    assert len(result) == 1
    assert result[0].user_account_uuid == member_uuid
    assert result[0].member_subject == "oidc|member"
    assert result[0].project_role == "viewer"


@pytest.mark.asyncio
async def test_ensure_owner_accepts_owner_and_rejects_other_roles() -> None:
    """Require the exact owner role for membership administration."""
    await projects._ensure_owner(
        _Session(_Result(scalar="owner")),  # type: ignore[arg-type]
        uuid.uuid4(),
        uuid.uuid4(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await projects._ensure_owner(
            _Session(_Result(scalar="editor")),  # type: ignore[arg-type]
            uuid.uuid4(),
            uuid.uuid4(),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "owner role required"


@pytest.mark.asyncio
async def test_ensure_user_exists_returns_existing_or_creates_missing() -> None:
    """Reuse an existing subject and persist a newly observed subject once."""
    existing = SimpleNamespace(user_account_uuid=uuid.uuid4(), oidc_subject="oidc|known")
    existing_session = _Session(_Result(scalars=[existing]))

    assert (
        await projects._ensure_user_exists(existing_session, "oidc|known")  # type: ignore[arg-type]
        is existing
    )
    assert existing_session.added == []
    assert existing_session.flush_calls == 0

    missing_session = _Session(_Result(scalars=[]))
    created = await projects._ensure_user_exists(  # type: ignore[arg-type]
        missing_session,
        "oidc|new",
    )
    assert created.oidc_subject == "oidc|new"
    assert created.display_name is None
    assert missing_session.added == [created]
    assert missing_session.flush_calls == 1


@pytest.mark.asyncio
async def test_ensure_not_changing_owner_role() -> None:
    """Reject owner mutation while allowing non-owner membership updates."""
    await projects._ensure_not_changing_owner_role(
        _Session(_Result(scalar="viewer")),  # type: ignore[arg-type]
        uuid.uuid4(),
        uuid.uuid4(),
    )

    with pytest.raises(HTTPException) as exc_info:
        await projects._ensure_not_changing_owner_role(
            _Session(_Result(scalar="owner")),  # type: ignore[arg-type]
            uuid.uuid4(),
            uuid.uuid4(),
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "cannot change owner role via invite endpoint"


@pytest.mark.asyncio
async def test_upsert_project_member_returns_persisted_role() -> None:
    """Commit and return the role produced by the PostgreSQL upsert."""
    session = _Session(_Result(scalar_required="editor"))

    result = await projects._upsert_project_member(  # type: ignore[arg-type]
        session,
        uuid.uuid4(),
        uuid.uuid4(),
        "editor",
    )

    assert result == "editor"
    assert session.commit_calls == 1


@pytest.mark.asyncio
async def test_add_project_member_orchestrates_owner_user_and_upsert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanitize the subject and return the role from the membership upsert."""
    project_uuid = uuid.uuid4()
    caller = _user()
    member_uuid = uuid.uuid4()
    session = _Session()
    steps: list[str] = []

    async def ensure_owner(*_args: object) -> None:
        steps.append("owner")

    async def ensure_user(_session: object, subject: str) -> object:
        steps.append(f"user:{subject}")
        return SimpleNamespace(
            user_account_uuid=member_uuid,
            oidc_subject=subject,
        )

    async def ensure_not_owner(*_args: object) -> None:
        steps.append("not-owner")

    async def upsert(*_args: object) -> str:
        steps.append("upsert")
        return "editor"

    monkeypatch.setattr(projects, "_ensure_owner", ensure_owner)
    monkeypatch.setattr(projects, "_ensure_user_exists", ensure_user)
    monkeypatch.setattr(projects, "_ensure_not_changing_owner_role", ensure_not_owner)
    monkeypatch.setattr(projects, "_upsert_project_member", upsert)
    monkeypatch.setattr(projects, "sanitize_for_storage", lambda value: value)

    result = await projects.add_project_member(
        project_uuid,
        ProjectMemberAddIn(member_subject="oidc|new", project_role="editor"),
        user=caller,
        session=session,  # type: ignore[arg-type]
    )

    assert steps == ["owner", "user:oidc|new", "not-owner", "upsert"]
    assert result.user_account_uuid == member_uuid
    assert result.member_subject == "oidc|new"
    assert result.project_role == "editor"


@pytest.mark.asyncio
async def test_add_project_member_rejects_sanitized_empty_subject(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fail closed if storage sanitization eliminates the member subject."""
    async def ensure_owner(*_args: object) -> None:
        return None

    monkeypatch.setattr(projects, "_ensure_owner", ensure_owner)
    monkeypatch.setattr(projects, "sanitize_for_storage", lambda _value: "   ")

    with pytest.raises(HTTPException) as exc_info:
        await projects.add_project_member(
            uuid.uuid4(),
            ProjectMemberAddIn(member_subject="oidc|candidate", project_role="viewer"),
            user=_user(),
            session=_Session(),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "member_subject required"
