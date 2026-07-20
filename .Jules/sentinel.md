## 2024-07-20 - Redact Sensitive Schema Comments in Public Shares
**Vulnerability:** Publicly shared schema snapshots (via `/api/share/...`) returned the entire JSON payload, which could expose sensitive internal schema comments (`comment`, `relation_comment`, `column_comment`) or sensitive data in `example_value` fields.
**Learning:** When generating share links, only specific fields should be exposed, but we export the entire `snapshot_json` from the database. A recursive sanitizer function must be applied to scrub IDOR/data leakage vectors before returning the JSON payload.
**Prevention:** Apply a recursive masking function (`_redact_sensitive_snapshot_fields`) on database JSON artifacts in read-only public endpoints.

## 2024-07-20 - Redact Sensitive Schema Comments in Public Share Exports
**Vulnerability:** Publicly shared schema snapshot export routes (SQL, DB Reversing Spec, Index Design Spec) returned the entire JSON payload without redacting sensitive fields.
**Learning:** When generating share links and associated artifacts, only specific fields should be exposed. The recursive sanitizer function (`_redact_sensitive_snapshot_fields`) must be applied to scrub IDOR/data leakage vectors before passing the JSON payload to export formatters.
**Prevention:** Always apply the recursive masking function (`_redact_sensitive_snapshot_fields`) on database JSON artifacts in read-only public endpoints before serialization or exporting.
