import uuid
import datetime as dt

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.projects import router
from app.auth import CurrentUser, get_current_user
from app.db import get_read_session
from app.models import ProjectSpace

app = FastAPI()
app.include_router(router)

class FakeScalars:
    def __init__(self, data: list) -> None:
        self.data = data

    def all(self) -> list:
        return self.data

class FakeResult:
    def __init__(self, data: list) -> None:
        self.data = data

    def scalars(self) -> FakeScalars:
        return FakeScalars(self.data)

class FakeSession:
    def __init__(self, execute_result: list | None = None) -> None:
        self.execute_result = execute_result or []
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        pass

    async def commit(self) -> None:
        pass

    async def execute(
        self, stmt: object, *args: object, **kwargs: object
    ) -> FakeResult:
        return FakeResult(self.execute_result)


def fake_get_current_user() -> CurrentUser:
    return CurrentUser(
        user_account_uuid=uuid.uuid4(), subject="test_user", display_name=None
    )


app.dependency_overrides[get_current_user] = fake_get_current_user


def test_list_projects_success() -> None:
    """Test that listing projects returns the correct payload."""
    fake_project = ProjectSpace(
        project_space_uuid=uuid.uuid4(),
        project_name="Test Project",
        created_by_user_uuid=uuid.uuid4(),
        created_at=dt.datetime.now(dt.timezone.utc),
    )

    def fake_get_read_session() -> FakeSession:
        return FakeSession([fake_project])

    app.dependency_overrides[get_read_session] = fake_get_read_session

    client = TestClient(app)
    response = client.get("/api/projects")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["project_name"] == "Test Project"
    assert data[0]["project_space_uuid"] == str(fake_project.project_space_uuid)


def test_list_projects_empty() -> None:
    """Test that listing projects returns an empty list when no projects exist."""
    def fake_get_read_session() -> FakeSession:
        return FakeSession([])

    app.dependency_overrides[get_read_session] = fake_get_read_session

    client = TestClient(app)
    response = client.get("/api/projects")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0
