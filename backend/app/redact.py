import copy
from typing import Any, Dict


def redact_sensitive_schema_data(snapshot_json: Dict[str, Any] | None) -> Dict[str, Any] | None:
    """Redacts sensitive properties like comments or example values from snapshot data."""
    if not snapshot_json:
        return snapshot_json

    redacted = copy.deepcopy(snapshot_json)

    if "tables" in redacted and isinstance(redacted["tables"], list):
        for table in redacted["tables"]:
            if "comment" in table and table["comment"] is not None:
                table["comment"] = "[REDACTED]"

            if "columns" in table and isinstance(table["columns"], list):
                for column in table["columns"]:
                    if "column_comment" in column and column["column_comment"] is not None:
                        column["column_comment"] = "[REDACTED]"
                    if "example_value" in column and column["example_value"] is not None:
                        column["example_value"] = "[REDACTED]"

    return redacted
