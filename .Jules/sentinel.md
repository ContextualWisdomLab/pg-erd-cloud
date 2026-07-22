## $(date +%Y-%m-%d) - Redact Sensitive Schema Comments in Public Shares
**Vulnerability:** Publicly shared schema snapshots (via `/api/share/...`) returned the entire JSON payload, which could expose sensitive internal schema comments (`comment`, `relation_comment`, `column_comment`) or sensitive data in `example_value` fields.
**Learning:** When generating share links, only specific fields should be exposed, but we export the entire `snapshot_json` from the database. A recursive sanitizer function must be applied to scrub IDOR/data leakage vectors before returning the JSON payload.
**Prevention:** Apply a recursive masking function (`_redact_sensitive_snapshot_fields`) on database JSON artifacts in read-only public endpoints.
## 2026-07-22 - Sensitive Data Leakage in Schema Exports
**Vulnerability:** The public, unauthenticated share endpoints were returning sensitive database schema metadata (comments, example values) when exporting schemas to SQL or Markdown format, failing to apply the redaction utility used for JSON payloads.
**Learning:** Data transformation functions (like snapshot_json_to_sql) should be treated as output sinks that require sanitized input, especially when the resulting file is served to unauthenticated users. The redaction logic was mistakenly limited to the JSON view endpoint.
**Prevention:** Always sanitize or redact sensitive data at the outermost layer (e.g., in the router) before passing it to downstream serializer functions or LLM prompts when the payload is destined for public exposure.
