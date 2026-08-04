# Engineering evidence register

This document records the authoritative standards, primary technical documentation, research evidence, and explicit evidence boundaries used to justify product and engineering decisions. References are formatted in APA 7th edition style. Entries should be amended when an upstream standard or dependency changes materially.

## 2026-08-04 — Database credential transport and production TLS

### Decision

- Database connection credentials are submitted only to an HTTPS API origin, except for explicit local-development loopback hosts.
- The credential-bearing `fetch()` call uses `redirect: "error"`; redirect responses therefore fail as network errors instead of forwarding the POST body.
- The production Compose profile requires a certificate and private key, exposes a TLS entry point, redirects loopback HTTP traffic to HTTPS, enables TLS on every application router, requires TLS 1.2 or later, enables strict SNI handling, and emits HSTS headers.
- SSRF findings are classified as `CWE-918`, not as the nonexistent shorthand `CVE-918`.

### Evidence

The Fetch Standard defines request redirect mode as `follow`, `error`, or `manual`. For a redirect response, redirect mode `error` sets the response to a network error. Traefik's current documentation defines entry-point redirection, TLS-only HTTP routers, user-provided certificates in dynamic configuration, minimum TLS versions, and strict SNI handling. MITRE defines server-side request forgery as CWE-918.

### Snowflake DNS-pinning boundary

The Snowflake Python Connector documents `account` as a required account identifier and `host` as an optional host name. It does not document a connection-specific DNS resolver or a separate TLS SNI/certificate hostname that can be paired safely with a literal validated IP. Consequently, a validated IP must not be substituted into the `account` field, and an IP override must not be represented as complete DNS-rebinding protection without connector-supported hostname verification or an independently enforced outbound egress boundary. This limitation remains an explicit security-design item rather than an unsupported implementation claim.

### References

MITRE Corporation. (2026, April 30). *CWE-918: Server-side request forgery (SSRF)*. Common Weakness Enumeration. https://cwe.mitre.org/data/definitions/918.html

Snowflake Inc. (n.d.). *Python Connector API*. Retrieved August 4, 2026, from https://docs.snowflake.com/en/developer-guide/python-connector/python-connector-api

Traefik Labs. (n.d.). *EntryPoints*. Retrieved August 4, 2026, from https://doc.traefik.io/traefik/reference/install-configuration/entrypoints/

Traefik Labs. (n.d.). *TLS certificates*. Retrieved August 4, 2026, from https://doc.traefik.io/traefik/https/tls/

Traefik Labs. (n.d.). *TLS options*. Retrieved August 4, 2026, from https://doc.traefik.io/traefik/v3.5/reference/routing-configuration/http/tls/tls-options/

WHATWG. (2026, July 2). *Fetch standard*. https://fetch.spec.whatwg.org/
