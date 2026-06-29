import datetime as dt
from app.models import utcnow

def test_utcnow():
    """Test that utcnow returns a datetime object with UTC timezone."""
    now = utcnow()
    assert isinstance(now, dt.datetime)
    assert now.tzinfo is dt.timezone.utc
