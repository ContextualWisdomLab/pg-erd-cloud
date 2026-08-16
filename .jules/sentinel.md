## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters (Part 2)
**Vulnerability:** More user-provided string fields (like names, SQL, and DBML) lacked strict validation against control characters.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters. For fields explicitly requiring newlines or tabs (e.g., `body`, `layout_json`, `sql`, `dbml`), use `pattern=r'^[^\x00-\x08\x0B\x0C\x0E-\x1F\x7F]+$'` to safely allow whitespace controls while blocking dangerous terminal escapes.
## 2025-02-18 - Preventing DoS via Pydantic Schema `max_length` Reduction
**Vulnerability:** STRIX CI detected a resource exhaustion (DoS) risk due to excessively high `max_length` limits on large text fields (`ApplySqlIn.sql`, `DbmlConvertIn.dbml`, `TableAnnotationUpsertIn.body`, `ConnectionCreateIn.dsn`).
**Learning:** Overly permissive `max_length` boundaries can allow malicious payloads to exhaust CPU and memory during Pydantic validation and downstream parsing, leading to Denial of Service.
**Prevention:** Always bound input lengths to reasonable, business-driven limits. Reduced `max_length` bounds on high-risk fields significantly (e.g. `262_144` -> `16_000` for SQL, `524_288` -> `65_536` for DBML, `10_000` -> `2_000` for annotations).
