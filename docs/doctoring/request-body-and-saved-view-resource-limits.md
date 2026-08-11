# Request-body and saved-view resource-limit contract

## Decision

Unsafe requests under `/api` are subject to a configurable pre-routing byte limit before FastAPI authentication dependencies or Pydantic request-model parsing. The default is 2 MiB through `API_REQUEST_BODY_MAX_BYTES`. The middleware rejects both an oversized valid `Content-Length` declaration and a streamed or chunked body whose observed bytes cross the limit. Accepted ASGI request messages are replayed unchanged.

Saved diagram layouts retain a narrower domain limit: the compact UTF-8 JSON representation of `layout_json`, with non-ASCII characters preserved rather than escaped, may not exceed 512 KiB. The transport limit is intentionally larger than the domain limit so a layout at the exact storage boundary can still include the request envelope and a 200-code-point view name. The backend validates the exact 512 KiB boundary after parsing; the frontend demo implementation applies the same name and serialized-layout limits before mutating its in-memory store.

## Security rationale

OWASP API Security Top 10 API4:2023 identifies unrestricted resource consumption when APIs omit or misconfigure maximum input and upload sizes, and recommends enforcing maximum sizes for incoming parameters and payloads. Request-rate limiting alone does not bound the memory or CPU cost of one request. The pre-routing limiter and the post-parse layout validator therefore serve different purposes:

1. `RequestBodyLimitMiddleware` bounds transport memory and parsing work for one unsafe API request.
2. `_bound_layout_size` preserves the saved-view storage and serialization contract after a valid request envelope is parsed.
3. Existing fixed-window rate limits bound request frequency.
4. Pydantic limits the view name to 1–200 characters.
5. Exact-boundary and one-byte-over tests prevent silent changes to the 512 KiB product contract.

The limiter is implemented as pure ASGI middleware using the `scope`, `receive`, and `send` interface described by Starlette. It buffers only applicable unsafe API requests, rejects before downstream routing when the bound is exceeded, and delegates safe methods, non-API paths, WebSockets, and lifespan traffic without body buffering.

## Saved-view demo parity

Demo mode is a product contract, not an unchecked mock. It must remain behaviorally aligned with network mode:

- same-millisecond creates receive distinct identifiers through a module-scoped sequence;
- names outside 1–200 characters are rejected before storage mutation;
- cyclic or otherwise non-serializable layouts are rejected;
- compact serialized layouts above 512 KiB are rejected;
- rejected creates and updates leave the store unchanged;
- an updated view moves to the front of the list, matching the backend's `updated_at DESC` ordering;
- create, read, update, and delete operations remain isolated by stable view identifier.

## Verification requirements

The exact pull-request head must pass:

- backend mypy;
- the complete backend pytest suite;
- production coverage including `app/request_body_limit.py`;
- frontend typecheck;
- the complete Vitest suite and production build;
- current-head Security Scan, comprising `osv-scan`, diff-scoped `dependency-review` that fails on Medium-or-higher findings, and repo-wide `trivy-fs` scanning `CRITICAL`, `HIGH`, and `MEDIUM` severities;
- current-head Semgrep;
- review-thread resolution and independent current-head approval.

The request limiter tests cover configuration rejection, valid and malformed `Content-Length`, exact-limit chunked replay, streamed over-limit rejection, disconnect replay, safe-method bypass, non-API bypass, and non-HTTP bypass. Saved-view tests cover ASCII and non-ASCII exact 512 KiB acceptance, one-byte-over rejection without mutation, same-timestamp identifier uniqueness, isolated mutation, newest-first update ordering, Unicode code-point name bounds, over-limit layouts, and cyclic layouts.

## APA 7 references

Encode OSS Ltd. (n.d.). *Middleware*. Starlette. Retrieved August 5, 2026, from https://www.starlette.io/middleware/

Encode OSS Ltd. (n.d.). *Requests*. Starlette. Retrieved August 5, 2026, from https://www.starlette.io/requests/

Meng, W., Qian, C., Hao, S., Borgolte, K., Vigna, G., Kruegel, C., & Lee, W. (2018). Rampart: Protecting web applications from CPU-exhaustion denial-of-service attacks. In *27th USENIX Security Symposium (USENIX Security 18)* (pp. 393–410). USENIX Association. https://www.usenix.org/conference/usenixsecurity18/presentation/meng

This study demonstrates that a small number of carefully constructed application requests can consume disproportionate server resources. It supports enforcing per-request bounds before expensive parsing, while retaining domain-specific validation after parsing.

OWASP Foundation. (2023). *API4:2023 unrestricted resource consumption*. OWASP API Security Top 10. https://owasp.org/API-Security/editions/2023/en/0xa4-unrestricted-resource-consumption/
