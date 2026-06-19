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
  typ.oid AS type_oid,
  typ_ns.nspname AS type_schema,
  typ.typname AS type_name,
  typ.typtype::text AS type_kind,
  typ.typcategory::text AS type_category,
  CASE
    WHEN typ.typtype = 'd'
    THEN pg_catalog.format_type(typ.typbasetype, typ.typtypmod)
    ELSE NULL
  END AS domain_base_type,
  base_typ_ns.nspname AS domain_base_schema,
  base_typ.typname AS domain_base_name,
  CASE
    WHEN typ.typcategory = 'A'
    THEN pg_catalog.format_type(typ.typelem, -1)
    ELSE NULL
  END AS array_element_type,
  elem_typ_ns.nspname AS array_element_schema,
  elem_typ.typname AS array_element_name,
  a.attndims AS array_dimensions,
  a.attnotnull AS is_not_null,
  a.atthasdef AS has_default,
  pg_catalog.pg_get_expr(ad.adbin, ad.adrelid) AS default_expr,
  pg_catalog.col_description(a.attrelid, a.attnum) AS column_comment
FROM pg_catalog.pg_attribute a
JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
JOIN pg_catalog.pg_type typ ON typ.oid = a.atttypid
JOIN pg_catalog.pg_namespace typ_ns ON typ_ns.oid = typ.typnamespace
LEFT JOIN pg_catalog.pg_type base_typ
  ON base_typ.oid = typ.typbasetype AND typ.typtype = 'd'
LEFT JOIN pg_catalog.pg_namespace base_typ_ns
  ON base_typ_ns.oid = base_typ.typnamespace
LEFT JOIN pg_catalog.pg_type elem_typ
  ON elem_typ.oid = typ.typelem AND typ.typcategory = 'A'
LEFT JOIN pg_catalog.pg_namespace elem_typ_ns
  ON elem_typ_ns.oid = elem_typ.typnamespace
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

  tbl.oid AS relation_oid,
  tbl.oid AS table_oid,
  tbl_ns.nspname AS table_schema_name,
  tbl.relname AS table_name,

  am.amname AS access_method,
  am_ext.extname AS access_method_extension,
  COALESCE(opclasses.operator_classes, ARRAY[]::text[]) AS operator_classes,
  COALESCE(opclasses.operator_class_extensions, ARRAY[]::text[]) AS operator_class_extensions,
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
LEFT JOIN LATERAL (
  SELECT ext.extname
  FROM pg_catalog.pg_depend dep
  JOIN pg_catalog.pg_extension ext ON ext.oid = dep.refobjid
  WHERE
    dep.classid = 'pg_catalog.pg_am'::regclass
    AND dep.objid = am.oid
    AND dep.refclassid = 'pg_catalog.pg_extension'::regclass
    AND dep.deptype = 'e'
  ORDER BY ext.extname
  LIMIT 1
) am_ext ON true
LEFT JOIN LATERAL (
  SELECT
    array_agg(opc_ns.nspname || '.' || opc.opcname ORDER BY cls.ordinality) AS operator_classes,
    COALESCE(
      array_agg(DISTINCT ext.extname ORDER BY ext.extname) FILTER (WHERE ext.extname IS NOT NULL),
      ARRAY[]::text[]
    ) AS operator_class_extensions
  FROM unnest(ix.indclass) WITH ORDINALITY AS cls(opclass_oid, ordinality)
  JOIN pg_catalog.pg_opclass opc ON opc.oid = cls.opclass_oid
  JOIN pg_catalog.pg_namespace opc_ns ON opc_ns.oid = opc.opcnamespace
  LEFT JOIN pg_catalog.pg_depend dep
    ON dep.classid = 'pg_catalog.pg_opclass'::regclass
    AND dep.objid = opc.oid
    AND dep.refclassid = 'pg_catalog.pg_extension'::regclass
    AND dep.deptype = 'e'
  LEFT JOIN pg_catalog.pg_extension ext ON ext.oid = dep.refobjid
) opclasses ON true
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


PK_COLUMNS_SQL = """
WITH params AS (
  SELECT $1::text AS schema_name, COALESCE($2::boolean, false) AS include_system
), pk AS (
  SELECT con.*
  FROM pg_catalog.pg_constraint con
  JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
  JOIN pg_catalog.pg_namespace n ON n.oid = rel.relnamespace
  CROSS JOIN params p
  WHERE
    con.contype = 'p'
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
)
SELECT
  con.oid AS constraint_oid,
  con.conname AS constraint_name,
  n.nspname AS schema_name,
  rel.oid AS relation_oid,
  rel.relname AS relation_name,
  k.ordinality AS column_ordinal,
  a.attname AS column_name
FROM pk con
JOIN pg_catalog.pg_class rel ON rel.oid = con.conrelid
JOIN pg_catalog.pg_namespace n ON n.oid = rel.relnamespace
JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS k(attnum, ordinality) ON true
JOIN pg_catalog.pg_attribute a ON a.attrelid = con.conrelid AND a.attnum = k.attnum
ORDER BY n.nspname, rel.relname, con.conname, k.ordinality;
"""


FK_EDGES_SQL = """
WITH params AS (
  SELECT $1::text AS schema_name, COALESCE($2::boolean, false) AS include_system
), fk AS (
  SELECT con.*
  FROM pg_catalog.pg_constraint con
  JOIN pg_catalog.pg_class child_rel ON child_rel.oid = con.conrelid
  JOIN pg_catalog.pg_namespace child_ns ON child_ns.oid = child_rel.relnamespace
  CROSS JOIN params p
  WHERE
    con.contype = 'f'
    AND (p.schema_name IS NULL OR child_ns.nspname = p.schema_name)
    AND (
      p.include_system
      OR (
        child_ns.nspname NOT IN ('pg_catalog', 'information_schema')
        AND child_ns.nspname NOT LIKE 'pg_toast%'
        AND child_ns.nspname NOT LIKE 'pg_temp_%'
        AND child_ns.nspname NOT LIKE 'pg_toast_temp_%'
      )
    )
)
SELECT
  con.oid AS fk_constraint_oid,
  con.conname AS fk_constraint_name,

  child_ns.nspname AS child_schema_name,
  child_rel.oid AS child_relation_oid,
  child_rel.relname AS child_relation_name,

  parent_ns.nspname AS parent_schema_name,
  parent_rel.oid AS parent_relation_oid,
  parent_rel.relname AS parent_relation_name,

  map.ordinality AS column_ordinal,
  child_att.attname AS child_column_name,
  parent_att.attname AS parent_column_name,

  con.confupdtype::text AS fk_on_update,
  con.confdeltype::text AS fk_on_delete,
  con.confmatchtype::text AS fk_match_type
FROM fk con
JOIN pg_catalog.pg_class child_rel ON child_rel.oid = con.conrelid
JOIN pg_catalog.pg_namespace child_ns ON child_ns.oid = child_rel.relnamespace
JOIN pg_catalog.pg_class parent_rel ON parent_rel.oid = con.confrelid
JOIN pg_catalog.pg_namespace parent_ns ON parent_ns.oid = parent_rel.relnamespace
JOIN LATERAL (
  SELECT ck.attnum AS child_attnum, fk.attnum AS parent_attnum, ck.ord AS ordinality
  FROM unnest(con.conkey) WITH ORDINALITY AS ck(attnum, ord)
  JOIN unnest(con.confkey) WITH ORDINALITY AS fk(attnum, ord) USING (ord)
) AS map ON true
JOIN pg_catalog.pg_attribute child_att
  ON child_att.attrelid = con.conrelid AND child_att.attnum = map.child_attnum
JOIN pg_catalog.pg_attribute parent_att
  ON parent_att.attrelid = con.confrelid AND parent_att.attnum = map.parent_attnum
ORDER BY child_schema_name, child_relation_name, fk_constraint_name, column_ordinal;
"""
