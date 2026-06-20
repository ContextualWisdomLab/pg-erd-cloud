# ⚡ Bolt Learnings

## 2025-02-14 - Optimize synchronous socket DNS resolution

**Learning:** Using `socket.getaddrinfo()` directly in an asynchronous context blocks the event loop, causing performance degradation under load as it runs synchronously.
**Action:** Use `asyncio.get_running_loop().getaddrinfo()` to perform non-blocking DNS resolution within an asynchronous application like FastAPI.
