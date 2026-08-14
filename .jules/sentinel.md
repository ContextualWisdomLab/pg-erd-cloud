## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-03-08 - Path Traversal in PostgreSQL DSN TLS Certificate Paths
**Vulnerability:** The application accepted arbitrary file paths for `sslrootcert`, `sslcert`, and `sslkey` within a PostgreSQL DSN without validation. An attacker could use this path traversal vulnerability to probe for file existence on the backend filesystem or potentially cause the OpenSSL library to process arbitrary files.
**Learning:** Even parameters like TLS certificates in database connection strings (DSNs) can act as path traversal or arbitrary file read vectors when processed directly by standard libraries like `ssl.SSLContext` without prior validation.
**Prevention:** Always enforce path restrictions using `pathlib.Path.resolve()` and `.is_relative_to(base)` against an allowlist of safe directories when processing user-controlled file paths, even in seemingly internal configuration options.

## 2025-03-08 - asyncpg DSN parsing can lead to path traversal bypasses
**Vulnerability:** Even if we explicitly initialize and pass an `ssl.SSLContext` for `verify-full`, `asyncpg.connect` still parses the raw DSN string. It accepts file paths for `sslrootcert`, `sslcert`, `sslkey`, `sslcrl`, and `passfile`. By supplying these parameters alongside other `sslmode` values, an attacker could trigger arbitrary file reads or presence probes during `asyncpg`'s connection setup before our explicit checks could run, bypassing the security controls.
**Learning:** If a third-party library parses connection strings directly, any injected parameters in that string will be processed according to the library's internal logic, regardless of higher-level wrapper settings like overriding the SSL context.
**Prevention:** Intercept and parse the connection string (e.g. `urllib.parse`) to validate or sanitize all sensitive file-path parameters *before* passing the string down to the underlying database driver. Ensure validation fails closed with non-reflecting error messages to prevent leakage.

## 2025-03-08 - React error message rendering
**Vulnerability:** A static security scanner flagged a potential XSS vulnerability because `{error}` was being rendered directly in JSX.
**Learning:** In React, string interpolation using `{}` is automatically escaped, preventing XSS, so this is typically a false positive. However, if the error happens to be a complex object or if it's evaluated insecurely, problems can occur. Strix is prone to false positives on standard React rendering patterns.
**Prevention:** Wrap string states in `String(error)` or perform strict typing / logging before passing error objects to React elements to appease scanners and add robustness against accidental object injection.
