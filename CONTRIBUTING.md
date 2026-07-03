# Contributing to pg-erd-cloud

Thank you for helping improve pg-erd-cloud. This project is a PostgreSQL-focused
cloud ERD and DDL workflow MVP with a Python backend, TypeScript frontend, and
Docker-based local environment.

## Ways to contribute

- Report bugs with a clear description, expected behavior, actual behavior, and
  reproduction steps.
- Propose product or UX improvements with screenshots, examples, or workflow
  notes when possible.
- Submit pull requests for documentation, tests, bug fixes, security hardening,
  and focused product improvements.
- Report security vulnerabilities privately. Do not open public issues for
  suspected vulnerabilities; follow [SECURITY.md](SECURITY.md).

## Development setup

Use Docker for the fastest full-stack setup:

```bash
cp .env.example .env
docker compose up -d --build
```

Backend development:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
alembic upgrade head
hypercorn --config python:app.hypercorn_config app.main:app \
  --bind 0.0.0.0:8000 --reload \
  --access-logfile - --error-logfile -
```

Frontend development:

```bash
cd frontend
npm ci
npm run dev
```

## Pull request expectations

- Keep changes focused and easy to review.
- Add or update tests when changing behavior.
- Update documentation when changing setup, security behavior, user-visible
  flows, APIs, or operational requirements.
- Keep generated files, local secrets, and `.env` files out of commits.
- Prefer small pull requests over broad rewrites.

## Quality checks

The CI workflow runs backend type checks and tests, frontend type checks and
tests, and the frontend production build. Before opening a pull request, run the
checks that match your change when practical:

```bash
cd backend
PYTHONPATH=. mypy app
PYTHONPATH=. pytest -q
```

```bash
cd frontend
npm run typecheck
npm run test
npm run build
```

## Security and privacy expectations

- Do not commit credentials, database DSNs, tokens, private keys, or production
  `.env` files.
- Treat project DSNs and generated schema metadata as sensitive unless the owner
  explicitly marks them shareable.
- Use GitHub pull requests for reviewable changes.
- Use private security reporting for vulnerabilities.

## Code of conduct

All contributors are expected to follow the project
[Code of Conduct](CODE_OF_CONDUCT.md).
