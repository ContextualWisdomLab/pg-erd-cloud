# KRDS Traversal & Inventory — pg-erd-cloud Design System

This document is the **authoritative, version-controlled record** of the KRDS
(Korea Design System) traversal performed for pg-erd-cloud. It is the repo
mirror for the target Figma "Product Design Kit" (`OTN0rBGtnVy0P7yq4Iv9Si`)
pages and is the durable source for the component/pattern/service-pattern
inventories and the Gap Report. Direct Figma MCP inspection/mutation was not
available in this environment, so Figma node/page/component existence remains a
verification gap. See [`README.md`](./README.md) for the overall summary.

> **Scope reality:** pg-erd-cloud is a specialized **B2B ERD-diagramming SaaS**,
> not a citizen-facing government portal. Many KRDS components/patterns are
> therefore **N/A** by design. Status is reported honestly: `Ready` (exists +
> documented + code-mapped), `Review` (exists informally, needs
> componentization/a11y verification), `Gap` (applicable but missing),
> `N/A` (out of scope for this product).

## 1. KRDS sub-page traversal checklist

### 1-1. Design style sub-pages (KRDS 스타일)
- [x] 디자인 스타일 소개 → 01. Foundation intro
- [x] 색상 (Color) → Foundation / Color
- [x] 타이포그래피 (Typography) → Foundation / Typography
- [x] 형태 (Shape) → Foundation / Shape
- [x] 레이아웃 (Layout) → Foundation / Layout
- [x] 아이콘 (Icon) → Foundation / Icon
- [x] 디자인 토큰 (Design Token) → 02. Tokens
- [x] 엘리베이션 (Elevation) → Foundation / Elevation
- [x] 선명한 화면 모드 (High Contrast Mode) → Foundation / High Contrast Mode

### 1-2. Component categories (KRDS 컴포넌트) — see §4
- [x] Identity, Navigation, Layout & Expression, Action, Selection, Feedback,
      Help, Input, Setting, Content, Mobile

### 1-3. Basic patterns (KRDS 기본 패턴) — see §5
- [x] All 12 (+ 모바일 알림) inventoried

### 1-4. Service patterns (KRDS 서비스 패턴) — see §6
- [x] 방문, 검색, 로그인, 신청, 정책 정보 확인 inventoried

## 2. Foundation inventory

| Area | KRDS ref | Product state | Status |
|---|---|---|---|
| Color | style_02 | Target `PG ERD Primitives` + `PG ERD Color` variable collections documented; code brand `#034ea2` tokenized as `--color-action-primary`; direct Figma verification pending | Review |
| Typography | style_03 | Target text-style set documented; system-ui font stack in code (not Pretendard GOV) | Review |
| Shape/Radius | style_04 | Target `PG ERD Radius` scale documented | Review |
| Layout | style_05 | Fixed sidebar + main; `@media` narrow breakpoint; not a formal 12-col grid | Review |
| Icon | style_06 | No dedicated icon component set; inline SVG/text labels | Gap |
| Elevation | style_08 | Target `Shadow/Modal`, `Focus/Ring` effect styles documented | Review |
| High Contrast Mode | style_09 | Target `High Contrast` variable mode documented; code mirrors it with `@media (prefers-contrast: more)` | Review |

## 3. Token inventory (3-tier)

| Tier | KRDS naming | Product mapping | Status |
|---|---|---|---|
| Primitive | `color.primary.*`, `color.gray.*`, `space.*`, `radius.*` | Target Figma `PG ERD Primitives`/`Spacing`/`Radius` collections; code also has `frontend/src/design-system/tokens.css` | Review (naming differs from KRDS scale; Figma unverified) |
| Semantic | `color.text.*`, `color.background.*`, `color.border.*` | Target Figma `PG ERD Color`; code `--color-action-primary/-hover`, `--color-border-focus/-error`, `--color-text-disabled` | Review (partial in code) |
| Component | `button.*`, `input.*` | `.btn--*` classes in `styles.css`; code-only `krds-*` wrappers need adoption and Figma variants | Review |

Key gap: direct Figma variable verification is blocked by unavailable Figma MCP
tools. The full `:root` CSS token layer is separately proposed in **PR #406**
(`codex/css-token-layer`, open but blocked as of 2026-07-03 by automated review
`CHANGES_REQUESTED` from model-pool exhaustion). This repo adds only a minimal,
non-duplicative subset to avoid conflict.

## 4. Component inventory (KRDS full traversal)

Format: Category | Component (KRDS) | Variant | State | Accessibility | Dev Mapping | Status

### Identity (03)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 공식 배너 (Masthead) | – | – | – | – | N/A (gov-portal only) |
| 운영기관 식별자 (Identifier) | – | – | – | – | N/A |
| 헤더 (Header) | single | – | partial | `App.tsx` top toolbar region | Review |
| 푸터 (Footer) | – | – | – | – | Gap |

### Navigation (04)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 건너뛰기 링크 (Skip link) | – | Focus | yes | `styles.css .skip-link` | Ready |
| 메인 메뉴 (Main menu) | – | Active | `aria-current="page"` | `App.tsx .workspaceNav` | Review |
| 브레드크럼 (Breadcrumb) | code-only | Current | `aria-current="page"` | `components/Breadcrumb.tsx` (not adopted) | Review |
| 사이드 메뉴 (Side menu) | – | – | partial | `App.tsx .sidebar` | Review |
| 콘텐츠 내 탐색 (In-page nav) | – | – | – | – | N/A |
| 페이지네이션 (Pagination) | code-only partial | Current/Disabled | `aria-current`, button labels | `components/Pagination.tsx` (not adopted; no first/last/ellipsis) | Review |

### Layout & Expression (05)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 구조화 목록 (Structured list) | – | Empty | partial | project/diagram lists, `.panelEmpty` | Review |
| 긴급 공지 (Critical alert) | – | – | `role="alert"` | `.error` banners | Review |
| 달력 (Calendar) | – | – | – | – | N/A |
| 디스클로저 (Disclosure) | – | – | – | – | N/A |
| 모달 (Modal) | many | Open/Close | focus trap | `components/modals/*`, `useDialogAccessibility` | **Ready** |
| 배지 (Badge) | Status/PK/FK | many | `aria-label` | `Status Pill`, `TableNode` `<abbr>` | **Ready** |
| 아코디언 (Accordion) | – | – | – | – | N/A |
| 이미지 (Image) | – | – | – | – | N/A |
| 캐러셀 (Carousel) | – | – | – | – | N/A |
| 탭 (Tab) | – | – | – | view switch uses nav semantics, not `tablist` | Gap |
| 표 (Table) | ERD node | many | yes | `erd/TableNode.tsx` | **Ready** (domain-specific) |
| 텍스트 목록 (Text list) | – | – | partial | list rendering | Review |
| 파비콘 (Favicon) | – | – | – | `index.html` | Review |

### Action (06)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 링크 (Link) | – | Focus | `:focus-visible` | `a:focus-visible` styles | Review |
| 버튼 (Button) | Primary/Secondary/Ghost | Hover/Focus/Disabled | yes | **`components/Button.tsx`** + Figma set | **Ready** |
| 플로팅 버튼 (Floating button) | – | – | – | – | N/A |

### Selection (07)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 라디오 버튼 (Radio) | code-only | Checked/Disabled/Error | partial | `components/Radio.tsx` (not adopted) | Review |
| 체크박스 (Checkbox) | code-only | Checked/Disabled/Error | partial | `components/Checkbox.tsx` (not adopted) | Review |
| 셀렉트 (Select) | code-only | Native select/Error/Disabled | partial | `components/Select.tsx` (not adopted) | Review |
| 태그 (Tag) | color | – | partial | `businessGroups` tags | Review |
| 토글 스위치 (Toggle) | – | – | – | – | N/A |

### Feedback (08)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 단계 표시기 (Step indicator) | – | – | – | – | N/A (no multi-step flow) |
| 스피너 (Spinner) | Small/Medium | Loading | `role="status"` + reduced motion | `components/Spinner.tsx`, auth loading | Review |

### Help (09)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 도움 패널 (Help panel) | – | – | – | – | N/A |
| 따라하기 패널 (Walkthrough) | – | – | – | – | N/A |
| 맥락적 도움말 (Contextual help) | – | – | partial | `.field-hint` | Review |
| 코치마크 (Coach mark) | – | – | – | – | N/A |
| 툴팁 (Tooltip) | – | – | yes | `TableNode` `<abbr title>` | Review |
| 음성지원 TTS | – | – | – | – | N/A |

### Input (10)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 날짜 입력 필드 (Date input) | – | – | – | – | N/A |
| 텍스트 영역 (Textarea) | – | – | – | – | Gap |
| 텍스트 입력 필드 (Text input) | code-only | Default/Error/Required | `aria-invalid` / `aria-describedby` | `components/TextInput.tsx` (modal adoption pending) | Review |
| 파일 업로드 (File upload) | – | – | – | – | N/A |

### Setting (11)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 언어 변경 (Language switcher) | – | – | – | – | N/A (single language) |
| 화면 크기 조정 (Text resize) | – | – | partial | relative units | Gap (no dedicated control) |

### Content (12)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 접근 가능한 미디어 (Accessible media) | – | – | – | – | N/A |
| 숨긴 콘텐츠 (Hidden content) | – | – | yes | `aria-hidden` (7), `noscript` fallback | Ready |

### Mobile (13)
| Component | Variant | State | A11y | Dev Mapping | Status |
|---|---|---|---|---|---|
| 범위 슬라이드 (Range slider) | – | – | – | – | N/A |
| 뒤로가기 버튼 (Back button) | – | – | partial | `App.tsx` view-switch buttons | Review |
| 바텀시트 (Bottom sheet) | – | – | – | – | N/A (desktop-first) |
| 수량 토글 (Quantity toggle) | – | – | – | – | N/A |
| 토스트 (Toast) | Info/Success | Visible | `role="status"` / `aria-live` | `components/Toast.tsx`, `ExportModal` copy feedback | Review |
| 스낵바 (Snackbar) | – | – | – | – | Gap |
| 탭바 (Tab bar) | – | – | – | – | N/A |
| 스플래시 스크린 (Splash screen) | – | – | – | – | N/A |

**Summary:** Ready 6 · Review 19 · Gap 5 · N/A 25 (of 55 KRDS items traversed).

## 5. Basic pattern inventory (KRDS 12 + mobile)

Format: Pattern | Components | Flow | Error | Empty | Loading | A11y | Status

| Pattern | Components | Flow | Error | Empty | Loading | A11y | Status |
|---|---|---|---|---|---|---|---|
| 개인 식별 정보 입력 | – | – | – | – | – | – | N/A |
| 도움 | field-hint | partial | – | – | – | partial | Gap |
| 동의 | – | – | – | – | – | – | N/A |
| 목록 탐색 | list, empty state | yes | – | yes | – | partial | Review |
| 사용자 피드백 | alert, aria-live | yes | yes | – | – | yes | Review |
| 상세 정보 확인 | modal, table | yes | yes | – | – | yes | Review |
| 오류 | `.error` role=alert, validation | yes | yes | – | – | yes | Review |
| 입력폼 | Input, Select, Button, modal | yes | yes | n/a | – | focus trap | **Ready** |
| 첨부파일 | – | – | – | – | – | – | N/A |
| 필터링·정렬 | search input | yes | – | – | – | partial | Review |
| 확인 | modal confirm (저장/삭제) | yes | yes | – | – | yes | Review |
| 모바일 알림 | – | – | – | – | – | – | N/A |

## 6. Service pattern inventory (KRDS 5)

Format: Service Pattern | Entry | Flow | Prototype | Do/Better/Best | Components | Status

| Service Pattern | Entry | Flow | Prototype | Do/Better/Best | Components | Status |
|---|---|---|---|---|---|---|
| 방문 (Visit) | dashboard | yes | target only; Figma verification pending | partial | workspace dashboard, nav | Review |
| 검색 (Search) | editor | yes | target only; Figma verification pending | partial | search/filter input, TableNode highlight | Review |
| 로그인 (Login) | auth gate | yes | – | partial | AuthGate, `authError`, sign-in | Review |
| 신청 (Application) | – | – | – | – | – | N/A |
| 정책 정보 확인 (Policy info) | – | – | – | – | – | N/A |

## 7. Accessibility checklist

- [x] `lang=ko`, landmarks, skip-link (`styles.css`)
- [x] Global `:focus-visible` outline (now token-driven `--color-border-focus`)
- [x] Modal focus trap + Esc + focus restore (`useDialogAccessibility`)
- [x] Icon/abbr `aria-label` (PK/FK/NN) — PR #417
- [x] `role="alert"` / `aria-live="polite"` feedback regions
- [x] Spinner `role="status"` and reduced-motion handling
- [x] Toast `role="status"` for short copy-feedback results
- [x] `noscript` fallback
- [x] High-contrast mode documented and code-linked (`prefers-contrast: more`);
      target Figma mode still needs direct verification
- [ ] Dark mode variable/CSS mode (Gap, optional product theme)
- [ ] Full keyboard nav for ERD canvas modeled/prototyped (Gap)

## 8. Dev handoff mapping
See target Figma `17. Dev Handoff` and [`README.md`](./README.md) §3. Key
mismatch to verify when Figma MCP is available: target `color/action/primary`
(`#2563eb`) vs code brand (`#034ea2`) — reconcile to `#034ea2` (KRDS-aligned,
higher contrast).

## 9. Gap Report

| Area | KRDS Reference | Issue | Severity | Required Action | Owner | Due |
|---|---|---|---|---|---|---|
| Foundation | Dark mode | No dark-mode token/CSS mode | Medium | Define only if product needs a separate dark theme beyond KRDS high contrast | Design/Dev | TBD |
| Foundation | Figma file | Direct Figma page/variable/component inspection unavailable | Critical | Re-run with Figma MCP enabled; verify/create pages 00–19/99 and component sets | Design | TBD |
| Foundation | Icon (style_06) | No icon component set/standard | Medium | Define icon set (size/stroke/color rules) | Design | TBD |
| Token | Design Token (style_07) | Full `:root` token layer not merged | High | Merge/re-review PR #406; reconcile naming | Dev | TBD |
| Component | Button (Action) | Was no reusable code component | High | **Done** — `components/Button.tsx` added and uses shared `.btn` CSS tokens | Dev | ✔ |
| Component | Breadcrumb/Pagination/Checkbox/Radio/Select/TextInput | Code-only wrappers exist but are not adopted and lack Figma variants | Medium | Add tests/adoption where product uses them; verify/create Figma variants | Design/Dev | TBD |
| Component | Pagination (Navigation) | Partial behavior only; no first/last/ellipsis behavior | Medium | Add missing KRDS behavior before broad adoption | Dev | TBD |
| Component | Spinner (Feedback) | Figma Spinner component set not directly verified | Medium | Verify/create Figma Spinner variants when Figma MCP is available | Design | TBD |
| Component | Toast (Mobile) | Figma Toast component set not directly verified | Low | Verify/create Figma Toast variants when Figma MCP is available | Design | TBD |
| Component | Snackbar (Mobile) | No Snackbar component for feedback with action | Low | Add only when a UI needs undo/retry action | Design/Dev | TBD |
| Pattern | 신청 (Application) | No multi-step application flow | Low | N/A for current product scope | – | – |
| Accessibility | Modal | Focus trap now documented; audit others | Medium | Extend a11y docs to all dialogs | Design/Dev | TBD |
| Brand color | Color (style_02) | Figma `color/action/primary` ≠ code `#034ea2` | Medium | Reconcile Figma var to `#034ea2` | Design | TBD |

**Severity:** Critical (a11y/legal/task-blocking) · High (core comp/pattern unusable) ·
Medium (usability/consistency) · Low (docs/examples).

## 10. Final classification

**Design System Draft.** Foundation, tokens, a repo-backed component inventory,
basic/service patterns, accessibility grounding, dev mapping, and versioning all
exist and are now code-linked (Button + Spinner + Toast + High Contrast Mode).
But direct Figma verification/mutation, dark mode, several applicable
components (Snackbar, Tab, Textarea, Text Resize, Icon set), the full CSS token
layer (PR #406), adoption of code-only wrappers, and complete a11y prototypes
remain open — so it is **not yet** a fully operable "Design System."
