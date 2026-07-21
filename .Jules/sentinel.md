## 2026-07-21 - Fix DBML Constraint Name Injection and Resource Exhaustion
**Learning:**
- Attacker-controlled quoted table identifiers in DBML could generate unsafe primary/foreign-key constraint names, enabling SQL statement injection when interpolated into unquoted downstream DDL.
- `text.splitlines()` without aggregate input size limits caused severe CPU and memory exhaustion (multi-gigabyte amplification).

**Action:**
- Applied `_safe_constraint_name` utility to generate deterministic constraint names from an ASCII allowlist, collapsing invalid characters, hashing for uniqueness over 63 characters length.
- Added a 10 MiB aggregate input limit `if len(text) > 10 * 1024 * 1024` and a limit of 100,000 max columns parsing loop break.
