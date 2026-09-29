## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-28 - Improve DSN Secret Redaction
**Vulnerability:** URL-encoded passwords (like those containing '%20' or '+') were not fully redacted from DSN strings because 'urllib.parse.urlsplit().password' does not decode the string fully. Additionally, short passwords bounded by non-alphanumeric characters (like '!sec') bypassed redaction due to strict boundary regex lookbehinds.
**Learning:** When redacting URL-encoded secrets, you must explicitly decode them using unquote_plus and generate all variations (decoded, quote, and quote_plus) to account for driver output formats. The boundary logic must check if the first/last characters are alphanumeric before asserting word boundaries.
**Prevention:** Always decode urlsplit secrets fully, apply variations during redaction, and ensure dynamic boundary regex patterns condition lookaheads/lookbehinds on the alphanumeric status of the edges of the secret.
