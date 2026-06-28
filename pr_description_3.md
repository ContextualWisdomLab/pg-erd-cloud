🛡️ Sentinel & 🧪 Tests: High & Medium Fixes for Auth and Project Members API & Fix tests

💡 What:
- `revoke_token_jti` and `is_token_jti_revoked` in `backend/app/auth.py` have been refactored to use a persistent database storage (`RevokedToken` model) instead of an in-memory dictionary.
- Created an Alembic migration (`0003_revoked_token.py`) for the new `revoked_token` table.
- Updated the `/api/projects/{project_space_uuid}/members` endpoint in `backend/app/api/projects.py` to enforce a minimum role of `editor` using `require_project_member`.
- Fixed React testing typecheck errors in `frontend/src/erd/__tests__/TableNode.test.tsx` and `App.editTable.test.tsx`.

🎯 Why:
- The previous auth implementation used an in-memory dictionary (`_revoked_token_jtis`) which would clear upon application restart. This was a High severity vulnerability that allowed revoked tokens to become valid again after a restart until their original expiry date.
- The `list_project_members` endpoint previously permitted any authenticated project member (including `viewer`s) to retrieve the complete list of project members and their roles. This posed an IDOR (Insecure Direct Object Reference) and potential data leakage risk. Restricting this to at least `editor` limits the exposure to users who already have modification rights.
- CI pipeline failed due to typing errors in frontend tests introduced by previous commits.

✅ Verification:
- Modified the endpoints and logic as required.
- Ran `pytest tests/test_auth_security.py`, `pytest tests/test_permissions.py` and `pytest` for all backend tests successfully.
- Code conforms to standard `ruff` formatting and linting.
- `pnpm run typecheck` and `pnpm run test` pass successfully in `frontend`.
