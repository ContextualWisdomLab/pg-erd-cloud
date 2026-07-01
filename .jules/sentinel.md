## 2025-02-28 - X-Forwarded-For IP Spoofing Prevention
**Vulnerability:** IP Spoofing / Rate-Limiting DoS via `X-Forwarded-For` Left-Most IP Extraction.
**Learning:** Extracting the left-most IP (`xff.split(",")[0]`) from `X-Forwarded-For` allows users to spoof their IP by manually providing a fake IP in the header, leading to rate limit circumvention or conversely, rate-limiting the wrong proxy server and causing DoS for legitimate users using that proxy. The right-most IP should be extracted as it represents the nearest trusted proxy, mitigating these spoofing risks.
**Prevention:** In rate-limiting and observability middlewares, ensure the right-most value (`xff.split(",")[-1].strip()`) is extracted when relying on the `X-Forwarded-For` header to guarantee that the IP address corresponds to the nearest, authenticated hop.
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
## 2026-06-23 - OIDC JWKS 갱신 관련 서비스 거부(DoS) 취약점
**Vulnerability:** JWT 인증을 처리하는 `_get_jwks` 함수에서, 알 수 없는 `kid`를 가진 토큰이 유입될 때마다 `force_refresh=True`가 호출되어 OIDC 엔드포인트(JWKS)로 외부 HTTP 갱신 요청을 즉시 보냅니다. 공격자가 고의로 무작위 `kid`를 포함한 토큰을 대량으로 보내면, 서버는 불필요하게 잦은 외부 요청을 수행하게 되어 스레드 고갈이나 외부 OIDC 제공자로부터 Rate Limit 제한을 받는 DoS(서비스 거부) 공격에 취약해집니다.
**Learning:** 서드파티 OIDC 제공자나 외부 API를 통해 공개키/설정을 동적으로 가져오는(fetch) 패턴에서는, 인증에 실패하거나 캐시 미스(Cache Miss)가 발생하는 경우에도 외부 요청을 제한할 수 있는 디바운싱(Debouncing)이나 Rate Limiting 로직이 반드시 필요합니다.
**Prevention:** 강제 캐시 갱신(`force_refresh`) 요청이 들어오더라도 `OIDC_JWKS_MIN_REFRESH_INTERVAL` 변수를 도입하여 최소 갱신 간격(예: 60초)을 둠으로써 연쇄적인 외부 호출로 인한 리소스 고갈을 방지합니다.

## 2024-06-25 - Fix SSRF validation rejecting Okta root domain
**Vulnerability:** A logic bug in `_parse_snowflake_dsn` incorrectly rejected authenticators using Okta root domains `okta.com` or `oktapreview.com` because it only checked `endswith(".okta.com")`, functioning as a DoS for legitimate configurations.
**Learning:** `endswith(".okta.com")` does not match `okta.com` due to the leading dot. This caused valid configurations to be rejected.
**Prevention:** Always explicitly allow the exact root domain when performing suffix checks that require a subdomain delimiter.
## 2026-06-22 - Token Revocation Cache and Project Members Access
**Learning:** The token revocation mechanism used an in-memory dictionary `_revoked_token_jtis` that doesn't persist across application restarts. This could allow revoked tokens to become valid again after a service restart until their natural expiration. Also, the `list_project_members` endpoint did not properly check authorization, potentially allowing low-privilege users (e.g. viewers) to enumerate all project members.
**Action:** Always implement persistent storage (e.g. database or Redis) for revoked tokens to ensure revocation survives application restarts. Also, ensure appropriate role-based access controls are strictly applied for viewing members in project spaces.
## 2026-06-22 - IDOR in Project Members List
**Learning:** The `/api/projects/{project_space_uuid}/members` endpoint exposed the full list of members and their roles to any user with `viewer` access. This excessive visibility could facilitate enumeration and social engineering attacks.
**Action:** Implemented stricter role-based access control (RBAC) on the endpoint to require a minimum `editor` role to view project members, mitigating the IDOR risk.

## 2026-06-26 - Password Leak in Database Introspection Exceptions
**Vulnerability:** Database driver exceptions can echo DSN fragments, query parameters, or assignment-style secrets after connection failures, leaking plaintext passwords through snapshot error messages and queue logs.
**Learning:** Redacting only the literal DSN is not enough. Error messages may contain decoded, percent-encoded, query-string, or `password=`/`api_key=` style forms of the same secret.
**Prevention:** Sanitize snapshot job errors before persisting or re-raising them, and raise sanitized exceptions with `from None` so Python exception chaining does not reattach the original secret-bearing exception.
