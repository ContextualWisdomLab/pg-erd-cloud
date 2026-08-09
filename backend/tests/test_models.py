import datetime as dt

from app.models import utcnow


def test_utcnow():
    """Verify that utcnow() returns a timezone-aware UTC datetime close to the current time."""
    before = dt.datetime.now(dt.timezone.utc)
    now = utcnow()
    after = dt.datetime.now(dt.timezone.utc)

    assert isinstance(now, dt.datetime)
    assert now.tzinfo == dt.timezone.utc
    assert before <= now <= after
