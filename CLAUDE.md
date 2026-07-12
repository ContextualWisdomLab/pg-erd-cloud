# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

pg-erd-cloud is a PostgreSQL-focused cloud ERD (entity-relationship diagram) collaboration/sharing service — currently a runnable MVP skeleton. It reverse-engineers a target PostgreSQL database (optionally Snowflake) into JSON schema snapshots, renders them as an interactive ERD (React Flow), and forward-engineers snapshots into DDL exports (PostgreSQL or Snowflake dialect), schema diffs/migration SQL, DBML/Mermaid exports, and "DB reversing spec" documents (markdown draft, LLM prompt, or live LLM draft via an OpenAI-compatible provider configured with `LLM_API_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`). Project owners can create share links for unauthenticated read/export access.

Repository docs are mixed-language: README.md and CHANGELOG.md are Korean; CONTRIBUTING.md, SECURITY.md, and most of docs/ are English.

## Common commands

### Full stack (Docker, dev)

```bash
cp .env.example .env   # set POSTGRES_PASSWORD and APP_SECRET
docker compose up -d --build
```

Frontend: http://localhost:5173 · Backend: http://localhost:8000 (health: `/healthz`). Source directories are bind-mounted; backend runs with `--reload` and frontend runs the Vite dev server, so edits hot-reload.

### Backend (backend/, Python ≥3.10, CI uses 3.10)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e .                 # add ".[snowflake]" for Snowflake reverse engineering
alembic upgrade head             # apply migrations (backend/alembic/versions)
hypercorn --config python:app.hypercorn_config app.main:app \
  --bind 0.0.0.0:8000 --reload --access-logfile - --error-logfile -
```

Checks (mirror CI):

```bash
cd backend
PYTHONPATH=. mypy app
PYTHONPATH=. pytest -q
PYTHONPATH=. pytest -q tests/test_snapshot_job.py                # single file
PYTHONPATH=. pytest -q tests/test_snapshot_job.py::test_name     # single test
```

CI installs backend deps with `pip install --require-hashes -r requirements-dev.lock`. The lockfiles are generated with uv (see header comments in `backend/requirements*.lock`); when changing dependencies in `backend/pyproject.toml`, regenerate both lockfiles, e.g.:

```bash
uv pip compile backend/pyproject.toml --python-version 3.10 --generate-hashes -o backend/requirements.lock
uv pip compile backend/pyproject.toml --python-version 3.10 --generate-hashes --extra dev -o backend/requirements-dev.lock
```

### Frontend (frontend/, Node 26 — see .nvmrc / engines)

```bash
cd frontend
npm ci
npm run dev                                              # Vite dev server on 5173
npm run typecheck                                        # tsc --noEmit
npm run test                                             # vitest run
npm run test -- src/erd/__tests__/cardinality.test.ts    # single test file
npm run build                                            # tsc -b && vite build
```

CI uses npm with `package-lock.json` (a `pnpm-lock.yaml` also exists, but CI caches npm).

### Production-style (Docker + Traefik)

```bash
cp .env.example .env
mkdir -p secrets
# write a long random value to secrets/app_secret (never commit; .gitignore covers **/secrets/**)
chmod 600 secrets/app_secret
docker compose -f compose.prod.yaml up -d --build
```

App entrypoint: http://localhost:8080 (`TRAEFIK_HTTP_PORT`).

## Architecture

Three deployable pieces in one repo:

- **backend/** — Python FastAPI app (async SQLAlchemy 2 + asyncpg on PostgreSQL 16), served by Hypercorn. The app's own PostgreSQL stores metadata: users, project spaces/members, encrypted DB connections, schema snapshots, job queue, diagram views, annotations, share links, API keys (`app/models.py`).
- **frontend/** — React 19 + TypeScript + Vite SPA. The ERD canvas is built on `@xyflow/react` (React Flow). Core ERD logic lives in `src/erd/` (snapshot→graph conversion, cardinality, FK auto-inference, DBML/Mermaid/SQL export); modal dialogs in `src/components/modals/`. Tests use Vitest + Testing Library (plus fast-check fuzz tests).
- **deploy/traefik/** — Traefik dynamic config used by `compose.prod.yaml`.

### Backend layout (backend/app/)

- `api/` — FastAPI routers (projects, connections, snapshots, share, diagram_views, annotations, api_keys, auth_routes, me), all mounted in `main.py` under `/api`.
- `jobs/` — Postgres-backed job queue (`JobQueue` table). Reverse engineering never blocks the request path: the API enqueues a `snapshot` job, and an in-process worker task (started in the FastAPI lifespan in `main.py`) claims and executes it. Optional Valkey/Redis (`valkey_queue.py`) is only a wake-up signal; Postgres remains the source of truth.
- `pg_introspect/` — pg_catalog-based introspection of the *target* PostgreSQL: schemas/tables/columns, PK/FK/UNIQUE/CHECK, indexes. Index access methods are discovered dynamically from `pg_am`/`pg_class.relam` and index DDL is preserved losslessly via `pg_get_indexdef()` — do not hardcode an index-type list (project principle, see README). Also synthesizes safe `example_value` column hints from name/type metadata only (never samples real table data).
- `snowflake_introspect/` — optional Snowflake reverse engineering (INFORMATION_SCHEMA; requires the `snowflake` extra).
- `ddl/` — forward engineering: snapshot → DDL export with dialect mapping, migration SQL, migration-safety checks.
- `diff/` — snapshot-to-snapshot schema diff.
- `spec/` — reversing-spec generation, naming lint, data dictionary, relationship inference, LLM integration.
- Cross-cutting: `auth.py` (OIDC/Casdoor JWT verification when `OIDC_ISSUER` is set, plus API keys and token revocation), `csrf.py`, `rate_limit.py` (in-memory fixed-window; global `/api/*` limit plus a stricter separate limit for public `/api/share/*`), `security_headers.py`, `observability.py` (JSON request logs + Prometheus metrics — see docs/observability.md), `sanitize.py`/`dsn_redaction.py`, `settings.py` (pydantic-settings; env vars are documented in `.env.example`).

### Data flow

1. A user registers a target-DB connection; the DSN is encrypted with `APP_SECRET` before being stored in the app DB.
2. Requesting a snapshot enqueues a job; the background worker connects to the target DB, introspects it, and stores a JSON snapshot (`SchemaSnapshot` + `SchemaSnapshotData`).
3. The frontend fetches snapshots via `/api/*` and renders the ERD; all exports (DDL, diff/migration SQL, reversing spec, DBML/Mermaid) are derived from the stored snapshot, not from live DB access.
4. Share links expose read-only snapshot/export routes under `/api/share/{share_uuid}/...` with a tighter rate limit, and sensitive fields (schema comments, example values) are redacted from publicly shared payloads.

### Dev vs prod compose

- `compose.yaml` (dev): postgres + backend + frontend. Bind mounts and hot reload; backend on 127.0.0.1:8000, frontend on 127.0.0.1:5173; `APP_SECRET` comes from `.env`; CORS allows http://localhost:5173.
- `compose.prod.yaml`: adds a Traefik edge router on :8080 that routes `/api/*` and `/healthz` to the backend and everything else to a static frontend (`frontend/Dockerfile.prod` builds `dist/` served by `serve-static.mjs`). No bind mounts or reload; `APP_SECRET` is injected as a Docker secret file (`APP_SECRET_FILE=/run/secrets/app_secret`); only Traefik is published. Traefik also applies security-headers middleware (`deploy/traefik/dynamic.yaml`).
- Both compose files run `alembic upgrade head` before starting the backend, so migrations must always be committed alongside model changes.

## Conventions and gotchas

- `APP_SECRET` is the encryption key for stored DSNs — changing it breaks decryption of existing data. Prefer `APP_SECRET_FILE` injection in production.
- Never commit `.env`, `secrets/`, credentials, or DSNs. Treat DSNs and generated schema metadata as sensitive (SECURITY.md, docs/api-security-checklist.md).
- Backend code is strictly typed: mypy runs with `disallow_untyped_defs` (see `[tool.mypy]` in backend/pyproject.toml). Public defs need docstrings — interrogate is configured with `fail-under = 100` in setup.cfg and `tests/test_docstrings.py` enforces it for checked modules.
- Long-running work (introspection of target DBs) goes through the job queue, never synchronously in a request handler.
- Middleware registration order in `app/main.py` is deliberate (security headers registered last so they wrap everything, including 429s and CORS preflight) — read the comments there before reordering.
- Do not use nested `${VAR:-${OTHER:-default}}` expressions in compose files; podman-compose mishandles them (noted inline in compose.yaml).
- Supply-chain pinning is enforced (OpenSSF Scorecard): Docker images are pinned by digest, GitHub Actions by commit SHA, and pip installs by `--require-hashes`. Preserve pinning when adding or updating any of these.
- CI (`.github/workflows/ci.yml`) runs backend mypy + pytest (Python 3.10, hash-locked deps) and frontend typecheck + vitest + production build (Node 26). CodeQL, Scorecard, and dependency-review workflows also run.
- User-visible frontend changes are recorded in CHANGELOG.md (Korean) and frontend/CHANGELOG.md.
- Add or update tests when changing behavior; prefer small, focused PRs (CONTRIBUTING.md).
