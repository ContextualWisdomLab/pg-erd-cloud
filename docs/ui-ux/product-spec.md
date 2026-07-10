# Cloud ERD Product Spec

This document connects the UI reference images in this folder to the implemented
pg-erd-cloud product surface. It is intentionally compact: use it as the shared
contract for filling empty screens, reviewing new UI PRs, and deciding whether a
visual gap is a design-only issue or missing product code.

## Information Architecture

- Auth gate: loading and unauthenticated states before workspace access.
- Workspace shell: persistent left sidebar with brand, primary navigation, and
  selected workspace context.
- Dashboard: summary metrics plus shortcuts into recent projects and diagrams.
- Projects: project list, inline project creation, and drill-in to diagrams.
- Diagrams: searchable snapshot list scoped to the selected project.
- Editor: database connection setup, snapshot creation, ERD canvas, table
  search, layout tools, grouping, index-cardinality guidance, sharing, and
  exports.

## Screen Definitions

| Screen | Reference | Primary job | Required empty state |
| --- | --- | --- | --- |
| Auth | `01-login-screen.png` | Confirm whether the user can enter the workspace. | Loading and authentication-required messages must explain the blocker. |
| Dashboard | `02-dashboard-screen.png` | Show project, connection, and diagram counts with recent work. | Recent project and diagram regions must tell users to create work in the editor. |
| Projects | `03-project-list-screen.png` | Create, select, and open project workspaces. | Empty list must offer project creation in the same screen. |
| Diagrams | `04-diagram-list-screen.png` | Search and open generated ERD snapshots. | Empty list must explain that editor reverse engineering creates diagrams. |
| New diagram | `05-new-diagram-modal.png` | Start a reverse-engineering flow from project and connection context. | Disabled actions must expose the missing project or connection reason. |
| ERD editor | `06-erd-editor-main.png` | Inspect and edit schema structure on the canvas. | Empty canvas must distinguish snapshot generation from ready-to-create state. |
| Add entity | `07-add-entity-modal.png` | Add a table manually when no snapshot exists or when modeling ahead. | Save remains disabled until a table name is present. |
| Relationship settings | `08-relationship-settings-modal.png` | Edit or delete relationship labels. | Destructive actions require explicit confirmation. |
| Share/export | `09-share-export-modal.png` | Create share links and copy/export SQL or visual formats. | Export sections must explain what is missing before output exists. |

## Key Screens

Dashboard, Projects, Diagrams, and Editor are the four persistent navigation
destinations. Auth, Add entity, Relationship settings, Group manager,
Cardinality, and Share/export are supporting states that should never feel like
separate destinations.

The Editor is the highest-risk product surface because it combines credential
setup, generated schema data, direct table editing, and export/share actions.
New visual work should preserve the current quiet operational style: light
surface, thin borders, compact controls, blue primary action, and restrained
modals.

## Wireframes

### Workspace Shell

```text
+----------------------+---------------------------------------------+
| Cloud ERD            | Current screen title                         |
| Dashboard            | Supporting description                       |
| Projects             |                                             |
| Diagrams             | Screen content: metrics, tables, or canvas   |
| Editor               |                                             |
|                      | Primary action area stays in the screen      |
+----------------------+---------------------------------------------+
```

### Editor

```text
+----------------------+---------------------------------------------+
| Project selector     | [search] [layout] [undo] [+] [group] [SQL] |
| New project          |                                             |
| Connection selector  |                                             |
| New connection       |                ERD canvas                    |
| Schema filter        |                                             |
| Reverse engineer     |     Empty state or table nodes/edges         |
+----------------------+---------------------------------------------+
```

### Share And Export Modal

```text
+-----------------------------------------------------+
| Share and export                               close |
| Share link: description                 [make link] |
| [readonly link]                         [copy link] |
| DDL export: description                   [copy DDL] |
| [readonly SQL textarea or missing-output hint]       |
+-----------------------------------------------------+
```

## User Stories

- As an authenticated engineer, I can see whether I have projects,
  connections, and diagrams before I start modeling.
- As a database owner, I can create a project and connection, then reverse
  engineer a schema without leaving the editor.
- As a modeler, I can start from an empty canvas by adding a table manually
  when snapshot data is not available yet.
- As a reviewer, I can search diagrams and open the relevant snapshot quickly.
- As a schema maintainer, I can search tables and columns on a crowded canvas.
- As a data architect, I can group tables and review index-cardinality guidance
  without losing canvas context.
- As a collaborator, I can create a share link and copy DDL from one export
  surface.

## Implementation Checklist

- Every persistent screen has populated, loading, and empty states.
- Every disabled primary action provides nearby visible or accessible reason
  text.
- Modals use `role="dialog"`, `aria-modal="true"`, a labelled heading, focus
  management, and Escape close behavior.
- Canvas controls remain compact and do not resize the toolbar when labels or
  status text changes.
- New visual work references the images in `docs/ui-ux` and the styles in
  `frontend/src/styles.css` before introducing new layout patterns.
