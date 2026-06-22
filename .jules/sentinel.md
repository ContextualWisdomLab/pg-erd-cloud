## 2025-02-28 - Snowflake DSN Authenticator SSRF
**Vulnerability:** The Snowflake DSN parser accepted arbitrary URLs in the `authenticator` query parameter without validation, leading to potential SSRF (Server-Side Request Forgery). The connector would make HTTP POST requests to this URL.
**Learning:** Third-party database connectors often accept extensive configuration parameters (like custom auth endpoints) that can be manipulated by malicious users if passed directly from user input (like a connection string).
**Prevention:** Strictly validate any URL or "custom endpoint" parameters in user-supplied connection strings against a safe allowlist (like `.okta.com` for Snowflake) or known safe constants.
2024-06-21 - [Prevent HMAC public key forgery in JWT algorithms]
**Vulnerability:** The application parsed `OIDC_ALGORITHMS` without blocking symmetric algorithms (like `HS256`). This allows an attacker to exploit the algorithm mechanism, forging a JWT token by treating the public JWKS key as an HMAC secret if the JWT decoder allows the `HS256` header algorithm.
**Learning:** You must not blindly trust the JWT token header algorithm (`alg`). You must explicitly supply a whitelist of acceptable algorithms to your JWT library AND ensure that public key verification configurations explicitly filter out symmetric algorithm families (`HS*`).
**Prevention:** Filter out `HS` algorithms when reading allowed configuration algorithms, and explicitly block them in allowlists passed to JWT decoders when dealing with RS256/ES256 public keys.
2026-06-21 - [Lack of Rate Limiting on Token Revocation Endpoint]
**Vulnerability:** The `/api/auth/revoke` token revocation endpoint lacked rate limiting, making it vulnerable to denial-of-service (DoS) and caching resource exhaustion attacks. Attackers could flood the system with rapid revocation requests.
**Learning:** Any endpoint that interacts with caching systems or performs authentication state mutations must have strict rate limiting to prevent resource exhaustion and abuse.
**Prevention:** Always ensure that revocation or authentication-related endpoints are covered by appropriate rate limiting middleware configurations.
## 2026-06-22 - Token Revocation Cache and Project Members Access
**Learning:** The token revocation mechanism used an in-memory dictionary `_revoked_token_jtis` that doesn't persist across application restarts. This could allow revoked tokens to become valid again after a service restart until their natural expiration. Also, the `list_project_members` endpoint did not properly check authorization, potentially allowing low-privilege users (e.g. viewers) to enumerate all project members.
**Action:** Always implement persistent storage (e.g. database or Redis) for revoked tokens to ensure revocation survives application restarts. Also, ensure appropriate role-based access controls are strictly applied for viewing members in project spaces.
## 2026-06-22 - IDOR in Project Members List
**Learning:** The `/api/projects/{project_space_uuid}/members` endpoint exposed the full list of members and their roles to any user with `viewer` access. This excessive visibility could facilitate enumeration and social engineering attacks.
**Action:** Implemented stricter role-based access control (RBAC) on the endpoint to require a minimum `editor` role to view project members, mitigating the IDOR risk.
