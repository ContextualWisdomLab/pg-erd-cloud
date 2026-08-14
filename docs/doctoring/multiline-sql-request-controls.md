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

`SecretSafeLegacyApplyRoute` validates this one sensitive request body before
`get_current_user` and `get_session`. A malformed, missing, oversized, or
control-bearing body therefore cannot enter authentication, metadata-session,
project lookup, credential, target, or driver work. The global sensitive-body
handler remains defense in depth: it ignores `RequestValidationError.body` and
returns the same fixed response for later validation failures. Neither boundary
parses the SQL authorization grammar; character acceptance does not authorize SQL.

## Evidence

- `tests/test_schema_validation.py` exhaustively covers every rejected code
  point at the beginning, middle, and end of a realistic multiline value, the
  accepted whitespace/Unicode boundaries, and the exact length limit.
- `tests/test_request_validation.py` proves the fixed response does not reflect
  hostile SQL or a secret-like literal, that production wiring registers the
  handler, and that invalid legacy-apply input stops before authentication or
  metadata-session dependencies.
- `tests/test_api_apply_sql.py` keeps the conservative parser, authorization,
  default-deny persistent path, and DSN-redacted execution failure contracts
  separate from character validation.

Repository CI, security scans, exact-head review, and protected-branch policy
remain authoritative; focused local tests do not transfer across revisions.

## Monitoring and rollback

Monitor the fixed validation-error counter by route and status without logging
request bodies, SQL fragments, credential-like values, or raw validation input.
An unexpected rise may indicate broken clients or hostile transport data. A
rollback must revert the route class, focused tests, schema pattern, fixed
handler, and this record together; never keep the behavior while removing its
non-reflection or pre-dependency proof.

## References

- Open Worldwide Application Security Project. (n.d.). *Logging cheat sheet*.
  OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
  This is implementation guidance for excluding or sanitizing untrusted event
  data and preventing carriage-return/line-feed log injection; it is not a
  certification source.
- The Unicode Consortium. (2025). *The Unicode standard, version 17.0—Chapter
  23: Special areas and format characters*.
  https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-23/
  This is the normative character authority used to distinguish control and
  format-code semantics from printable Unicode text.
- Yuan, H. Y., Wang, X., Yao, K., Chen, A. R., Ding, Z., & Li, Z. (2026).
  *Towards Secure Logging: Characterizing and Benchmarking Logging Code
  Security Issues with LLMs*. arXiv. https://arxiv.org/abs/2604.20211
  This empirical secure-logging study identifies log injection and sensitive
  information exposure as recurring logging-code security issue classes. It
  supports treating rejected body text as untrusted data, but does not prove
  this repository's implementation correct.
