import datetime as dt
from unittest import mock

from app.models import utcnow


def test_utcnow() -> None:
    """Verify that utcnow returns a timezone-aware UTC value near the current time."""
    now = utcnow()
    assert isinstance(now, dt.datetime)
    assert now.tzinfo is dt.timezone.utc

    delta = dt.datetime.now(dt.timezone.utc) - now
    assert abs(delta.total_seconds()) < 1.0


@mock.patch("app.models.dt.datetime")
def test_utcnow_calls_now(mock_datetime: mock.Mock) -> None:
    """Verify that utcnow delegates to datetime.now with the UTC timezone."""
    mock_now = mock.Mock()
    mock_datetime.now.return_value = mock_now

    result = utcnow()

    mock_datetime.now.assert_called_once_with(dt.timezone.utc)
    assert result == mock_now
