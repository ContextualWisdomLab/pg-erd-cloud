## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2024-05-24 - Suppress Bandit B608 False Positives in MySQL Introspector
**Vulnerability:** Bandit raised B608 (hardcoded_sql_expressions) warnings in `app/mysql_introspect/introspect.py` due to f-string SQL construction for `WHERE {where}`.
**Learning:** The `where` clause is safely constructed using parameterized static strings (`TABLE_SCHEMA NOT IN (%s...)` or `TABLE_SCHEMA = %s`) from `_schema_filter_clause`, making the f-string construction safe from injection. Refactoring to fully static strings is unnecessarily complex for dynamic parameterized `IN` clauses.
**Prevention:** Use `# nosec B608` to suppress legitimate false positives when SAST tools flag safe string-formatting of static SQL fragments, adhering to project guidelines.
