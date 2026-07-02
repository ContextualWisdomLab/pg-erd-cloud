🧪 [Test] Fix frontend typecheck issues for TableNode tests

💡 What:
- Fixed a TypeScript error in `frontend/src/erd/__tests__/TableNode.test.tsx` by typecasting props passed to `<TableNode>` to `any`.
- Adjusted the global namespace used for mocking `ResizeObserver` from `global` to `globalThis` to comply with the environment configuration.

🎯 Why:
- The tests were failing in the GitHub Actions frontend CI job due to missing property errors from `@xyflow/react` node requirements and an issue with defining the global object.
- Properly casting props and standardizing the global mock object resolves the type issues without losing test coverage scope.

✅ Verification:
- Ran `pnpm run typecheck` successfully with 0 errors.
- Ran `pnpm run test` successfully with all tests passing.
