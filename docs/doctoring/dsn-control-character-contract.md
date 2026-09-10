# DSN control-character transport contract

## Decision

`ConnectionCreateIn.dsn` rejects C0 controls (U+0000–U+001F), DEL (U+007F),
C1 controls (U+0080–U+009F), and the Unicode line and paragraph separators
U+2028/U+2029 at request validation time. The rejection happens before the DSN
is encrypted or handed to a dialect-specific parser. Printable Unicode,
percent-encoded credentials, and ordinary DSN punctuation remain valid.

This is a transport and log-integrity boundary. It is deliberately not a DSN
grammar parser, not an SSRF control, and not a replacement for secret
redaction. PostgreSQL, Snowflake, and MySQL parsers continue to validate their
own schemes and network targets.

## Why

A DSN is a structured connection string, but the request body also flows
through logs, error serialization, and operator terminals before and after
validation. Unescaped control characters and Unicode separators in
customer-submitted text enable log and terminal escape injection, and they can
split a single audit record into forged lines.

Dialect parsers are not a transport-integrity boundary: they run after the
request has already been accepted, and they do not constrain what the request
logging surface can record. Defining the contract on the visible request field
keeps the decisive check at the earliest boundary that owns the raw text.

Rejecting is preferable to sanitizing because a DSN is a machine credential.
Silently rewriting submitted connection strings would corrupt a legitimate
credential without telling the caller. A validation failure instead tells the
caller the value cannot be transported.

## Invariants

- Every covered code point fails validation at prefix, middle, and suffix
  positions of the field.
- Printable multilingual characters, percent-encoded values, and existing DSN
  punctuation are accepted unchanged.
- Validation failures never echo the submitted DSN; response redaction for
  shared validation errors remains owned by the multiline SQL/API validation
  boundary tracked in issue #764.
- Dialect parser, redaction, and DSN-focused schema tests remain green.

## Verification

- `backend/tests/test_schema_validation.py` drives all covered code points in
  prefix, middle, and suffix placements and asserts rejection, then asserts
  that a multilingual percent-encoded DSN round-trips unchanged.
- Focused backend suite (schema, DSN parser, redaction, API) passes.
- `mypy backend/app` stays clean.

Repository CI remains authoritative for the full backend suite, coverage,
SAST, and supply-chain evidence on the exact head.

## Operational monitoring and rollback

Monitor DSN validation failure rates and their response codes to distinguish
rejected hostile input from a regression that rejects legitimate credentials.
Roll back by removing the `dsn` pattern only if a verified false-positive
requires it; doing so reopens the documented log and terminal injection risk
and therefore requires a replacement transport contract and regression
evidence.

## References

PostgreSQL Global Development Group. (n.d.). *Connection strings*. PostgreSQL
Documentation. https://www.postgresql.org/docs/current/libpq-connect.html

The Unicode Consortium. (2024). *The Unicode standard* (Version 15.1.0).
https://www.unicode.org/versions/Unicode15.1.0/
