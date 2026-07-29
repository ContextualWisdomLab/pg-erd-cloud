## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2024-07-29 - Missing redaction on downstream snapshot exports
**Vulnerability:** Sensitive schema data (like column comments and example values) was exposed via public unauthenticated share link export endpoints (`export.sql`, `reversing-spec.md`, `index-design.md`) because redaction was only applied to the raw JSON endpoint, not downstream formatters.
**Learning:** Functions that transform data before HTTP delivery must still process redacted inputs when serving untrusted users. Redaction logic should ideally be applied as early as possible or centralized to avoid missing sibling endpoints.
**Prevention:** Apply `_redact_sensitive_snapshot_fields` uniformly across all public endpoints that load `SchemaSnapshotData` before passing the data to any export/serialization functions.
