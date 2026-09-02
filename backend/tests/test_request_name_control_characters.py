"""Regression tests for control characters in user-visible request names."""

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import BaseModel, ValidationError

from app.schemas import ApiKeyCreateIn, DiagramViewCreateIn, TableAnnotationUpsertIn


RequestFactory = Callable[[str], BaseModel]


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(
            lambda value: DiagramViewCreateIn(name=value, layout_json={}),
            id="diagram-view-name",
        ),
        pytest.param(
            lambda value: TableAnnotationUpsertIn(
                schema_name=value,
                relation_name="orders",
                body="annotation",
            ),
            id="annotation-schema-name",
        ),
        pytest.param(
            lambda value: TableAnnotationUpsertIn(
                schema_name="public",
                relation_name=value,
                body="annotation",
            ),
            id="annotation-relation-name",
        ),
        pytest.param(lambda value: ApiKeyCreateIn(key_name=value), id="api-key-name"),
    ],
)
@pytest.mark.parametrize("control", ["\n", "\x1b", "\x7f", "\x85", "\x9b"])
def test_request_names_reject_c0_del_c1_controls(
    factory: RequestFactory,
    control: str,
) -> None:
    """C0, DEL, and C1 controls must not cross name-bearing API boundaries."""
    with pytest.raises(ValidationError):
        factory(f"buyer{control}name")


@pytest.mark.parametrize(
    "factory",
    [
        pytest.param(
            lambda value: DiagramViewCreateIn(name=value, layout_json={}),
            id="diagram-view-name",
        ),
        pytest.param(
            lambda value: TableAnnotationUpsertIn(
                schema_name=value,
                relation_name="orders",
                body="annotation",
            ),
            id="annotation-schema-name",
        ),
        pytest.param(
            lambda value: TableAnnotationUpsertIn(
                schema_name="public",
                relation_name=value,
                body="annotation",
            ),
            id="annotation-relation-name",
        ),
        pytest.param(lambda value: ApiKeyCreateIn(key_name=value), id="api-key-name"),
    ],
)
def test_request_names_preserve_printable_unicode(factory: RequestFactory) -> None:
    """The security boundary must preserve ordinary printable international text."""
    factory("고객 주문 2026")
