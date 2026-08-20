"""Integration tests for the authenticated project-list endpoint."""

from __future__ import annotations

import datetime as dt
from typing import Any
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.projects import router
from app.auth import CurrentUser, get_current_user
from app.db import get_read_session
from app.models import ProjectSpace


class _FakeScalars:
    """Minimal scalar-result adapter for the project-list query."""

    def __init__(self, projects: list[ProjectSpace]) -> None:
        self._projects = projects

    def all(self) -> list[ProjectSpace]:
        """Return the configured project rows in database order."""

        return list(self._projects)


class _FakeResult:
    """Minimal SQLAlchemy result surface used by the route."""

    def __init__(self, projects: list[ProjectSpace]) -> None:
        self._projects = projects

    def scalars(self) -> _FakeScalars:
        """Expose project rows through SQLAlchemy's scalar-result shape."""

        return _FakeScalars(self._projects)


class _FakeReadSession:
    """Record the query and return a deterministic project result."""

    def __init__(self, projects: list[ProjectSpace]) -> None:
        self._projects = projects
        self.executed_statements: list[Any] = []

    async def execute(self, statement: Any) -> _FakeResult:
        """Record one statement and return the configured rows."""

        self.executed_statements.append(statement)
        return _FakeResult(self._projects)


def _project(project_uuid: str, name: str, created_at: dt.datetime) -> ProjectSpace:
    """Build one deterministic project row for endpoint projection tests."""

    return ProjectSpace(
        project_space_uuid=uuid.UUID(project_uuid),
        project_name=name,
        created_by_user_uuid=uuid.UUID(
            "018f5f45-9f18-7b65-b9d8-8d9acbc4ed43"
        ),
        created_at=created_at,
    )


@pytest.mark.parametrize(
    ("projects", "expected_payload"),
    [
        ([], []),
        (
            [
                _project(
                    "018f5f45-a0a1-7a2b-91bd-c1fc65b9b111",
                    "Newest Project",
                    dt.datetime(2026, 8, 15, 12, 0, tzinfo=dt.timezone.utc),
                ),
                _project(
                    "018f5f45-a0a1-7a2b-91bd-c1fc65b9b222",
                    "Older Project",
                    dt.datetime(2026, 8, 14, 12, 0, tzinfo=dt.timezone.utc),
                ),
            ],
            [
                {
                    "project_space_uuid": (
                        "018f5f45-a0a1-7a2b-91bd-c1fc65b9b111"
                    ),
                    "project_name": "Newest Project",
                },
                {
                    "project_space_uuid": (
                        "018f5f45-a0a1-7a2b-91bd-c1fc65b9b222"
                    ),
                    "project_name": "Older Project",
                },
            ],
        ),
    ],
)
def test_list_projects_returns_exact_authorized_projection(
    projects: list[ProjectSpace],
    expected_payload: list[dict[str, str]],
) -> None:
    """Return empty and populated lists through the public HTTP boundary."""

    current_user = CurrentUser(
        user_account_uuid=uuid.UUID(
            "018f5f45-9f18-7b65-b9d8-8d9acbc4ed43"
        ),
        subject="test_subject",
        display_name="Test User",
    )
    session = _FakeReadSession(projects)
    application = FastAPI()
    application.include_router(router)

    def current_user_override() -> CurrentUser:
        """Return the deterministic authenticated principal."""

        return current_user

    def read_session_override() -> _FakeReadSession:
        """Return the isolated deterministic read session."""

        return session

    application.dependency_overrides[get_current_user] = current_user_override
    application.dependency_overrides[get_read_session] = read_session_override

    with TestClient(application) as client:
        response = client.get("/api/projects")

    assert response.status_code == 200
    assert response.json() == expected_payload
    assert len(session.executed_statements) == 1

    compiled = session.executed_statements[0].compile()
    assert current_user.user_account_uuid in compiled.params.values()
    assert "project_member.user_account_uuid" in str(compiled)
