"""Behavioral coverage for table-annotation API authorization and persistence."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
import uuid

import pytest
from fastapi import HTTPException

from app.api import annotations
from app.auth import CurrentUser
from app.schemas import TableAnnotationUpsertIn


class _Scalars:
    """Small SQLAlchemy-like scalar collection."""

    def __init__(self, values: list[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        """Return all configured scalar rows."""
        return self._values


class _Rows:
    """Small SQLAlchemy-like result exposing scalars."""

    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self) -> _Scalars:
        """Return the configured scalar collection."""
        return _Scalars(self._values)


class _Session:
    """Async database-session double for annotation operations."""

    def __init__(
        self,
        *,
        scalar_values: list[object | None] | None = None,
        get_value: object | None = None,
        row_values: list[object] | None = None,
    ) -> None:
        self.scalar_values = list(scalar_values or [])
        self.get_value = get_value
        self.row_values = list(row_values or [])
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.commit_calls = 0

    async def scalar(self, _statement: object) -> object | None:
        """Return the next configured scalar value."""
        if not self.scalar_values:
            raise AssertionError("unexpected scalar query")
        return self.scalar_values.pop(0)

    async def get(self, _model: object, _key: uuid.UUID) -> object | None:
        """Return the configured annotation record."""
        return self.get_value

    async def execute(self, _statement: object) -> _Rows:
        """Return configured annotation rows."""
        return _Rows(self.row_values)

    def add(self, value: object) -> None:
        """Record a new annotation pending persistence."""
        self.added.append(value)

    async def delete(self, value: object) -> None:
        """Record an annotation scheduled for deletion."""
        self.deleted.append(value)

    async def commit(self) -> None:
        """Record one durable mutation boundary."""
        self.commit_calls += 1


def _user() -> CurrentUser:
    """Return one authenticated annotation caller."""
    return CurrentUser(
        user_account_uuid=uuid.uuid4(),
        subject="oidc|annotation-user",
        display_name="Annotation User",
    )


def _annotation(*, project_space_uuid: uuid.UUID | None = None) -> SimpleNamespace:
    """Return a production-shaped annotation record."""
    now = dt.datetime(2026, 8, 7, tzinfo=dt.timezone.utc)
    return SimpleNamespace(
        table_annotation_uuid=uuid.uuid4(),
        project_space_uuid=project_space_uuid or uuid.uuid4(),
        schema_name="public",
        relation_name="customer_account",
        body="Buyer-visible note",
        created_by=uuid.uuid4(),
        created_at=now,
        updated_at=now,
    )


def test_to_out_maps_annotation_fields() -> None:
    """Expose only the public annotation response fields."""
    annotation = _annotation()

    result = annotations._to_out(annotation)  # type: ignore[arg-type]

    assert result.table_annotation_uuid == annotation.table_annotation_uuid
    assert result.schema_name == "public"
    assert result.relation_name == "customer_account"
    assert result.body == "Buyer-visible note"
    assert result.created_at == annotation.created_at
    assert result.updated_at == annotation.updated_at


@pytest.mark.asyncio
async def test_get_authorized_annotation_hides_missing_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return no record when the annotation identifier is unknown."""
    authorization_calls: list[object] = []

    async def require_member(*args: object, **_kwargs: object) -> None:
        authorization_calls.extend(args)

    monkeypatch.setattr(annotations, "require_project_member", require_member)
    session = _Session(scalar_values=[None])

    result = await annotations._get_authorized_annotation(  # type: ignore[arg-type]
        session,
        uuid.uuid4(),
        _user(),
    )

    assert result is None
    assert authorization_calls == []


@pytest.mark.asyncio
async def test_get_authorized_annotation_returns_record_after_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return the annotation only after successful project authorization."""
    project_uuid = uuid.uuid4()
    user = _user()
    annotation = _annotation(project_space_uuid=project_uuid)
    observed: list[tuple[uuid.UUID, uuid.UUID, str | None]] = []

    async def require_member(
        _session: object,
        project_space_uuid: uuid.UUID,
        user_account_uuid: uuid.UUID,
        minimum_role: str | None = None,
    ) -> str:
        observed.append((project_space_uuid, user_account_uuid, minimum_role))
        return "editor"

    monkeypatch.setattr(annotations, "require_project_member", require_member)
    session = _Session(scalar_values=[project_uuid], get_value=annotation)

    result = await annotations._get_authorized_annotation(  # type: ignore[arg-type]
        session,
        annotation.table_annotation_uuid,
        user,
        minimum_role="editor",
    )

    assert result is annotation
    assert observed == [(project_uuid, user.user_account_uuid, "editor")]


@pytest.mark.asyncio
async def test_get_authorized_annotation_normalizes_forbidden_to_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Hide a known annotation when project membership is insufficient."""
    project_uuid = uuid.uuid4()

    async def forbidden(*_args: object, **_kwargs: object) -> None:
        raise HTTPException(status_code=403, detail="private membership detail")

    monkeypatch.setattr(annotations, "require_project_member", forbidden)
    session = _Session(scalar_values=[project_uuid], get_value=_annotation())

    result = await annotations._get_authorized_annotation(  # type: ignore[arg-type]
        session,
        uuid.uuid4(),
        _user(),
        minimum_role="editor",
    )

    assert result is None


@pytest.mark.asyncio
async def test_get_authorized_annotation_preserves_non_forbidden_http_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Do not swallow unrelated HTTP failures from the authorization dependency."""
    project_uuid = uuid.uuid4()

    async def unavailable(*_args: object, **_kwargs: object) -> None:
        raise HTTPException(status_code=503, detail="authorization unavailable")

    monkeypatch.setattr(annotations, "require_project_member", unavailable)
    session = _Session(scalar_values=[project_uuid])

    with pytest.raises(HTTPException) as exc_info:
        await annotations._get_authorized_annotation(  # type: ignore[arg-type]
            session,
            uuid.uuid4(),
            _user(),
        )

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "authorization unavailable"


@pytest.mark.asyncio
async def test_list_annotations_authorizes_and_maps_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authorize project access before returning mapped annotation rows."""
    project_uuid = uuid.uuid4()
    user = _user()
    annotation = _annotation(project_space_uuid=project_uuid)
    authorizations: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def require_member(
        _session: object,
        project_space_uuid: uuid.UUID,
        user_account_uuid: uuid.UUID,
        **_kwargs: object,
    ) -> str:
        authorizations.append((project_space_uuid, user_account_uuid))
        return "viewer"

    monkeypatch.setattr(annotations, "require_project_member", require_member)
    session = _Session(row_values=[annotation])

    result = await annotations.list_annotations(  # type: ignore[arg-type]
        project_uuid,
        user=user,
        session=session,
    )

    assert authorizations == [(project_uuid, user.user_account_uuid)]
    assert [item.table_annotation_uuid for item in result] == [
        annotation.table_annotation_uuid
    ]


@pytest.mark.asyncio
async def test_upsert_annotation_updates_existing_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Update body and timestamp on the existing unique table annotation."""
    project_uuid = uuid.uuid4()
    user = _user()
    existing = _annotation(project_space_uuid=project_uuid)
    original_updated_at = existing.updated_at

    async def require_member(*_args: object, **_kwargs: object) -> str:
        return "editor"

    monkeypatch.setattr(annotations, "require_project_member", require_member)
    session = _Session(scalar_values=[existing])

    result = await annotations.upsert_annotation(  # type: ignore[arg-type]
        project_uuid,
        TableAnnotationUpsertIn(
            schema_name="public",
            relation_name="customer_account",
            body="Updated annotation",
        ),
        user=user,
        session=session,
    )

    assert existing.body == "Updated annotation"
    assert existing.updated_at >= original_updated_at
    assert session.added == []
    assert session.commit_calls == 1
    assert result.body == "Updated annotation"


@pytest.mark.asyncio
async def test_upsert_annotation_creates_missing_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create a new annotation when the project/table key has no existing row."""
    project_uuid = uuid.uuid4()
    user = _user()

    async def require_member(*_args: object, **_kwargs: object) -> str:
        return "editor"

    monkeypatch.setattr(annotations, "require_project_member", require_member)
    session = _Session(scalar_values=[None])

    result = await annotations.upsert_annotation(  # type: ignore[arg-type]
        project_uuid,
        TableAnnotationUpsertIn(
            schema_name="public",
            relation_name="customer_account",
            body="New annotation",
        ),
        user=user,
        session=session,
    )

    assert len(session.added) == 1
    created = session.added[0]
    assert created.project_space_uuid == project_uuid  # type: ignore[attr-defined]
    assert created.created_by == user.user_account_uuid  # type: ignore[attr-defined]
    assert created.schema_name == "public"  # type: ignore[attr-defined]
    assert created.relation_name == "customer_account"  # type: ignore[attr-defined]
    assert session.commit_calls == 1
    assert result.body == "New annotation"


@pytest.mark.asyncio
async def test_delete_annotation_returns_uniform_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use a stable 404 when the authorized lookup returns no annotation."""

    async def missing(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(annotations, "_get_authorized_annotation", missing)

    with pytest.raises(HTTPException) as exc_info:
        await annotations.delete_annotation(  # type: ignore[arg-type]
            uuid.uuid4(),
            user=_user(),
            session=_Session(),
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "annotation not found"


@pytest.mark.asyncio
async def test_delete_annotation_deletes_authorized_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delete and commit exactly one authorized annotation record."""
    annotation = _annotation()

    async def authorized(*_args: object, **_kwargs: object) -> object:
        return annotation

    monkeypatch.setattr(annotations, "_get_authorized_annotation", authorized)
    session = _Session()

    result = await annotations.delete_annotation(  # type: ignore[arg-type]
        annotation.table_annotation_uuid,
        user=_user(),
        session=session,
    )

    assert result == {"ok": True}
    assert session.deleted == [annotation]
    assert session.commit_calls == 1
