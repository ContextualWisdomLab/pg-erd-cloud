# Apply SQL transport validation

## Status and boundary

Implemented. `ApplySqlIn` rejects U+0000–U+0008, U+000B, U+000C,
U+000E–U+001F, and U+007F–U+009F before authorization or database access.
Horizontal tab, line feed, and carriage return remain accepted so ordinary
multiline SQL is not damaged. The existing 262,144-character request limit and
downstream PostgreSQL DDL allowlist remain authoritative.

This validation protects transport, parser, driver, and audit-log integrity. It
is not SQL-injection prevention and does not expand the permitted DDL grammar.
Printable Unicode and SQL metacharacters are preserved for the dialect-owned
parser to classify.

## Failure privacy

FastAPI request-validation errors normally carry the rejected `input`. The
application-wide request-validation handler removes that field before forming
a 422 response. It retains the field location, error type, and safe diagnostic
message. Middleware records request metadata and status only; it does not log
the rejected body. This boundary also prevents connection strings and other
secret-bearing request fields from being reflected by validation responses.

## Acceptance evidence

- Every rejected C0, DEL, and C1 code point is tested at the beginning, middle,
  and end of a realistic DDL request.
- Tab, LF, CR, quoted Unicode identifiers, and existing length validation are
  preserved.
- An HTTP-boundary regression proves a secret-bearing SQL literal appears in
  neither the response nor captured logs.
- The conservative SQL parser/allowlist remains a separate execution gate.

## References

Bray, T. (2017). *The JavaScript Object Notation (JSON) data interchange
format* (RFC 8259). RFC Editor. https://www.rfc-editor.org/rfc/rfc8259.html
This defines the JSON string transport rules whose rejected-input diagnostics must not reflect raw request values.

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation:
Lexical structure*. https://www.postgresql.org/docs/18/sql-syntax-lexical.html
This preserves PostgreSQL-owned lexical authority, including multiline formatting and quoted identifiers, after transport validation.

Unicode Consortium. (2025). *The Unicode standard, version 17.0: Chapter 23—
Special areas and format characters*.
https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-23/
This supports distinguishing transport-unsafe control characters from printable Unicode that must remain available to the SQL parser.
