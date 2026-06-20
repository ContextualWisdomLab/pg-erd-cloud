# 2024-05-24 - Zero-dependency Object TTL Caching

**Learning:** When needing a fast short-lived memory cache to optimize hot path functions (like fetching the user object on every authenticated API request) in a Python backend, it is not always necessary to pull in third-party libraries like `cachetools`. A simple module-level dictionary pairing the value with an expiry timestamp and a basic pruning/size-capping strategy can be extremely effective.

**Action:** Before opting for external caching dependencies, evaluate if a simple dictionary cache with `maxsize` boundaries and simple TTL checking (`datetime.now(timezone.utc) < expires_at`) is sufficient and implement it directly to reduce bundle size and external complexity.
