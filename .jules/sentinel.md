## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2023-10-25 - Redacting Sensitive Snapshot Fields in Public Exports
**Vulnerability:** The public share link API exposed sensitive data (comments, relation comments, column comments, example values) in database schema exports like SQL, Markdown reversing specs, and Markdown index designs, bypassing the redaction that was only applied to the raw JSON payload.
**Learning:** Security redactions must be applied at the edge for all representation formats of a sensitive data source, not just the primary format, to ensure consistent data masking.
**Prevention:** Apply the `_redact_sensitive_snapshot_fields` function to the raw data structure before passing it to any downstream generator functions (like SQL builders or LLM prompts) that return data over public endpoints.
