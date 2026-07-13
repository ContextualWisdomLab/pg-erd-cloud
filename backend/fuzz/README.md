# Fuzzing

Coverage-guided and property-based fuzzing for pg-erd-cloud's untrusted-input
surfaces. All targets are **pure, deterministic, network-free** functions that
consume attacker-influenced data (connection strings, driver error messages, and
DB-introspection *snapshots* that may originate from a hostile database).

## Tools & licenses (permissive only)

| Tool | License | Role |
| --- | --- | --- |
| [Atheris](https://github.com/google/atheris) | Apache-2.0 | coverage-guided (libFuzzer) harnesses in `backend/fuzz/` |
| [Hypothesis](https://github.com/HypothesisWorks/hypothesis) | MPL-2.0 | property tests in `backend/tests/test_fuzz_properties.py` |

Neither is GPL/AGPL. Hypothesis is **not** in the pinned runtime/dev lock, so
`test_fuzz_properties.py` is `importorskip`-guarded and is skipped by the normal
hash-locked `pytest` job unless Hypothesis is installed locally.

## Targets (surfaced with CodeGraph)

Discovered via `codegraph init` + `codegraph explore` on the fresh clone:

| Harness | Target | Untrusted input | Invariant |
| --- | --- | --- | --- |
| `fuzz_dsn_redaction.py` | `app.dsn_redaction.redact_dsn_error_message` | driver error text + DSN | no crash; **DSN password never leaks verbatim** |
| `fuzz_dsn_guard.py` | `app.pg_introspect.dsn_guard` parse helpers | DSN query/host/port/IP | only `DsnTargetError` raised; IP parsing total |
| `fuzz_ddl_export.py` | `app.ddl.export.snapshot_json_to_sql` | schema snapshot + dialect | no crash (bad dialect → `ValueError` only); deterministic |
| `fuzz_spec_generators.py` | `app.spec.reversing` / `index_design` / `naming_lint` / `wide_tables` | schema snapshot | no crash; deterministic; report summary counts self-consistent |

`_snapshot.py` turns fuzzer bytes into snapshot-shaped dicts (the keys/value
types the generators branch on) so the fuzzer spends its budget on structure.

## Run locally

Atheris ships wheels for CPython 3.10–3.12 (Linux/macOS):

```bash
cd backend
python -m pip install atheris hypothesis
export PYTHONPATH=.

# Coverage-guided, time-bounded:
python fuzz/fuzz_dsn_redaction.py   -max_total_time=60 fuzz/corpus/dsn_redaction
python fuzz/fuzz_dsn_guard.py       -max_total_time=60 fuzz/corpus/dsn_guard
python fuzz/fuzz_ddl_export.py      -max_total_time=60 fuzz/corpus/ddl_export
python fuzz/fuzz_spec_generators.py -max_total_time=60 fuzz/corpus/reversing_spec

# Property-based (portable, no native build):
pytest tests/test_fuzz_properties.py -q
```

A crash writes a `crash-*` reproducer; re-run the harness with that file as the
sole argument to replay it.

## CI

The existing backend CI installs from `requirements-dev.lock` with
`--require-hashes` and runs `pytest -q`. The Hypothesis suite is skipped there
unless Hypothesis is added to that hash-locked dev set; the Atheris harnesses are
manual, bounded checks for security/robustness investigations.

## Findings

The initial harness run hardened four latent robustness bugs (see the PR):
unbounded recursion on a domain-typed column in the Snowflake export, and three
snapshot generators crashing on a non-list top-level key. Regression coverage
now lives in these fuzz targets.
