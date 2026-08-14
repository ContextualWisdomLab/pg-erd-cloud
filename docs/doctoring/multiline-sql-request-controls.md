# Multiline SQL request controls

## Status and scope

The transitional `ApplySqlIn.sql` request remains bounded to 262,144
characters. Its request-schema contract accepts ordinary Unicode text plus tab
(`U+0009`), line feed (`U+000A`), carriage return (`U+000D`), and all printable
spacing needed by multiline DDL. It rejects `U+0000`–`U+0008`, `U+000B`,
`U+000C`, `U+000E`–`U+001F`, and `U+007F`.

This boundary prevents NUL, DEL, and other non-text controls from crossing into
logs, audit tooling, parsers, and database-driver text boundaries. It does not
make SQL safe and is not described as SQL-injection prevention. The existing
conservative PostgreSQL DDL parser and deployer/default-deny route controls
remain the legacy authorization boundary; the structured forward-engineering
workflow still rejects browser SQL as execution authority.

## Secret-safe failure behavior

FastAPI/Pydantic validation details normally include the rejected input. The
production application therefore returns a fixed `422` body for validation
failures on `/api/connections/{uuid}/apply-sql`. That response contains neither
the SQL value nor secret-like literals embedded in it. Other API validation
responses retain the standard handler.

## Evidence

- `tests/test_schema_validation.py` exhaustively covers every rejected code
  point at the beginning, middle, and end of a realistic multiline value, the
  accepted whitespace/Unicode boundaries, and the exact length limit.
- `tests/test_request_validation.py` proves the fixed response does not reflect
  hostile SQL or a secret-like literal and that production wiring registers the
  handler.
- `tests/test_api_apply_sql.py` keeps the conservative parser, authorization,
  default-deny persistent path, and DSN-redacted execution failure contracts
  separate from character validation.

Repository CI, security scans, exact-head review, and protected-branch policy
remain authoritative; focused local tests do not transfer across revisions.
