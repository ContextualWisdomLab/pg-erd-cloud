# Forward Engineering Standards and Evidence Baseline

- **Document status:** Active engineering baseline
- **Runtime status:** Partially implemented; no compliance certification claimed
- **Last reviewed:** 2026-08-11

This document selects primary standards and one directly relevant research
paper for design and verification. It does not assert PostgreSQL compatibility,
WCAG conformance, ASVS verification, OWASP “compliance,” NIST conformance, or
any third-party certification. Those claims require scoped evidence against an
identified release.

Status labels are normative: **Implemented**, **Partially implemented**,
**Planned**, and **Rejected**.

## Baseline and precedence

| Source | How pg-erd-cloud uses it | Normative status for this project |
|---|---|---|
| PostgreSQL 18 official documentation | Lock/transaction behavior, `ALTER TABLE`, index transaction capability, and timeout semantics; behavior is verified separately on supported majors 14–18. | Normative technical reference, plus version-matrix tests |
| Valkey 8 official release and container image | Queue-signal sorted-set semantics, UUID-only ready/processing isolation, monotonic exact lease renewal, expired-owner renewal rejection, stale-token rejection, retry release, and acknowledgement are verified through the production adapter against a digest-pinned official image. Every PostgreSQL 14–18 matrix cell also composes Valkey with PostgreSQL-backed hashed attempt ownership and the execution-neutral consumer, proving durable abandon/retry/complete ordering, real one-second dual-lease expiry/takeover, stale-owner rejection, and exact signal cleanup across both stores. This does not prove production topology, startup wiring, process/container restart, failover, credentials, or worker recovery. | Integration-test runtime reference; scheduled publisher, signal lease/consumer contract, DB attempt primitives, dual-lease binding, and composed in-process ephemeral-store expiry/recovery evidence Implemented; application startup/deployment failover/worker evidence Planned |
| W3C WCAG 2.2 Recommendation | Keyboard, focus, labels, status/error communication, and target Level AA acceptance for the forward UI. | Normative product accessibility target; conformance not yet demonstrated |
| OWASP ASVS 5.0.0 | Verification requirements for architecture, authentication, access control, validation, API, data protection, logging, and secure communication. | Normative security verification baseline selected by the project; not certification |
| OWASP Top 10:2025 | Web-application risk taxonomy used to check design and test coverage. | Threat-model checklist, not a control catalog or certification |
| OWASP API Security Top 10:2023 | API authorization, resource consumption, SSRF, misconfiguration, inventory, and unsafe downstream consumption review. | API threat checklist |
| NIST SP 800-218, SSDF 1.1 | Secure-development practices for prepare/protect/produce/respond activities and release evidence. | Normative secure-development process baseline |
| NIST SP 800-218 Rev. 1, SSDF 1.2 initial public draft | Future-update watchlist. It was an initial public draft as of this review. | **Non-normative** until NIST publishes a final revision and the project adopts it |
| RFC 9457 | Target media model for consistent machine-readable API problem details. | Planned API error-contract baseline; current errors are not yet uniform RFC 9457 responses |
| Rae et al. (2013) | Research evidence that online schema change requires controlled intermediate states, sequencing, and verification. | Informative only; F1-specific mechanisms are not PostgreSQL prescriptions |

If a source conflicts with observed PostgreSQL behavior on a supported major,
the operation fails closed and requires an ADR/compiler contract update. A
research paper never overrides official PostgreSQL behavior, a security
requirement, or repository evidence.

## PostgreSQL engineering rules

### Locks, scans, and rewrites

- Treat `ALTER TABLE` as capable of acquiring `ACCESS EXCLUSIVE` unless the
  exact command documentation states a weaker level. Compiler risk metadata
  and review UI must not imply that a quick catalog change is harmless.
- PostgreSQL locks are normally held until transaction end. A transaction that
  performs multiple DDL statements can therefore accumulate blocking impact;
  bounded lock and statement timeouts remain mandatory even when rollback is
  available.
- Type changes and constraint validation can scan or rewrite data and indexes.
  Compiler v1 classifies every actual `ALTER COLUMN ... TYPE` as destructive
  with possible rewrite, table scan, and data-loss risk. Isolated execution and
  live data-aware preflight provide separate evidence; they do not downgrade
  that approval classification.
- `CREATE INDEX CONCURRENTLY` cannot execute inside a transaction block and can
  leave recovery work after failure. It and all non-transactional operations
  are **Rejected for v1**, not mixed into an executable partial plan.
- `lock_timeout`, `statement_timeout`, and transaction timeout policy must be
  finite and scoped to the worker session/transaction. A timeout establishes a
  bounded wait or execution failure; it does not by itself prove rollback or
  non-commit.

### Version support

The model contract accepts PostgreSQL majors 14–18. PostgreSQL 18 documentation
is the current design reference, but no operation ships on older supported
majors solely by inference. The [test strategy](TEST_STRATEGY.md) requires real
catalog, syntax, lock, privilege, transaction, and convergence tests on each
major.

### Project application

| Rule | Repository application | Status |
|---|---|---|
| SQL authority | Canonical server model and structured compiler; dialect-correct identifier quoting. | Partially implemented |
| Lock/rewrite disclosure | Each current statement has risk severity, declared lock, scan/rewrite/data-loss fields. | Implemented control-plane metadata; runtime measurement Planned |
| Live preconditions | Table-empty, no-NULL, and castability preconditions are represented. | Implemented plan metadata; bounded live-preflight execution and completion CAS are Implemented, as are the signed-plan lock-covered manifest, fixed parameterized privilege probes, and caller-owned same-connection read-only snapshot/privilege/precondition capture. Stored-target/attempt binding, target lock acquisition, durable apply-worker binding, and apply-time in-lock repetition remain Planned |
| Transaction capability | Current emitted statements declare `transactional: true`; blockers set executable `statements=[]`. Supported deltas may remain as review-only `proposed_statements`, with their risks included. | Implemented compiler subset; bounded all-transactional isolated executor core is Implemented, as is the target-free zero/no-op-or-one ordered apply-segment input; deployed sandbox worker and live apply transaction/rollback execution remain Planned |
| Drift control | Plans store base/target digests and bind a succeeded snapshot. | Implemented provenance, target-free signed manifest, fail-closed pure assessment, and bounded caller-owned same-connection strict snapshot capture; stored-target/attempt identity proof, lock proof, and in-lock pre-apply repetition remain Planned |
| Completion evidence | Exact post-apply target digest from a persisted verification snapshot. | Planned |

## Security verification baseline

The project uses ASVS 5.0.0 as a requirements source and OWASP Top 10/API Top
10 as threat-discovery views. Control identifiers must be pinned during a
release verification pass rather than guessed in this document; the release
artifact records the exact ASVS requirement IDs, applicability, evidence, and
exceptions.

| Security concern | Required project evidence | Current status |
|---|---|---|
| Architecture and trust boundaries | Versioned ADRs, architecture/UML, threat model, separate metadata/sandbox/live authority. | Partially implemented; dedicated integration databases prove the code boundary, while deployed sandbox/run isolation remains Planned |
| Authentication and session integrity | Existing authentication, CSRF for state changes, credentialed CORS, revocation/rate-limit tests. | Implemented general controls; forward HTTP matrix Planned |
| Object-level and function-level authorization | Uniform other-project 404; `viewer < editor < deployer < owner`; server checks on every resource/action. | Partially implemented |
| Input and execution safety | Unknown fields fail closed; server-rendered SQL; known structured executor kinds only; no browser SQL authority. | Partially implemented; legacy endpoint remains |
| SSRF and outbound target control | Explicit host allowlist, restricted-address rejection, DNS resolution and IP pinning, deployment egress verification. | Application guard Implemented; deployment evidence Planned |
| Cryptography and secret handling | AEAD at rest, in-memory decryption after authorization, redaction, rotation/recovery/key-separation policy. | Partially implemented |
| Resource consumption | Payload/statement bounds, API rate limits, worker concurrency, sandbox quota, finite target timeouts. | Partially implemented; worker controls Planned |
| Logging and audit | Correlation identifiers, append-only run events, bounded redacted diagnostics, alertable terminal states. | General request observability exists; run audit Planned |
| Supply chain and secure release | Hash-locked backend dependencies, npm lockfile, pinned CI actions, type/test/build/SAST and exact-head evidence. | Partially implemented; forward coverage/integration gates Planned |

Relevant threat categories include broken access control/object authorization,
security misconfiguration, injection, cryptographic failures, software/data
integrity failures, logging/alerting failures, unrestricted resource
consumption, SSRF, improper inventory, and unsafe consumption of target-driver
diagnostics. Mapping is for coverage; it is not a declaration that a category
has been eliminated.

## NIST SSDF application

NIST SSDF 1.1 is the adopted final process baseline:

| SSDF practice group | pg-erd-cloud evidence | Status |
|---|---|---|
| Prepare the Organization (PO) | Named architecture/security/operator owners; standards, threat model, release gates, and training/operating assumptions. | Partially implemented |
| Protect the Software (PS) | Protected source/CI, lockfiles, pinned actions, secret boundaries, provenance and review. | Partially implemented; branch/release evidence is external to this document |
| Produce Well-Secured Software (PW) | Server-authoritative design, ADRs, tests, code review, SAST, fail-closed compiler and planned fault injection. | Partially implemented |
| Respond to Vulnerabilities (RV) | `SECURITY.md`, dependency/SAST workflows, threat-model updates, incident evidence and runbook closure. | Partially implemented |

SSDF 1.2 (NIST SP 800-218 Rev. 1 initial public draft, published December 17,
2025) is explicitly **not normative** for this release baseline. Maintainers may
track its changes, but must not cite draft alignment as final NIST conformance.

## Accessibility baseline

The planned forward modal and all recovery views target WCAG 2.2 Level AA. At
minimum, design and tests must address:

- complete keyboard operation without timing-dependent traps;
- visible focus, logical focus order, modal containment, Escape behavior only
  where cancellation is safe, and focus restoration;
- programmatic names, headings, instructions, error association, and risk table
  semantics;
- status/progress/error live regions that do not collapse distinct recovery
  outcomes;
- adequate contrast, non-color risk indicators, target size, reflow/zoom, and
  no obscured focus; and
- authentication/confirmation interactions that remain understandable and do
  not depend on memory or inaccessible puzzle behavior.

Automated checks are necessary but insufficient. Manual keyboard and
representative assistive-technology evidence must be attached to the release.
The current repository does not contain the forward UI, so no WCAG conformance
claim is made.

## API problem details

RFC 9457 is the **Planned** uniform error envelope. Before public v1, the API
must choose and test `application/problem+json` responses with stable problem
type URIs or an explicitly documented compatible media contract. At minimum,
forward errors need machine-stable codes/types for stale revision/plan,
expired plan, idempotency conflict, invalid model/binding, unsupported schema,
drift, timeout, authorization, and unavailable evidence.

Current FastAPI routes commonly return `{"detail": ...}` strings. Those are
implementation truth, not RFC 9457 conformance. Cross-project identities must
remain uniformly masked regardless of the future error shape, and problem
details must never include DSNs, raw SQL batches, row values, or
credential-derived driver text.

## Research use and limits

Rae et al. describe an online, asynchronous schema-change system for Google's
F1 database. The paper supports the architectural need for explicit
intermediate states, controlled ordering, compatibility, and verification.
pg-erd-cloud does not infer that F1 algorithms, distributed guarantees, or
operational performance apply to PostgreSQL. The project instead uses official
PostgreSQL semantics plus its own integration and fault-injection evidence.

## Change control

- Review stable baseline versions at least for each planned release and when a
  referenced body publishes a final replacement.
- A major PostgreSQL operation/version expansion, non-transactional executor,
  changed approval authority, or changed recovery claim requires an ADR and
  contract version.
- Update the threat model, test strategy, runbook, traceability matrix, and
  citations in the same change that alters the baseline.
- Record standard version, scoped applicability, evidence location, exceptions,
  owner, and expiry in the release artifact. Do not use a green CI badge as a
  substitute for the scoped evidence.

## References

Internet Engineering Task Force. (2023). *Problem details for HTTP APIs*
(RFC 9457). https://www.rfc-editor.org/rfc/rfc9457.html

National Institute of Standards and Technology. (2022). *Secure software
development framework (SSDF) version 1.1: Recommendations for mitigating the
risk of software vulnerabilities* (NIST SP 800-218).
https://doi.org/10.6028/NIST.SP.800-218

National Institute of Standards and Technology. (2025, December 17). *Secure
software development framework (SSDF) version 1.2* (NIST SP 800-218 Rev. 1,
initial public draft). https://csrc.nist.gov/pubs/sp/800/218/r1/ipd

OWASP Foundation. (2023). *OWASP API Security Top 10 – 2023*.
https://owasp.org/API-Security/editions/2023/en/0x11-t10/

OWASP Foundation. (2025). *OWASP Application Security Verification Standard
5.0.0*. https://owasp.org/www-project-application-security-verification-standard/

OWASP Foundation. (2025). *OWASP Top 10:2025*.
https://owasp.org/Top10/2025/

PostgreSQL Global Development Group. (n.d.). *PostgreSQL 18 documentation:
ALTER TABLE*. Retrieved August 9, 2026, from
https://www.postgresql.org/docs/18/sql-altertable.html

PostgreSQL Global Development Group. (n.d.). *PostgreSQL 18 documentation:
CREATE INDEX*. Retrieved August 9, 2026, from
https://www.postgresql.org/docs/18/sql-createindex.html

PostgreSQL Global Development Group. (n.d.). *PostgreSQL 18 documentation:
Client connection defaults*. Retrieved August 9, 2026, from
https://www.postgresql.org/docs/18/runtime-config-client.html

PostgreSQL Global Development Group. (n.d.). *PostgreSQL 18 documentation:
Explicit locking*. Retrieved August 9, 2026, from
https://www.postgresql.org/docs/18/explicit-locking.html

Valkey Project. (2026, July 21). *Valkey 8.1.9*.
https://valkey.io/download/releases/v8-1-9/

Valkey Project. (2026). *valkey/valkey official container image*. Docker Hub.
Retrieved August 11, 2026, from https://hub.docker.com/r/valkey/valkey/

Rae, I., Rollins, E., Shute, J., Sodhi, S., & Vingralek, R. (2013). Online,
asynchronous schema change in F1. *Proceedings of the VLDB Endowment, 6*(11),
1045–1056. https://doi.org/10.14778/2536222.2536230

World Wide Web Consortium. (2024, December 12). *Web Content Accessibility
Guidelines (WCAG) 2.2*. https://www.w3.org/TR/WCAG22/

## Related authority

- [Forward-engineering v1 contract](contracts/forward-engineering-v1.md)
- [Threat model](security/forward-engineering-threat-model.md)
- [Test strategy](TEST_STRATEGY.md)
- [Operational runbook](runbooks/forward-engineering.md)
- [Documentation audit](DOCUMENTATION_AUDIT.md)
