# Product and technical gap baseline

## 2026-08-29 — ERD handle identifier hot path

### Buyer-visible problem

Large diagrams repeatedly create source and target handle identifiers for every
rendered column. The protected `main` implementation preserves identifier safety
but materializes an intermediate array for every call through
`Array.from(...).join('-')`.

### Implemented bounded change

- replace the intermediate array with one Unicode-code-point `for...of` pass;
- preserve `c-empty`, `src-`, `tgt-`, case, punctuation, Hangul, astral emoji,
  combining marks, zero-width-joiner sequences, and lone-surrogate behavior;
- add direct predecessor-equivalence regression cases;
- add a dependency-free Node 26 benchmark command with deterministic
  counterbalanced pairs, correct even-length medians, ordered raw evidence, and
  output checksums;
- keep V8 `heapUsed` delta as diagnostic evidence only.

### Evidence status

The committed Linux x64 Node 22.16.0 artifact is supporting evidence and reports
its exact runtime. It is not release authority. The unchanged PR head must pass
the repository-required Node 26 frontend tests, typecheck, coverage, production
build, security/supply-chain checks, Strix, OpenCode review, and any required
independent approval.

### Explicitly not claimed

- no whole-browser memory reduction;
- no garbage-collection count or pause-time reduction;
- no frame-rate or end-to-end diagram-load improvement;
- no customer-scale latency envelope without a rendered large-schema benchmark.

### Next action

After merge, add a browser-level benchmark that separates identifier generation,
React rendering, layout, and paint on representative 100/500/1,000-table schemas.
Only evidence from that benchmark may justify worker, virtualization, Rust/WASM,
or rendering-architecture changes.
