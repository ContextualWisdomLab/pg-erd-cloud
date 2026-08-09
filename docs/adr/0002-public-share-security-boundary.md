# ADR-0002: Public Share Security Boundary

- Status: Accepted
- Lifecycle: `active_pr` #824
- Date: 2026-08-09
- Supersedes: public routes that reused authenticated snapshot representations

## Context

A share UUID is a bearer capability: possession of the URL grants access until
expiry, and URLs can be copied, logged, synchronized, or leaked through browser
history. Schema metadata may disclose business vocabulary, internal topology,
comments, sampled values, and failure diagnostics. The authenticated reversing
workflow also exposes a paid live-LLM mode that a public viewer must not invoke.

The current canvas additionally contains local layout and modeling state that is
not persisted with a successful `schema_snapshot`. A public link therefore
cannot truthfully promise to share an unsaved edited diagram.

## Decision

Public sharing is a separate read-only representation and authorization
boundary, not an anonymous alias for authenticated APIs.

- A link is scoped to one project and `viewer` permission.
- Public listing and retrieval expose successful snapshots only.
- Public snapshot JSON and generated exports remove comments,
  `example_value`, and private failure diagnostics before rendering.
- Public routes never invoke live LLM work and never expose connection data,
  member data, mutation controls, annotations, or private diagram views.
- New links receive a configurable expiry and an owner-only, project-scoped
  authenticated API can delete a link immediately. The UI describes bearer
  access and states that it does not yet expose the revoke action.
- Public requests validate link existence and expiry through the primary
  session; a read replica must never extend a deleted capability during lag.
- Sharing the locally edited model/layout remains `planned`; until it is
  persisted and version-bound, the public viewer shares the sanitized stored
  snapshot only.

## Alternatives considered

- Reuse authenticated DTOs with fields hidden in the browser: rejected because
  data already crossed the trust boundary.
- Share any snapshot state: rejected because queued and failed jobs expose
  incomplete data and diagnostics.
- Allow public live-LLM generation: rejected because a bearer URL cannot carry
  project billing or purpose-bound authorization.
- Treat a UUID as a secret-management control: rejected because URLs have many
  routine disclosure paths.

## Consequences

- Public DTO/export tests must assert allowlisted output, not only a list of
  currently known sensitive fields.
- Rotation, access audit, UI revocation, and optional password/domain
  restriction remain explicit hardening work; expiry, API revocation, referrer,
  cache, and response-header controls are `active_pr` evidence.
- Persisted diagram views and annotations require a new decision before they
  may cross this boundary.

## Verification

- Backend tests cover cross-project snapshot rejection, successful-only
  filtering, primary-consistent revocation, path-scoped projection, expiry,
  redaction, and disabled live-LLM mode.
- Frontend tests cover the read-only route and absence of editing actions.
- The threat model tracks bearer-link leakage and inference threats.

## References

See OWASP Foundation (2025) and National Institute of Standards and Technology
(2022) in [`docs/references.md`](../references.md).
