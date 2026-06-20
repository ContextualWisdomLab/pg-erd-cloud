
## 2024-06-20 - [SSRF Bypass via DSN Query Parameters]
**Vulnerability:** `asyncpg` (and underlying `libpq`) respects connection parameters provided in the DSN query string (e.g., `?host=...` and `?hostaddr=...`). The `validate_postgres_dsn_target` function only checked `parsed.hostname`, allowing an attacker to provide a valid domain in the hostname but point the actual connection to an internal IP (like `127.0.0.1` or `169.254.169.254`) via the query string, resulting in an SSRF bypass.
**Learning:** Security validations on URLs/DSNs must account for how the underlying driver actually parses and connects to the URL, not just standard parsing mechanisms. Query parameters that can override connection properties are a common SSRF vector in database drivers.
**Prevention:** Always parse the query string of a DSN and validate any potential overrides (e.g., `host`, `hostaddr`, `port`) against the same security constraints (allowlists, restricted IPs) as the primary hostname.
