# ADR-0001: Adaptive contextual-orchestrator mode is the LLM-draft default

- Status: Accepted
- Date: 2026-08-16

## Context

pg-erd-cloud can call either contextual-orchestrator or another OpenAI-compatible provider. It omitted an explicit orchestration mode, so the contextual gateway's adaptive requirement was not reviewable. Sending an orchestration-only field to every provider would, however, violate the generic compatibility contract.

## Decision

When and only when `LLM_MODEL` is exactly `contextual-orchestrator`, every live LLM-draft request includes `orchestration_mode: "auto"`.

Contextual-orchestrator owns model/provider selection, test-time compute, workflow depth, verification, fallback, and known-price optimization. Quality sufficiency is the first constraint; cost is minimized among execution paths that satisfy it. Missing or untrusted price metadata is classified as unpriced, not free.

Other model identifiers receive the unchanged generic OpenAI-compatible request. pg-erd-cloud continues to own schema evidence, prompt construction, credential boundaries, response parsing, and fail-closed API errors. Explicit route or conduct modes are reserved for controlled ablation or a documented incident override and are not product defaults.

## Consequences

Contextual-orchestrator deployments obtain an explicit adaptive default without breaking direct providers that reject unknown fields. Simple drafts may still use one worker when adaptive policy finds that sufficient; complex or high-risk database guidance may use deeper orchestration.

## References

Omidvar, H., & Akhlaghi, V. (2026). *A communication-theoretic framework for LLM agents: Cost-aware adaptive reliability* [Preprint]. arXiv. https://doi.org/10.48550/arXiv.2605.09121

Tang, Y., Cetin, E., Xu, J., Sun, Q., Nielsen, S., Richard, V., Goda, H., Tymchenko, I., Nguyen, N., Lee, H., Ashiga, M., Kotyan, S., Kuroki, S., & Clanuwat, T. (2026). *Sakana Fugu technical report* [Technical report]. arXiv. https://doi.org/10.48550/arXiv.2606.21228
