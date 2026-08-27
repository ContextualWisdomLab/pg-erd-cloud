# JWT critical-header boundary

## Status

Implemented on pull request #895. This record describes a bounded authentication-header validation change; it does not claim that every JOSE extension is supported or that the complete OIDC deployment is certification-ready.

## Buyer and operator outcome

A compact OIDC JWT that declares a critical JOSE extension is rejected before JWKS retrieval or signature verification unless the application explicitly understands and processes that extension. The current deployment profile supports no critical extensions, so every structurally valid non-empty `crit` declaration fails closed with a fixed non-reflecting `401` response.

Malformed declarations also fail closed. The validator rejects:

- a present JSON `null` value;
- non-array values;
- an empty array;
- non-string or empty entries;
- duplicate names;
- names absent from the JOSE header;
- registered JWS header parameter names, including `alg`, `b64`, `typ`, `cty`, and `crit` itself.

JWTs that omit `crit` retain the existing token-type, content-type, algorithm allowlist, key-family, issuer, audience, expiry, and revocation checks. When a selected JWK declares its optional `alg` metadata, that case-sensitive value must also match the token header algorithm before key construction; a mismatch is rejected before signature verification.

## Authority and invariants

RFC 7515, Section 4.1.11 defines `crit` as a non-empty array of extension header names that are present in the JOSE header and that the recipient must understand and process. It forbids duplicate names, registered JWS/JWA names, names absent from the header, and the empty array. An unsupported listed extension makes the JWS invalid.

RFC 7797 registers `b64` as a JWS header parameter and requires `crit` to contain `b64` when that option is used. The current OIDC/JWT profile does not implement unencoded JWS payload processing, so `b64` is treated as registered critical metadata and rejected rather than misclassified as an unknown extension. RFC 7797 also states that JWTs must not use `b64: false` for interoperability.

RFC 7517, Section 4.4 defines a JWK `alg` member as the case-sensitive algorithm intended for use with that key. Therefore, when `alg` is present on the selected JWK, this implementation rejects a different token-header algorithm instead of overriding the key metadata during PyJWT key construction.

This repository uses JWS Compact Serialization for OIDC bearer tokens. Its JOSE header is the protected header segment, and the validation runs before any key lookup. Rejection therefore cannot be bypassed by selecting another key or algorithm.

The implementation deliberately does not maintain an allowlist of nominally accepted-but-unprocessed critical extensions. Adding one requires a separate ADR, extension-specific processing, negative tests proving that omission or malformed values fail closed, and exact-head security review.

## Verification

Focused regression tests cover the supported no-`crit` path, every malformed shape above, registered-name rejection including `b64`, absent extension members, malformed and unsupported critical metadata rejected before JWKS I/O, and a selected JWK whose declared algorithm conflicts with the token header. Exact-head repository CI, SAST, Strix, coverage, and independent review remain authoritative.

## Monitoring and rollback

Monitor fixed authentication failure categories rather than token contents. Do not log bearer tokens, complete JOSE headers, extension values, signing keys, or raw provider errors.

Rollback is limited to reverting the validation change if a verified provider unexpectedly emits `crit`. Operators must not bypass validation as an incident workaround. A provider requiring a critical extension must first supply a documented extension contract and an implementation that actually processes it.

## References

Jones, M. (2015). *JSON Web Key (JWK)* (RFC 7517). Internet Engineering Task Force. https://doi.org/10.17487/RFC7517

Jones, M., Bradley, J., & Sakimura, N. (2015). *JSON Web Signature (JWS)* (RFC 7515). Internet Engineering Task Force. https://doi.org/10.17487/RFC7515

Jones, M. (2016). *JSON Web Signature (JWS) unencoded payload option* (RFC 7797). Internet Engineering Task Force. https://doi.org/10.17487/RFC7797

Sheffer, Y., Hardt, D., & Jones, M. (2020). *JSON Web Token best current practices* (BCP 225; RFC 8725). Internet Engineering Task Force. https://doi.org/10.17487/RFC8725
