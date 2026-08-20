# ADR-0002: Product and technical gap baseline

- **Status:** Proposed
- **Date:** 2026-08-20
- **Scope:** pg-erd-cloud product, architecture, release, and ecosystem boundary
- **Supersedes:** none

## Decision

Use `docs/product-technical-gap-baseline.md` as the living, evidence-based backlog for buyer-visible gaps and release readiness. It must be refreshed from exact GitHub PR heads, current checks, the protected-branch ruleset, and the repository's current implementation before merge/release claims.

For visual design authority, record the live Figma identifiers here:

- **Figma File ID:** `csnpEEJfmqFWB0vNUoTkWA`
- **Supplemental Figma File ID:** `OTN0rBGtnVy0P7yq4Iv9Si`

Figma establishes visual intent; Storybook stories, design tokens, accessibility tests, and browser interaction tests establish the executable UI contract. This ADR does not declare the draft Figma PR approved.

The recurring delivery loop is proposed in pg-erd-cloud PR #943. It calls the
central OpenCode review/fix scheduler hourly, inspects up to 100 open PRs, and
uses the established protected merge credentials. The reusable workflow is
pinned to central `.github` commit
`aa8503f4383e8328d89104796bc3e9f7da810376`; the loop cannot approve, bypass,
or merge around the repository ruleset.

## Consequences

- Product and technical gaps remain visible after the ordinary PR queue is empty.
- A mutable GitHub check or review is never treated as permanent evidence.
- Connector work remains modular: pg-erd-cloud works alone and integrates with Clearfolio, naruon, and contextual-orchestrator through explicit contracts.
- New scale or Rust work requires measured evidence and a rollback path.

## References

Chen, P. P.-S. (1976). The entity-relationship model—Toward a unified view of data. *ACM Transactions on Database Systems, 1*(1), 9–36. https://doi.org/10.1145/320434.320440

Codd, E. F. (1970). A relational model of data for large shared data banks. *Communications of the ACM, 13*(6), 377–387. https://doi.org/10.1145/362384.362685

National Institute of Standards and Technology. (2022). *Secure software development framework (SSDF) version 1.1: Recommendations for mitigating the risk of software vulnerabilities* (NIST Special Publication 800-218). https://doi.org/10.6028/NIST.SP.800-218

