cd backend && uv add "ecdsa>=0.19.2" --upgrade
git add pyproject.toml uv.lock
git commit --amend --no-edit
