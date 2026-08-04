## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-04 - Fix SQL Injection in DBML Constraint Generation
**Vulnerability:** The DBML parser directly interpolated user-controlled identifiers (table names, schema names, column names) from DBML into raw SQL constraint definitions without sanitization or validation, allowing SQL statement injection if a user provided a malicious DBML string (e.g., `Table "users; DROP TABLE users" { id integer [pk] }`).
**Learning:** Never trust DBML or other schema definitions parsed from untrusted user input directly in string-interpolated SQL statements, even for DDL generation. Always use strict validation against SQL metacharacters (`;`, `"`, `'`, `--`, `/*`) for identifiers.
**Prevention:** Implement a `_validate_identifier(name: str) -> str` function that rejects metacharacters via a strict deny-list regex (`r'''['";]|--|/\*'''`) at all parsing ingestion points, causing parsing to fail with a clear ValueError early.
