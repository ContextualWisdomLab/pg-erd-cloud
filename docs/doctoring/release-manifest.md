# Release-evidence manifest

Status: **in progress** — first increment (pure manifest assembler) landed.
Tracks issue
[#953](https://github.com/ContextualWisdomLab/pg-erd-cloud/issues/953)
("[Release Epic] Ship the first commercial release with exact-head,
migration, operability, and supply-chain evidence").

## Why

Issue #953 requires that release inclusion, dependency pinning, migration
compatibility, exact-head provenance, and known limitations all be stated
from **one immutable manifest** rather than reconstructed from scattered
CI logs and PR comments. A large open-PR count is not itself a defect, but
a release is not credible when those facts cannot be pinned.

## Decision — pure manifest assembler (this increment)

`app/release/manifest.py`
`build_release_manifest(*, source_commit, backend_version, frontend_version,
migration_revisions, dependency_lock_digests, included_prs,
known_limitations, generated_at) -> dict` validates the facts a caller has
already gathered and returns a stable, JSON-serializable manifest. It runs
**no git, no network, no filesystem access** — the caller (a release
workflow) supplies every fact.

### Field contract

| Field | Rule | Output |
| --- | --- | --- |
| `source_commit` | non-empty; lowercased; `^[0-9a-f]{7,40}$` | lowercased commit |
| `backend_version` / `frontend_version` | `^\d+\.\d+\.\d+` (pre-release suffix allowed) | as given |
| `migration_revisions` | every item a non-empty str | `sorted(set(...))` |
| `dependency_lock_digests` | keys non-empty str; values `^sha256:[0-9a-f]{64}$` | dict with sorted keys |
| `included_prs` | every item an `int` > 0 (`bool` rejected) | `sorted(set(...))` |
| `known_limitations` | every item a non-empty str | order preserved |
| `generated_at` | `datetime.fromisoformat` parses **and** is tz-aware | as given |

`ValueError` is raised naming the **first** field that fails.

### Honesty rule

`is_ga_candidate = len(known_limitations) == 0`. Listing any limitation is
the supported way to ship a beta / non-GA artifact without the manifest
claiming GA. A release workflow that wants a GA claim must first drive
`known_limitations` to empty.

## Deferred (later increments on #953)

- **SBOM generation** — an SPDX or CycloneDX document per shipped artifact,
  referenced from the manifest by digest.
- **Signed build provenance / attestation** — SLSA v1.2-compatible, tying
  the manifest to the build that produced it.
- **The operability baseline** — SLI/SLO, dashboards, alerts, runbooks
  (links to the #951 capacity profile).
- **Migration rehearsal automation** — clean install on the supported
  PostgreSQL matrix + upgrade from the oldest supported `0.1.x`.
- **Per-dependency release-decision table** — a `release_blocker` /
  `post_ga_committed` / `experimental` / `not_planned` decision + rationale
  for each of #946–#952 and the other tracked PRs.
- **The full open-PR classification of record** — every open PR captured at
  its exact head and classified (see the #953 section of
  `docs/product-technical-gap-baseline.md`).

## References (APA 7th)

National Institute of Standards and Technology. (2022). *Secure software
development framework (SSDF) version 1.1* (NIST Special Publication
800-218). https://doi.org/10.6028/NIST.SP.800-218

SLSA Community. (2025). *Supply-chain levels for software artifacts
specification, version 1.2*. https://slsa.dev/spec/v1.2/

Linux Foundation. (2024). *System Package Data Exchange (SPDX)
specification, version 3.0*. https://spdx.dev/specifications/

OWASP Foundation. (2024). *CycloneDX specification, version 1.6*.
https://cyclonedx.org/specification/overview/
