# DSN Secret Redaction Boundary

## Incident class

Database drivers and connection libraries can repeat a database source name
(DSN), its user-information, or secret-bearing query parameters in an exception.
Passing those messages through unchanged can disclose passwords, tokens, API
keys, and connection strings in API responses, support bundles, or logs.

The risk is not limited to one textual representation. A driver can emit the raw
percent-encoded value, a decoded value, or a canonical re-encoding. A redactor
that handles only one form can leave equivalent credentials visible. Conversely,
using form-query decoding rules for URL user-information can create false
candidates and corrupt unrelated diagnostic text.

## Decision

`backend/app/dsn_redaction.py` applies two ordered defenses:

1. Recognized secret-key assignments such as `password=...`, `token: ...`, and
   `api_key=...` are masked independently of DSN parsing.
2. Additional candidates are derived from the supplied DSN and replaced in the
   remaining message.

The candidate domains remain intentionally separate:

- URL user-information passwords use `urllib.parse.unquote`. A literal `+`
  remains a plus, while percent-encoded octets such as `%20` are decoded. The
  implementation adds the raw, decoded, and `quote(..., safe="")` forms.
- Query-string secret values use `urllib.parse.unquote_plus`, because HTML form
  query semantics map `+` to a space. The implementation adds raw, decoded,
  `quote`, and `quote_plus` forms only in this domain.

Candidates longer than four characters are replaced by exact,
case-insensitive occurrence. Short candidates use Unicode-aware
`(?<!\w)` and `(?!\w)` boundaries, which mask a standalone value without
corrupting a larger identifier or natural-language word that merely contains
it. Malformed authorities use best-effort extraction and never cause the
redaction boundary itself to raise. The complete diagnostic message is
preserved; redaction does not impose an unrelated truncation policy.

## Verification

`backend/tests/test_dsn_redaction.py` covers:

- raw, decoded, and canonical encoded user-information passwords;
- query tokens with form-query decoding semantics;
- a literal-plus password without treating an unrelated space as equivalent;
- a `%20` user-information password without treating unrelated `a+b` text as
  equivalent;
- standalone Unicode and punctuation-bearing short secrets while preserving
  larger surrounding words;
- malformed and scheme-less DSNs;
- case-insensitive standalone candidates;
- assignment sanitization combined with DSN-derived candidates; and
- preservation of messages longer than 1,000 characters.

CI must install the immutable, hash-locked development dependency set and run
static typing and the full backend tests on the exact pull-request head. Security
Scan and Semgrep remain independent required gates.

## Operational impact

The function returns a sanitized diagnostic string. It does not alter connection
establishment, driver selection, DSN storage, authentication, or database
behavior. Downstream code should still avoid logging raw DSNs and should keep
structured secret fields out of log records. Redaction is a defense-in-depth
boundary, not permission to collect plaintext credentials.

## Research basis

Krause et al. (2023) found that accidental secret leakage is common in source
code workflows and that prevention and remediation mechanisms need low adoption
cost. Applying automatic redaction at the common error-message boundary reduces
the number of callers that must implement secret-specific handling correctly.

OWASP identifies passwords, access tokens, database connection strings,
credentials, and similar values as data that should not be recorded in plaintext
logs. Its secrets-management guidance explicitly requires encryption or masking
when a secret could otherwise reach a log. Python's `urllib.parse`
documentation is authoritative for the semantic distinction that
`unquote_plus` maps plus signs to spaces for form values, while `unquote` does
not.

The peer-reviewed paper is linked to the publisher-maintained open-access copy
rather than vendored as a binary, preserving provenance and avoiding a stale or
license-ambiguous repository copy.

## References

Krause, A., Klemmer, J. H., Huaman, N., Wermke, D., Acar, Y., & Fahl, S.
(2023). Pushed by accident: A mixed-methods study on strategies of handling
secret information in source code repositories. In *32nd USENIX Security
Symposium (USENIX Security 23)* (pp. 2527–2544). USENIX Association.
https://www.usenix.org/conference/usenixsecurity23/presentation/krause

Open Worldwide Application Security Project. (n.d.). *Logging cheat sheet*.
OWASP Cheat Sheet Series. Retrieved August 6, 2026, from
https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

Open Worldwide Application Security Project. (n.d.). *Secrets management cheat
sheet*. OWASP Cheat Sheet Series. Retrieved August 6, 2026, from
https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html

Python Software Foundation. (n.d.). *urllib.parse—Parse URLs into components*.
Python documentation. Retrieved August 6, 2026, from
https://docs.python.org/3/library/urllib.parse.html
