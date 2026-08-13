1. Update `frontend/src/erd/handleUtils.ts` and its test file to include decoding functions.
   - Add `decodeHandleId`, `decodeSourceHandleId`, and `decodeTargetHandleId` to `handleUtils.ts`.
   - Add tests for these functions in `handleUtils.test.ts`.
2. Verify the changes to `handleUtils.ts` and `handleUtils.test.ts`.
3. Update ERD exporters (`mermaid.ts`, `prisma.ts`, `dbml.ts`, `exportDataDictionary.ts`) to use the new decoding functions.
   - Decode edge handles during the initial edge processing step (O(E)).
   - Replace the expensive `sanitizeHandleId` encoding check inside the O(N * C) column loops with a direct O(1) native string lookup.
4. Verify the changes to ERD exporters.
5. Update `.jules/bolt.md` with the critical learning about handle decoding optimization (in Korean).
6. Verify the journal update.
7. Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.
8. Submit the performance improvement PR via the `submit` tool.
