#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
metadata_dsn="${E2E_METADATA_DSN:?E2E_METADATA_DSN is required}"
api_key="${E2E_API_KEY:?E2E_API_KEY is required}"
app_secret="${E2E_APP_SECRET:?E2E_APP_SECRET is required}"

key_hash="$(python3 -c 'import hashlib, sys; print(hashlib.pbkdf2_hmac("sha256", sys.argv[1].encode(), sys.argv[2].encode(), 210000).hex())' "$api_key" "$app_secret")"

psql "$metadata_dsn" \
  --set=ON_ERROR_STOP=1 \
  --file="$repo_root/scripts/e2e/seed_local_3nf.sql" \
  --command="DELETE FROM user_account WHERE oidc_subject = 'e2e-local-user';" \
  --command="INSERT INTO user_account (user_account_uuid, oidc_subject, display_name, created_at) VALUES ('00000000-0000-0000-0000-000000000001', 'e2e-local-user', 'Local E2E User', now());" \
  --command="INSERT INTO api_key (api_key_uuid, user_account_uuid, key_name, key_hash, key_prefix, created_at) VALUES ('00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'local-e2e', '$key_hash', 'pgerd_e2e', now());"
