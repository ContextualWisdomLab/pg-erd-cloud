## 2026-06-19 - Endless Polling in React Components
**Learning:** React `useEffect` with `setInterval` for polling can easily become a performance bottleneck (unnecessary network calls, state updates, and potential memory leaks) if the termination condition isn't handled correctly when the polled job reaches a terminal state.
**Action:** Always ensure polling mechanisms have a clean exit strategy by clearing intervals once a terminal state (like `succeeded`, `failed`, or `not_found`) is reached.

## 2026-06-19 - Expensive useMemo Keys
**Learning:** Using `JSON.stringify` on large data objects as a dependency for `useMemo` is an expensive hack to prevent re-renders, causing severe performance issues as the data size grows.
**Action:** Rely on proper reference management and stop unnecessary state updates (like fixing endless polling) instead of using deep stringification hacks for `useMemo` dependencies.
