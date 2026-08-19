## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2025-02-18 - Restrict DDL SQL Input
**Vulnerability:** The `ApplySqlIn` schema allowed arbitrary SQL input in its `sql` field, missing validation to ensure it was a safe, conservative PostgreSQL DDL subset. This allowed potentially dangerous SQL patterns that could lead to SQL injection.
**Learning:** Even when inputs are expected to be a specific subset, explicit regex validation must be implemented at the API boundary to prevent malicious injection, especially for fields used in database queries.
**Superseded:** The broad regex recommendation was replaced by `validate_forward_ddl`, which validates the conservative forward-DDL subset and supports multi-statement batches.

## 2025-02-18 - Restrict DDL SQL Input Properly
**Vulnerability:** The `ApplySqlIn` schema allowed arbitrary SQL input in its `sql` field at the validation level, exposing it to potential SQL injection or logic bypass before the custom executor (`validate_forward_ddl`) could process it. Relying on an oversimplified regex was incorrect and broke multi-statement support.
**Learning:** For complex inputs like SQL batches where a regex is insufficient and destructive, use Pydantic `@field_validator` to run the existing parser/validator logic directly.
**Prevention:** Rather than reinventing validation logic with a restrictive regex, use `@field_validator("sql")` on the Pydantic schema to invoke `validate_forward_ddl(v)`. Ensure any domain-specific exceptions (like `ForwardDdlValidationError`) are caught and re-raised as `ValueError` so Pydantic correctly flags them as a 422 Unprocessable Entity.
