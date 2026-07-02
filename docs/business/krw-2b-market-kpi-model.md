# KRW 2B Market And KPI Model

This document defines the business evidence needed before positioning
`pg-erd-cloud` as a KRW 2B enterprise-grade SaaS or on-premises product. It is a
working model, not a sales claim. Any unsupported number must remain labeled as
an assumption until measured or sourced.

## Decision Frame

The commercial question is not only whether the software runs. A buyer or
acquirer needs evidence that the product can:

- Solve a high-value database documentation and schema-understanding problem.
- Be deployed safely in SaaS and on-premises environments.
- Be operated and supported without founder-only knowledge.
- Enforce licensing, billing, security, and data-protection controls.
- Show credible adoption, usage, reliability, and retention signals.

## ICP Segments

| Segment | Need | Sale Motion | Evidence Status |
|---|---|---|---|
| Platform engineering teams | Keep database architecture understandable across services and teams | SaaS pilot to annual workspace contract | estimated |
| Data engineering teams | Document source schemas, snapshots, and change impact | SaaS team plan or enterprise workspace | estimated |
| SI and consulting teams | Reverse engineer customer databases and produce handoff artifacts | Per-seat or project-based on-premises package | estimated |
| Regulated enterprise DB teams | Keep ERDs and exports inside customer-controlled infrastructure | On-premises annual license plus support | estimated |
| Migration teams | Compare legacy and target schema structure during modernization | Time-boxed project license plus support | estimated |

Missing evidence:

- Customer interviews tied to each segment.
- Willingness-to-pay data.
- Competitive win/loss notes.
- Procurement constraints for regulated buyers.
- Support-cost data from real pilots.

## KRW 2B Scenario Model

These scenarios are planning assumptions. They should not be used as sales copy
until pricing data and customer evidence exist.

| Scenario | Package | Path To KRW 2B | Evidence Status |
|---|---|---:|---|
| Enterprise SaaS | Annual workspace subscriptions with SSO, support, audit, and usage limits | 20 customers at KRW 100M annual contract value | estimated |
| On-premises enterprise | Offline license, support SLA, deployment package, and upgrade path | 10 customers at KRW 200M annual license plus support | estimated |
| SI channel | Partner license for repeat customer assessments | 5 partners at KRW 400M annualized channel value | missing |
| Acquisition or strategic sale | Product, IP, design system, tests, deployability, and customer evidence | KRW 2B valuation justified by product readiness and pipeline | missing |

Required proof before using these scenarios externally:

- Pricing experiments or signed letters of intent.
- At least one paid pilot or documented procurement discussion.
- Measured support and implementation effort.
- Security review completion evidence.
- On-premises installation drill evidence.

## North-Star KPI

Commercial readiness north-star:

> Qualified database teams can create a trusted ERD, share/export it, and pass
> security/procurement review without direct maintainer intervention.

This should be measured through a combination of activation, workflow success,
operational reliability, and support burden.

## Product KPIs

| KPI | Target For Paid Pilot | Target For GA | Current Status |
|---|---:|---:|---|
| Workspace activation rate | 60% of invited workspaces create one project | 75% | project creation measured by `product_events_total`; invite denominator missing |
| Connection setup success rate | 80% of attempts complete or fail with actionable guidance | 90% | connection creation measured by `product_events_total`; live validation denominator missing |
| Snapshot creation success rate | 90% for supported PostgreSQL/Snowflake paths | 95% | snapshot queueing measured by `product_events_total` and job metrics |
| ERD editor first render p95 | under 3 seconds for pilot-size schemas | under 2 seconds | missing |
| Share/export success rate | 95% for supported export paths | 98% | share-link creation measured by `product_events_total` and share audit metrics |
| License validation success | 99% valid commercial tokens accepted | 99.9% | partially measured by tests |
| Billing reconciliation success | 99% provider events applied or queued for support review | 99.9% | partially measured by tests and `billing_events_total` |
| LLM draft cost-control evidence | every live draft has usage evidence and provider failures alert | per-account quota and billing attribution | fixed-window account/share quota, monthly account attribution, and support diagnostics summary implemented; provider invoice reconciliation still needs pilot/provider data |
| Backup restore drill | one successful drill before paid pilot | quarterly successful drills | measured by restore drill manifest validator example; real pilot evidence pending |
| Incident first response | within one business day | SLA-specific response time | documented, not measured |
| Support touches per activation | under 2 support touches | under 1 | missing |

## Guardrail Metrics

| Guardrail | Why It Matters | Required Action |
|---|---|---|
| Auth failure spike | May indicate configuration, attack, or expired tenant setup | Alert and support runbook |
| Share-link failures | Buyer-facing trust and collaboration path | Alert and audit event correlation |
| Billing/license failures | Direct revenue and access-control risk | Provider reconciliation and support evidence |
| Snapshot job failure rate | Core product utility | Queue metrics and customer-visible recovery |
| Restore drill failure | On-premises and enterprise trust | Block commercial release until resolved |
| Visual regression failure | UX trust and buyer demo quality | Require approved baseline update or fix |

## Measurement Plan

1. Add event taxonomy for activation, connection setup, snapshot job, share,
   export, license validation, billing event, restore drill, and support action.
   Initial low-cardinality lifecycle events now use
   `product_events_total(area, action, outcome)` for project, connection,
   snapshot, and share-link creation.
   Restore drill evidence now uses `docs/operations/restore-drills/*.json`
   manifests validated by `scripts/ci/validate_restore_drill_manifest.py`.
2. Keep customer identifiers redacted or pseudonymous in telemetry.
3. Make each KPI auditable from logs, metrics, or release artifacts.
4. Add sample dashboard queries after the event taxonomy is implemented.
5. Use pilot evidence to replace assumptions with measured values.

## Immediate Product Implications

- Billing provider reconciliation remains a P1 gap until provider-specific
  fulfillment, customer portal deep integration, and real provider catalog
  operating values exist. The checkout handoff API, common event recording path,
  raw-body HMAC signature verification path, configurable provider event alias
  normalization, configurable entitlement evidence and member-invite seat-limit
  enforcement, configurable plan catalog validation, normalized contract-state application path, and billing
  reconciliation outcome metrics are now covered by tests.
- Admin/support diagnostics are now partially measured by tests through the
  backend read-only diagnostics API, operator-only frontend view, demo-mode E2E
  support lookup with recent share-link evidence, and Product Design/Figma audit
  evidence in
  `docs/ui-ux/qa/2026-07-02-support-diagnostics-audit/`. PR #415 also has a
  commercial readiness evidence board in Figma at
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=63-2>, with a
  repository screenshot at
  `docs/ui-ux/qa/2026-07-02-commercial-readiness-evidence-board.png`. Support
  workload and resolution-time metrics still need pilot data.
- On-premises packaging drills are a P1 gap because regulated buyers need proof
  that the product can run and be recovered in their environment.
- Figma/Product Design work must include buyer-trust states, not only the happy
  path: empty workspace, connection failure, billing limit, account
  deactivation, share/export success, and support escalation.

## Evidence Status Summary

- Measured today: local automated tests for license, usage limits, account
  deactivation, checkout/plan-change handoff, provider-neutral billing event ingestion,
  provider event alias normalization, entitlement evidence, member-invite seat-limit
  enforcement, plan catalog validation, billing webhook outcome metrics,
  product lifecycle outcome metrics for project/connection/snapshot/share-link
  creation, LLM draft usage/failure metrics, audit logs, monthly account
  attribution API, support-visible current-month LLM usage,
  read-only support diagnostics with recent share-link summaries and redacted
  provider metadata summaries,
  operator-only support diagnostics UI, support diagnostics demo evidence,
  visual regression, accessibility, and E2E smoke paths.
- Estimated today: ICP fit, packaging mix, enterprise price points, activation
  rates, support effort, and buyer conversion.
- Missing today: real customer interviews, paid pilot data, procurement notes,
  pricing sensitivity, support workload, production telemetry, and provider invoice
  reconciliation data.
