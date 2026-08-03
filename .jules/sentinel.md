## 2025-02-18 - Hardening Pydantic String Fields Against Control Characters
**Vulnerability:** User-provided string fields (like project and connection names) lacked strict validation against control characters, only relying on length constraints.
**Learning:** This could potentially lead to Log Injection (CRLF injection), Null Byte Injection, or terminal escape injection if these strings are subsequently logged or rendered directly.
**Prevention:** Use explicit regex validation `pattern=r'^[^\x00-\x1F\x7F]+$'` on Pydantic string fields to strictly reject control characters.

## 2024-08-03 - Fix Shell injection in GitHub Actions workflow
**Vulnerability:** Shell injection in GitHub Actions `run` steps when using `${{ inputs.variable }}` string interpolation directly inside the bash script block.
**Learning:** GitHub Actions contexts can contain arbitrary user input, and string interpolation into a `run` step is vulnerable to injection if the input contains shell metacharacters (e.g. `"; ls"`).
**Prevention:** Pass context variables (like `inputs` or `github.event.pull_request.title`) into a `run` script via the `env:` map and read them as bash environment variables (e.g., `COUNT: ${{ inputs.commit_count }}` and reading `$COUNT`).
