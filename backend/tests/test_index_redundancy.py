from __future__ import annotations

from app.spec.index_redundancy import _index_columns, detect_index_redundancy


def _snap(index_defs, unique=None):
    """index_defs: {index_name: 'col1, col2'} on one table 'orders'."""
    unique = unique or set()
    return {
        "relations": [{"relation_oid": 1, "schema_name": "public", "relation_name": "orders"}],
        "indexes": [
            {
                "relation_oid": 1,
                "index_name": name,
                "is_unique": name in unique,
                "index_def": f"CREATE INDEX {name} ON public.orders USING btree ({cols})",
            }
            for name, cols in index_defs.items()
        ],
    }


def _cats(report):
    return {(i["category"], i["index"]) for i in report["items"]}


def test_detects_exact_duplicate():
    report = detect_index_redundancy(_snap({"ix_a": "member_id", "ix_b": "member_id"}))
    assert report["summary"]["duplicates"] == 1
    dup = report["items"][0]
    assert dup["severity"] == "warning" and dup["columns"] == ["member_id"]


def test_duplicate_keeps_the_unique_one():
    report = detect_index_redundancy(
        _snap({"uq_a": "email", "ix_b": "email"}, unique={"uq_a"})
    )
    dup = report["items"][0]
    assert dup["index"] == "ix_b" and dup["kept"] == "uq_a"


def test_detects_prefix_redundancy_but_not_unique_prefix():
    # ix_short(member_id) is a prefix of ix_long(member_id, created_at)
    report = detect_index_redundancy(
        _snap({"ix_short": "member_id", "ix_long": "member_id, created_at"})
    )
    assert ("prefix_redundant_index", "ix_short") in _cats(report)

    # but a UNIQUE index is a constraint — never suggested for dropping
    report2 = detect_index_redundancy(
        _snap({"uq_short": "member_id", "ix_long": "member_id, created_at"}, unique={"uq_short"})
    )
    assert report2["items"] == []


def test_different_columns_and_unparseable_defs_are_skipped():
    report = detect_index_redundancy(_snap({"ix_a": "member_id", "ix_b": "created_at"}))
    assert report["items"] == []
    # expression + partial indexes are skipped, not guessed
    snap = _snap({"ix_a": "member_id"})
    snap["indexes"].append({"relation_oid": 1, "index_name": "ix_expr",
                            "index_def": "CREATE INDEX ix_expr ON public.orders (lower(email))"})
    snap["indexes"].append({"relation_oid": 1, "index_name": "ix_part",
                            "index_def": "CREATE INDEX ix_part ON public.orders (member_id) WHERE deleted_at IS NULL"})
    assert detect_index_redundancy(snap)["items"] == []
    assert detect_index_redundancy({})["summary"]["total"] == 0


def test_functional_index_is_not_flagged_as_duplicate_of_a_plain_index():
    # A plain (email) index and a functional (lower(email)) index are DIFFERENT
    # indexes serving different queries. The parser must skip the expression
    # index rather than mis-read its inner argument as a plain 'email' column and
    # advise dropping a genuinely-needed index (the harmful false positive the
    # module docstring promises to avoid).
    snap = _snap({"ix_email": "email"})
    snap["indexes"].append(
        {
            "relation_oid": 1,
            "index_name": "ix_lower_email",
            "index_def": (
                "CREATE INDEX ix_lower_email ON public.orders "
                "USING btree (lower(email))"
            ),
        }
    )
    assert detect_index_redundancy(snap)["items"] == []


def test_index_columns_skips_expression_indexes_including_multi_column():
    # Balanced-paren parse: a nested '(' anywhere in the column list marks an
    # expression index, which is not comparable and must yield []. A multi-column
    # list mixing a plain column with an expression must NOT silently drop the
    # plain column and mis-report the expression as a column.
    assert _index_columns("CREATE INDEX i ON t USING btree (lower(email))") == []
    assert _index_columns("CREATE INDEX i ON t USING btree (a, lower(b))") == []
    assert _index_columns("CREATE INDEX i ON t USING btree (lower((email)::text))") == []
    # Plain / opclass / DESC lists still parse to their leading column tokens.
    assert _index_columns("CREATE INDEX i ON t USING btree (email)") == ["email"]
    assert _index_columns("CREATE INDEX i ON t (member_id, org_id)") == [
        "member_id",
        "org_id",
    ]
    assert _index_columns("CREATE INDEX i ON t USING gin (col gin_trgm_ops)") == ["col"]


def test_index_columns_ignores_parens_inside_quoted_identifiers():
    # A double-quoted identifier may legally contain parentheses. The scan must
    # skip quoted names so it locks onto the real column-list '(...)', not a '('
    # buried in the name — otherwise a genuinely-needed index gets mis-parsed and
    # wrongly advised for dropping (the harmful false positive this module avoids).
    assert _index_columns('CREATE INDEX "ix(foo)" ON t (email)') == ["email"]
    # A doubled "" is SQL's escape for a literal quote inside the identifier.
    assert _index_columns('CREATE INDEX "weird""(name)" ON t (a, b)') == ["a", "b"]
    # A quoted schema/table with parens must likewise be skipped.
    assert _index_columns('CREATE INDEX ix ON "my(schema)".orders (member_id)') == [
        "member_id",
    ]
    # An unterminated quote yields no comparable column list rather than crashing.
    assert _index_columns('CREATE INDEX "unterminated ON t (email)') == []
