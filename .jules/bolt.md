⚡ Bolt: Refactor _ensure_owner to use a single bulk query using in_ to fix N+1 issue. Benchmark measured 240x speedup when checking 1000 items (0.0024 seconds vs 0.5806 seconds).
## 2024-06-21 - [Optimize database queries using bulk operations]
**Learning:** Checking ownership of multiple projects using sequential `execute` statements results in an N+1 query issue, significantly degrading performance as the number of checks grows.
**Action:** Always prefer bulk queries using `.in_()` over iterating and running individual queries when processing sequences or sets of resources.
