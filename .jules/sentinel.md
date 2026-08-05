## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-14 - Fix incomplete DSN secret redaction and over-redaction
**Vulnerability:** URL-encoded secrets in driver error messages were only partially checked (using `urllib.parse.urlsplit().password` which returns percent-encoded values like `%20` or `+`), leaving un-encoded variants exposed. Additionally, short secrets could be improperly bounded, causing over-redaction (e.g. corrupting 'password' when secret was 'pass', or failing to redact non-alphanumeric bounded short secrets).
**Learning:** Raw DSN parsing requires explicit decoding (`unquote_plus`) and systematic re-encoding (`quote`, `quote_plus`) to handle all variations of DB driver output formats. Regular expression boundaries (`\b` or similar) do not work universally when secrets begin or end with non-alphanumeric characters.
**Prevention:** Explicitly apply `.isalnum()` checks to the first and last characters of a short secret before conditionally appending negative lookbehinds/lookaheads for word boundaries. Always decode fully before adding variations to redaction candidate lists.
