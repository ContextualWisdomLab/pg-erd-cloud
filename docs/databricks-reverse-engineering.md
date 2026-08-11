# Databricks reverse engineering

Status: **Partial**

This integration captures a bounded, read-only Unity Catalog snapshot through a
Databricks SQL warehouse. It does not create browser or server authority to run
arbitrary SQL, and it does not implement Databricks forward apply.

## Implemented contract

- A strict `databricks://` DSN carries the access token in password userinfo so
  the shared DSN error boundary can redact it. Only `catalog` and `schema` query
  parameters are accepted.
- The workspace hostname is validated by the shared SSRF guard before the
  optional connector opens HTTPS port 443.
- The server executes only fixed queries against the selected catalog's
  `information_schema` relations.
- Metadata result sets disable connector cloud fetch, avoiding an additional
  object-storage egress path.
- Catalog schemas, tables, views, columns, defaults, comments, and
  primary/unique/foreign-key metadata are mapped into the common snapshot shape
  with stable synthetic relation and constraint identifiers.
- Unity Catalog key constraints are informational rather than enforced. The
  snapshot preserves the reported enforcement and deferrability flags instead
  of presenting relationships as database-enforced guarantees.
- The snapshot records exact capability states. Traditional indexes and CHECK
  constraints are `unsupported`; Unity Catalog is `required`; key constraints
  are `preview`.

Example (placeholders only; never commit a real token):

```text
databricks://token:<access-token>@<workspace-host>/sql/1.0/warehouses/<warehouse-id>?catalog=main&schema=default
```

## Fail-closed boundaries

- Missing credentials, a non-443 port, a non-warehouse HTTP path, blank,
  duplicate, or unknown query parameters, and a missing catalog are rejected
  before connection.
- Unity Catalog privilege filtering applies to every returned row. A successful
  snapshot proves only the metadata visible to that principal; it is not proof
  that inaccessible objects do not exist.
- Constraint introspection is intentionally mandatory for this slice. A runtime
  where the Preview constraint relations are unavailable fails the snapshot
  instead of silently producing an apparently complete relationship model.
- DDL export and snapshot migration reject Databricks snapshots with HTTP 422;
  the API does not emit guessed SQL or convert the unsupported capability into
  an internal server error.
- Connection and query errors cross the existing DSN-redaction boundary. Tokens
  and full DSNs must never be logged.

## Planned

- OAuth machine-to-machine credentials sourced from the repository's planned
  credential registry rather than static personal access tokens.
- Real ephemeral Databricks SQL / Unity Catalog integration evidence across
  supported runtimes and privilege profiles.
- Explicit completeness evidence for privilege-filtered catalogs and accessible
  browser E2E for connection, snapshot, diagram review, and recovery.
- Databricks-specific type mapping and export policy. Forward apply remains
  rejected until a separate deterministic planner, preflight, approval, drift,
  recovery, and convergence contract is implemented.

## Primary references

- Databricks. (2026). *Databricks SQL Connector for Python*.
  <https://docs.databricks.com/aws/en/dev-tools/python-sql-connector>
- Databricks. (2026). *Information schema*.
  <https://docs.databricks.com/aws/en/sql/language-manual/information-schema/>
- Databricks. (2026). *KEY_COLUMN_USAGE* (Public Preview; Unity Catalog only).
  <https://docs.databricks.com/aws/en/sql/language-manual/information-schema/key_column_usage>
- Databricks. (2026). *REFERENTIAL_CONSTRAINTS* (Public Preview; Unity Catalog
  only).
  <https://docs.databricks.com/aws/en/sql/language-manual/information-schema/referential_constraints>
- Databricks. (2026). *databricks-sql-connector 4.4.0* (released July 22,
  2026). <https://pypi.org/project/databricks-sql-connector/>
