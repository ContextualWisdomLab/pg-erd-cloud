# Storybook inventory

This inventory is the executable visual handoff for repeated UI decisions in
pg-erd-cloud. Run `npm run storybook` from `frontend/` to inspect it locally.

| Story | Contract | Next buyer-facing action |
|---|---|---|
| `Design System/Design Tokens/Inventory` | Semantic colors, surfaces, borders, radii, spacing, and focus shadows are read from `src/design-tokens.css`. Every token row exposes the exact CSS source value as text, while the visual swatch is decorative and excluded from the accessibility tree. | Add a story beside each shared modal or toolbar control when its interaction contract is extracted. |

The application imports the same token stylesheet through `src/styles.css`, so
the inventory cannot silently drift from the deployed UI. Figma remains visual
intent; Storybook and interaction tests remain the executable implementation
contract. The authoritative Figma IDs are recorded in ADR-0002. The Figma token
reference already presents each custom property beside its value, so the
Storybook exact-value alternative keeps visual and non-visual handoff aligned.
