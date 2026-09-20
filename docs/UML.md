# UML and Behavioral Architecture

Status date: 2026-08-09
Notation: UML-shaped Mermaid diagrams; lifecycle labels are normative

These views separate the running system from the accepted but unimplemented
Forward Engineering target. Diagram presence is not implementation evidence.

## Current component view

```mermaid
flowchart TB
    browser["React SPA\nimplemented_on_main"]
    api["FastAPI API\nimplemented_on_main"]
    worker["Snapshot worker\nimplemented_on_main"]
    appdb[("Application PostgreSQL")]
    target[("Target database")]

    browser -->|authenticated and public HTTP| api
    api -->|tenant state and queued jobs| appdb
    worker -->|claim and persist| appdb
    worker -->|guarded introspection| target
    api -.->|deprecated synchronous apply| target
```

The SPA currently persists neither its complete edited schema intent nor a
version binding between layout/groups and a successful snapshot. `diagram_view`
and `table_annotation` APIs exist on main but are not integrated by the current
frontend. Public share in PR #824 renders sanitized snapshot state, not an
unsaved local edit.

## Current domain class view

```mermaid
classDiagram
    class ProjectSpace {
      +UUID project_space_uuid
      +string project_name
    }
    class DbConnection {
      +UUID db_connection_uuid
      +bytes dsn_ciphertext
      +bytes dsn_nonce
    }
    class SchemaSnapshot {
      +UUID schema_snapshot_uuid
      +string status
      +string schema_filter
    }
    class SchemaSnapshotData {
      +UUID schema_snapshot_uuid
      +JSON snapshot_json
    }
    class ShareLink {
      +UUID share_link_uuid
      +string permission_kind
      +datetime expires_at
    }

    ProjectSpace "1" --> "0..*" DbConnection
    ProjectSpace "1" --> "0..*" SchemaSnapshot
    DbConnection "1" --> "0..*" SchemaSnapshot
    SchemaSnapshot "1" --> "0..1" SchemaSnapshotData
    ProjectSpace "1" --> "0..*" ShareLink
```

The complete relational view is in [ERD](ERD.md); this class view intentionally
shows only the core discovery/share aggregate.

## Reverse-engineering sequence (`implemented_on_main`)

```mermaid
sequenceDiagram
    actor Editor
    participant API
    participant AppDB as Application PostgreSQL
    participant Worker
    participant Target as Target database

    Editor->>API: Request schema snapshot
    API->>AppDB: Insert snapshot and queued job
    API-->>Editor: 200 SnapshotOut (queued UUID/status)
    Worker->>AppDB: Claim with SKIP LOCKED
    Worker->>Target: Guarded catalog introspection
    Target-->>Worker: Schema metadata
    Worker->>AppDB: Store sanitized JSON and success
    Editor->>API: Read completed snapshot
    API-->>Editor: Snapshot DTO
```

## Public-share sequence (`active_pr` #824)

```mermaid
sequenceDiagram
    actor Owner
    actor Viewer
    participant API
    participant AppDB as Application PostgreSQL
    participant SPA as Read-only SPA

    Owner->>API: Create viewer bearer link
    API->>AppDB: Store project-scoped share link
    API-->>Owner: /api/share/{uuid} in url_path
    Owner->>Owner: UI maps API path to /share/{uuid}
    Viewer->>SPA: Open bearer URL
    SPA->>API: Read link and successful snapshots
    API->>AppDB: Validate link, expiry, project on primary
    AppDB-->>API: Snapshot and payload
    API-->>SPA: Sanitized public DTO
    SPA-->>Viewer: Read-only ERD
```

## Governed Forward Engineering sequence (`planned`)

```mermaid
sequenceDiagram
    actor Editor
    actor Approver
    participant Planner as Plan service
    participant Executor
    participant Target as Target PostgreSQL

    Editor->>Planner: Store desired model revision
    Planner->>Target: Read-only fingerprint and preflight
    Planner-->>Editor: Immutable plan, risks, digest
    Editor->>Planner: Start isolated dry-run
    Planner-->>Approver: Dry-run evidence and exact digest
    Approver->>Planner: Bound expiring approval
    Planner->>Executor: Enqueue authorized plan
    Executor->>Target: Revalidate, serialize, apply segments
    Executor->>Target: Re-introspect schema
    Executor-->>Editor: Convergence or recovery evidence
```

## Planned migration job state

```mermaid
stateDiagram-v2
    [*] --> Draft
    Draft --> Compiled: compile
    Compiled --> DryRunning: start dry-run
    DryRunning --> Reviewable: evidence succeeds
    DryRunning --> Rejected: unsupported or failed
    Reviewable --> Approved: bind approval
    Reviewable --> Rejected: policy rejects
    Approved --> Applying: drift check succeeds
    Approved --> Stale: fingerprint or approval changes
    Applying --> Verifying: all segments complete
    Applying --> Recoverable: partial nontransactional work
    Applying --> Failed: no partial commit
    Verifying --> Converged: residual diff is empty
    Verifying --> Diverged: residual diff remains
    Converged --> [*]
    Rejected --> [*]
    Stale --> [*]
    Recoverable --> [*]
    Failed --> [*]
    Diverged --> [*]
```

`Recoverable` is intentionally distinct from `Failed`: after a committed
non-transactional segment the system must never claim a global rollback.

## Current snapshot state (`implemented_on_main`)

```mermaid
stateDiagram-v2
    [*] --> Queued: create snapshot and job
    Queued --> Running: worker claims row
    Running --> Succeeded: persist snapshot JSON
    Running --> Failed: persist sanitized error
```

There is no current `Running` → `Queued` reclaim transition. A worker crash can
strand both job and snapshot state until operator intervention or future lease
recovery is implemented.

## Deployment view

```mermaid
flowchart TB
    subgraph client["Client trust boundary"]
      browser["Browser SPA"]
    end
    subgraph edge["Public edge"]
      proxy["Traefik edge proxy\nhost-local TLS terminator required"]
    end
    subgraph service["Application trust boundary"]
      api["FastAPI replicas\nwith one in-process worker task each"]
      appdb[("Application PostgreSQL")]
    end
    subgraph customer["Customer data boundary"]
      target[("Target database")]
    end

    browser -->|HTTPS via external terminator| proxy
    proxy --> api
    api -->|API and worker state| appdb
    api -->|worker outbound allowlisted TLS| target
```

The committed production stack routes HTTP internally and requires TLS
termination outside the stack on the same host because Traefik is published on
loopback only. The trust allowlist must contain the minimal direct-peer CIDR
Traefik actually observes after Docker NAT (commonly the Compose bridge gateway),
not an assumed pre-NAT terminator address. Traefik appends that peer to the chain;
the backend selects the second hop from the right for logging and rate limits.
Production credentials are currently loaded through environment-backed settings,
a documented deviation in `AGENTS.md`.
Migration to a credential registry is `planned`; this diagram does not imply
either external control is already deployed.

## Diagram change rule

Any change to trust boundaries, persisted aggregates, job state, public-share
surface, or Forward Engineering ordering updates this document, the relevant
ADR, [TRD](TRD.md), [ERD](ERD.md), and
[traceability matrix](traceability-matrix.md) in the same pull request.
