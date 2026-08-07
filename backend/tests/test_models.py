import datetime as dt
from unittest import mock

from app.models import utcnow


def test_utcnow_returns_utc_datetime():
    result = utcnow()
    assert isinstance(result, dt.datetime)
    assert result.tzinfo is dt.timezone.utc


@mock.patch("app.models.dt.datetime")
def test_utcnow_calls_datetime_now(mock_datetime):
    # Setup mock behavior so it acts somewhat like standard datetime
    mock_datetime.now.return_value = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
    mock_datetime.timezone = dt.timezone

    utcnow()
    mock_datetime.now.assert_called_once_with(dt.timezone.utc)
