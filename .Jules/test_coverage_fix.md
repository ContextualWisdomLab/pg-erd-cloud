## 2024-05-30 - Fix Test Coverage

**Learning:**
In order to achieve 100% test coverage we must provide coverage for all files. `app/db.py` was missing test logic so I mocked out connections and pooler behavior to simulate various edge cases. The `GroupModal.tsx` React component was also missing coverage for form validations on the client which I addressed via React Testing Library by simulating `submit` events.

**Action:**
Created new test logic for missing files to hit all branches and verify coverage using tools like `pytest` and `vitest`.
