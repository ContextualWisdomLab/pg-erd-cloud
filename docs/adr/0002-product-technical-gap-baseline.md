# ADR-0002: Product and technical gap baseline

- **Status:** Proposed
- **Date:** 2026-08-20
- **Scope:** pg-erd-cloud product, architecture, design, release, deployment, and ecosystem authority
- **Supersedes:** none

## Context

pg-erd-cloud has a broad implementation and a large active PR queue. A feature list, local test result, historical check, or individual PR description cannot by itself establish commercial readiness. Product completion requires a reproducible chain from buyer concern and research/standards input through architecture, issue, implementation, exact-head review/check evidence, migration, operability, and release artifacts.

The product must also remain independently deployable while participating in the CWL ecosystem. Identity, documents, LLM orchestration, PIM/knowledge graphs, and central development governance have separate authorities and must not be copied into this repository.

## Decision

### Living baseline

Use `docs/product-technical-gap-baseline.md` as the living evidence baseline. It must be refreshed from:

- protected `main` and the current ruleset/required checks;
- all open PR exact heads, reviews, unresolved threads, and check runs;
- current code, migrations, tests, deployment files, design assets, and runtime evidence;
- canonical Issues, including current implementation and review dependencies;
- primary standards/research recorded in `docs/doctoring/product-technical-gap-baseline.md`.

A mutable GitHub result is evidence only for the exact commit at which it was observed.

### Completion backlog

The canonical completion issues are:

- #946 — auditable credential-provider, secret lifecycle, and DSN re-encryption;
- #947 — evidence-backed normalization/dependency/hot-partition assessment;
- #948 — snapshot promotion, bitemporal lineage, retention, and metadata recovery;
- #949 — governed forward-engineering apply, convergence, and recovery;
- #950 — truthful GA deployment profiles, tenant isolation, SSO, and provisioning;
- #951 — large-schema SLOs, benchmark evidence, and measured Rust boundaries;
- #952 — optional tenant/purpose-scoped Clearfolio, contextual-orchestrator, and naruon workflows;
- #953 — commercial release integration, evidence bundle, version, and artifacts.

Implementation bodies remain in their focused issues and PRs. #953 owns release classification and integration, not duplicate feature specifications.

### Initial GA profile

The first permitted GA target is `single_tenant_managed`: one customer organization per deployment/database, project RBAC, OIDC organization binding, explicit secret/network/backup policy, and no cross-customer SaaS claim.

`multi_tenant_saas` remains non-GA until #950 proves tenant authority and database-enforced isolation across persistence, queue, cache, object storage, exports, telemetry, connectors, backup/restore, and identity lifecycle.

Persistent forward-engineering apply remains non-GA and default-deny until #949 closes. Execution-neutral planning and export may ship with an explicit limitation.

### Design authority

Record the live Figma identifiers:

- **Figma File ID:** `csnpEEJfmqFWB0vNUoTkWA`
- **Supplemental Figma File ID:** `OTN0rBGtnVy0P7yq4Iv9Si`

Figma is the source of reviewed visual intent. Shared design tokens, Storybook stories, accessibility/component tests, browser interaction tests, and production implementation form the executable UI contract. Screenshots are QA evidence only. A Figma file or draft PR is not automatically approved design authority.

### Delivery loop

PR #943 is the repository's proposed hourly entry point into the central OpenCode review/fix scheduler. It may inspect and repair current PR heads but cannot approve, bypass, or merge around protected rules. The reusable workflow is pinned immutably; after central `.github` Strix repair #1153 merges, the pin and affected target PR scans must be refreshed.

Every merge decision follows:

```text
refetch exact head and rules
→ inspect reviews/threads/checks
→ repair source-actionable findings
→ run focused and complete proportional proof
→ push normally
→ refetch new head
→ protected merge or advance to next eligible work
```

No approval/check evidence transfers from a predecessor SHA. Concurrent remote-agent commits are respected; force-push is not the default conflict strategy.

## Consequences

### Positive

- Buyer-visible gaps survive ordinary PR closure and are linked to executable acceptance criteria.
- Release claims distinguish GA, beta, experimental, disabled, and post-GA scope.
- Standalone and ecosystem/module boundaries remain explicit.
- Security, migration, data quality, temporal lineage, accessibility, operability, and supply-chain evidence become release inputs rather than afterthoughts.
- Rust adoption is driven by measured SLO/security leverage and a rollback path.
- PII/schema metadata remains usable for authorized work; protection relies on purpose, least privilege, encryption, broadcast minimization, retention, and audit rather than blanket masking.

### Costs and risks

- The baseline requires frequent refresh while PRs and hosted checks move.
- Commercial release may be delayed when migrations, backup/restore, exact-head checks, or external control-plane evidence are incomplete.
- The first GA profile is deliberately narrower than a shared multi-tenant SaaS offering.
- Maintaining Figma ↔ Storybook ↔ code ↔ tests ↔ PR/review traceability adds work but reduces silent design and accessibility drift.

## Rejected alternatives

- **Declare completion from feature count or local tests:** rejected because it omits exact-head integration, migration, security, operability, and release evidence.
- **Treat all 61 open PRs as release blockers:** rejected; #953 must classify each as blocker, post-GA, experimental, duplicate/superseded, or not planned.
- **Call project membership multi-tenancy:** rejected; it does not prove tenant authority or isolation.
- **Enable free-form or partially implemented live DDL apply:** rejected; #949's approval, execution, convergence, and recovery contracts are mandatory.
- **Move every hot path to Rust without profiling:** rejected; #951 requires measured leverage and parity.
- **Copy CWL services into this repository:** rejected; connectors and generated clients preserve ownership and modular deployment.

## References

See `docs/doctoring/product-technical-gap-baseline.md` for the complete APA 7th bibliography and requirement mapping.

International Organization for Standardization, International Electrotechnical Commission, & Institute of Electrical and Electronics Engineers. (2022). *Software, systems and enterprise—Architecture description* (ISO/IEC/IEEE 42010:2022). https://www.iso.org/standard/74393.html

National Institute of Standards and Technology. (2022). *Secure software development framework (SSDF) version 1.1: Recommendations for mitigating the risk of software vulnerabilities* (NIST Special Publication 800-218). https://doi.org/10.6028/NIST.SP.800-218

SLSA Community. (2025). *Supply-chain levels for software artifacts specification, version 1.2*. https://slsa.dev/spec/v1.2/