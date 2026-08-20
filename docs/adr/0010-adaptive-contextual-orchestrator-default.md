# ADR-0010: LLM draft requests use contextual-orchestrator auto

- Status: Accepted
- Date: 2026-08-16

## Context

pg-erd-cloud generates bounded LLM draft material through the organization gateway,
but an implicit or model-only request does not make execution-policy ownership
reviewable. The ERD product must not choose one provider/model or a fixed multi-agent
shape for every reverse-engineering and index-design task.

## Decision

The LLM request explicitly selects `orchestration_mode: "auto"` while retaining the
`contextual-orchestrator` model alias. The orchestration plane chooses the
quality-sufficient route, verification, or conducted workflow and minimizes known
cost only after capability constraints. Unknown price metadata is not treated as
free.

pg-erd-cloud retains prompt construction, database authorization, schema semantics,
strict response handling, and user-visible draft review. Explicit fixed modes remain
controlled orchestration experiments, not application defaults.

## References

Omidvar, H., & Akhlaghi, V. (2026). *A communication-theoretic framework for LLM agents: Cost-aware adaptive reliability* [Preprint]. arXiv. https://doi.org/10.48550/arXiv.2605.09121

This framework treats routing, retry, voting, and verification as reliability operators and introduces a cost-aware router that moves along a quality-cost frontier. It supports making orchestration depth and verification an adaptive gateway decision rather than a fixed application-level model choice.

Tang, Y., Cetin, E., Xu, J., Sun, Q., Nielsen, S., Richard, V., Goda, H., Tymchenko, I., Nguyen, N., Lee, H., Ashiga, M., Kotyan, S., Kuroki, S., & Clanuwat, T. (2026). *Sakana Fugu technical report* [Technical report]. arXiv. https://doi.org/10.48550/arXiv.2606.21228

The Fugu report describes orchestrator models that dynamically select agentic scaffolds and combine specialized agents. It supports the default auto mode because task difficulty can determine whether a single worker, verification, or a deeper multi-agent workflow is appropriate.
