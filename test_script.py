from dataclasses import dataclass

@dataclass
class SnowflakeRawData:
    version_rows: list[dict]
    schema_rows: list[dict]
    table_rows: list[dict]
    column_rows: list[dict]
    constraint_rows: list[dict]
