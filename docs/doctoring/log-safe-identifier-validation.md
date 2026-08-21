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

The validator preserves accepted strings exactly. It does not normalize,
rewrite, mask, or transliterate customer identifiers, so PostgreSQL labels and
user-facing names retain their original meaning.

## Security rationale

External text that creates a new logical line can forge or corrupt audit
records when it later reaches a line-oriented logger. Strict input validation
is preferable to matching a small list of attack strings. The boundary
therefore covers the complete C0/C1 ranges and Unicode line and paragraph
separators rather than only ASCII carriage return and line feed.

## Verification

- every C0, `DEL`, and C1 code point plus `U+2028` and `U+2029`;
- prefix, middle, and suffix placement for every protected field;
- exact preservation of valid Korean labels, ordinary spaces, and emoji;
- preservation of the existing whitespace-free member-subject contract;
- complete backend type checking and test execution on the exact head.

## Monitoring and rollback

Monitor validation-error counts by route and field without recording the
rejected value. Rollback must restore the preceding release as a whole rather
than weakening one character range or adding field-specific exceptions.

## References

MITRE Corporation. (2026, April 30). *CWE-117: Improper output neutralization
for logs (Version 4.20).* Common Weakness Enumeration.
https://cwe.mitre.org/data/definitions/117.html

The Unicode Consortium. (2025, August 20). *Unicode Standard Annex #31:
Unicode identifiers and syntax* (Unicode 17.0.0, Revision 43).
https://www.unicode.org/reports/tr31/tr31-43.html
