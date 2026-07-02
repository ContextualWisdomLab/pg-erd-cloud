from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.me import router
from app.auth import CurrentUser, get_current_user
from app.settings import settings

app = FastAPI()
app.include_router(router)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def _current_user(subject: str = "customer-owner") -> CurrentUser:
    return CurrentUser(
        user_account_uuid=uuid.uuid4(),
        subject=subject,
        display_name="Customer Owner",
    )


def test_me_marks_support_operator_from_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "support_operator_subjects", "support-operator")
    app.dependency_overrides[get_current_user] = lambda: _current_user(
        "support-operator"
    )

    response = TestClient(app).get("/api/me")

    assert response.status_code == 200
    assert response.json()["subject"] == "support-operator"
    assert response.json()["support_operator"] is True


def test_me_defaults_support_operator_to_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "support_operator_subjects", "support-operator")
    app.dependency_overrides[get_current_user] = lambda: _current_user(
        "customer-owner"
    )

    response = TestClient(app).get("/api/me")

    assert response.status_code == 200
    assert response.json()["subject"] == "customer-owner"
    assert response.json()["support_operator"] is False
