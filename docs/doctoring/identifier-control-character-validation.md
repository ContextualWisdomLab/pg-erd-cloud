# Identifier control-character validation

## Decision

User-visible names that function as identifiers or labels must not contain ASCII control characters `U+0000` through `U+001F` or `U+007F`. The policy applies at the Pydantic input boundary to project, connection, diagram-view, schema, relation, and API-key names before those values can reach logs, terminals, exports, database labels, or downstream parsers.

The policy is intentionally narrow. It permits ordinary spaces, punctuation, Korean, Japanese, emoji, and other Unicode text. It does not apply to the table-annotation body because that field is explicitly multiline prose; each output sink remains responsible for context-appropriate escaping or encoding of that body.

## Threat model

Control characters are non-printing code points with structural effects in line-oriented systems. CR and LF can forge additional log records, NUL can truncate or confuse native consumers, ESC can alter terminal presentation, and delimiter controls can corrupt CSV, Markdown, or protocol framing. Length limits alone do not preserve record structure.

CWE-117 describes the root weakness as external input reaching logs without correct neutralization and recommends known-good input validation plus context-aware output encoding. Boundary validation is therefore defense in depth, not a substitute for structured logging, CSV formula protection, Markdown/HTML escaping, SQL identifier quoting, or secret redaction.

## Validation contract

- Reject every code point in `U+0000`–`U+001F` and `U+007F` at the beginning, middle, or end of a protected field.
- Preserve existing minimum and maximum length constraints.
- Accept ordinary multilingual and supplementary-plane Unicode text.
- Do not silently delete or normalize prohibited characters; return a validation error so the caller can correct the name.
- Keep intentionally multiline annotation content valid.
- Reuse one documented printable-name policy across equivalent schema fields so later additions do not drift.

## Verification

The regression suite enumerates all 33 prohibited ASCII controls for each hardened field and exercises each at the beginning, middle, and end. Positive cases include ASCII, spaces, underscores, hyphens, Korean, Japanese, and emoji. A dedicated assertion preserves multiline annotation bodies. Repository mypy, the complete backend test suite, and the 100% production coverage contract remain required on the exact final head.

## Monitoring and rollback

Monitor validation-error rates by field name and bounded reason without logging rejected raw values. A sudden increase may indicate a client defect or probing. Rollback must not re-enable raw control characters; compatibility incidents should instead introduce a reviewed migration or reversible display encoding at the appropriate boundary.

## References

MITRE Corporation. (2026, April 30). *CWE-117: Improper output neutralization for logs*. Common Weakness Enumeration. https://cwe.mitre.org/data/definitions/117.html

The Unicode Consortium. (2025). *The Unicode Standard, Version 17.0.0*. https://www.unicode.org/versions/Unicode17.0.0/
