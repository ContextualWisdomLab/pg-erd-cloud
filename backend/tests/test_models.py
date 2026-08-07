import datetime as dt

from app.models import utcnow


def test_utcnow():
    now = utcnow()
    assert isinstance(now, dt.datetime)
    assert now.tzinfo == dt.timezone.utc

    delta = dt.datetime.now(dt.timezone.utc) - now
    assert delta.total_seconds() < 5
