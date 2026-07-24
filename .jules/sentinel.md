## 2026-07-10 - Redact Sensitive Schema Comments in Public Shares
**Vulnerability:** Publicly shared schema snapshots (via `/api/share/...`) returned the entire stored JSON payload, which could expose sensitive internal schema comments (`comment`, `relation_comment`, `column_comment`) or sensitive strings in `example_value` fields to unauthenticated readers.
**Learning:** Share endpoints export `snapshot_json` verbatim from the database, so field-level exposure decisions must be enforced at the read boundary; a recursive sanitizer has to scrub sensitive fields before the payload leaves the API.
**Prevention:** Apply a recursive masking function (`_redact_sensitive_snapshot_fields`) to database JSON artifacts in read-only public endpoints.

## 2026-07-10 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) relied on length constraints alone, admitting C0/C1 control characters.
**Learning:** Control characters in stored names enable log injection (CRLF), null-byte injection, and terminal escape injection wherever the strings are later logged or rendered.
**Prevention:** Use explicit regex validation that blocks C0/C1 control ranges (for example `r'^[^\x00-\x1F\x7F-\x9F]+$'`) with a Pydantic v2-friendly API such as `Field(pattern=...)` or `StringConstraints(pattern=...)`.

## 2026-07-07 - Enhance AES Key Derivation with HKDF and Legacy Fallback
**Vulnerability:** AES keys were derived from `APP_SECRET` with a raw SHA-256 hash, weakening protection when the secret has sub-optimal length or entropy distribution.
**Learning:** Upgrading key derivation is a breaking change for already-encrypted rows (stored DB credentials); a legacy-derivation fallback loop is required during the migration window so existing data stays decryptable.
**Prevention:** Use standardized KDFs (HKDF, PBKDF2) for key derivation from the start rather than direct hash calls, and plan a compatibility path before changing any KDF.
