from google_labs_jules_tools.git import submit

submit(
    branch_name="jules-add-project-member-refactoring",
    pr_title="🧹 [Code Health] Refactor add_project_member logic",
    pr_body="""🎯 **What:** Extracted internal logic in `add_project_member` to helper functions (`_ensure_owner`, `_ensure_user_exists`, `_ensure_not_changing_owner_role`, `_upsert_project_member`).

💡 **Why:** Reduces the cognitive complexity of the `add_project_member` endpoint and separates business logic layers. This makes the endpoint function much easier to read and allows the individual helper functions to potentially be tested and reused independently.

✅ **Verification:** Ran `ruff check` and `ruff format` to ensure code styling compliance. Re-ran the pytest suite in `backend/` and confirmed all 92 backend tests are passing successfully.

✨ **Result:** Improved modularity and readability of the codebase without changing the functionality."""
)
