# Threat Model

Status date: 2026-08-09
Scope: pg-erd-cloud runtime, PR #824 public sharing, and the planned governed
Forward Engineering boundary

This model uses asset/actor/trust-boundary analysis with STRIDE-style threat
categories. It supports risk review; it does not claim OWASP ASVS, CSAP, SOC 2,
or any other certification.

## Assets and protection objectives

| Asset | Confidentiality | Integrity | Availability |
| --- | --- | --- | --- |
| Target DSNs and application secrets | Never in client DTOs, logs, plans, or audit bodies | Rotation and key identity are controlled | Loss must fail closed without corrupting metadata |
| Project membership and approvals | Membership details are tenant-scoped | Role and approval cannot be forged or replayed | Authorization remains available without stale-replica bypass |
| Schema snapshots and annotations | Names/comments/examples may be sensitive | Snapshot identity and provenance are preserved | Large or malformed metadata is bounded |
| Desired models and migration plans | Private until purpose-bound sharing | Revision, target, plan order and digest are immutable | Durable recovery preserves exact state |
| Target database | No uncontrolled reads or egress | Only exact authorized supported changes run | Lock/rewrite/resource impact is bounded |
| Audit evidence | Sensitive bodies are redacted | Ordering and digest detect modification | Retention and export support incident response |
| Bearer share link | URL value is capability material | Scope, expiry and permission cannot be escalated | Abuse is rate-limited; owner API expiry/revocation is `active_pr` |

## Actors and trust boundaries

- Project `viewer`, `editor`, and `owner` principals authenticated by OIDC or an
  API key.
- Public bearer-link recipient, including an unintended recipient.
- Application API/worker and application PostgreSQL.
- Customer-controlled target database and DNS/network path.
- External OIDC, LLM, reverse proxy, and future credential-registry services.
- Supply-chain or compromised-client attacker able to alter browser requests.

The main boundaries are public edge → API, authenticated tenant → another
tenant, API/worker → target network, API → external providers, and mutable
browser state → server execution authority. See [Architecture](../ARCHITECTURE.md).

## Threat and control register

| ID | Category | Threat and abuse case | Current control/evidence | Residual or planned work |
| --- | --- | --- | --- | --- |
| TM-010 | Spoofing / IDOR | A user substitutes another project, connection, snapshot, view, annotation, key, or share UUID. | OIDC/API-key principals and project-role helpers; route tests. `implemented_on_main` | Composite DB invariants and consistent not-found semantics remain `planned`. |
| TM-020 | Information disclosure | A bearer URL leaks through copying, history, logs, referrers, caches, or an unintended recipient. | UUID capability, configurable creation expiry, owner-only project-scoped delete, and read-only DTO. Every public request validates link existence and expiry on the primary-consistent session, so replica lag cannot extend a revoked capability. API responses and the public SPA document use `Referrer-Policy: no-referrer` and `Cache-Control: no-store`; share hardening is `active_pr`. | Browser history and copied URLs remain capability leaks; UI revocation, rotation, access audit and optional domain/password restriction are `planned`. |
| TM-030 | Information disclosure | Public snapshot/export exposes comments, examples, errors, connections, annotations, or LLM prompts. | PR #824 filters to successful snapshots, projects root and collection rows through path-scoped public-v1 allowlists, rejects nested-object/wrong-level mutations, suppresses errors, and blocks public live LLM. | Complete Pydantic response models, formal route/version negotiation, generated client contracts, and broader property/fuzz/mutation tests remain `planned`. |
| TM-040 | SSRF / elevation | A DSN reaches loopback, private/link-local/cloud metadata, disallowed ports, or changes DNS after validation. | Scheme/query validation, a fail-closed required host allowlist, DNS resolution, and restricted-IP rejection. PostgreSQL connections use the validated IP set. `implemented_on_main` | The Snowflake connector still receives the account hostname rather than the validated IP, so DNS rebinding remains a connector-specific gap. Verified target identity and centralized egress policy remain deployment requirements. |
| TM-050 | Credential disclosure | DSNs or app/LLM/OIDC secrets leak through storage, responses, exception text, environment, or telemetry. | AES-GCM DSN ciphertext/nonce, response omission, error redaction tests. | Runtime environment-backed settings violate org policy; credential registry, rotation/rewrap and evidence are `planned`. |
| TM-060 | Tampering / SQL injection | A client modifies generated SQL or submits arbitrary DDL to the target. | Deprecated `/apply-sql` uses a small fail-closed validator and project role; frontend does not call it. | Server-owned typed plan/parser/rendering, exact digest approval, least-privilege executor, safe search path, and removal plan are `planned`. |
| TM-070 | TOCTOU / elevation | Target schema, privileges, server version, extensions, or approval changes between review and apply. | No production Forward Engineering path exists. | Immediate fingerprint/privilege/policy revalidation and expiring bound approval are required by FE-140/150. |
| TM-080 | Denial / integrity | Worker crash strands a snapshot/job in `running`, or duplicate work executes twice. | PostgreSQL queued rows survive restart and `SKIP LOCKED` prevents simultaneous queued-row claim. | Lease, heartbeat, reclaim, idempotency, retry, dead-letter state and stuck-job alerting are `planned`. |
| TM-090 | Repudiation | Actor denies approval or execution; mutable rows are altered after the event. | Ordinary timestamps and request/job identifiers provide partial evidence. | Canonically serialized, authenticated event chains with external signed/HMAC checkpoints or an immutable external sink, key rotation/verification, retention and access review are `planned`; an unauthenticated hash chain inside the same mutable database is insufficient. |
| TM-100 | Information disclosure | Authenticated live-LLM mode sends schema/comments/examples to an external provider without adequate purpose or retention control. | Public mode is blocked in PR #824; provider is configured explicitly. | Consent/purpose, data minimization, provider retention/region, DPA, egress audit and contextual-orchestrator policy are `planned`/`downstream`. |
| TM-110 | Denial of service | Public or authenticated endpoints consume CPU/memory/LLM budget across replicas. | Request-size bounds and in-memory per-worker rate limits exist. The production-style proxy contract allowlists the host-visible TLS-terminator source and selects the configured client hop so unrelated remote viewers do not share one proxy bucket. | The loopback-published reference stack trusts the Docker NAT gateway, so another compromised host-local process could forge forwarded IPs; a dedicated proxy network identity remains deployment hardening. Shared distributed limits, cost quotas, pagination, backpressure and abuse telemetry are `planned`. |
| TM-120 | Tampering / XSS | Schema-controlled strings become HTML/script or escape an export context. | React renders strings as text; export quoting and the explicit public DTO allowlist cover selected paths. | Browser E2E, content-security-policy validation, and broader property/fuzz/mutation tests remain required. |
| TM-130 | Authorization race | Read-replica lag returns stale membership during connection test/apply. | Public bearer validation is primary-consistent and route dependency tests prevent replica routing; other role lookups exist, but optional read routing can still be stale. | Every remaining security-sensitive authorization decision must use primary/consistency proof and integration evidence. |
| TM-140 | Supply chain | A vulnerable transitive development/runtime package or mutable CI action compromises builds. | Hash-locked Python, npm lock, pinned Actions and central security scans. The current working tree pins the affected transitive `nanoid` path to patched `3.3.17`, and the local npm audit is clean. | Commit the remediation and rerun exact-head CI/security/review gates; mutable or newly vulnerable dependencies remain a continuing risk. |

## Privacy data flow

Schema identifiers and comments can reveal customers, internal services, data
classes, or business relationships even when no table rows are copied. The
application therefore treats schema metadata as potentially confidential.
Column examples are optional and must not capture live PII by default. Public
sharing minimizes the representation; authenticated LLM egress is a separate
purpose and must not be inferred from project membership alone.

Retention, deletion, export, residency, legal basis, and data-subject handling
are product/deployment policies still requiring owners and schedules. Their
absence is a gap, not evidence that the product stores no personal data.

## Forward Engineering safety case

No single check establishes safe DDL. Release of FE-100 through FE-190 requires
linked evidence for all of:

1. semantic and identifier preservation;
2. target/version capability classification;
3. dependency ordering and operational risk;
4. isolated executable proof and read-only production preflight;
5. exact approval binding and drift revalidation;
6. serialized, idempotent, observable execution;
7. partial-state recovery and post-apply semantic convergence.

The existing transactional `dry_run` compatibility route satisfies none of
these as a complete safety case.

## Related control documents

- [Security reporting and disclosure policy](../SECURITY.md)
- [API security checklist](api-security-checklist.md)
- [Response security headers](response-security-headers.md)
- [CodeQL manual backfill ownership](security/codeql-sast-backfill.md)
- [Observability emission and downstream collection](observability.md)
- [Operations and incident boundaries](operations-runbook.md)

## Review triggers

Update this model for new public fields, authentication methods, connector
schemes, LLM providers, target write capabilities, persisted model entities,
queue semantics, cross-service data flows, or retention policy. Every High or
Critical validated finding receives an owner, lifecycle, test, and release
disposition in the traceability matrix or a dedicated security finding record.
