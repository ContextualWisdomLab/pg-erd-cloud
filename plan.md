1. **Explore ExportModal accessibility**
   - Check the tests and current implementation of `ExportModal.tsx`.
2. **Update Access Management button in ExportModal**
   - Change the native `disabled` attribute to `aria-disabled={true}` on the "접근 관리" (Access Management) button so it remains focusable and screen readers can read its `aria-describedby` hint.
   - Add `onClick={(e) => e.preventDefault()}` to prevent any action if clicked.
3. **Update CSS for the button**
   - In `frontend/src/styles.css`, update `.exportModal__disabledHintButton` to include `opacity: 0.5` and `cursor: not-allowed` to visually indicate it's disabled.
4. **Update Vitest test**
   - In `frontend/src/components/modals/ExportModal.test.tsx`, update the assertion for the "접근 관리" button to check for `toHaveAttribute('aria-disabled', 'true')` instead of `toBeDisabled()` as per the memory guidelines, and also ensure `.toHaveFocus()` can be checked if needed (but at least the tests pass).
5. **Run tests and checks**
   - Run `cd frontend && pnpm run typecheck && pnpm test && pnpm run build`.
6. **Pre-commit steps**
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
