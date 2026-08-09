# Security Policy

## Forward Engineering safety boundary

The live Forward Engineering workflow is not production-complete. Current code
implements a narrow server-authoritative model/plan control plane; isolated dry
run, durable apply, and convergence verification remain release blockers. See
the [Forward Engineering threat model](docs/security/forward-engineering-threat-model.md),
[v1 contract](docs/contracts/forward-engineering-v1.md), and
[operator runbook](docs/runbooks/forward-engineering.md). The legacy
`apply-sql` endpoint is a transitional compatibility surface and must not be
presented as the target graphical workflow.

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
