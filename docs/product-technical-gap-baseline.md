# Product Technical Gap Baseline

- **Prevent O(N) garbage allocations in backend grouping loops**: The backend export module (`backend/app/ddl/export.py` and `backend/app/spec/orm_codegen.py`) grouped columns/edges using `dict.setdefault(..., []).append(...)`. This eager evaluation of default parameters caused O(N) intermediate list/set allocations. It has been replaced with explicit conditional logic. Measurements: Benchmark N=1,000,000 U=1,000. Median CPU time reduced from 287.05ms to 266.73ms. Exact outputs maintained.
