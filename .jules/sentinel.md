## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.
## 2026-08-03 - [DSN Redaction Bypass]
**Vulnerability:** DSN redaction logic bypassed credentials in `urllib.parse.urlsplit` for non-standard DSNs lacking `://` (e.g., `scheme:user:password@host/db`) because `netloc` was not populated.
**Learning:** `urlsplit` has varying behavior depending on whether a scheme includes underscores or lacks slashes, placing credentials in the `path` and skipping redaction routines that only look at `netloc`/`password`.
**Prevention:** Always fall back to splitting on `:` and substituting a generic scheme (like `http://`) before re-parsing with `urlsplit` if `netloc` is missing from the initial parse, ensuring embedded secrets are still correctly extracted and masked.
## 2026-08-04 - [DSN Redaction Bypass on Non-standard Formats]
**Vulnerability:** DSN redaction logic bypassed credentials for scheme-less DSNs (e.g., `user:pass@host/db`), custom schemes without slashes, and bare `user:pass` strings because it relied strictly on `urllib.parse.urlsplit` which treats the userinfo as the scheme if `://` is missing. It also bypassed short secrets when embedded in strings.
**Learning:** Security redaction functions must proactively handle hostile, malformed, or unusual inputs that regex/URL parsers drop or misinterpret.
**Prevention:** Implement robust fallbacks: use `@` splitting directly to extract userinfo for scheme-less parsing, correctly handle multiple colons, explicitly search for lone `user:pass` formatted heuristics, and apply dual-pattern regex for embedded short secrets (while safeguarding known parameter names like "password").
## 2026-08-04 - [undici Dependencies Security Updates]
**Vulnerability:** The frontend `package-lock.json` contained an outdated transitive dependency on `undici@7.28.0` via `jsdom`, which is vulnerable to multiple CVEs including CRLF injection, desynchronization, and cross-user information disclosure (CVE-2026-15157, CVE-2026-16728, CVE-2026-14643, CVE-2026-16729).
**Learning:** Tools like `jsdom` bring in network-related dependencies like `undici`. When OSV scanner detects vulnerabilities in the frontend package lock, adding a direct override or explicit dependency ensures it is updated.
**Prevention:** Always bump frontend dependencies by applying `"pnpm": { "overrides": ... }` or directly injecting it into package overrides, then recreating the lock file.
