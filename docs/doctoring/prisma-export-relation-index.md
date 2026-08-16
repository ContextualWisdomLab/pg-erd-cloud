# Prisma export relation index

## Status

Implemented on pull request #894. This record covers one bounded exporter optimization. It does not claim that generated Prisma schemas already provide collision-free identifiers, complete reserved-word handling, or lossless database-name round trips.

## Buyer outcome

Prisma export previously scanned every processed edge while rendering every scalar field. For `N` models, `C` total columns, and `E` relationships, relation lookup added an avoidable `O(C × E)` pass after the existing edge traversal. Large ERDs therefore spent increasing browser-main-thread time rechecking unrelated relationships.

The exporter now builds one directed lookup table during its existing `O(E)` edge pass:

```text
sanitized source model + sanitized source field
→ target model + target field + relation name
```

Each rendered field performs one `Map.get` rather than iterating the complete relationship collection. The implementation therefore removes the full `E`-element scan from the `C`-column loop. Under the hash-table strategy used by mainstream ECMAScript engines this produces the conventional `O(N + C + E)` average path; the normative claim retained by this project is narrower: ECMA-262 guarantees only average access time sublinear in the number of map entries.

## Correctness invariants

- Existing source/target handle interpretation is unchanged.
- Existing relation names, optionality, target references, and back-relations are unchanged.
- Invalid source or target node identifiers remain ignored.
- When multiple relationships resolve to the same sanitized source-model/field key, the last relationship retains the predecessor implementation's effective outgoing-field behavior.
- The optimization does not alter database identifiers, Prisma identifier sanitization, or persistence state.

A realistic regression constructs 96 valid outgoing relations and 384 unrelated invalid edges. It verifies every forward and back relation and proves unrelated edges cannot create output. It deliberately avoids wall-clock thresholds, because shared CI runner load is not a stable correctness oracle.

## Standards traceability

ECMA-262 requires `Map` implementations to use hash tables or another mechanism whose average access time is sublinear in collection size. The product claim is therefore “no complete edge scan per field,” not an engine-independent constant-time guarantee.

Prisma's current schema reference requires model and field identifiers to match `[A-Za-z][A-Za-z0-9_]*` and documents `@map` and `@@map` for preserving database names. This PR intentionally does not expand identifier rewriting. A separate product slice, issue #898, owns reserved-name completeness, deterministic collision allocation, name mapping, and parser-backed schema validation.

## Monitoring and rollback

Monitor Prisma export duration, relationship count, model count, column count, generated schema bytes, and client-side error rate. Avoid logging schema contents or customer identifiers solely for performance telemetry.

Rollback is a normal code revert. No migration, stored data, API contract, or generated artifact registry is changed. If output parity fails, restore the prior edge scan and retain the large-diagram regression while the key-space defect is corrected.

## References

Ecma International. (2026). *ECMAScript 2026 language specification* (ECMA-262, 17th ed.). https://262.ecma-international.org/

Prisma Data, Inc. (2026). *Prisma schema API*. https://www.prisma.io/docs/orm/reference/prisma-schema-reference
