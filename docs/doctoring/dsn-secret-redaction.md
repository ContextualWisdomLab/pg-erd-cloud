# DSN secret-redaction boundary

## Decision

Database-driver errors are sanitized before they cross an API or diagnostic boundary. User-information passwords and query values are distinct encoding domains: authority values use `urllib.parse.unquote`, preserving literal plus signs, while query values use `urllib.parse.unquote_plus` because form encoding maps plus to space.

The sanitizer derives raw, decoded, and canonical encoded candidates, replaces longer candidates exactly, and applies Unicode word boundaries to short credentials. Matching is case-sensitive because credentials are case-sensitive. A final key-assignment pattern fails closed when malformed DSN syntax prevents complete parsing.

Malformed authorities are handled through bounded string slicing rather than returning the original error or raising. The output remains diagnostic text, not a safe shell command or HTML fragment.

## Verification

Tests cover nonstandard schemes, malformed IPv6 authorities, percent encoding, literal authority plus signs, query form plus signs, Unicode identifiers, punctuation-bearing short credentials, case sensitivity, assignment fallback, and parser edge branches. Complete backend pytest and mypy remain authoritative.

## References

Open Worldwide Application Security Project. (n.d.). *Logging cheat sheet*. OWASP Foundation. https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html

Python Software Foundation. (2026). *urllib.parse—Parse URLs into components*. https://docs.python.org/3/library/urllib.parse.html
