# Log-safe identifier validation

## Status

Implemented for user-controlled display identifiers.

## Decision

Project names, connection names, member subjects, saved ERD View names,
table-annotation schema and relation names, and API-key names reject C0
controls, `DEL`, C1 controls, Unicode line separator (`U+2028`), and Unicode
paragraph separator (`U+2029`). Ordinary spaces, multilingual text, and emoji
remain valid where the field contract already permits them. Annotation body
text remains intentionally multiline.

The accepted/rejected character profile is expressed with declarative Pydantic
`StringConstraints`, rather than an opaque post-validation callback. The same
regular-expression constraint is therefore part of generated JSON Schema and
OpenAPI metadata, so API clients, schema auditors, and contract tests can see
the server-enforced boundary. Member subjects use a specialized form of the
same profile that also preserves the existing whitespace-free identity
contract.

The validator preserves accepted strings exactly. It does not normalize,
rewrite, mask, or transliterate customer identifiers, so PostgreSQL labels and
user-facing names retain their original meaning.

## Security rationale

External text that creates a new logical line can forge or corrupt audit
records when it later reaches a line-oriented logger. A bounded input profile
reduces that attack surface, but it is not a substitute for structured logging,
context-appropriate output handling, or safe log viewers. The boundary covers
the complete C0/C1 ranges and Unicode line and paragraph separators rather than
matching only a short list of familiar carriage-return/newline payloads.

This rule is intentionally narrow. DSNs, forward DDL, DBML, and annotation
bodies have different grammars and sinks; their control-character contracts are
owned separately by issue #1010. This identifier profile must not be copied to
those fields merely to simplify validation.

## Research and standards traceability

- **CWE-117** characterizes insufficient neutralization of externally controlled
  log output as a log-integrity weakness. It supports treating log safety as a
  sink-aware security property; this input constraint is one upstream control,
  not permission to log rejected raw values.
- **Unicode Standard Annex #31, Revision 43 (Unicode 17.0.0)** is the current
  stable, citable UAX #31 release. It supports explicitly defining identifier
  profiles and additional constraints while retaining legitimate Unicode. The
  proposed Unicode 18 revision is not used as normative evidence because it is
  still a proposed update.
- **Pan et al. (2022)** evaluated LogInjector on 14 web applications and found
  16 log-injection vulnerabilities, including six zero-days. Their results also
  show that application-specific input filters can be bypassed, which supports
  exhaustive boundary/sink testing rather than relying on a few attack-string
  examples or on validation alone.
- **Boucher and Anderson (2023)** demonstrated that Unicode control semantics
  can create materially different machine and human interpretations across a
  broad range of programming languages. The applicability here is narrower:
  it supports an explicit, testable code-point policy and exact preservation of
  allowed text. It does **not** justify rejecting unrelated bidirectional,
  confusable, or multilingual characters from customer display identifiers.

## Verification

- every C0, `DEL`, and C1 code point plus `U+2028` and `U+2029`;
- prefix, middle, and suffix placement for every protected field;
- exact preservation of valid Korean labels, ordinary spaces, and emoji;
- preservation of the existing whitespace-free member-subject contract;
- generated JSON Schema exposes the same log-safe regex for every protected
  field, including the combined member-subject profile;
- complete backend type checking and test execution on the exact head.

## Monitoring and rollback

Monitor validation-error counts by route and field without recording the
rejected value. Rollback must restore the preceding release as a whole rather
than weakening one character range or adding field-specific exceptions.

## References

Boucher, N., & Anderson, R. (2023). Trojan source: Invisible vulnerabilities.
In *32nd USENIX Security Symposium (USENIX Security 23)* (pp. 6507–6524).
USENIX Association. https://www.usenix.org/conference/usenixsecurity23/presentation/boucher

MITRE Corporation. (2026, April 30). *CWE-117: Improper output neutralization
for logs (Version 4.20).* Common Weakness Enumeration.
https://cwe.mitre.org/data/definitions/117.html

Pan, Z., Chen, Y., Chen, Y., Shen, Y., & Li, Y. (2022). LogInjector: Detecting
web application log injection vulnerabilities. *Applied Sciences, 12*(15),
7681. https://doi.org/10.3390/app12157681

The Unicode Consortium. (2025, August 20). *Unicode Standard Annex #31:
Unicode identifiers and syntax* (Unicode 17.0.0, Revision 43).
https://www.unicode.org/reports/tr31/tr31-43.html
