# OIDC JWK algorithm binding

## Status

Implemented on the authentication boundary in `backend/app/auth.py`.

## Decision

The verifier first normalizes and allowlists the JWT protected-header `alg`. After selecting a JWK, it applies an independent key-bound algorithm check:

- a JWK without `alg` remains accepted because RFC 7517 defines the member as optional;
- a present JWK `alg` must be a string;
- a present JWK `alg` must exactly match the normalized JWT header algorithm;
- the existing RSA/EC key-type family check remains mandatory;
- PyJWT signature, issuer, audience, expiry, and required-claim verification remains a separate final boundary.

A mismatch or non-text JWK algorithm fails closed with the fixed `401 algorithm/key type mismatch` response before `PyJWK` construction or `jwt.decode` execution.

## Why

Passing `jwt.PyJWK(jwk).key` to `jwt.decode` strips the JWK object's algorithm metadata from the verification call. When more than one RSA signature algorithm is allowlisted, key type alone cannot distinguish an `RS256` key declaration from an `RS512` token header. Binding an explicitly declared JWK algorithm to the already allowlisted token algorithm prevents this algorithm-confusion path while retaining compatibility with standards-compliant keys that omit the optional member.

PyJWT 2.13.0 added equivalent binding when a `PyJWK` object is passed directly, following its published algorithm allow-list bypass advisory. pg-erd-cloud performs the check explicitly because the current integration passes the extracted key material and must keep this invariant reviewable at the application boundary.

## Invariants

- Token-controlled `alg` never selects an algorithm outside `OIDC_ALLOWED_ALGORITHMS`.
- A selected JWK cannot declare a different algorithm from the JWT header.
- A non-string declared JWK algorithm is never coerced.
- Missing JWK `alg` does not invent a provider claim and continues through key-family and cryptographic verification.
- Failure responses contain no token, key, issuer, or provider detail.

## Test-first evidence

`backend/tests/test_auth_jwk_algorithm_binding.py` was committed before the production remedy. The RED boundary demonstrated that both an `RS256` JWK paired with an `RS512` header and a non-text JWK algorithm reached `jwt.decode`. The production check then made both cases fail before key construction or signature verification. Existing authentication tests retain coverage of keys that omit `alg` and of valid key-type families.

Repository exact-head CI, security scans, complete authentication statement/branch coverage, and independent review remain authoritative; local focused evidence does not replace them.

## Operational monitoring and rollback

Monitor fixed-reason authentication failures after identity-provider key rotation. A sudden increase can identify an issuer publishing internally inconsistent JWT/JWK metadata. Do not relax the equality check to restore traffic. Roll back only to a version that passes a `PyJWK` object directly to a patched PyJWT release and retains an equivalent mismatch regression.

## References

Internet Engineering Task Force. (2015). *JSON Web Key (JWK)* (RFC 7517). RFC Editor. https://www.rfc-editor.org/rfc/rfc7517

PyJWT. (2026, May 21). *Algorithm allow-list bypass when decoding with PyJWK / PyJWKClient keys* (GHSA-jq35-7prp-9v3f). GitHub. https://github.com/jpadilla/pyjwt/security/advisories/GHSA-jq35-7prp-9v3f

PyJWT contributors. (2026). *Changelog: v2.13.0*. https://pyjwt.readthedocs.io/en/stable/changelog.html
