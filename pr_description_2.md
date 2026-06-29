🛡️ Sentinel: High Fix Token revocation cache vulnerability

💡 What:
- `revoke_token_jti` and `is_token_jti_revoked` in `backend/app/auth.py` have been refactored to use a persistent database storage (`RevokedToken` model) instead of an in-memory dictionary.
- Created an Alembic migration (`0003_revoked_token.py`) for the new `revoked_token` table.

🎯 Why:
- The previous implementation used an in-memory dictionary (`_revoked_token_jtis`) which would clear upon application restart.
- This was a High severity vulnerability that allowed revoked tokens to become valid again after a restart until their original expiry date.

✅ Verification:
- Ran `pytest tests/test_auth_security.py` and `pytest` for all backend tests successfully.
- Code conforms to standard `ruff` formatting and linting.
