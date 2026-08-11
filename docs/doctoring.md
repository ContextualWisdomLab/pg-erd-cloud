# ERD export hardening and handle contract

## Status and scope

**Implemented** for browser-generated DDL, Prisma, CSV/Markdown data dictionary,
and SVG export. This document records the browser export boundary; it does not
make those generated artifacts server-authoritative migration plans and does
not expand the forward-engineering apply boundary.

## Canonical relationship handles

Column handles encode each Unicode scalar as a lowercase four-to-six digit
hexadecimal chunk. Plain `c-*` handles remain decodable by the shared utility,
while relationship sinks require the role-specific forms:

- source column: `src-c-*`;
- target column: `tgt-c-*`;
- empty column name compatibility: `src-c-empty` / `tgt-c-empty`.

The decoder rejects unknown prefixes, uppercase or malformed chunks, surrogate
code points, values above `U+10FFFF`, partial handles, and inputs longer than
10,000 UTF-16 code units. A supplied handle is authoritative: if either side is
malformed, role-swapped, partial, or names no column on the corresponding
node, the export fails closed for that relationship. Legacy edge metadata and
primary/non-primary inference are consulted only when both handles are absent.

Export paths build node and column indexes once. The complete relationship
pass is `O(N×C + E×H)`, where `N` is the number of tables, `C` their average
column count, `E` the edge count, and `H` the handle length. Prisma relation
metadata is keyed by the exact node/column tuple, and colliding display field
names receive deterministic relation-name suffixes instead of overwriting a
distinct relationship.

## Other export protections

- CSV values beginning with ASCII or full-width formula markers, after Unicode
  whitespace, are prefixed with an apostrophe before CSV quoting.
- SVG text and attributes escape XML metacharacters; node coordinates are
  converted to finite numeric fallbacks before interpolation.
- Markdown dictionary cells escape table, code, link, and HTML delimiters.

These controls protect exported text. They do not authorize SQL execution,
validate PostgreSQL semantics, or replace the structured server-side plan and
capability checks maintained on the canonical forward-engineering lane.

## Acceptance evidence

Focused regressions cover ASCII, mixed-case and Unicode identifiers,
supplementary code points, the empty-name sentinel, malformed chunks, wrong
roles, unknown columns, partial handles, distinct Prisma relations sharing a
field, hostile CSV prefixes, and SVG text/coordinate injection. App coverage
also exercises the Prisma download route. Repository CI remains the authority
for the complete typecheck, test, coverage, build, and security gates.

## References

Open Worldwide Application Security Project. (n.d.). *CSV injection*.
https://owasp.org/www-community/attacks/CSV_Injection

The Unicode Consortium. (2025). *The Unicode standard, version 17.0: Core
specification*. https://www.unicode.org/versions/Unicode17.0.0/

World Wide Web Consortium. (2008). *Extensible Markup Language (XML) 1.0
(Fifth Edition)*. https://www.w3.org/TR/2008/REC-xml-20081126/
