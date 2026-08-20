# Storybook inventory

This inventory is the executable visual handoff for repeated UI decisions in
pg-erd-cloud. Run `npm run storybook` from `frontend/` to inspect it locally.

| Story | Contract | Next buyer-facing action |
|---|---|---|
| `Design System/Design Tokens/Inventory` | Semantic colors, surfaces, borders, radii, spacing, and focus shadows are read from `src/design-tokens.css`. | Add a story beside each shared modal or toolbar control when its interaction contract is extracted. |

The application imports the same token stylesheet through `src/styles.css`, so
the inventory cannot silently drift from the deployed UI. Figma remains visual
intent; Storybook and interaction tests remain the executable implementation
contract. The authoritative Figma IDs are recorded in ADR-0002.
