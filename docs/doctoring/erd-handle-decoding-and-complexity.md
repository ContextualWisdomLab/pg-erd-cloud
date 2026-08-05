# ERD handle decoding and export-complexity contract

## Decision

React Flow column handles use one canonical internal representation:

```text
c-<code-point>[-<code-point>...]
src-c-<code-point>[-<code-point>...]
tgt-c-<code-point>[-<code-point>...]
```

Each code-point chunk is lowercase hexadecimal. Values U+0000 through U+FFFF use exactly four hexadecimal digits; supplementary values use the shortest five- or six-digit representation. The empty column name is represented only by `c-empty`, `src-c-empty`, or `tgt-c-empty`.

The decoder accepts only strings that could have been produced by `sanitizeHandleId`, `sourceColumnHandleId`, or `targetColumnHandleId`. It rejects unknown prefixes, uppercase hexadecimal, missing or empty chunks, mixed `empty` payloads, code points above U+10FFFF, and non-shortest zero-padded chunks. This one-to-one grammar prevents multiple attacker-controlled handle spellings from resolving to the same logical column.

## Standards basis

ECMAScript defines `String.prototype.codePointAt` for obtaining the code point beginning at a string position and `String.fromCodePoint` for constructing a string from validated numeric code points. The handle encoder iterates the ECMAScript string by code point and serializes each value; the decoder performs the inverse operation only after grammar, range, and canonical-form checks.

The Unicode Standard defines the Unicode codespace as U+0000 through U+10FFFF. It distinguishes Unicode scalar values from surrogate code points and explains that UTF-8 and UTF-32 representations outside the scalar-value range are ill-formed. Database identifiers arrive through UTF-8 JSON and therefore use well-formed scalar values in production; the internal JavaScript helper nevertheless preserves the existing ECMAScript string round-trip contract for inputs accepted by the encoder.

## Performance rationale

Previously, an export resolved each edge handle by scanning every candidate column and re-encoding its name until a match was found. With `C` columns on the endpoint table and an encoded handle length of `H`, one lookup performed O(C × H) string work and generated transient encoded strings. Direct validated decoding performs O(H) work, after which exporters compare the decoded name against existing column metadata without rescanning and re-encoding the full candidate set.

The optimization is applied to DDL and data-dictionary export paths. It does not change database identifiers, edge ownership, handle generation, file formats, package dependencies, or the npm lock. Export tests cover missing and malformed handles so invalid graph edges remain non-authoritative rather than being mapped by a permissive decoder.

## Verification contract

The exact pull-request head must pass:

- canonical ASCII, punctuation, Korean, and supplementary-code-point round trips;
- all three supported prefixes and empty-name forms;
- malformed prefix, uppercase, partial chunk, empty chunk, out-of-range value, and over-padded chunk rejection;
- focused DDL and data-dictionary export regressions;
- frontend typecheck, complete 100% coverage suite, and production build;
- Security Scan, Semgrep, CodeRabbit, and independent current-head review;
- an npm-only diff with the canonical `package.json` and `package-lock.json`, no `pnpm-lock.yaml`, and no unrelated application orchestration tests.

## APA 7 references

ECMA International. (n.d.). *ECMAScript language specification: String.fromCodePoint and String.prototype.codePointAt*. Retrieved August 5, 2026, from https://tc39.es/ecma262/multipage/text-processing.html

The Unicode Consortium. (2025). *The Unicode standard, version 17.0.0: Chapter 3, Conformance*. https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-3/
