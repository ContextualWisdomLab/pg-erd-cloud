## 2024-06-25 - 스냅샷 생성 시 잘못된 연결 ID 입력 처리 개선 (IDOR 및 리소스 열거 방지)
**Vulnerability:** `/api/snapshots/by-project/{project_space_uuid}` 엔드포인트에서 요청된 프로젝트에 속하지 않는 잘못된 `db_connection_uuid` 입력을 받았을 때 요청을 거부하는 대신 "failed" 상태의 스냅샷 작업을 데이터베이스에 생성하는 취약점이 있었습니다.
**Learning:** 성공적인 HTTP 상태 코드와 함께 "failed" 도메인 객체를 반환하면 공격자가 다른 프로젝트의 리소스 ID를 열거(IDOR)할 수 있으며, 시스템 데이터베이스에 정크 레코드를 무수히 생성(DoS/DB 고갈)할 수 있습니다.
**Prevention:** 교차 참조되는 리소스 ID가 항상 인증된 부모 리소스 범위에 속하는지 검증하고, 잘못된 상태를 생성하는 대신 존재 여부를 숨기기 위해 `404 Not Found` 오류로 안전하게 실패하도록 구현해야 합니다.

## 2025-02-21 - [Okta SSRF vulnerability in Snowflake DSN authenticator parsing]
**Vulnerability:** Found a Server-Side Request Forgery (SSRF) bypass in Snowflake DSN parsing for Okta authenticators via the `.endswith(".okta.com")` string check.
**Learning:** The simple `.endswith` check permitted inputs like `attacker-okta.com` or potentially backslash manipulation in `urllib.parse` parsing.
**Prevention:** Always use precise regex patterns (`^([a-zA-Z0-9-]+\.)*(okta|oktapreview)\.com$`) or strict URI structural inspection to validate target URLs for SSRF protections rather than naive substring matching.

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

## 2026-06-22 - Missing Rate Limiting on Token Revocation Endpoint
**Vulnerability:** The `/api/auth/logout` token revocation endpoint lacked its intended tighter rate limit because `_revoke_rate_limit_policy` in `backend/app/main.py` used the stale route prefix `"/api/auth/revoke"` instead of `"/api/auth/logout"`.
**Learning:** Any endpoint that interacts with caching systems or performs authentication state mutations must have strict rate limiting to prevent resource exhaustion and abuse. Route-prefix policies must match the actual `APIRouter` path exactly.
**Prevention:** Always verify that sensitive endpoint rate-limit prefixes match the actual route definitions, and keep app-wiring regression tests for those policies.
## 2024-05 - [CRITICAL] Authentication Bypass via X-Dev-User Leftover Mitigation
**Vulnerability:** Leftover logic defining an `X-Dev-User` bypass vector existed partially in the backend CORS allowed headers and heavily in the frontend via localStorage and request headers.
**Learning:** Even after backend vulnerability logic is removed (e.g. `try_get_subject_for_rate_limit` fallback logic removed), residual CORS configurations (`backend/app/main.py`) or client-side storage & transmission (`frontend/src/api.ts` and `frontend/src/App.tsx`) might still mistakenly use and expose development bypass tokens.
**Prevention:** When removing an auth-bypass test vector, conduct a full-stack search (e.g., `grep -rn "X-Dev-User" .`) to ensure the entire trace, including frontend localStorage keys, UI toggles, and backend CORS configuration, is cleanly removed.

## 2026-06-23 - OIDC JWKS 갱신 관련 서비스 거부(DoS) 취약점
**Vulnerability:** JWT 인증을 처리하는 `_get_jwks` 함수에서, 알 수 없는 `kid`를 가진 토큰이 유입될 때마다 `force_refresh=True`가 호출되어 OIDC 엔드포인트(JWKS)로 외부 HTTP 갱신 요청을 즉시 보냅니다. 공격자가 고의로 무작위 `kid`를 포함한 토큰을 대량으로 보내면, 서버는 불필요하게 잦은 외부 요청을 수행하게 되어 스레드 고갈이나 외부 OIDC 제공자로부터 Rate Limit 제한을 받는 DoS(서비스 거부) 공격에 취약해집니다.
**Learning:** 서드파티 OIDC 제공자나 외부 API를 통해 공개키/설정을 동적으로 가져오는(fetch) 패턴에서는, 인증에 실패하거나 캐시 미스(Cache Miss)가 발생하는 경우에도 외부 요청을 제한할 수 있는 디바운싱(Debouncing), Rate Limiting, 그리고 동시 갱신 직렬화가 필요합니다.
**Prevention:** 강제 캐시 갱신(`force_refresh`) 요청이 들어오더라도 `OIDC_JWKS_MIN_REFRESH_INTERVAL` 변수와 JWKS 갱신 lock을 사용하여 최소 갱신 간격을 보장하고 concurrent bad `kid` 요청이 외부 호출을 병렬 증폭하지 못하게 합니다.

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
## 2024-06-30 - JWT Algorithm Confusion

**Vulnerability:** The application was susceptible to JWT algorithm confusion. It decoded JWTs without validating that the algorithm provided in the token header (`alg`) matched the key type (`kty`) of the JSON Web Key (JWK) fetched from the provider.
**Learning:** Even when using a fixed whitelist of allowed algorithms (`RS256`), an attacker can craft a token with an `RS256` header, but if the provider somehow exposes both symmetric and asymmetric keys, or if the library misinterprets the key format, it could lead to improper validation. More importantly, explicitly enforcing `kty` to `alg` alignment prevents a wide class of downgrade/confusion attacks before `jwt.decode` is even invoked.
**Prevention:** Always validate that `kty == 'RSA'` requires `alg` starting with `RS` or `PS`, and `kty == 'EC'` requires `alg` starting with `ES`. Never rely solely on the `alg` header or the presence of a key identifier (`kid`) without checking the key material's intended type.

## 2026-06-26 - Password Leak in Database Introspection Exceptions
**Vulnerability:** Database driver exceptions can echo DSN fragments, query parameters, or assignment-style secrets after connection failures, leaking plaintext passwords through snapshot error messages and queue logs.
**Learning:** Redacting only the literal DSN is not enough. Error messages may contain decoded, percent-encoded, query-string, or `password=`/`api_key=` style forms of the same secret.
**Prevention:** Sanitize snapshot job errors before persisting or re-raising them, and raise sanitized exceptions with `from None` so Python exception chaining does not reattach the original secret-bearing exception.

## 2026-06-29 - Unsafe Inline Scripts in CSP
**Learning:** Permitting `'unsafe-inline'` in Content-Security-Policy (CSP) headers opens the application to severe Cross-Site Scripting (XSS) risks.
**Action:** Removed `'unsafe-inline'` from `script-src` and `style-src` directives in `frontend/index.html` to harden the application against XSS vulnerabilities while ensuring frontend tests and builds succeed safely.
