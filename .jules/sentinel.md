## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Properly decoding DSN passwords for error message redaction
**Vulnerability:** URL-encoded passwords embedded in a DSN weren't fully unquoted before adding them to the redaction candidate list. `urlsplit` unquotes partially (or depending on python version) but specifically when searching error messages they may expose fully decoded strings (like spaces or `+` signs) from the driver.
**Learning:** `urlsplit().password` returns a string that may be URL-encoded or partially decoded. If the DB driver emits an error containing the fully decoded password, it won't be redacted properly unless the password candidate list includes the decoded variation (via `unquote_plus`). This causes critical information exposure.
**Prevention:** To prevent secret leakage when searching and replacing in raw error messages, you must generate and test all variations (decoded via `unquote_plus`, and re-encoded via `quote` and `quote_plus`) to account for different database driver output formats.
