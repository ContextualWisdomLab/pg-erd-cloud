# Architecture

pg-erd-cloud reverse-engineers a target PostgreSQL (optionally Snowflake)
database into JSON schema snapshots, renders them as an interactive ERD, and
forward-engineers those snapshots into DDL, diffs, DBML/Mermaid, ORM models,
and reversing-spec documents. Project owners can create share links for
unauthenticated read/export access.

## Deployable pieces

- `backend/` — FastAPI, async SQLAlchemy, Hypercorn. Metadata lives in the
  app PostgreSQL. Target-database introspection runs on the job queue.
- `frontend/` — React 19 + Vite SPA. The canvas is React Flow. Export and
  graph conversion live in `frontend/src/erd/`.
- `deploy/traefik/` — production edge routing used by `compose.prod.yaml`.

## Data flow

1. A user stores an encrypted target DSN.
2. Snapshot creation enqueues a job; the worker introspects and stores JSON.
3. The SPA renders the snapshot and derives every export from that JSON.
4. Share links expose redacted read/export routes under `/api/share/`.

## Current product contracts

- Search identity and sequential snapshot polling:
  `docs/doctoring/search-identity-and-sequential-polling.md`
- Prisma identifier allocation:
  `docs/adr/0011-prisma-identifier-allocation.md`
- UI surfaces and empty states: `docs/ui-ux/product-spec.md`
- LLM drafts via contextual-orchestrator:
  `docs/llm-orchestrator-integration.md`

## Standalone and submodule

This repository must run alone (Docker Compose or local venv + Vite) and also
compose as a module beside naruon, contextual-orchestrator, and the org
`.github` reusable workflows. Runtime secrets should move from environment
reads in `backend/app/settings.py` to a credential registry; env remains the
bootstrap path only.
