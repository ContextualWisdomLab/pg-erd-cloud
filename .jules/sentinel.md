## 2025-02-28 - Snowflake DSN Authenticator SSRF
**Vulnerability:** The Snowflake DSN parser accepted arbitrary URLs in the `authenticator` query parameter without validation, leading to potential SSRF (Server-Side Request Forgery). The connector would make HTTP POST requests to this URL.
**Learning:** Third-party database connectors often accept extensive configuration parameters (like custom auth endpoints) that can be manipulated by malicious users if passed directly from user input (like a connection string).
**Prevention:** Strictly validate any URL or "custom endpoint" parameters in user-supplied connection strings against a safe allowlist (like `.okta.com` for Snowflake) or known safe constants.
