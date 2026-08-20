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
- registered JWS header parameter names, including `alg`, `typ`, `cty`, and `crit` itself.

JWTs that omit `crit` retain the existing token-type, content-type, algorithm allowlist, key-family, issuer, audience, expiry, and revocation checks.

## Authority and invariants

RFC 7515, Section 4.1.11 imposes producer-side structural requirements: `crit` is a non-empty array of extension header names, and producers must not include duplicate names, registered JWS/JWA names, names absent from the JOSE header, or an empty array. Separately, a recipient must understand and process every extension listed in `crit`; this deployment supports none, so it rejects every otherwise-structurally-valid `crit` declaration. Rejecting registered names is therefore a producer validation rule, while rejecting unsupported critical extensions is this deployment's recipient policy.

This repository uses JWS Compact Serialization for OIDC bearer tokens. Its JOSE header is the protected header segment, and the validation runs before any key lookup. Rejection therefore cannot be bypassed by selecting another key or algorithm.

The implementation deliberately does not maintain an allowlist of nominally accepted-but-unprocessed critical extensions. Adding one requires a separate ADR, extension-specific processing, negative tests proving that omission or malformed values fail closed, and exact-head security review.

## Verification

Focused regression tests cover the supported no-`crit` path, every malformed shape above, registered-name rejection, absent extension members, and the RFC Appendix E-style case in which a present but unknown critical extension is rejected. Exact-head repository CI, SAST, Strix, coverage, and independent review remain authoritative.

## Monitoring and rollback

Monitor fixed authentication failure categories rather than token contents. Do not log bearer tokens, complete JOSE headers, extension values, signing keys, or raw provider errors.

Rollback is limited to reverting the validation change if a verified provider unexpectedly emits `crit`. Operators must not bypass validation as an incident workaround. A provider requiring a critical extension must first supply a documented extension contract and an implementation that actually processes it.

## References

Jones, M., Bradley, J., & Sakimura, N. (2015). *JSON Web Signature (JWS)* (RFC 7515). Internet Engineering Task Force. https://doi.org/10.17487/RFC7515

Sheffer, Y., Hardt, D., & Jones, M. (2020). *JSON Web Token best current practices* (BCP 225; RFC 8725). Internet Engineering Task Force. https://doi.org/10.17487/RFC8725
