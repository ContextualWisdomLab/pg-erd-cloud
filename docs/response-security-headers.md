# Response security headers

## Why

The backend is an API-first service, but it still benefits from baseline
**response hardening** headers to reduce the risk of clickjacking, MIME-sniffing,
and accidental embedding.

This repository applies headers in two places:

1) **Ingress / reverse proxy (recommended for production)**
2) **FastAPI middleware (fallback for dev/test parity)**

## Applied headers (default)

### Always

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`

### Conditional

- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
  - Applied only when the request is HTTPS (request URL scheme).
  - If you terminate TLS at a reverse proxy, prefer setting HSTS at the proxy.

### CSP

The FastAPI middleware sets a minimal API-friendly CSP by default:

<!-- markdownlint-disable MD013 -->
```http
Content-Security-Policy: default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'
```
<!-- markdownlint-enable MD013 -->

Note: HTTP headers are transmitted as a single line; any wrapping in this
document is for readability only.

To avoid breaking Swagger UI, CSP is **not applied** to these endpoints:

- `/docs`, `/docs/oauth2-redirect`
- `/redoc`
- `/openapi.json`

## Where it's configured

- **FastAPI**: `backend/app/security_headers.py` (middleware wired in
  `backend/app/main.py`)
- **Nginx (prod frontend container)**: `frontend/nginx.conf` (adds baseline
  headers with `always`)

## Validation (smoke)

Example checks:

```bash
# backend (dev)
curl -fsS -D- http://127.0.0.1:8000/healthz -o /dev/null

# docs should NOT include CSP
curl -fsS -D- http://127.0.0.1:8000/docs -o /dev/null

# frontend prod container (nginx)
curl -fsS -D- http://127.0.0.1:8080/ -o /dev/null
curl -fsS -D- http://127.0.0.1:8080/api/me -o /dev/null
```
