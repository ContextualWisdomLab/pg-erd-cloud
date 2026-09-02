# Security Policy

## Request-name input boundary

Name-like request fields that can appear in logs, terminal output, audit evidence, or generated API material reject Unicode C0 controls (U+0000–U+001F), DEL (U+007F), and C1 controls (U+0080–U+009F). This applies to project, connection, diagram-view, table-annotation schema/relation, API-key names, and member subjects at the request-schema boundary. Ordinary printable Unicode remains valid for name fields; member subjects retain their stricter no-whitespace identity contract.

This validation is defense in depth. Output encoders and structured logging must still treat request values as data rather than terminal commands or log syntax.

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
