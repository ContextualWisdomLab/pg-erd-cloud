# Documentation Authority Index

This directory is the canonical documentation graph for pg-erd-cloud. A broad
README, pull-request body, Figma canvas, chat transcript, or generated API page
does not replace the authorities below.

## Lifecycle vocabulary

| Label | Meaning |
| --- | --- |
| `implemented_on_main` | The protected `main` branch contains executable evidence. |
| `active_pr` | The capability exists only on the exact linked pull-request head. |
| `planned` | Accepted product or technical intent without production implementation. |
| `research_only` | Evidence or exploration that has not become a product commitment. |
| `downstream` | Owned by another independently deployable service. |
| `deprecated` | Still present for compatibility but not the target design. |
| `out_of_scope` | Explicitly excluded from this product boundary. |

## Canonical authorities

| Concern | Authority |
| --- | --- |
| Product identity, personas, journeys and acceptance | [PRD](PRD.md) |
| Technology, contracts and production target | [TRD](TRD.md) |
| Current API representations and compatibility | [API contract](API.md) |
| Current vs governed Forward Engineering support | [Capability matrix](forward-engineering-support-matrix.md) |
| System structure and trust boundaries | [Architecture](../ARCHITECTURE.md) |
| Durable decisions and supersession | [ADR index](adr/README.md) |
| Structure and behavioral diagrams | [UML](UML.md) |
| Application and planned Forward Engineering data models | [ERD](ERD.md) |
| Security/privacy assumptions, threats and controls | [Threat model](threat-model.md) |
| Verification layers and release evidence | [Test strategy](test-strategy.md) |
| Requirement-to-code/test/PR evidence | [Traceability](traceability-matrix.md) |
| Documentation completeness and known limits | [Coverage matrix](documentation-coverage-matrix.md) |
| Standards and research in APA 7 style | [References](references.md) |
| Live UI source and precedence | [Figma contract](ui-ux/figma-contract.md) |
| Runtime operational baseline | [Observability](observability.md) |
| Deployment drift workflow | [CI drift check](ci-drift-check.md) |
| Safe operations and incident boundaries | [Operations runbook](operations-runbook.md) |
| Release, rollback and recovery evidence | [Release plan](release-plan.md) |
| External commercial work-loop behavior and evidence | [Automation contract](automation-contract.md) |

## Evidence precedence

1. Protected-main code, migrations, tests and release artifacts.
2. Exact-head `active_pr` code and checks, explicitly labelled with its PR.
3. Accepted ADRs and requirements.
4. Live Figma contract for presentation and interaction intent.
5. Research and planned designs.
6. Historical screenshots and compatibility notes.

A higher-precedence source does not silently erase a decision. Material
conflicts are resolved with a new or superseding ADR and corresponding
traceability update.

## Related control and integration documents

These specialist documents refine, but do not replace, the canonical
authorities above. Their lifecycle and owner headers identify repository,
deployment, organization, or downstream-service responsibility.

- [Security reporting policy](../SECURITY.md)
- [API security checklist](api-security-checklist.md)
- [Response security headers](response-security-headers.md)
- [CodeQL manual backfill](security/codeql-sast-backfill.md)
- [Azure VMSS health guidance](azure-vmss-health-extension.md)
- [Clearfolio integration](clearfolio-integration.md)
- [Contextual orchestrator integration](llm-orchestrator-integration.md)
