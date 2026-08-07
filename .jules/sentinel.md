## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-07 - Mitigating DoS in String Split Operations
**Vulnerability:** Unbounded string allocations during parsing via `split` and `map` (like decoding handle strings into columns) can cause high memory allocation spikes and denial of service (DoS) when fed excessively long strings.
**Learning:** Functions that parse handles should implement reasonable length bounds on inputs before allocating intermediate arrays via `split` and `map`.
**Prevention:** Implement an explicit maximum length check (e.g. `if (str.length > 512) return null;`) before parsing string identifiers to prevent buffer exhaustion.
