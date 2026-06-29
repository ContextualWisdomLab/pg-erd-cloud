## 2025-02-21 - [Okta SSRF vulnerability in Snowflake DSN authenticator parsing]
**Vulnerability:** Found a Server-Side Request Forgery (SSRF) bypass in Snowflake DSN parsing for Okta authenticators via the `.endswith(".okta.com")` string check.
**Learning:** The simple `.endswith` check permitted inputs like `attacker-okta.com` or potentially backslash manipulation in `urllib.parse` parsing.
**Prevention:** Always use precise regex patterns (`^([a-zA-Z0-9-]+\.)*(okta|oktapreview)\.com$`) or strict URI structural inspection to validate target URLs for SSRF protections rather than naive substring matching.
