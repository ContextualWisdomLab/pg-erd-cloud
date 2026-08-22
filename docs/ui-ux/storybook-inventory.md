# Storybook inventory

This inventory is the executable visual handoff for repeated UI decisions in
pg-erd-cloud. Run `npm run storybook` from `frontend/` to inspect it locally.

| Story | Contract | Next buyer-facing action |
|---|---|---|
| `Design System/Design Tokens/Inventory` | Runtime semantics come from `src/design-tokens.css`. Exact values shown by Storybook come from `src/design-token-values.ts`, and a regression test requires that mirror to match every CSS custom-property name and value exactly. Visual swatches are decorative and excluded from the accessibility tree. | Add a story beside each shared modal or toolbar control when its interaction contract is extracted. |

The application imports the runtime token stylesheet through `src/styles.css`.
`design-tokens.stories.test.tsx` reads that CSS source during the test run and
fails if the executable Storybook value mirror drifts. Figma remains visual
intent; Storybook and interaction tests remain the executable implementation
contract. The authoritative Figma IDs are recorded in ADR-0002. The Figma token
reference presents each custom property beside its value, so the Storybook
exact-value alternative keeps visual and non-visual handoff aligned.
