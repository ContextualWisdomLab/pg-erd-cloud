## 2025-06-27 - [Map Initialization Overhead]
**Learning:** Initializing Maps with `new Map(array.map(...))` creates unnecessary intermediate arrays, consuming memory and triggering garbage collection overhead, especially noticeable when dealing with many nodes.
**Action:** Use a `for...of` loop to directly `map.set()` elements rather than creating an intermediate array of tuples, especially in frequently executed or rendering paths.
## 2025-07-15 - [Request URL Parsing Overhead in Starlette Middleware]
**Learning:** `request.url.path` dynamically parses the entire ASGI scope into a full URL object on every access. In hot paths like rate limiting middleware where every request is evaluated, this causes massive string parsing/object allocation.
**Action:** Use `request.scope.get("path", "")` instead of `request.url.path` when only the path is needed to avoid full URL initialization.
