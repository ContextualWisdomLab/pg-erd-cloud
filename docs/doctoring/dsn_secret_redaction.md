# DSN secret-redaction contract

## Purpose

Database drivers may include connection-string fragments in exceptions. Those
messages can reach application logs or sanitized API errors, so pg-erd-cloud
must remove passwords, tokens, database connection strings, and equivalent
secret values before a message leaves the backend boundary. This defense is a
last-resort containment control; callers should still prefer generic public
errors and avoid logging raw driver exceptions.

## Encoding domains

URL user information and URL query parameters do not use interchangeable plus
semantics:

- user-information passwords are percent-decoded with
  `urllib.parse.unquote`; a literal `+` remains a literal plus;
- secret query values are form-decoded with `urllib.parse.unquote_plus`; a
  literal `+` represents a space;
- user-information candidates include their raw, decoded, and canonical
  percent-encoded representations;
- query candidates additionally include `quote_plus` representations because
  form encoders may emit spaces as plus signs.

This separation prevents a literal user-information password such as `a+b`
from creating the unrelated candidate `a b`, while still redacting query
secrets emitted in either `%20` or `+` form.

## Short-secret boundary rule

Secrets longer than four characters are replaced wherever their exact candidate
occurs. Candidates of four characters or fewer are inherently collision-prone
and are replaced only when the complete occurrence is not adjacent to a Unicode
word character:

```text
(?<!\w)<escaped candidate>(?!\w)
```

The rule redacts bounded values such as `user:a+@host` while preserving larger
identifiers and expressions such as `password`, `a+b`, or `café` when they do
not equal the candidate. Assignment-shaped values with secret-bearing keys are
also masked by the existing final assignment sanitizer.

## Malformed input and disclosure posture

Redaction must never raise because a DSN is malformed. If `urlsplit` rejects an
authority, the bounded best-effort parser extracts only the authority and query
segments needed to derive candidates. The function does not connect to the
reported host, resolve a URI, read a file, or expose the original DSN in a new
message.

No candidate generator can anticipate arbitrary transformations performed by
every driver. Therefore:

1. raw driver exceptions remain internal;
2. sanitized messages are treated as potentially sensitive operational data;
3. regression tests cover raw, decoded, percent-encoded, form-encoded,
   malformed, short, punctuation-bearing, and non-over-redaction cases;
4. a newly observed driver representation must be added test-first before its
   transformation is accepted into the candidate contract.

## Verification evidence

The security regression suite verifies:

- nonstandard schemes and malformed authorities;
- percent-encoded user-information and query secrets;
- literal-plus user-information semantics;
- form-plus query semantics;
- short alphanumeric and punctuation-bearing secrets;
- preservation of larger identifiers and arithmetic-like text;
- complete production application tests, SAST, and repository security scans.

## References

Open Worldwide Application Security Project. (n.d.). *Logging cheat sheet*.
Retrieved August 5, 2026, from
https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

Python Software Foundation. (2026). *urllib.parse—Parse URLs into components*
(Python 3.14.6 documentation).
https://docs.python.org/3/library/urllib.parse.html
