# DSN secret-redaction boundary

## Decision

Database-driver error messages are sanitized before they can cross the backend response or diagnostic boundary. The sanitizer derives a bounded set of exact password and secret spellings from the configured DSN, replaces those spellings longest-first, and finishes with a key-name assignment sanitizer.

DSN user-information and query values intentionally use different decoding rules:

- authority/user-information passwords use `urllib.parse.unquote`; a literal `+` remains a plus sign;
- query keys and secret values use `urllib.parse.unquote_plus`; form-encoded `+` represents a space;
- authority candidates include the raw value, its percent-decoded value, and the canonical `quote(..., safe="")` spelling;
- query candidates additionally include both `quote` and `quote_plus` spellings because database clients may render form values in either percent-encoded form.

Using `unquote_plus` for authority passwords is rejected. It turns a legitimate literal-plus credential such as `a+b` into the unrelated phrase `a b`, causing over-redaction and potentially corrupting useful operator diagnostics.

## Short-secret boundary

Candidates longer than four characters are replaced by exact occurrence. Short credentials require more care because ordinary messages may contain the same one-to-four-character sequence.

When a short secret begins or ends with a Python Unicode word character, the corresponding regular-expression edge uses `(?<!\w)` or `(?!\w)`. Python's default Unicode-aware `\w` behavior prevents a one-character secret from being removed inside larger Korean, Latin, or other Unicode identifiers. No boundary is added to a punctuation edge, because punctuation is part of the credential and an exact occurrence must remain redactable even when adjacent to a word character.

ASCII-only boundary classes such as `[A-Za-z0-9]` are rejected because they treat non-ASCII letters as separators and can redact an embedded secret from a larger internationalized identifier.

## Malformed-input behavior

`urllib.parse.urlsplit` is not a DSN validator and can raise `ValueError` for malformed authorities. Redaction must fail closed rather than returning the original secret-bearing diagnostic. The existing bounded fallback therefore extracts only the authority and query regions with string slicing, then applies the same domain-specific candidate rules.

The sanitizer never opens a socket, resolves a hostname, authenticates to a database, mutates a DSN, or persists a credential. It receives an already available DSN and error message and returns a redacted string.

## Standalone and modular boundary

This module has no framework, database, network, or Naruon dependency. `pg-erd-cloud` can use it directly in its standalone backend, while another ContextualWisdomLab service can import the same pure function through a narrow adapter. Credential ownership, storage, rotation, tenant authorization, and audit retention remain outside this module.

## Verification contract

Permanent tests exercise realistic driver messages and require:

1. raw, decoded, and percent-encoded authority passwords are removed;
2. query-token spellings rendered with percent or form encoding are removed;
3. a literal `+` in user-information does not create a false space candidate;
4. a `+` in a form query still decodes to a space candidate;
5. short ASCII and non-ASCII secrets are removed when standalone but preserved inside larger Unicode identifiers;
6. punctuation-edge short secrets remain removable next to word characters;
7. malformed authorities still redact recovered secrets; and
8. secret-key names and unrelated larger words are not corrupted.

The complete backend pytest/mypy gate, repository-wide 100% production statement and branch coverage, frontend checks/build, Security Scan, SAST Semgrep, current-head automated review, and independent approval remain mandatory.

## Privacy and claim boundary

Redaction is defense in depth. Database connection strings, passwords, access tokens, and primary secrets must not be logged in the first place. Candidate extraction cannot guarantee removal of an unknown secret that is absent from the DSN and does not appear in a recognized assignment. Callers must therefore keep public error messages fixed and non-sensitive, restrict diagnostic access, and avoid serializing raw driver exceptions.

No formal OWASP or standards conformance is claimed.

## Rollback

Rollback must preserve the decoding-domain split and Unicode boundary tests. Reintroducing `unquote_plus` for authority passwords or ASCII-only word boundaries would restore demonstrated over-redaction defects and is not an acceptable rollback. A replacement sanitizer must pass the same realistic and malformed-input contracts before this implementation is removed.

## APA 7th references

Berners-Lee, T., Fielding, R., & Masinter, L. (2005). *Uniform resource identifier (URI): Generic syntax* (RFC 3986). RFC Editor. https://doi.org/10.17487/RFC3986

OWASP Foundation. (2026). *Logging cheat sheet*. OWASP Cheat Sheet Series. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

Python Software Foundation. (2026). *urllib.parse—Parse URLs into components* (Python 3.14.6 documentation). https://docs.python.org/3.14/library/urllib.parse.html
