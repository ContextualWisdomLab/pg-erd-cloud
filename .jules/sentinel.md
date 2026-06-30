## 2026-06-30 - Insecure Frontend DSN Handling
**Vulnerability:** The application stored database connection strings (DSNs) directly in the frontend component state (`App.tsx`), posing a security risk as sensitive credentials could be exposed in the client-side memory or logged.
**Learning:** Sensitive credentials like DSNs should not be handled directly in the frontend state. Instead, they should be captured directly from form inputs upon submission to minimize their footprint in memory.
