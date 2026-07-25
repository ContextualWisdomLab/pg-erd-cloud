## $(date +%Y-%m-%d) - Redact Sensitive Schema Comments in Public Shares
**Vulnerability:** Publicly shared schema snapshots (via `/api/share/...`) returned the entire JSON payload, which could expose sensitive internal schema comments (`comment`, `relation_comment`, `column_comment`) or sensitive data in `example_value` fields.
**Learning:** When generating share links, only specific fields should be exposed, but we export the entire `snapshot_json` from the database. A recursive sanitizer function must be applied to scrub IDOR/data leakage vectors before returning the JSON payload.
**Prevention:** Apply a recursive masking function (`_redact_sensitive_snapshot_fields`) on database JSON artifacts in read-only public endpoints.

## 2024-05-28 - Unredacted Sensitive Snapshot Information Leak
**Vulnerability:** Information Disclosure where database snapshot fields containing sensitive comments and example values were not redacted when being served through unauthenticated share link export endpoints (`export.sql`, `reversing-spec.md`, and `index-design.md`).
**Learning:** Downstream spec serializers and SQL generators were reading raw JSON directly from the database without a sanitization filter layer when accessed via unauthenticated public share links, bypassing the `_redact_sensitive_snapshot_fields` check used in other unauthenticated snapshot endpoints.
**Prevention:** Apply data redaction transformations early in the data retrieval lifecycle, uniformly before data reaches any endpoint-specific business logic or downstream rendering layer, especially when dealing with unauthenticated contexts.
