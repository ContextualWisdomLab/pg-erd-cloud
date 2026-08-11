# DBML identifier-to-DDL trust boundary

## Status

Implemented for the server DBML conversion path. This record describes a
security engineering control, not a certification claim.

## Authority and invariants

DBML is untrusted text. `app.spec.dbml_import` decodes its supported identifier
grammar into plain canonical names; it never stores quote delimiters as part of
the name. Quoted DBML identifiers use doubled double quotes for an embedded
quote. Table paths have either one segment (`public` is implied) or exactly two
segments. Reference paths have one to three segments according to the supported
DBML forms.

Before a decoded name can reach snapshot JSON or DDL, the server requires:

- non-empty text with no NUL;
- at most 63 UTF-8 bytes, preventing PostgreSQL truncation and object aliasing;
- terminated, unambiguous quoting and path segmentation; and
- a line no larger than the parser's existing 4,096-character work bound.

Malformed identifier input raises `DbmlParseError`. The HTTP conversion route
returns 422 and does not emit a partial snapshot or partial DDL. Unsupported
non-identifier DBML extensions remain outside this intentionally bounded parser
subset; this control does not claim full DBML grammar support.

## Rendering boundary

SQL parameters cannot bind object identifiers. `app.ddl.identifiers` is the
single dialect-owned validation and double-quote renderer used by DDL export,
migration generation (through the export renderer), index recommendations, and
Snowflake introspection rendering. The DBML constraint adapter uses the same
renderer when it builds primary- and foreign-key definitions.

Semicolons, whitespace, reserved words, Unicode, `--`, `//`, and other
punctuation are valid identifier data when quoted. They are not deny-listed.
Embedded `"` is rendered as `""`, keeping the value inside exactly one SQL
identifier token. The statement splitter likewise ignores semicolons inside
single- and double-quoted tokens. Statement validation and apply authorization
remain separate controls; successful quoting does not authorize generated SQL
for execution.

## Failure and recovery

Clients should correct the exact 422 diagnostic and resubmit the complete DBML
document. No database or stored snapshot has been changed at that point. If a
previous client relied on silently skipped malformed table/reference lines, it
must repair those lines; accepting a deceptively partial schema would violate
the fail-closed contract.

## Acceptance evidence

`backend/tests/test_dbml_import.py` covers ordinary names, Unicode, reserved
words, whitespace, embedded quotes, semicolons, comment markers, NUL, empty and
unterminated quotes, excessive UTF-8 length, empty/over-deep paths, bounded
hostile input, FK constraint rendering, API 422 behavior, and
parse→canonicalize→render round trips. DDL, migration, index-design, Snowflake,
and apply-validator focused suites protect the shared renderer's consumers.

## References

Su, Z., & Wassermann, G. (2006). The essence of command injection attacks in
web applications. *Proceedings of the 33rd ACM SIGPLAN-SIGACT Symposium on
Principles of Programming Languages*, 372–382.
https://doi.org/10.1145/1111037.1111070. The paper formalizes injection as a
failure to preserve the output language's grammatical structure and motivates
parsing untrusted input into structured values before rendering it. That model
supports this boundary's parse → canonicalize → identifier-render sequence.

Ray, D., & Ligatti, J. (2012). Defining code-injection attacks. *Proceedings of
the 39th ACM SIGPLAN-SIGACT Symposium on Principles of Programming Languages*,
179–190. https://doi.org/10.1145/2103621.2103678. The authors distinguish data
values from executable syntax by their role in the generated output. That
distinction supports accepting punctuation as identifier data while requiring
the dialect renderer to keep it inside one identifier token.

Open Worldwide Application Security Project. (2026). *SQL injection prevention
cheat sheet*. OWASP Cheat Sheet Series.
https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html

PostgreSQL Global Development Group. (2026). *PostgreSQL 18 documentation:
Lexical structure*. https://www.postgresql.org/docs/18/sql-syntax-lexical.html
