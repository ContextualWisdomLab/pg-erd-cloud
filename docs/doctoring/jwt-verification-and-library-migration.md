# JWT verification library migration

## Decision

The OIDC verification path uses `PyJWT[crypto]` with the `cryptography` backend. The application, not the token header, owns the accepted asymmetric algorithm allowlist. A selected JSON Web Key is converted through `PyJWK` and used only after the header algorithm and key type are proven compatible.

The migration removes the `python-jose` and pure-Python `ecdsa` dependency path from both production and development hash locks. It does not broaden accepted token formats, create a verification fallback, or change the issuer, audience, revocation, or user-provisioning boundaries.

## Verification contract

A token is accepted only when all of the following hold:

- the protected header parses and uses an allowed `typ` value;
- nested JWT content (`cty`) is rejected;
- `alg` is present, is in the server-configured allowlist, and is compatible with the JWK key type;
- the signing key is selected by `kid`, with one rate-limited JWKS refresh for key rotation;
- signature, issuer, expiration, and JWT ID verification succeed;
- `exp`, `iss`, and `jti` are present, and `aud` is present and verified when an audience is configured;
- clock tolerance is the application-owned 60-second leeway;
- verification-library errors become a generic authentication failure while unrelated programming errors remain visible to error monitoring;
- the verified JWT ID has not been revoked.

The accepted algorithm list is never computed from the untrusted token header. Symmetric `HS*` algorithms and `none` are excluded from configuration parsing so an asymmetric public key cannot be confused with an HMAC secret.

## Supply-chain rationale

The former dependency graph introduced the pure-Python `ecdsa` package. CVE-2024-23342 documents a Minerva-style timing side channel in its P-256 signing implementation. The application does not require that package: OIDC signature verification is served by PyJWT's cryptography-backed asymmetric key support. Removing the entire unused path is preferable to retaining a vulnerable or disputed transitive component behind an assumption that it will not execute.

Both generated lockfiles are regenerated from the same declaration change and remain hash-locked. Acceptance requires proving that `python-jose`, `types-python-jose`, and `ecdsa` are absent while `PyJWT`, `cryptography`, and their complete closures remain pinned.

## Test evidence

Focused authentication regressions cover malformed headers, unsupported algorithms and token types, key-type mismatch, unknown signing keys and refresh behavior, required-claim enforcement, optional-audience behavior, leeway forwarding, PyJWK conversion, generic verification failures, and propagation of unrelated programming errors. The complete backend suite, mypy, production coverage contract, dependency installation, and repository security gates remain mandatory on the exact final head.

## Monitoring and rollback

Monitor OIDC authentication failure rate by bounded reason category, JWKS refresh frequency, unknown-key incidence, issuer/audience mismatch, expired-token rate, and revocation lookup latency without logging raw tokens or claims. Rollback must restore a reviewed cryptography-backed verifier and regenerated hash locks; it must not restore the removed `ecdsa` path or accept token-selected algorithms.

## Standards status

RFC 8725 is the current Best Current Practice used by this decision. `draft-ietf-oauth-rfc8725bis-04` is monitored because it was published in 2026, but it is an Internet-Draft and is not treated as a final standard or as stronger authority than the published RFC.

## References

Jones, M., Bradley, J., & Sakimura, N. (2015). *JSON Web Token (JWT)* (RFC 7519). Internet Engineering Task Force. https://doi.org/10.17487/RFC7519

National Institute of Standards and Technology. (2026). *CVE-2024-23342 detail*. National Vulnerability Database. https://nvd.nist.gov/vuln/detail/CVE-2024-23342

PyJWT maintainers. (2026). *PyJWT 2.13.0 documentation*. https://pyjwt.readthedocs.io/en/2.13.0/

Sheffer, Y., Hardt, D., & Jones, M. (2020). *JSON Web Token best current practices* (RFC 8725). Internet Engineering Task Force. https://doi.org/10.17487/RFC8725

Sheffer, Y., Hardt, D., & Jones, M. (2026). *JSON Web Token best current practices* (Internet-Draft draft-ietf-oauth-rfc8725bis-04). Internet Engineering Task Force. https://datatracker.ietf.org/doc/draft-ietf-oauth-rfc8725bis/04/
