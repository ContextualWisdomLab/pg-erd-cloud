## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-19 - URL-encoded Secret Redaction
**Vulnerability:** The error message redaction utility (`redact_dsn_error_message`) failed to fully sanitize connection secrets because `urllib.parse.urlsplit().password` returns URL-encoded strings. If an underlying database driver (like asyncpg or pymysql) outputs the error with unencoded or differently-encoded characters (like spaces as `+`), the simple string replacement would fail. Also, the word boundary logic prevented matching secrets that started or ended with special characters (like `=`).
**Learning:** Secrets should always be decoded fully (using `unquote_plus`), and all permutations (decoded, quoted, quote_plus) should be added to the redaction candidate set to account for unpredictable driver error formatting. Regex boundaries for short secret redaction must dynamically adjust based on whether the secret itself starts or ends with alphanumeric characters.
**Prevention:** When building redaction masks, explicitly decode parsed passwords with `unquote_plus`, then re-encode them to cover all variations. Conditionally apply regex boundaries based on `secret[0].isalnum()` and `secret[-1].isalnum()`.
