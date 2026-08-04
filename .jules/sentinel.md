## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-03 - [DSN Redaction Bypass]
**Vulnerability:** DSN redaction logic bypassed credentials in `urllib.parse.urlsplit` for non-standard DSNs lacking `://` (for example, `scheme:user:password@host/db`) because `netloc` was not populated.
**Learning:** `urlsplit` has varying behavior when slashes are omitted, often placing credentials in `path`; blindly splitting at the first colon can then mistake scheme-less userinfo for a scheme and can discard query secrets whose values contain colons.
**Prevention:** When `netloc` is missing, preserve the complete scheme-less DSN and parse it as an authority. Only add a second interpretation after removing a validated leading scheme token when the pre-`@` structure contains both scheme and userinfo separators. Preserve the full query in every interpretation, extract encoded and decoded secret candidates, and cover scheme-less userinfo plus query values containing colons with regression tests.
