# ADR-0005: Versioned Documentation Authority

- Status: Accepted
- Lifecycle: `active_pr` #824
- Date: 2026-08-09
- Supersedes: README-, chat-, and screenshot-only decision capture

## Context

Before this change the repository had no canonical PRD, TRD, architecture
entry point, ADR index, logical ERD, UML behavior set, threat model, test
strategy, or requirement traceability. README, CHANGELOG, Figma, source, and
historical screenshots contained overlapping claims with no shared lifecycle
vocabulary. Conversation decisions could therefore disappear or planned work
could be mistaken for shipped behavior.

## Decision

Maintain a versioned documentation graph rooted at `ARCHITECTURE.md` and
`docs/README.md`. Every material capability is labelled exactly as one of:
`implemented_on_main`, `active_pr`, `planned`, `research_only`, `downstream`,
`deprecated`, or `out_of_scope`.

Durable architectural choices use ADRs with alternatives, consequences, and
verification. PRD requirements have stable IDs. The traceability matrix maps
requirements to architecture, code, tests, and exact PR/main evidence. UML and
ERD documents distinguish current physical/logical truth from target models.
Figma authority is node-level and does not imply runtime delivery. Machine
tests verify required files, internal links, diagram presence, lifecycle
vocabulary, and known legacy naming exceptions.

## Alternatives considered

- One large README: rejected because product, technical, decision, data, and
  verification authorities change at different rates.
- Treat the conversation transcript as specification: rejected because it is
  not versioned beside code and lacks reviewable supersession.
- Generate all documentation from code: rejected because product intent,
  alternatives, planned states, and rejected choices are not fully derivable.
- Documentation-only completion: rejected; each implemented requirement still
  needs executable or operational evidence.

## Consequences

- A documentation PR may make the knowledge system structurally sufficient
  without making a planned feature implemented or a release ready.
- Contradictions are recorded and resolved; they are not hidden by picking the
  most convenient source.
- Changes to schema, APIs, trust boundaries, workflows, or Figma authority must
  update the linked documents in the same PR.

## Verification

- `backend/tests/test_documentation_contract.py` validates the graph's minimum
  machine-checkable contract.
- `docs/documentation-coverage-matrix.md` records the pre-change gap and current
  residual evidence limits.
- Review compares every lifecycle claim with protected-main or exact-PR code.

## References

See Object Management Group (2017), International Organization for
Standardization (2023), and National Institute of Standards and Technology
(2022) in [`docs/references.md`](../references.md).
