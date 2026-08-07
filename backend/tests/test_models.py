"""Direct contracts for model-layer timestamp helpers."""

from __future__ import annotations

import datetime as dt
from unittest import mock

from app.models import utcnow


def test_utcnow_returns_timezone_aware_utc_value() -> None:
    """Return a UTC-aware timestamp close to the current wall-clock value."""
    now = utcnow()

    assert isinstance(now, dt.datetime)
    assert now.tzinfo is dt.timezone.utc
    assert abs((dt.datetime.now(dt.timezone.utc) - now).total_seconds()) < 1.0


@mock.patch("app.models.dt.datetime")
def test_utcnow_delegates_to_datetime_now_in_utc(mock_datetime: mock.Mock) -> None:
    """Call ``datetime.now`` with UTC rather than constructing a naive value."""
    expected = mock.Mock()
    mock_datetime.now.return_value = expected

    assert utcnow() is expected
    mock_datetime.now.assert_called_once_with(dt.timezone.utc)
