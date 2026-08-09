# ADR-0001: Live Figma Design Authority

- Status: Accepted
- Lifecycle: `active_pr` #824
- Date: 2026-08-09
- Supersedes: historical PNG-first interpretation and deleted node `29:143`

## Context

The repository contained historical PNG references, current source behavior,
two Figma files and a deleted share/export node. A metadata request that loaded
only one page was previously misread as evidence that the design file was
empty. Direct Figma Plugin API inspection instead shows 18 pages in file
`csnpEEJfmqFWB0vNUoTkWA`, including `Screen Templates` (`7:9`), `Developer
Handoff`, and `Implementation Contracts` (`45:2`). The screen page contains
Auth, dashboard, list, editor and six current modal frames.

Figma also contains internal conflicts: a general 360 px sidebar variable and
a concrete editor split of 300/850/290; modal showcase dimensions that differ
from explicit handoff variables; and several color pairs that do not meet the
applicable WCAG 2.2 contrast criterion.

## Decision

Use the following precedence for UI implementation and review:

1. Concrete live Screen Templates and Implementation Contracts.
2. Explicit Developer Handoff mappings and component descriptions.
3. Current source behavior explicitly documented by Figma as an intentional
   extension.
4. Current committed QA evidence.
5. Historical PNGs.

Concrete screens override free-standing variables unless handoff explicitly
maps that property to a variable. Semantic `--pg-*` tokens bridge design and
code. Implementation applies a documented accessibility override when the
supplied value fails a standards-based requirement. Design QA must inspect
live nodes and implemented runtime states; metadata-page truncation is never
treated as proof of absence.

## Alternatives considered

- Historical PNGs as authority: rejected because they are stale and omit
  current components and interaction contracts.
- Product Design Kit file `OTN0rBGtnVy0P7yq4Iv9Si` as authority: rejected
  because its canvas contains only `Page 2` and its token inventory conflicts
  with the concrete screen file.
- Copy raw values without precedence: rejected because conflicts become
  arbitrary and inaccessible values become production defects.
- Treat production code as the sole design authority: rejected because it
  makes design drift impossible to distinguish from intentional extension.

## Consequences

- `docs/ui-ux/figma-contract.md` is the node-level bridge and must be checked
  whenever screen or token contracts change.
- Figma and code can intentionally differ, but every difference needs a named
  reason and verification evidence.
- Pixel similarity alone cannot override keyboard, accessible-name, focus,
  contrast, scrolling or responsive requirements.
- PR #824 remains `active_pr` until the exact head passes visual and CI gates
  and is merged.

## Verification

- Plugin API page/node inventory for the authoritative file.
- `get_design_context` for concrete editor and Implementation Contracts nodes.
- Semantic token, responsive CSS, dialog interaction and browser screenshot
  tests described in `design-qa.md` and `docs/test-strategy.md`.

## References

See World Wide Web Consortium (2023, 2024) and Object Management Group (2017)
in [`docs/references.md`](../references.md).
