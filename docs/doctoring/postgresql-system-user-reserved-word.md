# PostgreSQL `SYSTEM_USER` reserved-word contract

## Status

Implemented for the PostgreSQL 18 naming-lint profile.

## Decision

The naming linter classifies `system_user` case-insensitively as a high-severity `reserved_word` finding. PostgreSQL 18.4 lists `SYSTEM_USER` as reserved, so an unquoted schema object using that token is not a portable ordinary identifier and requires quoting semantics that the product intentionally treats as a naming hazard.

The linter does not rewrite an identifier. It reports the exact object so the user can rename it deliberately. Quoted identifiers remain a database-authoring choice; this rule exists to prevent a generated or reviewed schema from silently depending on quoting for a token that PostgreSQL itself reserves.

## Standards and implementation evidence

ISO/IEC 9075-2:2023 is the current published SQL/Foundation international standard. A sixth-edition technical corrigendum is under publication in August 2026, while the seventh edition remains a committee draft; neither draft status replaces the published 2023 baseline. PostgreSQL 18.4 Appendix C is the implementation authority for the product's PostgreSQL profile and explicitly classifies `SYSTEM_USER` as reserved in PostgreSQL as well as in the listed SQL standards.

## Verification contract

- A table named `system_user` produces a high-severity `reserved_word` finding.
- Matching is case-insensitive, consistent with the existing reserved-word lookup.
- Existing clean snake-case identifiers remain unaffected.
- No automatic rename or database mutation occurs.
- The focused regression is kept in `backend/tests/test_naming_lint.py`.

## Monitoring and rollback

When the supported PostgreSQL major changes, compare the complete reserved-word profile against that major's Appendix C before changing the set. If PostgreSQL reclassifies a token, update the implementation, regression evidence, and this record together. Rollback of this rule is acceptable only with authoritative evidence that the supported PostgreSQL profile no longer reserves `SYSTEM_USER`.

## References

International Organization for Standardization, & International Electrotechnical Commission. (2023). *ISO/IEC 9075-2:2023: Information technology—Database languages SQL—Part 2: Foundation (SQL/Foundation)* (6th ed.). International Organization for Standardization. https://www.iso.org/standard/76584.html

PostgreSQL Global Development Group. (2026). *Appendix C. SQL key words*. In *PostgreSQL 18.4 documentation*. https://www.postgresql.org/docs/18/sql-keywords-appendix.html
