# Clearfolio reference-document viewer — integration

[Clearfolio](https://github.com/ContextualWisdomLab/clearfolio) is a document-viewer
platform (Java backend + JS preview). pg-erd-cloud links it so a project can attach
external reference documents (requirements, design specs, contracts — PDF/DOCX/PPT)
and view them next to the ERD.

## Architecture: pg-erd-cloud is the *buyer gateway*

pg-erd-cloud authenticates its own user (OIDC / API key), maps the principal to
Clearfolio tenant claims, **HMAC-signs** them, and proxies to Clearfolio's
connector API. Clearfolio verifies the signature, enforces permissions, and
isolates tenants.

### Signing contract (must match Clearfolio's verifier)

```
payload   = "\n".join([tenantId, subjectId, canonicalPermissions, issuedAt])
signature = base64url( HMAC_SHA256(secret, payload) )        # no padding
```

Sent as `X-Clearfolio-{Tenant-Id, Subject-Id, Permissions, Claims-Issued-At,
Claims-Signature}`. Implemented in `app/integrations/clearfolio.py`
(`sign_tenant_claims`, `build_tenant_headers`) and covered by a golden-vector test.

### Connector calls (proxied, SSRF-validated gateway host)

| Step | Clearfolio endpoint |
| --- | --- |
| Submit document | `POST /api/v1/convert/jobs` (multipart) |
| Poll status | `GET /api/v1/convert/jobs/{jobId}` |
| Viewer bootstrap | `GET /api/v1/viewer/{docId}` (signed previewResourcePath) |
| Artifact link | `POST /api/v1/viewer/{docId}/artifact-links` |

## Configuration

```bash
CLEARFOLIO_GATEWAY_URL=https://clearfolio.example.com
CLEARFOLIO_TENANT_CLAIMS_HMAC_SECRET=<shared gateway secret>
CLEARFOLIO_TENANT_ID=pg-erd-cloud            # default
CLEARFOLIO_PERMISSIONS=job:create,job:read,job:retry,viewer:read,artifact-link:create,analytics:read
```

Unset → the connector raises `ClearfolioNotConfigured` (feature is opt-in; no live
Clearfolio instance required for the rest of pg-erd-cloud).

## Status / next

- ✅ Connector core (signing + gateway client + config) — this PR, contract-mocked tests.
- ⬜ Project-scoped endpoints + `reference_document` persistence (IDOR per project) — follow-up (needs the alembic chain).
- ⬜ Frontend: attach/upload panel + embedded Clearfolio viewer bootstrap.
