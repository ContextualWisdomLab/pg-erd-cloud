## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters (Extended)
**Vulnerability:** Several Pydantic string fields such as schema names, relation names, and diagram view names were missing strict validation against ASCII control characters, only relying on length constraints.
**Learning:** Incomplete validation across schemas can lead to log injection, terminal manipulation, or unintended backend behaviors if these fields are logged or processed.
**Prevention:** Consistently apply the explicit regex validation `pattern=r"^[^\x00-\x1F\x7F]+$"` on all relevant Pydantic string fields, except for fields like bodies or raw scripts that legitimately require newlines and tabs.
