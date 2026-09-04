## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2025-02-18 - Silencing Bandit False Positive SQL Injection Warnings (B608)
**Vulnerability:** Bandit B608 reports dynamic string formatting (like `f"FROM information_schema.TABLES WHERE {where} "`) as potential SQL injection vulnerabilities.
**Learning:** If the dynamic parameter is constructed entirely via internal logic (e.g., hardcoded constants like `"TABLE_SCHEMA = %s"`) rather than untrusted user input, it is completely safe.
**Prevention:** Append `# nosec B608` to the specific line performing the safe string concatenation to silence the false positive while ensuring actual parameterized data injection is correctly handled by the database cursor.
