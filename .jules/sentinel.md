## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Handling False Positive SQL Injection (B608)
**Vulnerability:** Bandit flagged string-based SQL queries using safe placeholders (f-strings with validated structural data, not direct input) as medium-severity vulnerabilities.
**Learning:** Automated security scans can misidentify query builder strings as SQL injections when the actual runtime execution uses parameterized cursors safely.
**Prevention:** Append `# nosec B608` to the specific SQL formatting strings where only safe structural components (like schema filters) are concatenated, preventing CI failure.
