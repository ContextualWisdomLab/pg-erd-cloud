#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime="${CONTAINER_RUNTIME:-podman}"
network_name="pg-erd-cloud-e2e"
postgres_name="pg-erd-cloud-e2e-postgres"
db_password="${E2E_DB_PASSWORD:-e2e-local-password}"
db_port="${E2E_POSTGRES_PORT:-55433}"
app_secret="${E2E_APP_SECRET:-e2e-local-app-secret}"
api_key="${E2E_API_KEY:-pgerd_e2e_local_only_key}"
postgres_image="docker.io/library/postgres:16@sha256:b4ffbb18020d17edaf767a80987c618d43fa198ff85f8bcbec17d7ea7a6f6918"
frontend_pid=""
backend_pid=""
e2e_venv=""

cleanup() {
  status=$?
  if [[ -n "$frontend_pid" ]]; then
    kill "$frontend_pid" 2>/dev/null || true
  fi
  if [[ -n "$backend_pid" ]]; then
    kill "$backend_pid" 2>/dev/null || true
  fi
  if (( status != 0 )); then
    if [[ -f /tmp/pg-erd-cloud-e2e-backend.log ]]; then
      sed -n '1,220p' /tmp/pg-erd-cloud-e2e-backend.log
    fi
    if [[ -f /tmp/pg-erd-cloud-e2e-frontend.log ]]; then
      sed -n '1,220p' /tmp/pg-erd-cloud-e2e-frontend.log
    fi
  fi
  if [[ -n "$e2e_venv" ]]; then
    rm -rf "$e2e_venv"
  fi
  "$runtime" rm --force "$postgres_name" >/dev/null 2>&1 || true
  "$runtime" network rm "$network_name" >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

if ! "$runtime" network inspect "$network_name" >/dev/null 2>&1; then
  "$runtime" network create "$network_name" >/dev/null
fi
"$runtime" rm --force "$postgres_name" >/dev/null 2>&1 || true

"$runtime" run --detach \
  --name "$postgres_name" \
  --network "$network_name" \
  --network-alias postgres \
  --publish "127.0.0.1:$db_port:5432" \
  --env POSTGRES_DB=erd \
  --env POSTGRES_USER=erd \
  --env "POSTGRES_PASSWORD=$db_password" \
  "$postgres_image" >/dev/null

until "$runtime" exec "$postgres_name" pg_isready -U erd -d erd >/dev/null 2>&1; do
  sleep 1
done

e2e_venv="$(mktemp -d /tmp/pg-erd-cloud-e2e-venv.XXXXXX)"
uv venv "$e2e_venv" --python 3.14 >/dev/null
uv pip install --python "$e2e_venv/bin/python" \
  --require-hashes -r "$repo_root/backend/requirements.lock" >/dev/null

(
  cd "$repo_root/backend"
  DATABASE_URL="postgresql+asyncpg://erd:$db_password@127.0.0.1:$db_port/erd" \
  APP_SECRET="$app_secret" \
  CORS_ORIGINS=http://127.0.0.1:5173 \
  E2E_TEST_MODE=true \
  DB_INTROSPECTION_ALLOWED_HOSTS=localhost,127.0.0.1 \
  DB_INTROSPECTION_ALLOW_LOCAL_TARGETS=true \
  PYTHONPATH=. "$e2e_venv/bin/alembic" upgrade head
)

(
  cd "$repo_root/backend"
  DATABASE_URL="postgresql+asyncpg://erd:$db_password@127.0.0.1:$db_port/erd" \
  APP_SECRET="$app_secret" \
  CORS_ORIGINS=http://127.0.0.1:5173 \
  E2E_TEST_MODE=true \
  DB_INTROSPECTION_ALLOWED_HOSTS=localhost,127.0.0.1 \
  DB_INTROSPECTION_ALLOW_LOCAL_TARGETS=true \
  PYTHONPATH=. "$e2e_venv/bin/hypercorn" --config python:app.hypercorn_config \
    app.main:app --bind 127.0.0.1:8000 --access-logfile - --error-logfile -
) >/tmp/pg-erd-cloud-e2e-backend.log 2>&1 &
backend_pid=$!

until curl --fail --silent http://127.0.0.1:8000/healthz >/dev/null; do
  sleep 1
done

E2E_METADATA_DSN="postgresql://erd:$db_password@127.0.0.1:$db_port/erd" \
E2E_API_KEY="$api_key" \
E2E_APP_SECRET="$app_secret" \
  "$repo_root/scripts/e2e/seed_local_3nf.sh"

if [[ ! -x "$repo_root/frontend/node_modules/.bin/playwright" ]]; then
  (cd "$repo_root/frontend" && npm ci)
fi
(cd "$repo_root/frontend" && npx playwright install chromium)

(
  cd "$repo_root/frontend"
  VITE_API_BASE_URL='' \
  E2E_API_PROXY_TARGET=http://127.0.0.1:8000 \
    npm run dev -- --host 127.0.0.1 --port 5173
) >/tmp/pg-erd-cloud-e2e-frontend.log 2>&1 &
frontend_pid=$!

until curl --fail --silent http://127.0.0.1:5173/ >/dev/null; do
  sleep 1
done

(cd "$repo_root/frontend" && \
  E2E_API_KEY="$api_key" \
  E2E_TARGET_DSN="postgresql://erd:$db_password@localhost:$db_port/erd" \
  npm run e2e)
