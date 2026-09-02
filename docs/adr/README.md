# Architecture Decision Records

ADRs record durable decisions, alternatives and consequences. `Accepted` means
the decision is the governing direction; it does **not** mean the capability is
shipped. Delivery truth is carried separately by the lifecycle label. Reversal
requires an explicit superseding ADR.

| ADR | Decision | Status | Lifecycle |
| --- | --- | --- | --- |
| [ADR-0001](0001-live-figma-design-authority.md) | Live Figma precedence and audited accessibility overrides | Accepted | `active_pr` #824 |
| [ADR-0002](0002-public-share-security-boundary.md) | Separate public bearer DTO/export boundary | Accepted | `active_pr` #824 |
| [ADR-0003](0003-postgresql-job-queue-authority.md) | PostgreSQL is the durable job source of truth | Accepted | `implemented_on_main` |
| [ADR-0004](0004-server-authoritative-forward-engineering.md) | Server-owned structured Forward Engineering plan and executor | Accepted | `planned` |
| [ADR-0005](0005-versioned-documentation-authority.md) | Canonical versioned documentation graph and lifecycle labels | Accepted | `active_pr` #824 |
| [ADR-0006](0006-continuous-commercial-work-loop.md) | Hourly review-to-merge-to-next loop; no empty-queue stop | Accepted | Repository mirror `active_pr`; runtime `downstream` |

## Required ADR fields

Every ADR contains status, lifecycle, context, decision, alternatives,
consequences, verification and references. Superseding ADRs identify both the
record and the compatibility/migration effect.
