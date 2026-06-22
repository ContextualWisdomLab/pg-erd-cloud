import pytest
from app.snowflake_introspect.introspect import _parse_snowflake_dsn
from app.pg_introspect.dsn_guard import DsnTargetError


@pytest.mark.asyncio
async def test_snowflake_dsn_rejects_ssrf():
    with pytest.raises(DsnTargetError, match="database host must not be localhost"):
        await _parse_snowflake_dsn("snowflake://user:pass@localhost/db")

    with pytest.raises(
        DsnTargetError, match="database host resolves to a restricted IP range"
    ):
        await _parse_snowflake_dsn("snowflake://user:pass@127.0.0.1/db")

    with pytest.raises(
        DsnTargetError, match="database host resolves to a restricted IP range"
    ):
        await _parse_snowflake_dsn("snowflake://user:pass@169.254.169.254/db")
