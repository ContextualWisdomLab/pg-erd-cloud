import datetime as dt
from unittest import mock

from app.models import utcnow

def test_utcnow():
    """Test that utcnow returns a timezone-aware datetime in UTC."""
    now = utcnow()
    assert isinstance(now, dt.datetime)
    assert now.tzinfo is not None
    assert now.tzinfo == dt.timezone.utc

    # Assert it's reasonably close to the actual current time
    assert (dt.datetime.now(dt.timezone.utc) - now).total_seconds() < 1.0

@mock.patch("app.models.dt.datetime")
def test_utcnow_calls_now(mock_datetime):
    """Test that utcnow calls datetime.now with dt.timezone.utc."""
    # Set up the mock to return a specific value
    mock_now = mock.Mock()
    mock_datetime.now.return_value = mock_now

    # Call the function
    result = utcnow()

    # Verify datetime.now was called with UTC timezone
    mock_datetime.now.assert_called_once_with(dt.timezone.utc)

    # Verify it returns exactly what datetime.now returned
    assert result == mock_now
