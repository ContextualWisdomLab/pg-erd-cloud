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
## 2026-06-22 - Missing Rate Limiting on Token Revocation Endpoint
**Vulnerability:** The `/api/auth/revoke` token revocation endpoint lacked rate limiting because the route prefix in the rate limiting middleware configuration (`_revoke_rate_limit_policy` in `backend/app/main.py`) was incorrect (`"/api/auth/revoke"` instead of `"/api/auth/logout"`).
**Learning:** Any endpoint that interacts with caching systems or performs authentication state mutations must have strict rate limiting to prevent resource exhaustion and abuse. It is critical to ensure that the configured `route_prefix` matches the actual route definition.
**Prevention:** Always verify that the route prefix in the rate limiter configuration matches the actual route defined in the router, and write tests that explicitly check rate limits on sensitive endpoints.
## 2024-05-XX - [CRITICAL] Authentication Bypass via X-Dev-User Leftover Mitigation
**Vulnerability:** Leftover logic defining an `X-Dev-User` bypass vector existed partially in the backend CORS allowed headers and heavily in the frontend via localStorage and request headers.
**Learning:** Even after backend vulnerability logic is removed (e.g. `try_get_subject_for_rate_limit` fallback logic removed), residual CORS configurations (`backend/app/main.py`) or client-side storage & transmission (`frontend/src/api.ts` and `frontend/src/App.tsx`) might still mistakenly use and expose development bypass tokens.
**Prevention:** When removing an auth-bypass test vector, conduct a full-stack search (e.g., `grep -rn "X-Dev-User" .`) to ensure the entire trace, including frontend localStorage keys, UI toggles, and backend CORS configuration, is cleanly removed.
