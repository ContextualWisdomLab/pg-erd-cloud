"""Regression tests for control characters in request identity fields."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas import (
    ApiKeyCreateIn,
    ConnectionCreateIn,
    DiagramViewCreateIn,
    ProjectCreateIn,
    ProjectMemberAddIn,
    TableAnnotationUpsertIn,
)


RequestFactory = Callable[[str], BaseModel]


_NAME_FACTORIES: tuple[RequestFactory, ...] = (
    lambda value: ProjectCreateIn(project_name=value),
    lambda value: ConnectionCreateIn(conn_name=value, dsn="postgresql://example/test"),
    lambda value: DiagramViewCreateIn(name=value, layout_json={}),
    lambda value: TableAnnotationUpsertIn(
        schema_name=value,
        relation_name="orders",
        body="annotation",
    ),
    lambda value: TableAnnotationUpsertIn(
        schema_name="public",
        relation_name=value,
        body="annotation",
    ),
    lambda value: ApiKeyCreateIn(key_name=value),
)


@pytest.mark.parametrize("factory", _NAME_FACTORIES)
@pytest.mark.parametrize("control", ["\n", "\x1b", "\x7f", "\x85", "\x9b"])
def test_request_names_reject_c0_del_c1_controls(
    factory: RequestFactory,
    control: str,
) -> None:
    """C0, DEL, and C1 controls must not cross name-bearing API boundaries."""
    with pytest.raises(ValidationError):
        factory(f"buyer{control}name")


def test_member_subject_rejects_c1_control() -> None:
    """Opaque member subjects must not carry terminal-control bytes either."""
    with pytest.raises(ValidationError):
        ProjectMemberAddIn(member_subject="buyer\x9bname")


@pytest.mark.parametrize("factory", _NAME_FACTORIES)
def test_request_names_preserve_printable_unicode(factory: RequestFactory) -> None:
    """The security boundary must preserve ordinary printable international text."""
    factory("고객 주문 2026")
