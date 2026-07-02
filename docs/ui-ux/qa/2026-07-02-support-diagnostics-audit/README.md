# Support Diagnostics Product Design Audit

Date: 2026-07-02

Scope: commercial-readiness audit evidence for the support-operator billing
diagnostics path and the default buyer-demo dashboard.

Capture source:

- Local frontend demo server: `http://127.0.0.1:5174/`
- Demo mode: `VITE_DEMO_MODE=true`
- Support operator URL: `/?demo-support=operator`
- Browser automation: Playwright via the repository frontend dependency
- Figma design file:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si>
- Figma audit section:
  <https://www.figma.com/design/OTN0rBGtnVy0P7yq4Iv9Si?node-id=48-2>
- Figma Code Connect: not used

Evidence files:

1. `01-support-diagnostics-desktop.png`
   - Desktop operator view after looking up `customer-owner`.
   - Health: usable for operator review.
   - Risk: long billing and reactivation URLs wrap awkwardly inside detail
     cards.
2. `02-support-diagnostics-mobile.png`
   - Narrow viewport support diagnostics view.
   - Health: stable and reachable.
   - Risk: recent billing event table hides plan and received-at context
     off-screen, so the narrow support view needs stacked events or an explicit
     horizontal-scroll cue before it can be treated as a buyer-critical mobile
     support workflow.
3. `03-demo-dashboard-commercial.png`
   - Default commercial demo dashboard.
   - Health: solid buyer-demo entry state.
   - Risk: account status, billing status, and support escalation remain hidden
     from the default dashboard unless the operator support mode is active.
4. `04-figma-support-diagnostics-audit-section.png`
   - First Figma placement check. Rejected because uploaded image fills cropped
     part of the evidence.
5. `05-figma-support-diagnostics-audit-section-fit.png`
   - Accepted Figma placement check after switching image fills to `FIT`.

Audit conclusion:

- The read-only support diagnostics path is credible enough for paid-pilot
  support demos when the operator is authorized.
- The default dashboard remains appropriate as the buyer entry point, but it
  does not yet communicate billing or support trust signals.
- Narrow-width support diagnostics should remain a review/support fallback, not
  a primary mobile workflow, until event rows are redesigned for stacked reading.

Implementation evidence:

- `frontend/src/api.ts` exposes demo-only support-operator state through
  `?demo-support=operator`.
- `frontend/e2e/app-smoke.spec.ts` verifies that the support operator can open
  the support diagnostics screen, look up a subject, and inspect recent billing
  events.
