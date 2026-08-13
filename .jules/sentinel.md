## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-03-08 - Path Traversal in PostgreSQL DSN TLS Certificate Paths
**Vulnerability:** The application accepted arbitrary file paths for `sslrootcert`, `sslcert`, and `sslkey` within a PostgreSQL DSN without validation. An attacker could use this path traversal vulnerability to probe for file existence on the backend filesystem or potentially cause the OpenSSL library to process arbitrary files.
**Learning:** Even parameters like TLS certificates in database connection strings (DSNs) can act as path traversal or arbitrary file read vectors when processed directly by standard libraries like `ssl.SSLContext` without prior validation.
**Prevention:** Always enforce path restrictions using `pathlib.Path.resolve()` and `.is_relative_to(base)` against an allowlist of safe directories when processing user-controlled file paths, even in seemingly internal configuration options.
