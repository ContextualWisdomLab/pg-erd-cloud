from __future__ import annotations

from dataclasses import dataclass
import re


class ForwardDdlValidationError(ValueError):
    """Raised when forward-apply SQL falls outside the safe DDL subset."""


@dataclass(frozen=True)
class ForwardDdlBatch:
    """Validated SQL batch accepted by the forward-apply executor."""

    sql: str


_WORD_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|\d+|[(),.]")
_SNAKE_CASE_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
_DANGEROUS_KEYWORDS = {
    "ANALYZE",
    "CALL",
    "CHECK",
    "COPY",
    "DATABASE",
    "DELETE",
    "DO",
    "DROP",
    "EXECUTE",
    "EXTENSION",
    "FUNCTION",
    "DEFAULT",
    "GRANT",
    "INSERT",
    "LISTEN",
    "LOCK",
    "MERGE",
    "NOTIFY",
    "POLICY",
    "PROCEDURE",
    "REFRESH",
    "REVOKE",
    "ROLE",
    "RULE",
    "SCHEMA",
    "SECURITY",
    "SELECT",
    "SERVER",
    "SYSTEM",
    "TEMP",
    "TEMPORARY",
    "TRIGGER",
    "TRUNCATE",
    "UNLOGGED",
    "UPDATE",
    "USER",
    "VACUUM",
    "VIEW",
}
_TYPE_WORDS = {
    "BIGINT",
    "BOOLEAN",
    "CHAR",
    "DATE",
    "DECIMAL",
    "DOUBLE",
    "INTEGER",
    "JSONB",
    "NUMERIC",
    "PRECISION",
    "REAL",
    "SERIAL",
    "SMALLINT",
    "TEXT",
    "TIME",
    "TIMESTAMP",
    "TIMESTAMPTZ",
    "UUID",
    "VARCHAR",
    "WITH",
    "ZONE",
}
_CONSTRAINT_WORDS = {
    "CONSTRAINT",
    "KEY",
    "NOT",
    "NULL",
    "PRIMARY",
    "REFERENCES",
    "UNIQUE",
}
_CREATE_TABLE_WORDS = _TYPE_WORDS | _CONSTRAINT_WORDS | {
    "CREATE",
    "EXISTS",
    "IF",
    "NOT",
    "TABLE",
}
_ALTER_TABLE_WORDS = _TYPE_WORDS | _CONSTRAINT_WORDS | {
    "ADD",
    "ALTER",
    "COLUMN",
    "EXISTS",
    "IF",
    "RENAME",
    "TABLE",
    "TO",
}
_CREATE_INDEX_WORDS = {
    "BTREE",
    "CREATE",
    "EXISTS",
    "HASH",
    "IF",
    "INDEX",
    "NOT",
    "ON",
    "USING",
}


def validate_forward_ddl(sql: str) -> ForwardDdlBatch:
    """Return normalized SQL if it is a conservative forward-apply DDL batch.

    The forward-apply API intentionally accepts text from an editor. To keep that
    feature from becoming arbitrary SQL execution, only a small schema-evolution
    subset is allowed: create table, alter table add/rename column, and create
    index. Object identifiers must be unquoted snake_case names.
    """

    if not sql.strip():
        raise ForwardDdlValidationError("forward DDL is empty")
    if len(sql) > 262_144:
        raise ForwardDdlValidationError("forward DDL exceeds the maximum size")
    _reject_unsafe_syntax(sql)

    statements = _split_statements(sql)
    if not statements:
        raise ForwardDdlValidationError("forward DDL is empty")
    if len(statements) > 25:
        raise ForwardDdlValidationError("forward DDL may contain at most 25 statements")

    normalized: list[str] = []
    for statement in statements:
        tokens = _tokenize(statement)
        _reject_dangerous_keywords(tokens)
        head = _upper(tokens[0])
        if head == "CREATE" and len(tokens) > 1 and _upper(tokens[1]) == "TABLE":
            _validate_create_table(tokens)
        elif head == "ALTER" and len(tokens) > 1 and _upper(tokens[1]) == "TABLE":
            _validate_alter_table(tokens)
        elif head == "CREATE" and len(tokens) > 1 and _upper(tokens[1]) == "INDEX":
            _validate_create_index(tokens)
        else:
            raise ForwardDdlValidationError(
                "forward DDL allows only CREATE TABLE, ALTER TABLE, and CREATE INDEX"
            )
        normalized.append(_format_statement(tokens))

    return ForwardDdlBatch(sql=";\n".join(normalized) + ";")


def _reject_unsafe_syntax(sql: str) -> None:
    if not sql.isascii():
        raise ForwardDdlValidationError("forward DDL must use ASCII identifiers")
    if "--" in sql or "/*" in sql or "*/" in sql:
        raise ForwardDdlValidationError("comments are not allowed in forward DDL")
    if "'" in sql or '"' in sql or "$" in sql:
        raise ForwardDdlValidationError(
            "quoted literals and quoted identifiers are not allowed"
        )


def _split_statements(sql: str) -> list[str]:
    statements = [part.strip() for part in sql.split(";")]
    return [statement for statement in statements if statement]


def _tokenize(statement: str) -> list[str]:
    tokens = _WORD_RE.findall(statement)
    rendered = "".join(tokens)
    compact = re.sub(r"\s+", "", statement)
    if rendered != compact:
        raise ForwardDdlValidationError(
            "forward DDL contains unsupported punctuation or operators"
        )
    if not tokens:
        raise ForwardDdlValidationError("forward DDL statement is empty")
    return tokens


def _reject_dangerous_keywords(tokens: list[str]) -> None:
    for token in tokens:
        if token in {"(", ")", ",", "."} or token.isdigit():
            continue
        upper = _upper(token)
        if upper in _DANGEROUS_KEYWORDS:
            raise ForwardDdlValidationError(
                f"{upper} is not allowed in forward DDL"
            )


def _validate_create_table(tokens: list[str]) -> None:
    index = 2
    if _matches(tokens, index, ["IF", "NOT", "EXISTS"]):
        index += 3
    index = _parse_qualified_name(tokens, index, "table")
    if index >= len(tokens) or tokens[index] != "(":
        raise ForwardDdlValidationError("CREATE TABLE must declare columns")
    _expect_balanced_parentheses(tokens[index:])
    _validate_allowed_words(tokens, _CREATE_TABLE_WORDS, "CREATE TABLE")
    for clause in _split_top_level_commas(tokens[index + 1 : -1]):
        _validate_table_clause(clause)


def _validate_alter_table(tokens: list[str]) -> None:
    index = 2
    if _matches(tokens, index, ["IF", "EXISTS"]):
        index += 2
    index = _parse_qualified_name(tokens, index, "table")
    if index >= len(tokens):
        raise ForwardDdlValidationError("ALTER TABLE must include an action")
    _validate_allowed_words(tokens, _ALTER_TABLE_WORDS, "ALTER TABLE")
    for action in _split_top_level_commas(tokens[index:]):
        _validate_alter_table_action(action)


def _validate_create_index(tokens: list[str]) -> None:
    index = 2
    if _matches(tokens, index, ["IF", "NOT", "EXISTS"]):
        index += 3
    index = _parse_identifier(tokens, index, "index")
    if index >= len(tokens) or _upper(tokens[index]) != "ON":
        raise ForwardDdlValidationError("CREATE INDEX must specify ON table")
    index = _parse_qualified_name(tokens, index + 1, "table")
    if index < len(tokens) and _upper(tokens[index]) == "USING":
        if index + 1 >= len(tokens) or _upper(tokens[index + 1]) not in {
            "BTREE",
            "HASH",
        }:
            raise ForwardDdlValidationError("CREATE INDEX uses an unsupported method")
        index += 2
    if index >= len(tokens) or tokens[index] != "(":
        raise ForwardDdlValidationError("CREATE INDEX must list indexed columns")
    _expect_balanced_parentheses(tokens[index:])
    _validate_allowed_words(tokens, _CREATE_INDEX_WORDS, "CREATE INDEX")
    for column in _split_top_level_commas(tokens[index + 1 : -1]):
        if len(column) != 1:
            raise ForwardDdlValidationError("CREATE INDEX allows only column names")
        _parse_identifier(column, 0, "index column")


def _validate_table_clause(tokens: list[str]) -> None:
    if not tokens:
        raise ForwardDdlValidationError("CREATE TABLE contains an empty clause")
    first = _upper(tokens[0])
    if first == "CONSTRAINT":
        _parse_identifier(tokens, 1, "constraint")
        return
    if first in {"PRIMARY", "UNIQUE"}:
        return
    if first == "FOREIGN":
        raise ForwardDdlValidationError(f"{first} constraints are not supported")
    _parse_identifier(tokens, 0, "column")


def _validate_alter_table_action(tokens: list[str]) -> None:
    if not tokens:
        raise ForwardDdlValidationError("ALTER TABLE contains an empty action")
    first = _upper(tokens[0])
    if first == "ADD":
        index = 1
        if index < len(tokens) and _upper(tokens[index]) == "COLUMN":
            index += 1
        _parse_identifier(tokens, index, "column")
        return
    if first == "RENAME":
        if _matches(tokens, 1, ["COLUMN"]):
            after_old = _parse_identifier(tokens, 2, "column")
            if after_old >= len(tokens) or _upper(tokens[after_old]) != "TO":
                raise ForwardDdlValidationError("RENAME COLUMN must include TO")
            end = _parse_identifier(tokens, after_old + 1, "column")
            if end != len(tokens):
                raise ForwardDdlValidationError("RENAME COLUMN has trailing tokens")
            return
        if _matches(tokens, 1, ["TO"]):
            end = _parse_identifier(tokens, 2, "table")
            if end != len(tokens):
                raise ForwardDdlValidationError("RENAME TO has trailing tokens")
            return
    raise ForwardDdlValidationError(
        "ALTER TABLE allows only ADD COLUMN and RENAME actions"
    )


def _validate_allowed_words(
    tokens: list[str], allowed_words: set[str], statement_kind: str
) -> None:
    for token in tokens:
        if token in {"(", ")", ",", "."} or token.isdigit():
            continue
        upper = _upper(token)
        if upper not in allowed_words and not _SNAKE_CASE_RE.fullmatch(token):
            raise ForwardDdlValidationError(
                f"{statement_kind} contains unsupported token: {token}"
            )


def _parse_qualified_name(tokens: list[str], index: int, kind: str) -> int:
    index = _parse_identifier(tokens, index, kind)
    if index < len(tokens) and tokens[index] == ".":
        return _parse_identifier(tokens, index + 1, kind)
    return index


def _parse_identifier(tokens: list[str], index: int, kind: str) -> int:
    if index >= len(tokens):
        raise ForwardDdlValidationError(f"missing {kind} identifier")
    token = tokens[index]
    if not _SNAKE_CASE_RE.fullmatch(token):
        raise ForwardDdlValidationError(
            f"{kind} identifier must be unquoted snake_case: {token}"
        )
    return index + 1


def _expect_balanced_parentheses(tokens: list[str]) -> None:
    depth = 0
    for token in tokens:
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
            if depth < 0:
                break
    if depth != 0:
        raise ForwardDdlValidationError("parentheses are not balanced")


def _split_top_level_commas(tokens: list[str]) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    depth = 0
    for token in tokens:
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        if token == "," and depth == 0:
            chunks.append(current)
            current = []
        else:
            current.append(token)
    chunks.append(current)
    return chunks


def _matches(tokens: list[str], index: int, expected: list[str]) -> bool:
    if index + len(expected) > len(tokens):
        return False
    return (
        [_upper(token) for token in tokens[index : index + len(expected)]] == expected
    )


def _upper(token: str) -> str:
    return token.upper()


def _format_statement(tokens: list[str]) -> str:
    sql = ""
    no_space_before = {")", ",", "."}
    no_space_after = {"(", "."}
    for token in tokens:
        if sql and token not in no_space_before and sql[-1] not in no_space_after:
            sql += " "
        sql += token
    return sql
