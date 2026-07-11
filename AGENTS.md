# AGENTS.md

Cross-agent conventions for this repo (`pg-erd-cloud`), readable by any coding
agent (Claude, Codex, Cursor, opencode, …). This is a Python backend
(`backend/`, FastAPI + SQLAlchemy/Alembic) plus a TypeScript/Vite frontend
(`frontend/`), shipped via Docker Compose (`compose.yaml`, `compose.prod.yaml`)
behind Traefik (`deploy/traefik/`).

<!-- BEGIN cwl-agent-guidance -->
## Agent guidance (CWL governance)

### Security & review gate

- Every PR runs a central, required **Security Scan** gate: `osv-scan` +
  `dependency-review` (diff-scoped, moderate/Medium and above) and `trivy-fs`
  (repo-wide, CRITICAL/HIGH/MEDIUM). It runs against **every PR base, including
  stacked PRs**.
- A failing **`trivy-fs`, `osv-scan`, or `dependency-review` is a REAL
  finding, not a flake.** Read the job log and the run's SARIF/artifacts so the
  specific package, advisory, CVE/GHSA/OSV id, severity, and affected file are
  visible, then **remediate Medium and above** — do not weaken or disable the
  gate:
  - Vulnerable dependency: bump it. Python lives in `backend/requirements.lock`
    / `backend/requirements-dev.lock` (hash-locked) and `backend/pyproject.toml`;
    frontend in `frontend/package.json` + `frontend/package-lock.json` /
    `frontend/pnpm-lock.yaml`.
  - Container/config misconfig: fix the offending `backend/Dockerfile`,
    `frontend/Dockerfile`, `frontend/Dockerfile.prod`, the `compose*.yaml`
    files, or `deploy/traefik/dynamic.yaml`.
  - Genuine false positive only: add a narrow, **documented** `.trivyignore`
    (or `.trivyignore.yaml`) entry — scoped and with a reason.
- Reproducing locally: a stale local DB misses findings. Run
  `trivy --download-db-only` first, and scan the **merge ref** (PR merged into
  base), not just the PR head.
- The org `code_scanning` ruleset is intentionally **CodeQL-only** (multiple
  code-scanning tools can't converge on one PR ref). Gating is by the Security
  Scan **job result**, not the `code_scanning` rule — do **not** add tools to
  that rule.

### Code exploration

- Always initialize CodeGraph in the active worktree (`codegraph init`) before
  substantial review or remediation, and run `codegraph sync` after edits. Use
  it to inspect callers, callees, and impact radius before relying on local
  intuition.
- Also use `rg`/structured search for text, generated files, sparse checkouts,
  and languages CodeGraph cannot parse. A missing or partial CodeGraph result is
  not proof that a behavior or dependency path is absent; record the limitation
  in the PR/check evidence when it matters.

### Config & secrets (KV, not env)

- Org rule: at runtime, do **not** read config/secrets via `os.getenv()` /
  raw environment variables. Read them from a KV / credential registry. Org
  Actions secrets (e.g. `OPENAI_API_KEY`) flow **into** the KV via a
  bootstrap/CI step; runtime reads from the KV — env is only transport into the
  KV, never the runtime source.
- Reference implementation: `xtrmLLMBatchPython`'s pgcrypto-encrypted Postgres
  credential registry (`get_credential(name)`). Reuse that pattern (a DB-backed
  KV is fine) unless a dedicated KV is adopted.
- **Known deviation to migrate (this repo):** `backend/app/settings.py`
  (`Settings(BaseSettings)`) currently loads runtime secrets/config directly
  from the environment / `.env` — `app_secret` (DSN encryption key),
  `database_url`, `llm_api_key`, and the OIDC/Valkey credentials. The
  Docker/Podman `*_FILE` pattern for `app_secret` is a step in the right
  direction, but env is still the runtime source. Migrate these reads to a
  KV / credential registry (`get_credential(name)`); keep env only as the
  bootstrap path that seeds the KV.

### This repo's role in the ecosystem

- **This repo (`pg-erd-cloud`):** ERD tool for developers and data architects
  (project-management context).
- The org is an ecosystem built around **naruon** — the hub: an email/PIM that
  DOM-decomposes emails and files into a persisted knowledge graph. Each
  component below is a **standalone program that must ALSO work as a git
  submodule**, grown separately and together:
  - **waf-ids-ai-soc** — WAF / IDS / AI SOC / load balancer / API management.
  - **clearfolio** — document viewer.
  - **pg-erd-cloud** — ERD tool (this repo).
  - **contextual-orchestrator** — LLM cost/perf/upstream-LB gateway (beyond
    LiteLLM).
  - **codec-carver** — STT / omni-modal speech-video codec.
  - **fast-mlsirm** — LLM-as-a-Judge calibration + evaluation-item quality
    (uses aFIPC FIPC + kaefa item-fit).
  - **feelanet-adfs** — passwordless SSO (OIDC / SCIM / ADFS / LDAP / FIDO2 /
    OAuth2.1; eliminate passwords).
  - **newsdom-api** — PDF→DOM sidecar.
  - **semantic-data-portal** — upper ontology / catalog / governance plane with
    its own graph engine.

### Research grounding (attach paper PDFs)

- Org rule: substantive feature/process PRs should find the relevant academic
  papers and **commit their PDFs into the PR** (e.g. a `docs/papers/` or
  `references/` dir) with full citations. Respect copyright: attach the PDF
  only when redistribution is permissible; otherwise cite + link + summarize.
- For this repo (ERD / schema design), ground substantive work in the relevant
  literature — e.g. data modeling, ER theory, schema normalization, or
  graph/layout algorithms for diagram rendering.
<!-- END cwl-agent-guidance -->
