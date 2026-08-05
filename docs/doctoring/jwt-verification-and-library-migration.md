# JWT verification library migration and security contract

## Decision

The backend uses `PyJWT[crypto]` for OIDC JWT verification and removes the `python-jose[cryptography]` dependency path that introduced the pure-Python `ecdsa` package. The decision is not based on a claim that `python-jose` has no maintainers: version 3.5.0 was released in May 2025. The security reason is narrower and auditable: `ecdsa` remains affected by the Minerva P-256 timing side-channel advisory (CVE-2024-23342 / GHSA-wj6h-64fc-37mp / PYSEC-2026-1325), and its upstream security policy treats side-channel resistance as out of scope with no planned fix.

PyJWT 2.13.0 was released on May 21, 2026 and publishes source and wheel artifacts through PyPI Trusted Publishing with provenance attestations. `PyJWT[crypto]` relies on the `cryptography` backend and does not require the vulnerable `ecdsa` package for this OIDC verification path.

## Verification invariants

The application contract follows RFC 7519 and the stable JWT Best Current Practice in RFC 8725:

1. The verifier supplies a fixed application-controlled algorithm allowlist and never trusts the token header to choose an algorithm.
2. Symmetric `HS*` algorithms and `none` are excluded from the OIDC asymmetric verification profile.
3. The selected JWK is converted to the key object expected by PyJWT through `jwt.PyJWK(jwk).key`.
4. The issuer is verified and the `iss` claim is required.
5. Expiration is verified and the `exp` claim is required.
6. The token identifier is verified by the application contract and `jti` is required.
7. Audience verification and the `aud` requirement are enabled whenever an OIDC audience is configured.
8. The token type and key identifier checks remain application-level gates before signature verification.
9. Verification failures expose a uniform HTTP 401 response rather than parser or key details.
10. Tests cover invalid headers, key selection, required claims, issuer, audience, expiration, leeway, refresh behavior, and PyJWT exception handling.

RFC 8725 remains the published Best Current Practice as of August 5, 2026. The July 2026 `draft-ietf-oauth-rfc8725bis-07` revision is monitored as an Internet-Draft, but it is not treated as a replacement standard until approved and published.

## Migration notes

`python-jose` accepted a raw JWK mapping in the prior call site. PyJWT expects a cryptographic key object, so the migration uses `jwt.PyJWK(jwk).key`. Required claims are expressed with PyJWT's `options={"require": [...]}` contract, while `leeway` is passed as a top-level decode argument. PyJWT exceptions are caught through `jwt.PyJWTError`; unrelated programming errors are not swallowed.

The hash-locked production and development requirements must be regenerated from `backend/pyproject.toml`. Merge is prohibited unless `python-jose`, `types-python-jose`, and `ecdsa` are absent from both locks; `PyJWT[crypto]` and its `cryptography` dependency must remain hash-pinned; backend mypy and the complete pytest suite must pass with the repository's 100% production coverage gate.

## APA 7 references

GitHub, Inc. (2026). *Minerva timing attack on P-256 in python-ecdsa* (GHSA-wj6h-64fc-37mp). GitHub Advisory Database. https://github.com/advisories/GHSA-wj6h-64fc-37mp

Jones, M., Bradley, J., & Sakimura, N. (2015). *JSON Web Token (JWT)* (RFC 7519). Internet Engineering Task Force. https://doi.org/10.17487/RFC7519

PyJWT maintainers. (2026). *PyJWT 2.13.0 documentation*. https://pyjwt.readthedocs.io/en/stable/

PyPI. (2026). *PyJWT 2.13.0*. Python Package Index. https://pypi.org/project/PyJWT/2.13.0/

PyPI. (2025). *python-jose 3.5.0*. Python Package Index. https://pypi.org/project/python-jose/3.5.0/

Sheffer, Y., Hardt, D., & Jones, M. B. (2020). *JSON Web Token best current practices* (RFC 8725; BCP 225). Internet Engineering Task Force. https://doi.org/10.17487/RFC8725

Sheffer, Y., Hardt, D., & Jones, M. B. (2026). *JSON Web Token best current practices* (Internet-Draft draft-ietf-oauth-rfc8725bis-07). Internet Engineering Task Force. https://datatracker.ietf.org/doc/draft-ietf-oauth-rfc8725bis/
