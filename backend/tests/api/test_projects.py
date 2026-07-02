import uuid
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app
from app.auth import get_current_user, CurrentUser
from app.db import get_session, get_read_session
from app.schemas import ProjectMemberAddIn
from app.api.projects import (
    _ensure_owner,
    _ensure_user_exists,
    _ensure_not_changing_owner_role,
    _upsert_project_member,
)
from app.settings import settings
from app.csrf import generate_csrf_token, CSRF_HEADER_NAME

test_user = CurrentUser(
    user_account_uuid=uuid.uuid4(), subject="test-subject", display_name="Test User"
)


def mock_get_current_user():
    return test_user


app.dependency_overrides[get_current_user] = mock_get_current_user


class MockScalarResult:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items

    def first(self):
        return self.items[0] if self.items else None


class MockExecuteResult:
    def __init__(
        self, scalars=None, all_results=None, scalar_one_or_none=None, scalar_one=None
    ):
        self._scalars = scalars
        self._all_results = all_results
        self._scalar_one_or_none = scalar_one_or_none
        self._scalar_one = scalar_one

    def scalars(self):
        return MockScalarResult(self._scalars)

    def all(self):
        return self._all_results

    def scalar_one_or_none(self):
        return self._scalar_one_or_none

    def scalar_one(self):
        return self._scalar_one


class AsyncSessionMock:
    def __init__(self, execute_return=None):
        self.execute_return = execute_return
        if execute_return is None:
            self.execute = AsyncMock()
        elif not callable(execute_return):
            self.execute = AsyncMock(return_value=execute_return)
        else:
            self.execute = AsyncMock(side_effect=execute_return)

        self.add = MagicMock()
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.begin = AsyncMock()


@pytest.fixture
def client():
    # Set up client and valid CSRF token header for all requests
    c = TestClient(app)
    c.headers[CSRF_HEADER_NAME] = generate_csrf_token(settings.app_secret)
    return c


def test_list_projects(client):
    class MockProject:
        def __init__(self, uuid_val, name):
            self.project_space_uuid = uuid_val
            self.project_name = name

    p1 = MockProject(uuid.uuid4(), "Project 1")
    p2 = MockProject(uuid.uuid4(), "Project 2")

    mock_session = AsyncSessionMock(execute_return=MockExecuteResult(scalars=[p1, p2]))
    app.dependency_overrides[get_read_session] = lambda: mock_session

    response = client.get("/api/projects")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["project_name"] == "Project 1"


def test_create_project(client):
    mock_session = AsyncSessionMock()
    app.dependency_overrides[get_session] = lambda: mock_session

    response = client.post("/api/projects", json={"project_name": "New Project"})
    assert response.status_code == 200
    data = response.json()
    assert data["project_name"] == "New Project"
    assert "project_space_uuid" in data

    # Assert session methods were called
    assert mock_session.add.call_count == 2
    mock_session.flush.assert_called_once()
    mock_session.commit.assert_called_once()


def test_create_project_invalid_name(client):
    response = client.post("/api/projects", json={"project_name": ""})
    assert response.status_code == 422


def test_list_project_members(client):
    p_uuid = uuid.uuid4()
    u_uuid = uuid.uuid4()

    class MockMember:
        def __init__(self, role):
            self.project_role = role

    class MockUser:
        def __init__(self, uuid_val, subject):
            self.user_account_uuid = uuid_val
            self.oidc_subject = subject

    m = MockMember("owner")
    u = MockUser(u_uuid, "test-owner")

    mock_session = AsyncSessionMock()

    with patch(
        "app.api.projects.require_project_member", new_callable=AsyncMock
    ) as mock_require:
        mock_session.execute.return_value = MockExecuteResult(all_results=[(m, u)])
        app.dependency_overrides[get_read_session] = lambda: mock_session

        response = client.get(f"/api/projects/{p_uuid}/members")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["member_subject"] == "test-owner"
        assert data[0]["project_role"] == "owner"
        mock_require.assert_called_once()


def test_add_project_member_empty_subject(client):
    p_uuid = uuid.uuid4()

    # We must not patch out _ensure_owner if we want to hit line 199 because _ensure_owner would
    # raise HTTP 403 if it fails, which happens before line 199.
    # Actually, we can patch it to just pass so it reaches the empty subject check.
    with patch("app.api.projects._ensure_owner", new_callable=AsyncMock) as mock_owner:
        mock_owner.return_value = None

        response = client.post(
            f"/api/projects/{p_uuid}/members",
            json={"member_subject": "   ", "project_role": "viewer"},
        )

        assert response.status_code == 422
        assert "String should match pattern" in response.json()["detail"][0]["msg"]


def test_add_project_member_unauthorized(client):
    p_uuid = uuid.uuid4()

    with patch("app.api.projects._ensure_owner", new_callable=AsyncMock) as mock_owner:
        mock_owner.side_effect = HTTPException(
            status_code=403, detail="owner role required"
        )

        response = client.post(
            f"/api/projects/{p_uuid}/members",
            json={"member_subject": "new-member", "project_role": "viewer"},
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "owner role required"


def test_add_project_member_invalid_role(client):
    p_uuid = uuid.uuid4()

    response = client.post(
        f"/api/projects/{p_uuid}/members",
        json={
            "member_subject": "new-member",
            "project_role": "admin",
        },  # admin is not allowed
    )

    assert response.status_code == 422


def test_add_project_member_change_owner(client):
    p_uuid = uuid.uuid4()

    with (
        patch("app.api.projects._ensure_owner", new_callable=AsyncMock),
        patch("app.api.projects._ensure_user_exists", new_callable=AsyncMock),
        patch(
            "app.api.projects._ensure_not_changing_owner_role", new_callable=AsyncMock
        ) as mock_role_check,
    ):
        mock_role_check.side_effect = HTTPException(
            status_code=400, detail="cannot change owner role via invite endpoint"
        )

        response = client.post(
            f"/api/projects/{p_uuid}/members",
            json={"member_subject": "existing-owner", "project_role": "viewer"},
        )

        assert response.status_code == 400
        assert (
            response.json()["detail"] == "cannot change owner role via invite endpoint"
        )


@pytest.mark.asyncio
async def test_ensure_owner_success():
    session = AsyncSessionMock(
        execute_return=MockExecuteResult(scalar_one_or_none="owner")
    )
    await _ensure_owner(session, uuid.uuid4(), uuid.uuid4())
    # Should not raise any exception


@pytest.mark.asyncio
async def test_ensure_owner_failure():
    session = AsyncSessionMock(
        execute_return=MockExecuteResult(scalar_one_or_none="viewer")
    )
    with pytest.raises(HTTPException) as exc_info:
        await _ensure_owner(session, uuid.uuid4(), uuid.uuid4())
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "owner role required"


@pytest.mark.asyncio
async def test_ensure_user_exists_already_exists():
    class MockUser:
        def __init__(self):
            self.user_account_uuid = uuid.uuid4()
            self.oidc_subject = "test-subject"

    mock_u = MockUser()
    session = AsyncSessionMock(execute_return=MockExecuteResult(scalars=[mock_u]))

    user = await _ensure_user_exists(session, "test-subject")
    assert user == mock_u
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_user_exists_created():
    session = AsyncSessionMock(execute_return=MockExecuteResult(scalars=[]))

    user = await _ensure_user_exists(session, "new-subject")
    assert user.oidc_subject == "new-subject"
    session.add.assert_called_once()
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_ensure_not_changing_owner_role_success():
    session = AsyncSessionMock(
        execute_return=MockExecuteResult(scalar_one_or_none="viewer")
    )
    await _ensure_not_changing_owner_role(session, uuid.uuid4(), uuid.uuid4())
    # Should not raise any exception


@pytest.mark.asyncio
async def test_ensure_not_changing_owner_role_failure():
    session = AsyncSessionMock(
        execute_return=MockExecuteResult(scalar_one_or_none="owner")
    )
    with pytest.raises(HTTPException) as exc_info:
        await _ensure_not_changing_owner_role(session, uuid.uuid4(), uuid.uuid4())
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "cannot change owner role via invite endpoint"


@pytest.mark.asyncio
async def test_upsert_project_member():
    session = AsyncSessionMock(execute_return=MockExecuteResult(scalar_one="viewer"))

    role = await _upsert_project_member(session, uuid.uuid4(), uuid.uuid4(), "viewer")
    assert role == "viewer"
    session.execute.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_add_project_member_handler_success():
    p_uuid = uuid.uuid4()
    body = ProjectMemberAddIn(member_subject="new-user", project_role="editor")

    with (
        patch("app.api.projects._ensure_owner", new_callable=AsyncMock),
        patch(
            "app.api.projects._ensure_user_exists", new_callable=AsyncMock
        ) as mock_user,
        patch(
            "app.api.projects._ensure_not_changing_owner_role", new_callable=AsyncMock
        ),
        patch(
            "app.api.projects._upsert_project_member", new_callable=AsyncMock
        ) as mock_upsert,
    ):

        class MockUser:
            def __init__(self):
                self.user_account_uuid = uuid.uuid4()
                self.oidc_subject = "new-user"

        mock_u = MockUser()
        mock_user.return_value = mock_u
        mock_upsert.return_value = "editor"

        session = AsyncSessionMock()

        from app.api.projects import add_project_member

        result = await add_project_member(p_uuid, body, test_user, session)

        assert result.member_subject == "new-user"
        assert result.project_role == "editor"


@pytest.mark.asyncio
async def test_add_project_member_no_subject_raises_400():
    from app.api.projects import add_project_member
    from app.schemas import ProjectMemberAddIn

    class FakeSession:
        pass

    class FakeUser:
        user_account_uuid = uuid.uuid4()

    p_uuid = uuid.uuid4()
    body = ProjectMemberAddIn(member_subject="a", project_role="viewer")
    body.member_subject = "   "  # Bypass validator

    with pytest.raises(HTTPException) as exc_info:
        import app.api.projects

        original = app.api.projects._ensure_owner
        app.api.projects._ensure_owner = AsyncMock()
        try:
            await add_project_member(p_uuid, body, FakeUser(), FakeSession())
        finally:
            app.api.projects._ensure_owner = original

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "member_subject required"
