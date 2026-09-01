# Credential-provider contract

Status: **in progress** — first increment (typed boundary + two providers)
landed. Tracks issue
[#946](https://github.com/ContextualWisdomLab/pg-erd-cloud/issues/946)
("[Security/Product Gap] Replace runtime secret transport with an auditable
credential-provider contract").

## Problem

`Settings` is built directly from environment variables and `.env`.
`APP_SECRET_FILE` is a useful fail-closed Docker/Podman seam, but database
credentials, OIDC settings, LLM provider credentials, Clearfolio HMAC
material, metrics tokens, and Valkey credentials remain runtime configuration
with no single auditable lifecycle. Deployment-time environment transport
alone is not evidence of least privilege, rotation, revocation, or access
attribution.

The claim is **not** that environment variables are forbidden — it is that
they are no longer the *unaudited runtime authority*.

## Decision — the boundary (this increment)

`app/secret_provider/`:

* **`SecretReference`** — non-secret metadata only (`name`, `purpose`,
  `provider`, optional `version` / `intended_consumer`). No value field. Its
  `__str__` carries no value.
* **`ResolvedSecret`** — holds the value but exposes it only via
  `reveal()`; `__str__` / `__repr__` / `__format__` all redact, so an
  `f"{secret}"`, a `%s`, a log record, or a traceback cannot leak it. Carries
  `retrieved_at` and an opaque `audit_reference` (a truncated SHA-256 of
  provider + purpose + name + size — never the value) for use-to-retrieval
  correlation.
* **`CredentialProvider`** — a `runtime_checkable` `Protocol`:
  `provider_name` + `resolve(reference) -> ResolvedSecret`. Implementations
  fail closed and never fall back to an unaudited source.
* **`SecretResolutionError`** — the single fail-closed exception. Its message
  names the reference and the reason, never the value.
* **`LocalMountedFileProvider(base_dir="/run/secrets", *, max_bytes=64 KiB)`**
  — the explicit `local_secret_file` deployment profile. Fails closed on:
  missing, empty, oversized, non-UTF-8, symlink, path-escape (`..`, absolute,
  multi-segment name), non-regular file, and a file that escapes the base
  directory. Strips exactly one trailing `\n`. No hidden environment fallback.
* **`DeterministicTestProvider(mapping)`** — in-memory, fixed timestamp, fails
  closed for an unknown name.

`Settings` is **not** wired to this yet — that is the next increment.

## Deferred (later increments on #946)

- **`Settings` integration** behind a `local_secret_file` deployment profile;
  runtime modules consume typed handles instead of reading env/files.
- **Organization credential-registry provider** (Keyverse / the org registry)
  with timeout / permission-denial / revoked-version / stale-cache fail-closed
  behaviour and a documented cache TTL + invalidation.
- **`APP_SECRET` rotation** — see the design below.
- **Recovery runbook** proving that recovery when the active encryption key is
  unavailable cannot expose DSN plaintext.
- **LLM provider credentials** move to the `contextual-orchestrator` contract;
  pg-erd-cloud does not become a general-purpose provider-key vault.
- Non-secret credential **metadata records** (purpose, provider, version,
  created/rotated/revoked timestamps, intended consumer, retrieval audit
  reference) persisted for audit.

## APP_SECRET dual-read / single-write rotation — DESIGN (not yet implemented)

`APP_SECRET` encrypts stored DSNs. Rotating it must re-encrypt existing rows
without an outage or silent data loss.

1. **Key set, not a key.** The crypto layer takes an ordered key list:
   `[active, *previous]`, each a `SecretReference` (e.g.
   `app_secret` / `app_secret_previous_1` …). Decryption tries the active key
   first, then each previous key (**dual-read**). Encryption always uses the
   active key (**single-write**).
2. **Rotation step 1** — provision the new key as `app_secret`, demote the old
   one to `app_secret_previous_1`. New writes use the new key immediately;
   old rows still decrypt via the previous key. No downtime.
3. **Rotation step 2** — a bounded, resumable migration job walks
   `db_connection` rows, decrypts with whichever key works, re-encrypts with
   the active key, and records progress. It uses optimistic concurrency
   (version column) so a concurrent snapshot job that updates a connection
   does not corrupt it; a row already re-encrypted is skipped.
4. **Rotation step 3** — once every row's stored key generation is the active
   one, the previous key is removed from the key set and revoked at the
   provider.
5. **Failure modes** — if no key in the set decrypts a row, the row is
   surfaced as `needs_key_recovery`, never silently dropped; the migration job
   is idempotent and safe to re-run.

## References (APA 7th)

Barker, E. (2020). *Recommendation for key management: Part 1 — General*
(NIST Special Publication 800-57 Part 1 Revision 5). National Institute of
Standards and Technology. https://doi.org/10.6028/NIST.SP.800-57pt1r5

National Institute of Standards and Technology. (2022). *Secure software
development framework (SSDF) version 1.1* (NIST Special Publication 800-218).
https://doi.org/10.6028/NIST.SP.800-218

Open Worldwide Application Security Project. (n.d.). *Secrets management cheat
sheet*. OWASP Cheat Sheet Series.
https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html
