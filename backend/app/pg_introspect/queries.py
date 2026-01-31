from __future__ import annotations


SCHEMAS_SQL = """
WITH params AS (
  SELECT $1::text AS schema_name, COALESCE($2::boolean, false) AS include_system
)
SELECT
  n.oid AS schema_oid,
  n.nspname AS schema_name
FROM pg_catalog.pg_namespace n
CROSS JOIN params p
WHERE
  (p.schema_name IS NULL OR n.nspname = p.schema_name)
  AND (
    p.include_system
    OR (
      n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND n.nspname NOT LIKE 'pg_toast%'
      AND n.nspname NOT LIKE 'pg_temp_%'
      AND n.nspname NOT LIKE 'pg_toast_temp_%'
    )
  )
ORDER BY n.nspname;
"""


RELATIONS_SQL = """
WITH params AS (
  SELECT $1::text AS schema_name, COALESCE($2::boolean, false) AS include_system
)
SELECT
  n.nspname AS schema_name,
  c.oid AS relation_oid,
  c.relname AS relation_name,
  c.relkind::text AS relation_kind,
  c.relispartition AS is_partition
FROM pg_catalog.pg_class c
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
CROSS JOIN params p
WHERE
  c.relkind IN ('r','p','v','m')
  AND (p.schema_name IS NULL OR n.nspname = p.schema_name)
  AND (
    p.include_system
    OR (
      n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND n.nspname NOT LIKE 'pg_toast%'
      AND n.nspname NOT LIKE 'pg_temp_%'
      AND n.nspname NOT LIKE 'pg_toast_temp_%'
    )
  )
ORDER BY n.nspname, c.relkind, c.relname;
"""


COLUMNS_SQL = """
WITH params AS (
  SELECT $1::text AS schema_name, COALESCE($2::boolean, false) AS include_system
)
SELECT
  n.nspname AS schema_name,
  c.oid AS relation_oid,
  c.relname AS relation_name,
  c.relkind::text AS relation_kind,
  a.attnum AS column_position,
  a.attname AS column_name,
  pg_catalog.format_type(a.atttypid, a.atttypmod) AS data_type,
  a.attnotnull AS is_not_null,
  a.atthasdef AS has_default,
  pg_catalog.pg_get_expr(ad.adbin, ad.adrelid) AS default_expr,
  pg_catalog.col_description(a.attrelid, a.attnum) AS column_comment
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
LEFT JOIN pg_catalog.pg_attrdef ad ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
CROSS JOIN params p
WHERE
  c.relkind IN ('r','p','v','m')
  AND a.attnum > 0
  AND NOT a.attisdropped
  AND (p.schema_name IS NULL OR n.nspname = p.schema_name)
  AND (
    p.include_system
    OR (
      n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND n.nspname NOT LIKE 'pg_toast%'
      AND n.nspname NOT LIKE 'pg_temp_%'
      AND n.nspname NOT LIKE 'pg_toast_temp_%'
    )
  )
ORDER BY n.nspname, c.relname, a.attnum;
"""


CONSTRAINTS_SQL = """
WITH params AS (
  SELECT $1::text AS schema_name, COALESCE($2::boolean, false) AS include_system
)
SELECT
  con.oid AS constraint_oid,
  con.conname AS constraint_name,
  con.contype::text AS constraint_type,
  n.nspname AS schema_name,
  rel.oid AS relation_oid,
  rel.relname AS relation_name,
  frel.oid AS foreign_relation_oid,
  fn.nspname AS foreign_schema_name,
  frel.relname AS foreign_relation_name,
  con.conkey AS constrained_attnums,
  con.confkey AS referenced_attnums,
  con.confupdtype::text AS fk_on_update,
  con.confdeltype::text AS fk_on_delete,
  con.confmatchtype::text AS fk_match_type,
  pg_catalog.pg_get_constraintdef(con.oid, true) AS constraint_def,
  pg_catalog.pg_get_expr(con.conbin, con.conrelid) AS check_expr
FROM pg_catalog.pg_constraint con
JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
JOIN pg_catalog.pg_namespace n ON n.oid = rel.relnamespace
LEFT JOIN pg_catalog.pg_class frel ON frel.oid = con.confrelid
LEFT JOIN pg_catalog.pg_namespace fn ON fn.oid = frel.relnamespace
CROSS JOIN params p
WHERE
  con.contype IN ('p','f','u','c')
  AND (p.schema_name IS NULL OR n.nspname = p.schema_name)
  AND (
    p.include_system
    OR (
      n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND n.nspname NOT LIKE 'pg_toast%'
      AND n.nspname NOT LIKE 'pg_temp_%'
      AND n.nspname NOT LIKE 'pg_toast_temp_%'
    )
  )
ORDER BY n.nspname, rel.relname, con.conname;
"""


INDEXES_SQL = """
WITH params AS (
  SELECT $1::text AS schema_name, COALESCE($2::boolean, false) AS include_system
)
SELECT
  idx.oid AS index_oid,
  idx_ns.nspname AS index_schema_name,
  idx.relname AS index_name,

  tbl.oid AS table_oid,
  tbl_ns.nspname AS table_schema_name,
  tbl.relname AS table_name,

  am.amname AS access_method,
  ix.indisunique AS is_unique,
  ix.indisprimary AS is_primary,
  ix.indisvalid AS is_valid,

  pg_catalog.pg_get_expr(ix.indpred, ix.indrelid) AS predicate_expr,
  pg_catalog.pg_get_indexdef(idx.oid) AS index_def
FROM pg_catalog.pg_index ix
JOIN pg_catalog.pg_class idx ON idx.oid = ix.indexrelid
JOIN pg_catalog.pg_namespace idx_ns ON idx_ns.oid = idx.relnamespace
JOIN pg_catalog.pg_class tbl ON tbl.oid = ix.indrelid
JOIN pg_catalog.pg_namespace tbl_ns ON tbl_ns.oid = tbl.relnamespace
JOIN pg_catalog.pg_am am ON am.oid = idx.relam
CROSS JOIN params p
WHERE
  tbl.relkind IN ('r','p','m')
  AND (p.schema_name IS NULL OR tbl_ns.nspname = p.schema_name)
  AND (
    p.include_system
    OR (
      tbl_ns.nspname NOT IN ('pg_catalog', 'information_schema')
      AND tbl_ns.nspname NOT LIKE 'pg_toast%'
      AND tbl_ns.nspname NOT LIKE 'pg_temp_%'
      AND tbl_ns.nspname NOT LIKE 'pg_toast_temp_%'
    )
  )
ORDER BY tbl_ns.nspname, tbl.relname, idx.relname;
"""
