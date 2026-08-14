# Security Policy

## Reporting a Vulnerability

If you believe you have found a security vulnerability in this project, please **do not** open a public issue.

Preferred: report privately via GitHub Security Advisories:

- [Report a security advisory](https://github.com/ContextualWisdomLab/pg-erd-cloud/security/advisories/new)

Include, when possible:

- A clear description of the issue and potential impact
- Steps to reproduce (PoC), affected versions/commits, and environment details
- Any suggested fix or mitigation

## Disclosure Timeline

We aim to:

- Acknowledge receipt within **3 business days**
- Provide a remediation plan or status update within **14 days**
- Fix the issue and coordinate disclosure within **90 days**, when feasible

Timelines may vary depending on severity, complexity, and downstream impact.

## PostgreSQL connection-file boundary

PostgreSQL connection strings are untrusted input. They may select a permitted
network target and standard non-file connection options, but they cannot name
files on the pg-erd-cloud host. The connection guard rejects `passfile`,
`sslcert`, `sslcrl`, `sslkey`, and `sslrootcert` query parameters before DNS or
driver setup, using one fixed error that does not disclose the supplied path.

Client certificates and custom trust roots require a future server-owned secret
provider that passes already-authorized material to the connection layer. A
browser-supplied path and a hard-coded filesystem allowlist are not secret
authorization and must not be used as a substitute.
