import datetime as dt
from app.models import utcnow

def test_utcnow_returns_utc_datetime():
    """Test that utcnow returns a timezone-aware datetime in UTC."""
    result = utcnow()
    assert isinstance(result, dt.datetime)
    assert result.tzinfo is dt.timezone.utc
