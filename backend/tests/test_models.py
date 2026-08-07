import datetime as dt

from app.models import utcnow


def test_utcnow_returns_utc_datetime():
    result = utcnow()
    assert isinstance(result, dt.datetime)
    assert result.tzinfo is dt.timezone.utc
