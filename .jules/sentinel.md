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

## 2023-10-25 - [Snowflake 및 PostgreSQL DSN SSRF 우회 방어]
**Vulnerability:** Snowflake DSN `authenticator` 파라미터 값에 대해 단순히 `.endswith(".okta.com")` 등의 조건을 사용하여 검증함. 이로 인해 `https://evil.com\.okta.com` 이나 URL 인코딩을 통해 검증을 우회하여 내부 네트워크 또는 임의의 공격자 서버로 요청을 보낼 수 있는 SSRF 취약점이 존재함. PostgreSQL DSN의 Allowed Host 검증 시에도 하위 도메인 검증이 미흡하여 백슬래시(`\`)를 이용한 우회가 가능했음.
**Learning:** `urlparse` 등 URL 파싱 라이브러리는 백슬래시(`\`)나 특정 형태의 URL에 대해 브라우저나 HTTP 클라이언트와 다르게 동작할 수 있으며, 단순히 문자열의 끝부분을 검사하는 `.endswith()` 방식은 SSRF 공격에 취약함. Hostname 검증은 정규표현식을 통해 허용된 문자(RFC 1123)만 포함하는지 검사하거나, 분할된 서브도메인을 명확하게 평가해야 함.
**Prevention:**
- 외부 URL의 Hostname을 검증할 때는 정규표현식(`^[a-zA-Z0-9.-]+$`) 등을 사용하여 비정상적인 문자가 없는지 우선 확인.
- 도메인 검증 시에는 전체 일치 또는 `.` 으로 시작하는 서브도메인 검증을 동시에 수행해야 함.
- 허용되지 않은 속성(username, password, query, fragment 등)은 SSRF 우회를 방지하기 위해 엄격히 제한.
