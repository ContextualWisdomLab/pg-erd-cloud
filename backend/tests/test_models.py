import datetime as dt
from unittest.mock import patch
from app.models import utcnow

def test_utcnow_returns_datetime():
    """Test that utcnow returns a datetime object."""
    result = utcnow()
    assert isinstance(result, dt.datetime)

def test_utcnow_is_timezone_aware():
    """Test that the returned datetime is timezone-aware."""
    result = utcnow()
    assert result.tzinfo is not None

def test_utcnow_is_utc():
    """Test that the returned datetime uses UTC timezone."""
    result = utcnow()
    assert result.tzinfo == dt.timezone.utc

def test_utcnow_uses_now():
    """Test that utcnow actually calls dt.datetime.now."""
    mock_now = dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    with patch('app.models.dt.datetime') as mock_datetime:
        mock_datetime.now.return_value = mock_now

        result = utcnow()

        mock_datetime.now.assert_called_once_with(dt.timezone.utc)
        assert result == mock_now
