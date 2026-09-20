# Forward Engineering Capability Matrix

Status date: 2026-08-09
Verdict: current export/diff/migration/apply paths are separate partial
capabilities; governed Forward Engineering is `planned`

Symbols: `yes` means executable code exists on main for that exact column;
`partial` means material semantics are omitted or narrowed; `no` means the path
does not support it. These labels do not assert production safety.

| Construct/behavior | Snapshot capture | Full snapshot DDL export | Name-based diff | Advisory migration SQL | Deprecated apply validator | Governed target |
| --- | --- | --- | --- | --- | --- | --- |
| Schemas | yes | partial | no | create missing only | no (`SCHEMA` rejected) | Versioned support outcome |
| Tables | yes | yes | add/remove | create/drop | create only; `DROP` rejected | Structured plan with dependency/risk |
| Columns | yes | yes | add/remove/type/null | add/drop/type/null | add only; no drop/type/null change | Full typed AST and data preconditions |
| Table rename | names only | n/a | treated add/remove | drop/create consequence | rename accepted | Identity-aware explicit rename |
| Column rename | names only | n/a | treated add/remove | drop/add consequence | rename accepted | Identity-aware explicit rename |
| Primary keys | yes | yes | ordered change detected | create on new table; existing change is comment | create-table subset | Planned constraint operation |
| Foreign keys | yes | yes | add/remove | add/drop when named | rejected | Planned ordered operation |
| UNIQUE/CHECK | captured | export path support varies by source | no | no | limited create-table tokens; `CHECK` rejected | Explicit versioned support outcome |
| Defaults/identity/generated | capture varies | partial | no | no | `DEFAULT` rejected | Explicit semantic model and capability |
| Indexes/access methods | dynamic PostgreSQL capture | yes, including quoted/concurrent output where rendered | no | no | plain btree/hash columns only; no quotes/concurrently | Version/capability/risk-specific statements |
| Comments | yes | no | table comment only | table comment | comments/quoted literals rejected | Separate metadata statements and redaction |
| Views/functions/triggers/types/extensions | snapshot coverage varies | incomplete | no | no | rejected | Fail closed until individually supported |
| Partitioning/RLS/ownership/grants | metadata/output coverage varies | incomplete | no | no | rejected | Fail closed until individually supported |
| Quoted/mixed-case/Unicode identifiers | captured as values | renderer quotes | name comparison | renderer quotes | ASCII unquoted snake_case only | Preserve exact identifiers end to end |
| Compiler/model version binding | no | no | no | no | no | Required |
| Target fingerprint and drift recheck | snapshot UUID only | no | compares chosen snapshots | compares chosen snapshots | no binding | Required immediately before apply |
| Isolated real dry-run | no | no | no | no | target transaction rollback | Disposable compatible target required |
| Bound approval | no | no | no | no | no | Exact digest/target/revision/expiry required |
| Durable apply/recovery/convergence | no | no | no | no | synchronous transaction | Durable segmented job plus re-introspection |

## Authority mismatch

Frontend/full export SQL commonly quotes identifiers, foreign keys, and
`CREATE INDEX CONCURRENTLY`, but does not emit captured comments. The validator rejects comments, quoted
identifiers, foreign keys, `CONCURRENTLY`, drops, literals, and many ALTER
forms. The frontend has no apply call. Therefore "SQL can be generated" must
never be converted into "the product can safely apply its generated SQL."

## Promotion rule

A matrix cell moves to governed support only with one server-owned AST/model,
PostgreSQL-version capability classification, dependency/risk analysis,
isolated real execution, target preflight, exact approval binding, failure
recovery, and semantic round-trip tests. Unsupported constructs remain visible
and block apply; they are not silently flattened or discarded.
