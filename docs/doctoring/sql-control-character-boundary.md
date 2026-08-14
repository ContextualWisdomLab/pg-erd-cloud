# SQL request control-character boundary

Status: **Implemented** for the existing `ApplySqlIn` request schema. This is a
transport and log-integrity guard; it is not an SQL-injection defense and does
not broaden the deterministic forward-DDL allowlist.

## Contract

Forward-engineering SQL is multiline text. Space, tab (`U+0009`), line feed
(`U+000A`), carriage return (`U+000D`), printable Unicode, and the existing
262,144-character maximum remain supported. The request schema rejects:

- `U+0000` through `U+0008`;
- `U+000B` and `U+000C`;
- `U+000E` through `U+001F`;
- `U+007F`.

The guard runs before the database lookup, SQL parser, connection recovery, or
driver boundary. An invalid value is converted to one fixed invalid sentinel
before Pydantic produces its validation error. FastAPI can therefore serialize
the standard `422` response without reflecting the submitted SQL, comments, or
string literals through the error `input` field. Request logging records route,
status, duration, request identifier, and client address only; it does not log
the request body.

The conservative structured parser and statement allowlist remain the actual
execution authorization boundary. Passing this character check is never proof
that SQL is supported or safe to execute.

## Verification

Parameterized schema tests exercise every rejected code point at the start,
middle, and end of a SQL payload. A realistic multiline request verifies that
tab, CR, LF, Unicode identifiers, comments, string literals, spaces, and
punctuation are preserved. Model and API tests assert that a distinctive secret
inside rejected SQL is absent from both validation errors and the HTTP response.

## Operations and rollback

Monitor `422` rates on the apply-SQL route without adding request bodies or
submitted SQL to telemetry. A sudden increase may identify a client encoding
regression. Rollback is a normal application rollback; removing only this guard
would reopen the transport/log-integrity risk and requires a replacement
redaction boundary first. No schema migration, dependency, or target-database
change is involved.

## References

Open Worldwide Application Security Project. (n.d.). *Logging cheat sheet*.
https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

The Unicode Consortium. (2024). *The Unicode standard, version 16.0.0: Control
codes*. https://www.unicode.org/versions/Unicode16.0.0/
