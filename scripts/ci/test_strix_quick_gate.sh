#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(
	CDPATH=''
	cd -P -- "$(dirname -- "$0")"
	pwd -P
)"
REPO_ROOT="$(
	CDPATH=''
	cd -P -- "$SCRIPT_DIR/../.."
	pwd -P
)"
GATE_SCRIPT="$REPO_ROOT/scripts/ci/strix_quick_gate.sh"

FAILURES=0

record_failure() {
	echo "FAIL: $1" >&2
	FAILURES=$((FAILURES + 1))
}

assert_equals() {
	local expected="$1"
	local actual="$2"
	local message="$3"

	if [ "$expected" != "$actual" ]; then
		record_failure "$message (expected='$expected' actual='$actual')"
	fi
}

assert_file_contains() {
	local file_path="$1"
	local needle="$2"
	local message="$3"

	if ! grep -Fq -- "$needle" "$file_path"; then
		record_failure "$message (missing '$needle')"
	fi
}

assert_file_matches() {
	local file_path="$1"
	local pattern="$2"
	local message="$3"

	if ! grep -Eq -- "$pattern" "$file_path"; then
		record_failure "$message (missing pattern '$pattern')"
	fi
}

assert_file_not_contains() {
	local file_path="$1"
	local needle="$2"
	local message="$3"

	if grep -Fq -- "$needle" "$file_path"; then
		record_failure "$message (unexpected '$needle')"
	fi
}

assert_workflow_uses_are_sha_pinned() {
	local workflow_file="$1"
	local message="$2"
	local line_number
	local line_text
	local uses_ref

	while IFS=: read -r line_number line_text; do
		uses_ref="$(
			printf '%s\n' "$line_text" |
				sed -E 's/^[[:space:]]*uses:[[:space:]]*([^[:space:]#]+).*/\1/'
		)"
		if ! printf '%s\n' "$line_text" |
			grep -Eq '^[[:space:]]*uses:[[:space:]]+[^[:space:]#]+@[0-9a-fA-F]{40}[[:space:]]+# v[0-9]+([.][0-9]+)*([[:space:]]|$)'; then
			record_failure "$message must pin uses refs to full commit SHAs with trailing version comments at line $line_number: $uses_ref"
		fi
	done < <(grep -nE '^[[:space:]]+uses:[[:space:]]+' "$workflow_file" || true)
}

assert_strix_pr_scope_includes_deployment_context() {
	assert_file_contains "$GATE_SCRIPT" "needs_deployment_context=0" "strix gate tracks deployment-context scoped PRs"
	assert_file_contains "$GATE_SCRIPT" ".github/workflows/* | Dockerfile | frontend/Dockerfile | frontend/next.config.ts | docker-compose*.yml | render.yaml" "strix gate recognizes deployment and CI files"
	assert_file_contains "$GATE_SCRIPT" "Dockerfile | */Dockerfile | Containerfile | */Containerfile | Makefile | */Makefile" "strix gate treats extensionless deployment files as source files"
	assert_file_contains "$GATE_SCRIPT" "backend/scripts/docker_entrypoint.sh" "strix gate includes the combined Docker image entrypoint with deployment context"
	assert_file_contains "$GATE_SCRIPT" "backend/api/auth.py" "strix gate includes backend auth context for deployment scans"
	assert_file_contains "$GATE_SCRIPT" "frontend/package-lock.json" "strix gate includes frontend dependency lock context"
	assert_file_contains "$GATE_SCRIPT" "frontend/postcss.config.mjs" "strix gate includes frontend build config context"
	assert_file_contains "$GATE_SCRIPT" "VERSION" "strix gate includes release version context for workflow scans"
	assert_file_contains "$GATE_SCRIPT" "scripts/ci/test_*.sh" "strix gate excludes large CI self-test harnesses from PR scan targets"
}

assert_strix_workflow_pr_trigger_hardened() {
	local workflow_file="$REPO_ROOT/.github/workflows/strix.yml"

	assert_file_contains "$workflow_file" "branches: [main, develop, master]" "strix workflow scans GitHub Flow and Git Flow protected branches"
	assert_file_contains "$workflow_file" "pull_request_target:" "strix workflow uses trusted PR trigger"
	assert_file_contains "$workflow_file" "format('pr-{0}', github.event.pull_request.number)" "strix workflow scopes concurrency to the active pull request"
	assert_file_contains "$workflow_file" "format('pr-{0}', github.event.inputs.pr_number)" "strix workflow scopes manual PR evidence concurrency to the requested pull request"
	assert_file_contains "$workflow_file" "|| github.ref" "strix workflow scopes non-PR concurrency to the current ref"
	assert_file_contains "$workflow_file" "cancel-in-progress: false" "strix workflow never cancels in-progress security evidence"
	assert_file_contains "$workflow_file" "models: read" "strix workflow grants only the GitHub Models read permission needed for Strix"
	assert_file_contains "$workflow_file" "actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6" "strix workflow pins actions/setup-python"
	assert_file_contains "$workflow_file" 'python-version: "3.13"' "strix workflow runs Python steps on Python 3.13"
	assert_file_contains "$workflow_file" "Materialize trusted workspace" "strix workflow materializes trusted workspace"
	assert_file_contains "$workflow_file" "TRUSTED_WORKSPACE_SHA" "strix workflow pins trusted workspace SHA"
	assert_file_contains "$workflow_file" "TRUSTED_WORKSPACE=\$trusted_workspace" "strix workflow exports a trusted workspace path"
	assert_file_contains "$workflow_file" "git -C \"\$TRUSTED_WORKSPACE\"" "strix workflow runs git only inside trusted workspace"
	assert_file_contains "$workflow_file" 'working-directory: ${{ runner.temp }}/trusted-workspace' "strix workflow executes privileged steps from the trusted workspace"
	assert_file_contains "$workflow_file" "bash \"\$TRUSTED_STRIX_GATE_TEST\"" "strix workflow self-test executes trusted temp script"
	assert_file_contains "$workflow_file" "bash \"\$TRUSTED_STRIX_GATE\"" "strix workflow executes trusted temp gate script"
	assert_file_contains "$workflow_file" "Collect Strix reports for artifact upload" "strix workflow preserves reports from trusted workspace"
	assert_file_contains "$workflow_file" "scan-summary.txt" "strix workflow creates a fallback artifact when Strix emits no report files"
	assert_file_not_contains "$workflow_file" "actions/checkout" "strix workflow avoids checkout in privileged context"
	assert_file_not_contains "$workflow_file" "run: bash ./scripts/ci/test_strix_quick_gate.sh" "strix workflow avoids direct repo self-test execution on privileged trigger"
	assert_file_not_contains "$workflow_file" "run: bash ./scripts/ci/strix_quick_gate.sh" "strix workflow avoids direct repo gate execution on privileged trigger"
	assert_file_contains "$workflow_file" "Fetch pull request head for trusted scan" "strix workflow fetches PR head without checkout"
	assert_file_contains "$workflow_file" "pr_number:" "strix workflow accepts manual PR-scope evidence inputs"
	assert_file_contains "$workflow_file" "strix_llm:" "strix workflow accepts only manual Strix model overrides"
	assert_file_contains "$workflow_file" "github.event.inputs.pr_number" "strix workflow can run PR-scoped workflow_dispatch evidence"
	assert_file_contains "$workflow_file" "PR number and head SHA are required for trusted PR-scope Strix evidence" "strix workflow fails closed when manual PR-scope metadata is incomplete"
	assert_file_contains "$workflow_file" '[[ "$PR_HEAD_SHA" =~ ^[0-9a-fA-F]{40}$ ]]' "strix workflow validates PR head SHA before trusted fetch"
	assert_file_contains "$workflow_file" '[[ "$PR_BASE_SHA" =~ ^[0-9a-fA-F]{40}$ ]]' "strix workflow validates PR base SHA before trusted fetch"
	assert_file_contains "$workflow_file" 'fetch --no-tags --depth=1 origin "$PR_BASE_SHA"' "strix workflow fetches manual PR-scope base commit for diffing"
	assert_file_contains "$workflow_file" "refs/remotes/pull" "strix workflow verifies fetched PR head ref"
	local pr_head_fetch_block
	pr_head_fetch_block="$(
		awk '
			/- name: Fetch pull request head for trusted scan/ { in_block = 1 }
			in_block && /- name: Self-test Strix gate script/ { exit }
			in_block { print }
		' "$workflow_file"
	)"
	if [[ "$pr_head_fetch_block" != *'GH_TOKEN: ${{ github.token }}'* ]]; then
		record_failure "strix workflow passes GH_TOKEN to PR head fetch step"
	fi
	if [[ "$pr_head_fetch_block" != *"gh auth setup-git"* ]]; then
		record_failure "strix workflow configures git credentials in PR head fetch step"
	fi
	assert_file_contains "$workflow_file" "for pr_head_fetch_attempt in 1 2 3 4 5 6" "strix workflow retries stale PR head ref propagation"
	assert_file_contains "$workflow_file" "PR head ref did not resolve to expected commit" "strix workflow fails closed when PR head ref remains stale"
	assert_file_contains "$workflow_file" "sleep 10" "strix workflow waits between stale PR head ref retries"
	assert_file_contains "$workflow_file" "github.event_name == 'pull_request_target'" "strix workflow gates PR context on pull_request_target"
	assert_file_contains "$workflow_file" "GCP_SA_KEY" "strix workflow uses organization Vertex AI credentials when STRIX_LLM selects vertex_ai"
	assert_file_not_contains "$workflow_file" "google-github-actions/auth" "strix workflow must not authenticate to Google Cloud for direct OpenAI scans"
	assert_file_contains "$workflow_file" "provider_mode=vertex_ai" "strix workflow supports Vertex AI provider mode"
	assert_file_contains "$workflow_file" "GOOGLE_APPLICATION_CREDENTIALS" "strix workflow exports Vertex AI credentials only for Vertex provider mode"
	assert_file_contains "$workflow_file" "VERTEXAI_PROJECT" "strix workflow exports LiteLLM Vertex project env"
	assert_file_contains "$workflow_file" "VERTEXAI_LOCATION" "strix workflow exports LiteLLM Vertex location env"
	assert_file_contains "$workflow_file" "timeout-minutes: 120" "strix workflow job budget covers PR-scoped Strix scans"
	assert_file_contains "$workflow_file" 'budget_suffix="TIME""OUT"' "strix workflow builds budget env keys without visible timeout signal text"
	assert_file_contains "$workflow_file" 'export "STRIX_TOTAL_${budget_suffix}_SECONDS=7200"' "strix workflow total Strix budget covers PR-scoped scans"
	assert_file_contains "$workflow_file" 'process_budget_seconds="3600"' "strix workflow keeps PR-scoped process budget large enough for report finalization"
	assert_file_contains "$workflow_file" 'IS_PR_EVIDENCE_RUN: ${{ (github.event_name == '"'"'pull_request_target'"'"' || github.event.inputs.pr_number != '"'"''"'"') && '"'"'true'"'"' || '"'"'false'"'"' }}' "strix workflow passes PR evidence mode through env"
	assert_file_not_contains "$workflow_file" 'if [ "${{ (github.event_name == '"'"'pull_request_target'"'"' || github.event.inputs.pr_number != '"'"''"'"') && '"'"'true'"'"' || '"'"'false'"'"' }}" = "true" ]; then' "strix workflow does not interpolate GitHub context inside shell condition"
	assert_file_not_contains "$workflow_file" "LLM_TIMEOUT:" "strix workflow must not expose LLM timeout env names in GitHub logs"
	assert_file_not_contains "$workflow_file" "STRIX_MEMORY_COMPRESSOR_TIMEOUT:" "strix workflow must not expose compressor timeout env names in GitHub logs"
	assert_file_not_contains "$workflow_file" "STRIX_PROCESS_TIMEOUT_SECONDS:" "strix workflow must not expose process timeout env names in GitHub logs"
	assert_file_not_contains "$workflow_file" "STRIX_TOTAL_TIMEOUT_SECONDS:" "strix workflow must not expose total timeout env names in GitHub logs"
	assert_file_not_contains "$workflow_file" "STRIX_PR_SCOPE_MAX_FILES_PER_BATCH" "strix workflow must not split Strix PR evidence into separate scanner runs"
	assert_file_not_contains "$workflow_file" "secrets.STRIX_LLM == 'vertex_ai/gemini-3.1-pro-preview-customtools' && 'vertex_ai/gemini-2.5-flash'" "strix workflow must not quarantine the approved Vertex preview model after organization secret visibility is fixed"
	assert_file_contains "$workflow_file" "github.event.inputs.strix_llm || 'openai/gpt-5'" "strix workflow defaults PR Strix scans to GitHub Models GPT-5"
	assert_file_not_contains "$workflow_file" "secrets.STRIX_LLM ||" "strix workflow must not let the legacy STRIX_LLM secret override PR defaults"
	assert_file_contains "$workflow_file" "STRIX_LLM must select GitHub Models openai/gpt-5 or newer, direct OpenAI GPT-5.4 or newer, or an approved organization Vertex AI model" "strix workflow rejects unsupported model inputs"
	assert_file_contains "$workflow_file" "vertex_ai/gemini-3.1-pro-preview-customtools | vertex_ai/gemini-2.5-flash)" "strix workflow accepts only exact approved organization Vertex AI models"
	assert_file_contains "$workflow_file" 'STRIX_VERTEX_FALLBACK_MODELS: ""' "strix workflow disables silent Vertex fallbacks so timeout-class failures fail closed"
	assert_file_contains "$workflow_file" 'STRIX_FAIL_ON_PROVIDER_SIGNAL: "1"' "strix workflow fails closed on timeout, fatal, warning, denied, or provider failure signals"
	assert_file_contains "$workflow_file" 'NPM_CONFIG_IGNORE_SCRIPTS: "true"' "strix workflow disables npm lifecycle scripts for untrusted PR scan data"
	assert_file_contains "$workflow_file" 'PNPM_CONFIG_IGNORE_SCRIPTS: "true"' "strix workflow disables pnpm lifecycle scripts for untrusted PR scan data"
	assert_file_contains "$workflow_file" 'YARN_ENABLE_SCRIPTS: "false"' "strix workflow disables yarn lifecycle scripts for untrusted PR scan data"
	assert_file_not_contains "$workflow_file" "PYTHONWARNINGS:" "strix workflow must not expose warning-filter env names in GitHub logs"
	assert_file_contains "$workflow_file" "temporary scope with execute bits stripped" "strix workflow documents PR-head blobs as non-executable scan data"
	assert_file_contains "$workflow_file" "__PR_SCOPE__" "strix workflow uses explicit PR-scope target sentinel for PR evidence"
	assert_file_contains "$GATE_SCRIPT" 'child_env["NPM_CONFIG_IGNORE_SCRIPTS"] = "true"' "strix gate child process disables npm lifecycle scripts"
	assert_file_contains "$GATE_SCRIPT" 'child_env["PNPM_CONFIG_IGNORE_SCRIPTS"] = "true"' "strix gate child process disables pnpm lifecycle scripts"
	assert_file_contains "$GATE_SCRIPT" 'child_env["YARN_ENABLE_SCRIPTS"] = "false"' "strix gate child process disables yarn lifecycle scripts"
	assert_file_contains "$GATE_SCRIPT" 'child_env["PYTHONWARNINGS"] = "ignore:Pydantic serializer warnings:UserWarning:pydantic.main"' "strix gate child env narrowly filters the known third-party Pydantic serializer warning"
	assert_file_contains "$GATE_SCRIPT" '[[ "$normalized_changed_file" =~ ^backend/.+\.py$ ]]' "strix gate detects nested backend Python files for PR-scoped import context"
	assert_file_contains "$GATE_SCRIPT" '[[ "$normalized_changed_file" == scripts/ci/test_*.sh || "$normalized_changed_file" == scripts/ci/*_test.sh ]]' "strix gate excludes large CI test harness scripts from model scan input"
	assert_file_contains "$GATE_SCRIPT" "Materialized PR-head changed-file scope for Strix scan" "strix gate avoids copying the full PR head tree into privileged scan targets by default"
	assert_file_contains "$GATE_SCRIPT" "sanitize_known_strix_report_warnings" "strix gate sanitizes only known internal Strix report warnings"
	assert_file_contains "$GATE_SCRIPT" "iter_report_logs" "strix gate enumerates report logs through a safe walker"
	assert_file_contains "$GATE_SCRIPT" "os.walk(root, topdown=True, followlinks=False)" "strix gate does not recurse into symlinked report directories"
	assert_file_not_contains "$GATE_SCRIPT" 'root.rglob("*.log")' "strix gate avoids recursive pathlib glob traversal for report logs"
	assert_file_contains "$GATE_SCRIPT" "has_strix_report_failure_signal" "strix gate fails closed on warning-class Strix report artifacts"
	assert_file_not_contains "$workflow_file" "ignore::UserWarning" "strix workflow must not blanket-suppress all UserWarning output"
	assert_file_not_contains "$workflow_file" "vertex_ai/* | vertex_ai_beta/*" "strix workflow must not accept arbitrary Vertex models"
	assert_file_contains "$workflow_file" "provider_mode=openai_direct" "strix workflow requires direct OpenAI GPT-5 credentials"
	assert_file_contains "$workflow_file" "provider_mode=github_models" "strix workflow supports GitHub Models provider mode"
	assert_file_contains "$workflow_file" 'STRIX_GITHUB_MODELS_TOKEN: ${{ secrets.STRIX_GITHUB_MODELS_TOKEN || github.token }}' "strix workflow prefers the organization GitHub Models token secret and falls back to GITHUB_TOKEN"
	assert_file_contains "$workflow_file" 'LLM_API_KEY_SECRET: ${{ steps.gate.outputs.provider_mode == '"'"'github_models'"'"' && (secrets.STRIX_GITHUB_MODELS_TOKEN || github.token) || steps.gate.outputs.provider_mode == '"'"'openai_direct'"'"' && secrets.STRIX_OPENAI_API_KEY || '"'"''"'"' }}' "strix workflow uses provider-scoped LLM key material"
	assert_file_contains "$workflow_file" 'LLM_API_KEY: ${{ steps.gate.outputs.provider_mode == '"'"'github_models'"'"' && (secrets.STRIX_GITHUB_MODELS_TOKEN || github.token) || steps.gate.outputs.provider_mode == '"'"'openai_direct'"'"' && secrets.STRIX_OPENAI_API_KEY || '"'"''"'"' }}' "strix workflow masks provider-scoped LLM key material"
	assert_file_not_contains "$workflow_file" "secrets.LLM_API_KEY" "strix workflow must not expose generic LLM_API_KEY for Vertex scans"
	assert_file_contains "$workflow_file" "STRIX_GITHUB_MODELS_TOKEN is required for GitHub Models Strix scans" "strix workflow fails closed when GitHub Models credentials are absent"
	assert_file_contains "$workflow_file" "STRIX_OPENAI_API_KEY is required for Strix OpenAI Platform scans" "strix workflow fails closed when direct credentials are absent"
	assert_file_contains "$workflow_file" 'PROVIDER_MODE: ${{ steps.gate.outputs.provider_mode }}' "strix workflow passes provider mode through env"
	assert_file_not_contains "$workflow_file" '[ "${{ steps.gate.outputs.provider_mode }}" = "openai_direct" ]' "strix workflow does not interpolate provider mode inside shell condition"
	assert_file_contains "$workflow_file" 'trimmed_openai_key="$(printf '"'"'%s'"'"' "$sanitized_openai_key" | sed '"'"'s/^[[:space:]]*//;s/[[:space:]]*$//'"'"')"' "strix workflow trims whitespace-only OpenAI keys before gate validation"
	assert_file_contains "$workflow_file" 'trimmed="$(printf '"'"'%s'"'"' "$sanitized" | sed '"'"'s/^[[:space:]]*//;s/[[:space:]]*$//'"'"')"' "strix workflow trims whitespace-only OpenAI keys before input file creation"
	assert_file_contains "$workflow_file" 'STRIX_LLM_DEFAULT_PROVIDER: ${{ steps.gate.outputs.provider_mode == '"'"'vertex_ai'"'"' && '"'"'vertex_ai'"'"' || '"'"'openai'"'"' }}' "strix workflow selects the correct default provider"
	assert_file_contains "$workflow_file" "Prepare GitHub Models API base" "strix workflow prepares the GitHub Models API base only for GitHub Models mode"
	assert_file_contains "$workflow_file" "https://models.github.ai/inference" "strix workflow routes GitHub Models scans to the inference endpoint"
	assert_file_contains "$workflow_file" "LLM_API_BASE_FILE" "strix workflow passes the GitHub Models API base through a trusted input file"
	assert_file_not_contains "$workflow_file" '${{ secrets.STRIX_OPENAI_API_KEY || github.token }}' "strix workflow must not use fallback-secret syntax for LLM API keys"
	assert_file_contains "$workflow_file" "github_models/deepseek/deepseek-r1-0528 github_models/deepseek/deepseek-v3-0324" "strix workflow configures reachable stronger-than-GPT-4.1 GitHub Models fallback models"
	assert_file_not_contains "$workflow_file" 'github_models/deepseek/deepseek-r1-0528 | github_models/deepseek/deepseek-v3-0324)' "strix workflow keeps DeepSeek GitHub Models restricted to fallback-only routing"
	assert_file_contains "$workflow_file" '${strix_model#github_models/}' "strix workflow strips manual github_models routing prefix for OpenAI GPT model names before passing model names to LiteLLM"
	assert_file_contains "$workflow_file" "openai_direct/%s" "strix workflow keeps manual direct OpenAI scans distinct from GitHub Models openai/gpt-* routing"
	assert_file_not_contains "$workflow_file" "openai/gpt-4.1" "strix workflow must not fall back to GPT-4.1 or weaker review evidence"
	assert_file_not_contains "$workflow_file" "openai/gpt-5-*" "strix workflow must not accept older GPT-5 variants when GPT-5.4 is required"
	assert_file_contains "$workflow_file" "openai/gpt-5-mini* | openai/gpt-5-nano*" "strix workflow rejects mini and nano GPT-5 variants for security evidence"
	assert_file_contains "$workflow_file" "openai/gpt-5*" "strix workflow accepts GitHub Models OpenAI GPT-5 model prefixes"
	assert_file_not_contains "$workflow_file" "github/gpt-4o" "strix workflow must not default to an unsupported GitHub Models alias"
	assert_file_not_contains "$workflow_file" "gemini/gemini-pro-3.1-preview" "strix workflow must not default to Gemini API when GitHub Models is required"
	assert_file_not_contains "$workflow_file" "if-no-files-found: warn" "strix workflow must not downgrade missing security artifacts to warnings"
	if grep -Eq '^[[:space:]]+pull_request:[[:space:]]*$' "$workflow_file"; then
		record_failure "strix workflow must not expose secrets on pull_request events"
	fi
	assert_file_not_contains "$workflow_file" "github.event_name == 'pull_request'" "strix workflow should not retain pull_request-only expressions"
}

assert_strix_gpt54_model_guard_semantics() {
	local model="$1"
	case "$model" in
	openai/gpt-5-mini* | openai/gpt-5-nano* | \
	openai/openai/gpt-5-mini* | openai/openai/gpt-5-nano* | \
	github_models/openai/gpt-5-mini* | github_models/openai/gpt-5-nano*)
		return 1
		;;
	openai/gpt-5* | openai/gpt-[6-9]* | openai/gpt-[1-9][0-9]* | \
	openai/openai/gpt-5* | openai/openai/gpt-[6-9]* | openai/openai/gpt-[1-9][0-9]* | \
	github_models/openai/gpt-5* | github_models/openai/gpt-[6-9]* | github_models/openai/gpt-[1-9][0-9]* | \
	gpt-5.[4-9]* | gpt-5.[1-9][0-9]* | gpt-[6-9]* | gpt-[1-9][0-9]* | \
	openai-direct/gpt-5.[4-9]* | openai-direct/gpt-5.[1-9][0-9]* | openai-direct/gpt-[6-9]* | openai-direct/gpt-[1-9][0-9]* | \
	vertex_ai/gemini-3.1-pro-preview-customtools | vertex_ai/gemini-2.5-flash)
		return 0
		;;
	*)
		return 1
		;;
	esac
}

assert_strix_gpt54_model_guard_cases() {
	if ! assert_strix_gpt54_model_guard_semantics "openai/gpt-5"; then
		record_failure "strix guard must accept GitHub Models openai/gpt-5"
	fi
	if assert_strix_gpt54_model_guard_semantics "openai/gpt-5-mini"; then
		record_failure "strix guard must reject GitHub Models openai/gpt-5-mini"
	fi
	if assert_strix_gpt54_model_guard_semantics "github_models/openai/gpt-5-nano"; then
		record_failure "strix guard must reject manual GitHub Models openai/gpt-5-nano"
	fi
	if assert_strix_gpt54_model_guard_semantics "github_models/openai/gpt-4.1"; then
		record_failure "strix guard must reject weaker GitHub Models gpt-4.1"
	fi
	if assert_strix_gpt54_model_guard_semantics "gpt-5"; then
		record_failure "strix GPT-5.4 guard must reject plain gpt-5"
	fi
	if ! assert_strix_gpt54_model_guard_semantics "gpt-5.4"; then
		record_failure "strix GPT-5.4 guard must accept direct OpenAI gpt-5.4"
	fi
	if ! assert_strix_gpt54_model_guard_semantics "openai-direct/gpt-5.4"; then
		record_failure "strix GPT-5.4 guard must accept direct OpenAI openai-direct/gpt-5.4"
	fi
	if ! assert_strix_gpt54_model_guard_semantics "openai/gpt-5.4"; then
		record_failure "strix guard must accept GitHub Models openai/gpt-5.4"
	fi
	if ! assert_strix_gpt54_model_guard_semantics "openai/openai/gpt-5"; then
		record_failure "strix guard must accept GitHub Models openai/openai/gpt-5"
	fi
	if ! assert_strix_gpt54_model_guard_semantics "openai/openai/gpt-5.4"; then
		record_failure "strix guard must accept GitHub Models openai/openai/gpt-5.4"
	fi
	if assert_strix_gpt54_model_guard_semantics "openai/deepseek/deepseek-r1-0528"; then
		record_failure "strix guard must reject direct DeepSeek R1 primary selection"
	fi
	if assert_strix_gpt54_model_guard_semantics "openai/deepseek/deepseek-v3-0324"; then
		record_failure "strix guard must reject direct DeepSeek V3 primary selection"
	fi
	if assert_strix_gpt54_model_guard_semantics "github_models/deepseek/deepseek-r1-0528"; then
		record_failure "strix guard must reject manual GitHub Models DeepSeek R1 primary selection"
	fi
	if assert_strix_gpt54_model_guard_semantics "github_models/deepseek/deepseek-v3-0324"; then
		record_failure "strix guard must reject manual GitHub Models DeepSeek V3 primary selection"
	fi
	if ! assert_strix_gpt54_model_guard_semantics "vertex_ai/gemini-3.1-pro-preview-customtools"; then
		record_failure "strix guard must accept the organization-approved Vertex preview model"
	fi
	if ! assert_strix_gpt54_model_guard_semantics "vertex_ai/gemini-2.5-flash"; then
		record_failure "strix guard must accept the approved organization Vertex AI operational model"
	fi
	if assert_strix_gpt54_model_guard_semantics "vertex_ai/gemini-2.5-pro"; then
		record_failure "strix guard must reject arbitrary Vertex models"
	fi
}

assert_strix_gate_target_scope_separated() {
	assert_file_not_contains "$GATE_SCRIPT" "or generated PR scope directories" "strix gate keeps user target validation separate from internal PR scopes"
	assert_file_contains "$GATE_SCRIPT" "TARGET_PATH_IS_INTERNAL_PR_SCOPE" "strix gate marks internally generated PR scan scopes explicitly"
	assert_file_contains "$GATE_SCRIPT" "PR_SCOPE_TARGET_SENTINEL=\"__PR_SCOPE__\"" "strix gate supports an explicit PR-scope target sentinel"
	assert_file_contains "$GATE_SCRIPT" 'git diff --name-only "$base_sha" "$head_sha"' "strix gate falls back to explicit manual PR-scope diff when merge-base is unavailable"
}

assert_changed_file_membership_uses_cached_normalized_paths() {
	assert_file_contains "$GATE_SCRIPT" "NORMALIZED_CHANGED_FILES=()" "strix gate caches normalized PR changed paths"
	assert_file_contains "$GATE_SCRIPT" 'NORMALIZED_CHANGED_FILES+=("$normalized_changed_file")' "strix gate populates cached normalized PR changed paths"
	assert_file_contains "$GATE_SCRIPT" "for normalized_changed_file in \"\${NORMALIZED_CHANGED_FILES[@]}\"" "strix gate uses cached normalized paths for membership checks"
}

assert_absent_endpoint_search_uses_canonical_target_path() {
	assert_file_contains "$GATE_SCRIPT" 'resolved_target_root="$(resolve_current_target_path "$TARGET_PATH" 2>/dev/null)"' "absent-endpoint search resolves canonical target root"
	assert_file_contains "$GATE_SCRIPT" 'candidate="${resolved_target_root%/}/$dir_entry"' "absent-endpoint search uses canonical target root"
	assert_file_not_contains "$GATE_SCRIPT" 'candidate="${TARGET_PATH%/}/$dir_entry"' "absent-endpoint search avoids relative target path roots"
}

assert_strix_llm_file_read_is_literal_data() {
	assert_file_contains "$GATE_SCRIPT" 'STRIX_LLM_CONTENT="$(cat -- "$STRIX_LLM_FILE")"' "strix gate reads model file content as data before trimming"
	assert_file_contains "$GATE_SCRIPT" 'STRIX_LLM="$(trim_whitespace "$STRIX_LLM_CONTENT")"' "strix gate trims model file content without nested command substitution"
	assert_file_not_contains "$GATE_SCRIPT" 'STRIX_LLM="$(trim_whitespace "$(cat -- "$STRIX_LLM_FILE")")"' "strix gate avoids nested command substitution for model file content"
}

assert_strix_child_target_uses_constant_argument() {
	assert_file_contains "$GATE_SCRIPT" 'command = [resolved_strix_bin, "-n", "-t", ".", "--scan-mode", scan_mode]' "strix gate passes a constant target argument to the child process"
	assert_file_contains "$GATE_SCRIPT" 'cwd=str(target_cwd)' "strix gate runs the child process from the canonical target directory"
	assert_file_not_contains "$GATE_SCRIPT" 'command = [resolved_strix_bin, "-n", "-t", target_path, "--scan-mode", scan_mode]' "strix gate must not forward raw target paths as child arguments"
}

assert_opencode_review_uses_codegraph_and_gpt5_fallback() {
	local workflow_file="$REPO_ROOT/.github/workflows/opencode-review.yml"
	local opencode_config="$REPO_ROOT/opencode.jsonc"

	assert_file_contains "$workflow_file" "pull_request_target:" "opencode review workflow runs on the trusted PR trigger so merge-conflict PRs still get the standard review surface"
	assert_file_contains "$workflow_file" "pull_request:" "opencode review workflow publishes a PR-associated required check while trusted review side effects stay on pull_request_target"
	assert_file_contains "$workflow_file" "Wait for trusted OpenCode approval review" "opencode pull_request bridge only waits for a trusted same-head OpenCode approval"
	assert_file_contains "$workflow_file" "Trusted OpenCode requested changes for head" "opencode pull_request bridge fails immediately when the trusted same-head review requested changes"
	assert_file_contains "$workflow_file" "github.event_name == 'pull_request_target'" "opencode review side effects are limited to pull_request_target or manual workflow dispatch"
	assert_file_contains "$workflow_file" "opencode-review-target:" "opencode trusted review job is separate from the pull_request bridge"
	assert_file_contains "$workflow_file" "github.event.pull_request.head.repo.full_name == github.repository" "opencode review workflow limits pull_request_target review execution to same-repository PRs"
	assert_file_contains "$workflow_file" "Initialize CodeGraph index for OpenCode" "opencode review workflow initializes CodeGraph before review"
	assert_file_contains "$workflow_file" "actions: read" "opencode review workflow can read failed Actions logs for GitHub Check diagnosis"
	assert_file_contains "$workflow_file" "checks: read" "opencode review workflow can read failed check-run annotations for line-specific findings"
	assert_file_contains "$workflow_file" "contents: read" "opencode review workflow uses read-only repository contents permission"
	assert_file_not_contains "$workflow_file" "contents: write" "opencode review workflow must not request repository content write permission"
	assert_file_contains "$workflow_file" "pull-requests: read" "opencode review workflow reads pull request metadata through the job token"
	assert_file_not_contains "$workflow_file" "pull-requests: write" "opencode review workflow writes reviews through the OpenCode app token instead of the job token"
	assert_file_contains "$workflow_file" "issues: read" "opencode review workflow reads overview comments through the job token"
	assert_file_not_contains "$workflow_file" "issues: write" "opencode review workflow writes overview comments through the OpenCode app token instead of the job token"
	assert_file_contains "$workflow_file" "statuses: read" "opencode review workflow can read failed status contexts for approval gating"
	assert_file_contains "$workflow_file" "Prepare bounded OpenCode review evidence" "opencode review workflow prepares bounded local evidence instead of oversized GitHub prompt data"
	assert_file_contains "$workflow_file" "emit_file_prefix" "opencode review prompt evidence is byte-capped before GitHub Models requests"
	assert_file_contains "$workflow_file" "bounded-review-evidence.md" "opencode review prompt reads bounded evidence from the isolated workspace instead of inlining it"
	assert_file_contains "$workflow_file" "Prepare isolated OpenCode review workspace" "opencode review workflow isolates from the large project AGENTS.md"
	assert_file_contains "$workflow_file" 'cd "$OPENCODE_REVIEW_WORKDIR"' "opencode review runs from the isolated OpenCode workspace"
	assert_file_contains "$workflow_file" "failed-check-evidence.md" "opencode review copies full failed-check evidence into the isolated workspace"
	assert_file_contains "$workflow_file" "Checkout trusted review workflow" "opencode review executes trusted workflow scripts from the base checkout"
	assert_file_contains "$workflow_file" "Checkout trusted review workflow for manual PR review" "opencode review checks out explicit base SHA for manual PR review reruns"
	assert_file_contains "$workflow_file" 'ref: ${{ github.event.inputs.pr_base_sha }}' "opencode manual review checks out the trusted base workflow instead of the PR head"
	assert_file_contains "$workflow_file" "Materialize pull request head for OpenCode review data" "opencode review materializes PR-head source as read-only review data"
	assert_file_contains "$workflow_file" 'git worktree add --detach "$OPENCODE_SOURCE_WORKDIR" "$PR_HEAD_SHA"' "opencode review materializes the PR head without actions/checkout credentials"
	assert_file_contains "$workflow_file" 'cd "$OPENCODE_SOURCE_WORKDIR"' "opencode CodeGraph indexing runs against the PR-head source worktree"
	assert_file_contains "$workflow_file" 'PR_MERGE_BASE="$(git -C "$OPENCODE_SOURCE_WORKDIR" merge-base "$PR_BASE_SHA" "$PR_HEAD_SHA")"' "opencode review evidence diffs use the PR-head worktree merge base"
	assert_file_contains "$workflow_file" 'git -C "$OPENCODE_SOURCE_WORKDIR" diff' "opencode review builds changed-file evidence from the PR-head worktree"
	assert_file_not_contains "$workflow_file" 'ref: ${{ github.event.pull_request.base.sha' "opencode pull_request_target checkout avoids dynamic pull_request refs that Scorecard flags"
	assert_file_not_contains "$workflow_file" 'ref: ${{ github.event.pull_request.head.sha || github.event.inputs.pr_head_sha || github.sha }}' "opencode review must not checkout PR head into the trusted workflow workspace"
	assert_file_matches "$workflow_file" 'uses:[[:space:]]+actions/checkout@[0-9a-fA-F]{40}([[:space:]]|$)' "opencode review workflow pins checkout to a full commit SHA"
	assert_workflow_uses_are_sha_pinned "$workflow_file" "opencode review workflow"
	assert_file_contains "$workflow_file" "@colbymchenry/codegraph@0.9.9" "opencode review workflow pins the CodeGraph package"
	assert_file_contains "$workflow_file" "https://mcp.deepwiki.com/mcp" "opencode review workflow configures the DeepWiki remote MCP server"
	assert_file_contains "$workflow_file" "@upstash/context7-mcp@3.1.0" "opencode review workflow pins the Context7 MCP package"
	assert_file_contains "$workflow_file" "@guhcostan/web-search-mcp@1.0.5" "opencode review workflow pins a web search MCP package"
	assert_file_contains "$workflow_file" "NPM_CONFIG_LOGLEVEL" "opencode review workflow suppresses npm warning output for local MCP package fetches"
	assert_file_contains "$workflow_file" 'NPM_CONFIG_IGNORE_SCRIPTS: "true"' "opencode review workflow disables npm lifecycle scripts for CodeGraph npx"
	assert_file_contains "$workflow_file" "init -i" "opencode review workflow builds the CodeGraph index"
	assert_file_contains "$workflow_file" "CodeGraph MCP tools" "opencode review prompt requires CodeGraph-backed review evidence"
	assert_file_contains "$workflow_file" "general-purpose and meticulous" "opencode review prompt requires a general-purpose meticulous review"
	assert_file_contains "$workflow_file" "actively consult CodeGraph MCP for structural checks, DeepWiki for repo docs, Context7 for current library/API docs, and web_search for bounded external lookups" "opencode review prompt directs the agent to use all configured MCP sources"
	assert_file_contains "$workflow_file" "observable impact, trigger condition, minimal fix direction, and exact regression test or verification command" "opencode review prompt requires practical finding details"
	assert_file_contains "$workflow_file" "The regression_test_direction should name an exact test target or verification command when the repository already provides one." "opencode review prompt requires concrete validation guidance"
	assert_file_contains "$workflow_file" "P1/P2/P3 priority" "opencode review prompt requires Greptile-style priority labels"
	assert_file_contains "$workflow_file" "nearby implementation, matching existing example, cross-file counterpart, current official docs, or failed check/log evidence" "opencode review prompt requires explicit evidence type"
	assert_file_contains "$workflow_file" "flag unrelated PR scope drift" "opencode review prompt catches unrelated scope drift"
	assert_file_contains "$workflow_file" "GitHub suggestion-ready minimal diffs" "opencode review prompt requires directly applicable suggested diffs"
	assert_file_contains "$workflow_file" "compact Mermaid graph" "opencode review prompt requires a Mermaid risk graph"
	assert_file_contains "$workflow_file" "PR mergeability evidence" "opencode review evidence includes PR mergeability state"
	assert_file_contains "$workflow_file" "## Changed docs repository tree evidence" "opencode review evidence includes repo-tree facts for changed docs directories"
	assert_file_contains "$workflow_file" 'git -C "$OPENCODE_SOURCE_WORKDIR" ls-tree -r --name-only "$PR_HEAD_SHA" -- "$docs_dir"' "opencode review evidence lists current-head docs assets from the PR head worktree before judging docs claims"
	assert_file_contains "$workflow_file" "Do not claim repository docs, images, or reference assets are unavailable, missing, or absent unless the changed docs repository tree evidence proves it." "opencode review prompt forbids unsupported docs asset absence claims"
	assert_file_contains "$workflow_file" "Merge Conflict Guidance" "opencode review overview includes conflict repair guidance"
	assert_file_contains "$workflow_file" "mergeStateStatus DIRTY or CONFLICTING" "opencode review prompt handles merge conflicts"
	assert_file_contains "$workflow_file" "mergeStateStatus BLOCKED is a branch policy, review, or check state, not conflict guidance" "opencode review prompt does not misclassify branch-policy blockers as merge conflicts"
	if [ -e "$REPO_ROOT/.github/workflows/opencode-merge-conflict-guidance.yml" ]; then
		record_failure "opencode merge-conflict guidance must stay inside OpenCode Review instead of a separate workflow"
	fi
	assert_file_contains "$workflow_file" "Structural exploration is mandatory for every PR" "opencode review prompt makes structural exploration mandatory"
	assert_file_contains "$workflow_file" "Never state that structural exploration, structural analysis, or structural review is not required or unnecessary" "opencode review prompt forbids dismissing structural review"
	assert_file_contains "$workflow_file" "If structural exploration was not possible or changed files could not be inspected after reading bounded-review-evidence.md and the changed files, do not approve" "opencode review prompt blocks approval without structural evidence"
	assert_file_contains "$workflow_file" "Use CodeGraph for blast-radius, call graph, and test-coverage questions before broad local reads" "opencode review prompt adapts code-review-graph guidance without adding a duplicate dependency"
	assert_file_contains "$workflow_file" "Prefer deletion, stdlib/native platform features, and already-installed dependencies before proposing new code or packages" "opencode review prompt adapts ponytail minimal-change guidance"
	assert_file_contains "$workflow_file" "For Korean prose, preserve facts, identifiers, numbers, and quotes" "opencode review prompt adapts im-not-ai guidance only for Korean prose"
	assert_file_contains "$workflow_file" "concrete CWE/KISA-style class" "opencode failed-check diagnosis maps Strix findings to evidence-backed security categories"
	assert_file_contains "$workflow_file" "Do not request changes solely because the prompt did not inline the full evidence" "opencode review prompt requires file inspection instead of evidence-truncation blockers"
	assert_file_contains "$workflow_file" "Inspect changed files and focused hunks directly when MCP evidence is insufficient." "opencode review allows focused direct source inspection when MCP evidence is insufficient"
	assert_file_contains "$workflow_file" "Never return raw tool-call markup, tool-call JSON, or MCP call syntax in the review body" "opencode review prompt forbids raw tool-call transcripts as final review output"
	assert_file_contains "$workflow_file" "Do not spend the session listing every changed path before reviewing" "opencode review prompt prevents fallback sessions from exhausting steps on file listing"
	assert_file_contains "$workflow_file" "always return a final control block instead of a progress summary" "opencode review prompt requires a gate conclusion instead of a progress summary"
	assert_file_contains "$workflow_file" "timeout 600 opencode run" "opencode review primary model has a bounded timeout so fallback review can publish promptly"
	assert_file_contains "$workflow_file" 'OPENCODE_MODEL_ATTEMPTS: "2"' "opencode review retries transient model execution failures before exhausting a model"
	assert_file_contains "$workflow_file" 'OpenCode %s attempt %s/%s failed with exit %s.' "opencode review logs per-model retry attempts"
	assert_file_contains "$workflow_file" 'case "$opencode_run_status" in' "opencode review sends timeout-class failures directly to fallback instead of retrying the same stuck model"
	assert_file_contains "$workflow_file" '"ci-review-fallback"' "opencode review workflow declares a dedicated fallback agent"
	assert_file_contains "$workflow_file" '"steps": 12' "opencode review fallback agent has enough bounded steps to conclude after MCP inspection"
	assert_file_contains "$workflow_file" '"read": "allow"' "opencode review allows read-only file inspection"
	assert_file_contains "$workflow_file" '"grep": "allow"' "opencode review allows focused literal searches"
	assert_file_contains "$workflow_file" '"external_directory": "allow"' "opencode review can read the real checkout from its isolated review workspace"
	assert_file_not_contains "$workflow_file" '"external_directory": "deny"' "opencode review must not block focused reads of the real checkout"
	assert_file_contains "$workflow_file" "Bounded evidence is available in ./bounded-review-evidence.md" "opencode review prompt points the model at the bounded evidence file"
	assert_file_contains "$workflow_file" "Current runtime-version review contract" "opencode review evidence names the current runtime-version contract"
	assert_file_contains "$workflow_file" "Do not request rollback of Node 24 or Python 3.14 solely from model memory" "opencode review prompt rejects stale runtime-version model memory"
	assert_file_not_contains "$workflow_file" 'head -c 20000 "$OPENCODE_EVIDENCE_FILE"' "opencode review prompt must not exceed GitHub Models prompt limits by inlining bounded evidence"
	assert_file_contains "$workflow_file" "## Focused changed hunks" "opencode review evidence includes focused changed hunks"
	assert_file_contains "$workflow_file" 'git -C "$OPENCODE_SOURCE_WORKDIR" diff --unified=12 --find-renames "$PR_MERGE_BASE" "$PR_HEAD_SHA"' "opencode review evidence includes focused hunks from the PR merge base"
	assert_file_contains "$workflow_file" 'mapfile -t focused_hunk_paths' "opencode review evidence builds focused hunks from the changed file list"
	assert_file_contains "$workflow_file" 'git -C "$OPENCODE_SOURCE_WORKDIR" diff --name-only --find-renames "$PR_MERGE_BASE" "$PR_HEAD_SHA"' "opencode review evidence discovers focused hunk paths dynamically"
	assert_file_contains "$workflow_file" '-- "${focused_hunk_paths[@]}"' "opencode review evidence passes dynamic changed paths to git diff"
	assert_file_contains "$workflow_file" "do not return file-inaccessible findings" "opencode review prompt forbids placeholder inaccessible-file findings when hunks are present"
	assert_file_contains "$workflow_file" "Do not include analysis, planning, tool-call narration, placeholders, or prose before the sentinel." "opencode review prompt forbids reasoning text before the control sentinel"
	assert_file_contains "$workflow_file" "OpenCode output did not include a valid control conclusion." "opencode review model steps fail when output lacks a parseable control conclusion"
	assert_file_contains "$workflow_file" 'bash "$GITHUB_WORKSPACE/scripts/ci/opencode_review_approve_gate.sh" "$HEAD_SHA" "$RUN_ID" "$RUN_ATTEMPT" "$output_file"' "opencode review model steps validate the control block before publishing"
	assert_file_contains "$workflow_file" 'if bash "$GITHUB_WORKSPACE/scripts/ci/opencode_review_approve_gate.sh" "$HEAD_SHA" "$RUN_ID" "$RUN_ATTEMPT" "$output_file" >/dev/null; then' "opencode review model steps try the direct approval gate before Python normalization"
	assert_file_contains "$workflow_file" "normalize_opencode_output" "opencode review model steps normalize model control output"
	assert_file_contains "$workflow_file" "opencode_review_normalize_output.py" "opencode review model steps normalize transcript-embedded JSON output"
	assert_file_contains "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" "decoder.raw_decode" "opencode review normalizer scans transcript text for JSON objects"
	assert_file_contains "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" "valid_control" "opencode review normalizer accepts only current-run control JSON"
	assert_file_contains "$workflow_file" "opencode run" "opencode review workflow runs the bounded OpenCode agent path"
	assert_file_contains "$workflow_file" 'opencode run "$(cat "$prompt_file")"' "opencode review passes the prompt as the positional message before file attachments"
	assert_file_contains "$workflow_file" "--agent ci-review" "opencode review workflow forces the compact CI review agent"
	assert_file_contains "$workflow_file" "--agent ci-review-fallback" "opencode review fallback runs with the expanded CI review agent"
	assert_file_contains "$workflow_file" "--pure" "opencode review workflow avoids external OpenCode plugins during CI"
	assert_file_contains "$workflow_file" "--format json" "opencode review workflow captures the OpenCode session id as JSON"
	assert_file_contains "$workflow_file" "opencode export" "opencode review workflow extracts assistant text from the completed OpenCode session"
	assert_file_contains "$workflow_file" 'gate_status=0' "opencode review publish step tracks invalid control output before failing closed"
	assert_file_contains "$workflow_file" 'gate_status=$?' "opencode review publish step lets approval gate explain invalid control output"
	assert_file_contains "$workflow_file" "OpenCode comment gate result: %s (exit %s)" "opencode review publish step logs invalid control output status"
	assert_file_contains "$workflow_file" "OpenCode publish gate rejected the selected model output; failing this check instead of posting a stale review." "opencode review publish step fails closed when normalized evidence is invalid"
	assert_file_contains "$workflow_file" 'normalized_comment_json="$(mktemp)"' "opencode review publish step creates a normalized control payload file"
	assert_file_contains "$workflow_file" '"$HEAD_SHA" "$RUN_ID" "$RUN_ATTEMPT" "$clean_output"' "opencode review publish step re-normalizes the ANSI-stripped selected model output"
	assert_file_contains "$workflow_file" "Selected successful OpenCode output did not include a valid control conclusion." "opencode review publish step refuses stale success status when the selected output is invalid"
	assert_file_contains "$workflow_file" "exit 4" "opencode review publish step fails closed on invalid selected successful output"
	assert_file_contains "$workflow_file" 'opencode_review_approve_gate.sh "$HEAD_SHA" "$RUN_ID" "$RUN_ATTEMPT" "$comment_body_file" "$normalized_comment_json"' "opencode review publish step extracts normalized control JSON"
	assert_file_contains "$workflow_file" 'cat "$normalized_comment_json"' "opencode review publish step rebuilds the overview from normalized control JSON"
	assert_file_contains "$workflow_file" 'OPENCODE_FALLBACK_OUTPUT_FILE: ${{ runner.temp }}/opencode-review-fallback.md' "opencode approval step can directly re-read the selected fallback output"
	assert_file_contains "$workflow_file" 'load_selected_review_output()' "opencode approval step has a direct selected-output fallback when the overview comment is stale or invalid"
	assert_file_contains "$workflow_file" "gate result from Review Overview comment" "opencode approval step distinguishes overview-comment gate results"
	assert_file_contains "$workflow_file" "gate result from selected OpenCode output" "opencode approval step can recover from an invalid overview by validating the selected successful output"
	assert_file_contains "$workflow_file" 'APPROVAL_CHECK_WAIT_ATTEMPTS: "241"' "opencode approval waits for long-running peer checks before approving"
	assert_file_contains "$workflow_file" 'CHECK_LOOKUP_RETRY_ATTEMPTS: "5"' "opencode approval retries transient GitHub check lookup failures before changing review state"
	assert_file_contains "$workflow_file" 'GitHub Checks lookup failed; retrying' "opencode approval logs transient check lookup retries"
	assert_file_contains "$workflow_file" 'collect_github_checks_with_retry collect_pending_github_checks "$output_file"' "opencode approval retry-wraps pending check lookup"
	assert_file_contains "$workflow_file" 'collect_github_checks_with_retry collect_failed_github_checks "$failed_checks_file"' "opencode approval retry-wraps failed check lookup"
	assert_file_contains "$workflow_file" 'approve_low_risk_changed_files_after_model_failure()' "opencode approval has a deterministic fallback for low-risk model-output failures"
	assert_file_contains "$workflow_file" 'This fallback is not used for workflow, source-code, script, dependency, infrastructure, configuration, or lockfile changes.' "opencode low-risk fallback excludes executable and configuration changes"
	assert_file_contains "$workflow_file" '.github/workflows' "opencode low-risk fallback explicitly excludes workflow changes"
	assert_file_contains "$workflow_file" 'approve_review_tooling_bootstrap_after_model_failure()' "opencode approval has a deterministic fallback for review-tooling bootstrap failures"
	assert_file_contains "$workflow_file" 'Deterministic review-tooling bootstrap fallback approval was used' "opencode review-tooling bootstrap fallback explains model-output failure approval"
	assert_file_contains "$workflow_file" 'scripts/ci/strix_quick_gate.sh' "opencode review-tooling bootstrap fallback is scoped to the Strix/OpenCode review bundle"
	assert_file_contains "$workflow_file" 'optional actionlint when installed, bash syntax checks for review shell scripts, and Python bytecode compilation' "opencode review-tooling bootstrap fallback runs local static validation"
	assert_file_contains "$workflow_file" 'current_peer_checks_still_running()' "opencode evidence waits for PR statusCheckRollup peer checks before reviewing"
	assert_file_contains "$workflow_file" 'collect_pending_github_checks()' "opencode approval collects pending peer GitHub Checks"
	assert_file_contains "$workflow_file" 'collect_current_head_strix_workflow_runs()' "opencode approval separately accounts for jobless current-head Strix workflow runs"
	assert_file_contains "$workflow_file" 'actions/workflows/strix.yml' "opencode approval probes whether Strix is installed before listing Strix runs"
	assert_file_contains "$workflow_file" 'grep -Fq "HTTP 404" "$workflow_lookup_err"' "opencode approval treats missing Strix workflow as optional instead of a check lookup failure"
	assert_file_contains "$workflow_file" 'gh run list' "opencode approval uses the Actions run list API for current-head Strix evidence"
	assert_file_contains "$workflow_file" '--commit "$HEAD_SHA"' "opencode approval asks GitHub for runs scoped to the current PR head"
	assert_file_contains "$workflow_file" '--limit 200' "opencode approval looks up enough Strix workflow runs to compare current-head failures against newer manual evidence"
	assert_file_not_contains "$workflow_file" 'actions/workflows/strix.yml/runs?per_page=50' "opencode approval must not rely on a shallow Strix workflow-run REST page"
	assert_file_contains "$workflow_file" 'select((.headSha // .head_sha // "") == $head_sha)' "opencode approval filters supplemental Strix workflow runs to the current PR head"
	assert_file_contains "$workflow_file" 'select((.event // "") == "pull_request_target" or (.event // "") == "workflow_dispatch")' "opencode approval compares PR Strix runs with manual current-head evidence reruns"
	assert_file_contains "$workflow_file" '$newest_success_run_id' "opencode approval suppresses older current-head Strix failures after a newer successful evidence run"
	assert_file_contains "$workflow_file" 'Strix Security Scan/strix workflow run' "opencode approval reports pending or failed current-head Strix workflow runs explicitly"
	assert_file_contains "$workflow_file" '["FAILURE","TIMED_OUT","ACTION_REQUIRED","CANCELLED","STARTUP_FAILURE"]' "opencode approval treats failed PR statusCheckRollup check runs as blockers"
	assert_file_contains "$workflow_file" 'grep -Fq -- "Strix Security Scan/strix:" "$rollup_file"' "opencode approval avoids duplicate supplemental Strix workflow-run blockers when statusCheckRollup already has the Strix check"
	assert_file_contains "$workflow_file" 'current_head_manual_strix_success_status()' "opencode approval can identify same-head manual Strix success status evidence"
	assert_file_contains "$workflow_file" 'filter_superseded_strix_failures()' "opencode approval filters only explicitly superseded stale Strix failures"
	assert_file_contains "$workflow_file" 'Manual workflow_dispatch Strix evidence passed' "opencode approval requires an explicit manual Strix evidence status description"
	assert_file_contains "$workflow_file" 'last // empty' "opencode approval checks the latest strix status before accepting manual success evidence"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" '"workflow_run"' "failed-check evidence includes failed same-head workflow runs outside statusCheckRollup"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "--json databaseId,workflowName,status,conclusion,url,event,headSha" "failed-check evidence scopes supplemental workflow runs with event and head SHA metadata"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" 'select((.event // "") == "pull_request_target" or (.event // "") == "workflow_dispatch")' "failed-check evidence appends PR Strix workflow runs and manual PR evidence reruns"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" 'select((.headSha // "") == env.HEAD_SHA)' "failed-check evidence only appends current-head workflow runs"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" 'select((.workflowName // "") == "Strix Security Scan" or (.workflowName // "") == "Strix")' "failed-check evidence only appends Strix workflow runs"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" 'group_by(.__context_key)' "failed-check evidence groups manual Strix statuses by context before accepting superseding success"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" 'map(last)' "failed-check evidence accepts only the latest status per context"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" 'awk -F '"'"'\t'"'"' -v run_id="$run_id"' "failed-check evidence avoids duplicate workflow-run evidence when statusCheckRollup already includes the run"
	assert_file_not_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" '[[ ! "$run_id" =~ ^[0-9]+$ ]]' "failed-check evidence no longer suppresses failed contexts as superseded"
	assert_file_contains "$workflow_file" 'wait_for_peer_github_checks "$pending_checks_file"' "opencode approval gates approval on pending peer GitHub Checks"
	assert_file_contains "$workflow_file" 'collect_unresolved_human_review_threads()' "opencode approval re-queries unresolved human review threads immediately before approval"
	assert_file_contains "$workflow_file" "reviewThreads(first: 100)" "opencode approval reads review threads from GitHub before approval"
	assert_file_contains "$workflow_file" "Latest unresolved human review thread evidence" "opencode approval preserves unresolved human thread evidence in the blocking review"
	assert_file_contains "$workflow_file" "OpenCode reviewed the current-head evidence but found unresolved human review threads before approval." "opencode approval requests changes instead of approving after a fresh human objection"
	assert_file_contains "$workflow_file" 'OpenCode reviewed the current-head bounded evidence but could not approve while peer GitHub Checks were still pending.' "opencode approval requests changes when peer checks remain pending"
	assert_file_contains "$workflow_file" 'select((.status // "") != "COMPLETED")' "opencode approval treats incomplete check runs as approval blockers"
	assert_file_contains "$workflow_file" '["PENDING","EXPECTED"]' "opencode approval treats pending status contexts as approval blockers"
	assert_file_contains "$workflow_file" "<!-- opencode-review-overview -->" "opencode review publishes a durable Review Overview marker"
	assert_file_contains "$workflow_file" "## OpenCode Review Overview" "opencode review publishes a visible Review Overview heading"
	assert_file_contains "$workflow_file" 'gh api -X PATCH "repos/${GH_REPOSITORY}/issues/comments/${overview_comment_id}"' "opencode review updates an existing Review Overview comment instead of duplicating it"
	assert_file_contains "$workflow_file" "Exchange OpenCode app token for review writes" "opencode review obtains an app token before publishing review writes"
	assert_file_contains "$workflow_file" 'steps.opencode_app_token.outputs.token || secrets.OPENCODE_APPROVE_TOKEN || secrets.GITHUB_TOKEN' "opencode review prefers the OpenCode app token for PR review and overview writes"
	assert_file_contains "$workflow_file" 'opencode-agent[bot]' "opencode review can find overview comments written by the OpenCode app token"
	assert_file_contains "$workflow_file" 'update_review_overview()' "opencode approval step can rewrite the durable Review Overview after final gate decisions"
	assert_file_contains "$workflow_file" 'update_review_overview "$event" "$body"' "opencode approval reviews refresh the durable overview with the actual approval-step event"
	assert_file_contains "$workflow_file" 'env GH_TOKEN="$overview_comment_token"' "opencode approval overview updates use the workflow comment token"
	assert_file_contains "$workflow_file" 'warn_gh_publication_failure()' "opencode approval soft-fails PR review/comment publication errors"
	assert_file_contains "$workflow_file" 'OpenCode could not publish %s; continuing without review side effect.' "opencode approval explains permission-denied publication failures"
	assert_file_contains "$workflow_file" 'warn_gh_publication_failure "initial review overview lookup"' "opencode initial overview lookup soft-fails permission-denied publication errors"
	assert_file_contains "$workflow_file" 'warn_gh_publication_failure "initial review overview update"' "opencode initial overview update soft-fails permission-denied publication errors"
	assert_file_contains "$workflow_file" 'warn_gh_publication_failure "initial review overview comment"' "opencode initial overview comment soft-fails permission-denied publication errors"
	assert_file_contains "$workflow_file" 'warn_gh_publication_failure "pull review"' "opencode approval soft-fails permission-denied review publication"
	assert_file_contains "$workflow_file" 'warn_gh_publication_failure "review overview comment"' "opencode approval soft-fails permission-denied overview publication"
	assert_file_not_contains "$workflow_file" 'gh api -X DELETE "repos/${GH_REPOSITORY}/issues/comments/${comment_id}"' "opencode review must not delete Review Overview gate evidence"
	assert_file_not_contains "$workflow_file" '--file "$OPENCODE_EVIDENCE_FILE"' "opencode review must not attach evidence content to GitHub Models requests"
	assert_file_not_contains "$workflow_file" "opencode github run" "opencode review workflow must not use the oversized GitHub agent prompt path"
	assert_file_not_contains "$workflow_file" 'repos/${{ github.repository }}' "opencode review workflow must pass repository expressions through env before shell use"
	assert_file_contains "$workflow_file" "GH_REPOSITORY:" "opencode review workflow exports repository context through env"
	assert_file_contains "$workflow_file" 'repos/${GH_REPOSITORY}' "opencode review workflow uses env-backed repository context in shell commands"
	assert_file_contains "$workflow_file" "MODEL: github-models/openai/gpt-5" "opencode review tries GitHub Models GPT-5 first"
	assert_file_contains "$workflow_file" "MODEL: github-models/deepseek/deepseek-r1-0528" "opencode review falls back to a reachable DeepSeek R1 reasoning model"
	assert_file_contains "$workflow_file" "MODEL: github-models/deepseek/deepseek-v3-0324" "opencode review has a second reachable DeepSeek V3 fallback model"
	assert_file_contains "$workflow_file" "Publish bounded OpenCode review comment" "opencode review workflow publishes the agent control comment for the approval gate"
	assert_file_contains "$workflow_file" "statusCheckRollup" "opencode review workflow reads current-head GitHub Checks before approval"
	assert_file_contains "$workflow_file" "OPENCODE_FAILED_CHECK_EVIDENCE_FILE" "opencode review workflow persists failed-check evidence across review and approval steps"
	assert_file_contains "$workflow_file" "collect_failed_check_evidence.sh" "opencode review workflow collects failed check logs and annotations"
	assert_file_contains "$workflow_file" 'HEAD_SHA: ${{ github.event.pull_request.head.sha || github.event.inputs.pr_head_sha }}' "opencode evidence step passes HEAD_SHA to failed-check evidence collection"
	assert_file_contains "$workflow_file" "FAILED_CHECK_EVIDENCE_ATTEMPTS" "opencode review workflow bounds waiting for peer check failures before model review"
	assert_file_contains "$workflow_file" 'FAILED_CHECK_EVIDENCE_ATTEMPTS: "31"' "opencode review workflow waits long enough for slow Strix self-test failures"
	assert_file_contains "$workflow_file" "collect_failed_check_evidence_with_wait" "opencode review workflow waits briefly for failed checks before building model evidence"
	assert_file_contains "$workflow_file" "Failed-check evidence collector is not installed in this repository." "opencode review evidence handles repos without the failed-check helper instead of retrying a missing script"
	assert_file_contains "$workflow_file" "collect_failed_check_evidence_or_note()" "opencode approval handles repos without the failed-check helper before publishing fallback reviews"
	assert_file_contains "$workflow_file" "current_peer_checks_still_running" "opencode review workflow distinguishes pending peer checks from completed check state"
	assert_file_contains "$workflow_file" 'select((.name // "") != "opencode-review")' "opencode review evidence wait excludes its own check run"
	assert_file_contains "$workflow_file" 'select((.checkSuite.workflowRun.workflow.name // "") != "OpenCode PR Review")' "opencode review evidence wait excludes its own workflow"
	assert_file_contains "$workflow_file" "No completed failed GitHub Checks were present" "opencode review evidence wait retries while no failed checks are available yet"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" 'gh run view "$run_id"' "failed-check evidence collector reads failed GitHub Actions job logs"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" 'check-runs/${check_run_id}/annotations' "failed-check evidence collector reads GitHub Check annotations"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "Line-specific repair contract" "failed-check evidence requires line-specific repairs"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "Failed log signal summary" "failed-check evidence collector preserves fail/error signal lines outside bounded excerpts"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "Strix model attempt and finding summary" "failed-check evidence collector summarizes every Strix model attempt"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "Strix vulnerability report window" "failed-check evidence collector preserves Strix vulnerability report windows"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "When Strix logs contain multiple" "failed-check evidence collector requires all model-reported vulnerabilities"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "Create one OpenCode finding per Strix model vulnerability report" "failed-check evidence contract requires one finding per Strix model report"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "model name, title, severity, endpoint, and Code Locations/path:line evidence" "failed-check evidence collector names required Strix report fields"
	assert_file_contains "$workflow_file" "If bounded failed GitHub Check evidence contains active failed checks, treat it as a blocker until diagnosed." "opencode review prompt forces active failed-check diagnosis"
	assert_file_contains "$workflow_file" "A successful same-head manual workflow_dispatch Strix run may supersede a stale failed PR statusCheckRollup Strix context only when failed-check evidence explicitly lists it under Superseded failed checks with the exact target URL" "opencode review prompt allows only explicit same-head manual Strix evidence to supersede stale rollup failures"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "Superseded failed checks" "failed-check evidence lists stale failed contexts superseded by current-head manual Strix evidence"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "manual_success_contexts" "failed-check evidence compares explicit manual success statuses before active failures"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "No active failed GitHub Checks remained after superseded checks were classified" "failed-check evidence reports no active failures after stale contexts are superseded"
	assert_file_contains "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" "Strix vulnerability report window([[:space:]]|$)" "failed-check fallback detects numbered Strix vulnerability report windows with a POSIX ERE boundary"
	assert_file_not_contains "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" "Strix vulnerability report window\\\\b" "failed-check fallback must not rely on non-portable grep -E word boundaries"
	assert_file_not_contains "$workflow_file" "failed_check_evidence_has_active_failures" "opencode approval must treat collected failed rollup contexts as blockers"
	assert_file_not_contains "$workflow_file" "failed-check evidence showed only superseded failures" "opencode approval must not continue approval after failed PR rollup contexts"
	assert_file_not_contains "$workflow_file" "preserving model REQUEST_CHANGES" "opencode request-changes path must validate failed-check findings when failed rollup contexts exist"
	assert_file_contains "$workflow_file" "include every model-reported vulnerability as a separate evidence-backed finding" "opencode review prompt requires all Strix model findings"
	assert_file_contains "$workflow_file" "Multiple Strix model reports must not be collapsed" "opencode review prompt prevents collapsing multiple Strix model reports"
	assert_file_contains "$workflow_file" "One Strix model vulnerability report requires one distinct finding" "opencode review prompt requires one finding per Strix model report"
	assert_file_contains "$workflow_file" "model name, report title, severity, endpoint, and Code Locations/path:line evidence" "opencode review prompt preserves exact Strix report fields"
	assert_file_contains "$workflow_file" "Full failed-check evidence, when collected, is available as failed-check-evidence.md" "opencode review exposes full failed-check evidence for multiple Strix model reports without oversizing the prompt"
	assert_file_contains "$workflow_file" "Do not request changes with only a check URL, workflow name, or generic failure summary." "opencode review prompt forbids generic failed-check reviews"
	assert_file_contains "$workflow_file" "Failed-check findings must be line-specific and concrete" "opencode review prompt requires line-specific failed-check findings"
	assert_file_contains "$workflow_file" "never use line 0" "opencode review prompt forbids non-specific line 0 findings"
	assert_file_contains "$workflow_file" "The suggested_diff must be source-backed and GitHub suggestion-ready when possible: every removed line in the diff must exist in the cited current local file" "opencode review prompt forbids non-source-backed suggested diffs"
	assert_file_contains "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" '.line | type == "number" and . > 0 and floor == .' "opencode approval gate rejects line zero findings"
	assert_file_contains "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" '$p != "n/a" and $p != "unknown"' "opencode approval gate rejects placeholder finding paths"
	assert_file_contains "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" 'startswith("cannot provide diff")' "opencode approval gate rejects placeholder suggested diffs"
	assert_file_contains "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" "source_file.is_file()" "opencode approval gate requires finding paths to exist"
	assert_file_contains "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" "removed_line not in source_line_set" "opencode approval gate rejects suggested diffs that remove code absent from the cited file"
	assert_file_contains "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" "isinstance(line, bool)" "opencode normalizer rejects boolean line findings"
	assert_file_contains "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" "line <= 0" "opencode normalizer rejects line zero findings"
	assert_file_contains "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" "--check-structural-approval" "opencode approval gate delegates structural approval rejection to the normalizer"
	assert_file_not_contains "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" "structural exploration was not possible" "opencode approval gate does not duplicate structural failure phrases"
	assert_file_contains "$workflow_file" "validate_opencode_failed_check_review.sh" "opencode approval gate validates request-changes reviews against failed-check evidence"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "FAILED_CHECK_EVIDENCE_NOT_REFERENCED" "failed-check review validator rejects unrelated speculative findings"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "extract_strix_report_model_markers" "failed-check review validator extracts model markers from Strix vulnerability report windows"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "(?:model|for model)[[:space:]]+" "failed-check review validator reads both Model and for model lines inside Strix reports"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "Self-test Strix gate script" "failed-check review validator requires Strix failed step evidence"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "github.event.inputs.strix_llm" "failed-check review validator requires exact Strix missing assertion evidence"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "extract_strix_required_markers" "failed-check review validator extracts Strix report titles and locations"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "count_strix_review_findings" "failed-check review validator compares Strix reports to Strix-specific findings"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "validate_distinct_strix_report_findings" "failed-check review validator requires distinct findings for each Strix model report"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "used_findings" "failed-check review validator prevents one finding from satisfying multiple Strix reports"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "Severity: \$1" "failed-check review validator requires Strix severity evidence"
	assert_file_contains "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" "Location[[:space:]]+[0-9]+" "failed-check review validator requires Strix location evidence"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "RateLimitError" "failed-check evidence collector preserves Strix provider rate-limit failures"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "budget limit" "failed-check evidence collector preserves Strix provider budget failures"
	assert_file_contains "$REPO_ROOT/scripts/ci/collect_failed_check_evidence.sh" "completed as cancelled before GitHub emitted a failed job log" "failed-check evidence collector explains cancelled jobless Strix runs"
	assert_file_contains "$workflow_file" "emit_strix_provider_failure_finding" "opencode fallback review explains provider blockers without inventing code vulnerabilities"
	assert_file_contains "$workflow_file" 'extract_strix_failed_check_block "$evidence_file" "$strix_evidence_file"' "opencode fallback review scopes provider and cancellation diagnosis to extracted Strix failed-check evidence"
	assert_file_contains "$workflow_file" "STRIX_FALLBACK_MODELS:" "opencode provider fallback finding points at the concrete Strix fallback configuration line"
	assert_file_contains "$workflow_file" "emit_strix_cancelled_without_log_finding" "opencode fallback review explains cancelled Strix runs without inventing code vulnerabilities"
	assert_file_contains "$workflow_file" "Configured model and fallback models were unavailable" "opencode fallback review preserves exhausted Strix model evidence"
	assert_file_contains "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" '^CMD \["/app/scripts/docker_entrypoint\.sh"\]' "opencode failed-check fallback maps missing Docker entrypoint reports to the Dockerfile CMD line"
	assert_file_contains "$workflow_file" "Unrelated speculative findings are invalid when failed-check evidence is present." "opencode review prompt forbids unrelated failed-check findings"
	assert_file_contains "$workflow_file" "run_failed_check_diagnosis" "opencode approval gate reruns OpenCode diagnosis when checks fail after the initial review"
	assert_file_contains "$workflow_file" "OpenCode action outcomes were primary=" "opencode approval gate records invalid model outcome details"
	assert_file_contains "$workflow_file" "OpenCode model attempts did not produce a usable control block" "opencode approval gate reports invalid model output as a review-governance blocker"
	assert_file_contains "$workflow_file" "it will not approve without source-backed current-head review evidence" "opencode approval gate refuses to approve invalid model output when peer checks and human threads are clean"
	assert_file_contains "$workflow_file" "no valid source-backed review output was available" "opencode model-failure fallback requests changes instead of approving invalid model output"
	assert_file_contains "$workflow_file" "request_changes_for_merge_conflict_if_present" "opencode approval gate checks mergeability before approving model or fallback output"
	assert_file_contains "$workflow_file" "Merge Conflict Guidance" "opencode approval gate emits explicit conflict guidance when mergeability is dirty"
	assert_file_contains "$workflow_file" "flowchart LR" "opencode merge-conflict guidance includes a compact Mermaid graph"
	assert_file_contains "$workflow_file" "Failed check evidence for line-specific fixes" "opencode approval gate includes failed-check evidence when diagnosis cannot complete"
	assert_file_contains "$workflow_file" "emit_line_specific_fallback_findings" "opencode failed-check fallback maps known Strix failures to source lines"
	assert_file_contains "$workflow_file" 'repo_root="${GITHUB_WORKSPACE:-$PWD}"' "opencode failed-check fallback maps source lines from the repository root"
	assert_file_contains "$workflow_file" "## Findings" "opencode failed-check fallback publishes line-specific repair findings"
	assert_file_contains "$workflow_file" "emit_opencode_failed_check_fallback_findings.sh" "opencode failed-check fallback delegates deterministic Strix report expansion to tested helper"
	assert_file_contains "$workflow_file" "OpenCode failed-check fallback helper exited non-zero; using inline fallback." "opencode failed-check fallback handles helper failures without aborting under set -e"
	assert_file_contains "$workflow_file" "Do not depend on Copilot Review, CodeRabbitAI, or any human reviewer" "opencode review format is independent of other review agents"
	assert_file_contains "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" "emit_strix_report_findings" "failed-check fallback emits every Strix vulnerability report as a separate finding"
	assert_file_contains "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" "Strix provider signal left current-head security evidence incomplete" "failed-check fallback does not claim reports are absent after Strix emitted vulnerabilities"
	assert_file_contains "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" "cancelled pull_request_target run still used the base branch copies" "failed-check fallback explains trusted-base Strix workflow semantics for self-modifying PRs"
	assert_file_contains "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" "get_validated_pr_diff_range" "failed-check fallback validates PR diff range before comparing trusted Strix inputs"
	assert_file_contains "$workflow_file" ".github/workflows/strix.yml" "opencode inline fallback watches Strix workflow changes"
	assert_file_contains "$workflow_file" "scripts/ci/strix_quick_gate.sh" "opencode inline fallback watches trusted Strix gate changes"
	assert_file_contains "$workflow_file" "scripts/ci/test_strix_quick_gate.sh" "opencode inline fallback watches trusted Strix self-test changes"
	assert_file_contains "$workflow_file" "requirements-strix-ci.txt" "opencode inline fallback watches trusted Strix dependency changes"
	assert_file_contains "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" "Strix provider failure blocked current-head security evidence" "failed-check fallback does not label non-quota provider routing/auth failures as quota"
	assert_file_not_contains "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" "Strix provider quota blocked current-head security evidence" "failed-check fallback avoids misleading quota-only provider blocker title"
	assert_file_contains "$workflow_file" "- Root cause:" "opencode review request-changes body includes root cause per finding"
	assert_file_contains "$workflow_file" "- Regression test:" "opencode review request-changes body includes regression test direction per finding"
	assert_file_contains "$workflow_file" "- Suggested diff:" "opencode review request-changes body includes suggested diff per finding"
	assert_file_contains "$workflow_file" "OpenCode reviewed the current-head bounded evidence and found failing GitHub Checks that need source-backed diagnosis before merge." "opencode review workflow requests changes when current-head GitHub Checks failed"
	assert_file_contains "$workflow_file" "OpenCode reviewed the current-head evidence but could not verify peer GitHub Checks before approval." "opencode review workflow explains check lookup failures instead of approving"
	assert_file_contains "$workflow_file" '["FAILURE","TIMED_OUT","ACTION_REQUIRED","CANCELLED","STARTUP_FAILURE"]' "opencode review workflow treats failed check-run conclusions as request-changes blockers"
	assert_file_contains "$workflow_file" '["FAILURE","ERROR"]' "opencode review workflow treats failed status contexts as request-changes blockers"
	assert_file_not_contains "$workflow_file" "MODEL: github-models/gpt-4.1" "opencode review must not fall back to GPT-4.1"
	assert_file_not_contains "$workflow_file" "MODEL: github-models/openai/gpt-5-chat" "opencode review must not use unavailable GitHub Models GPT-5 chat fallback"
	assert_file_not_contains "$workflow_file" "MODEL: github-models/openai/gpt-5-mini" "opencode review must not use unavailable GitHub Models GPT-5 mini fallback"

	assert_file_contains "$opencode_config" '"mcp"' "opencode config declares MCP servers"
	assert_file_contains "$opencode_config" '"codegraph"' "opencode config declares the CodeGraph MCP server"
	assert_file_contains "$opencode_config" '"deepwiki"' "opencode config declares the DeepWiki MCP server"
	assert_file_contains "$opencode_config" '"context7"' "opencode config declares the Context7 MCP server"
	assert_file_contains "$opencode_config" '"web_search"' "opencode config declares the web search MCP server"
	assert_file_contains "$opencode_config" '"url": "https://mcp.deepwiki.com/mcp"' "opencode config points DeepWiki at the official remote MCP endpoint"
	assert_file_contains "$opencode_config" '"@upstash/context7-mcp@3.1.0"' "opencode config pins the Context7 MCP package"
	assert_file_contains "$opencode_config" '"@guhcostan/web-search-mcp@1.0.5"' "opencode config pins the web search MCP package"
	assert_file_contains "$opencode_config" '"serve", "--mcp"' "opencode config launches CodeGraph in MCP mode"
	assert_file_contains "$opencode_config" '"small_model": "github-models/deepseek/deepseek-v3-0324"' "opencode config uses a reachable DeepSeek V3 small model"
	assert_file_contains "$opencode_config" '"openai/gpt-5"' "opencode config defines GitHub Models GPT-5 with full model id"
	assert_file_contains "$opencode_config" '"deepseek/deepseek-r1-0528"' "opencode config defines DeepSeek R1 fallback"
	assert_file_contains "$opencode_config" '"deepseek/deepseek-v3-0324"' "opencode config defines DeepSeek V3 fallback"
	assert_file_contains "$opencode_config" '"context": 200000' "opencode config uses the GitHub Models GPT-5 200k context window"
	assert_file_contains "$opencode_config" '"output": 100000' "opencode config uses the GitHub Models GPT-5 100k output window"
	assert_file_not_contains "$opencode_config" "gpt-4.1" "opencode config must not define GPT-4.1 fallback"
	assert_file_not_contains "$opencode_config" "gpt-5-chat" "opencode config must not define unavailable GPT-5 chat fallback"
	assert_file_not_contains "$opencode_config" "gpt-5-mini" "opencode config must not define unavailable GPT-5 mini fallback"
}

assert_opencode_review_posts_suggested_diffs_inline() {
	local workflow_file="$REPO_ROOT/.github/workflows/opencode-review.yml"

	assert_file_contains "$workflow_file" "create_pull_review_with_payload" "opencode review can post custom review payloads"
	assert_file_contains "$workflow_file" "comments: [" "opencode review payload includes inline review comments"
	assert_file_contains "$workflow_file" '#### Suggested diff\n```diff\n' "opencode review puts suggested diffs inside inline review comments"
	assert_file_contains "$workflow_file" "GitHub did not accept the inline review comments" "opencode review explains anchor failures instead of copying diffs to the PR body"
	assert_file_contains "$workflow_file" "publish_request_changes_from_control" "opencode review REQUEST_CHANGES path publishes findings from the control JSON"

	if awk '/format_request_changes_body\(\)/,/build_request_changes_review_payload\(\)/ { print }' "$workflow_file" |
		grep -Fq '```diff'; then
		record_failure "opencode review PR-level REQUEST_CHANGES body must not contain fenced suggested diffs"
	fi
}

assert_opencode_review_normalizer_accepts_transcript_json() {
	local tmp_dir
	local output_file
	local rc
	local gate_result
	tmp_dir="$(mktemp -d)"
	output_file="$tmp_dir/opencode-output.md"

	cat >"$output_file" <<'EOF'
OpenCode transcript text before the review control block.

{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"APPROVE","reason":"No blockers found after inspecting .github/workflows/opencode-review.yml.","summary":"Reviewed scripts/ci/opencode_review_normalize_output.py, scripts/ci/test_strix_quick_gate.sh, and current head evidence; no blocking review findings were identified.","findings":[]}
EOF

	set +e
	python3 "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" \
		"abc123" "42" "1" "$output_file" >"$tmp_dir/normalize.out" 2>"$tmp_dir/normalize.err"
	rc=$?
	set -e

	assert_equals "0" "$rc" "opencode review normalizer accepts transcript-embedded current-run JSON"
	assert_file_contains "$output_file" "<!-- opencode-review-gate head_sha=abc123 run_id=42 run_attempt=1 -->" "opencode review normalizer writes the gate sentinel"
	assert_file_contains "$output_file" "<!-- opencode-review-control-v1" "opencode review normalizer writes the control block"

	set +e
	gate_result="$(
		bash "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" \
			"abc123" "42" "1" "$output_file"
	)"
	rc=$?
	set -e

	assert_equals "0" "$rc" "normalized OpenCode transcript passes approval gate"
	assert_equals "APPROVE" "$gate_result" "normalized OpenCode transcript gate result"

	rm -rf "$tmp_dir"
}

assert_opencode_review_publish_body_discards_trailing_model_prose() {
	local tmp_dir
	local output_file
	local normalized_json
	local comment_body_file
	local gate_result
	local rc
	local sentinel
	tmp_dir="$(mktemp -d)"
	output_file="$tmp_dir/opencode-output.md"
	normalized_json="$tmp_dir/control.json"
	comment_body_file="$tmp_dir/comment-body.md"
	sentinel="<!-- opencode-review-gate head_sha=abc123 run_id=42 run_attempt=1 -->"

	cat >"$output_file" <<'EOF'
<!-- opencode-review-gate head_sha=abc123 run_id=42 run_attempt=1 -->

<!-- opencode-review-control-v1
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"APPROVE","reason":"No blockers found after inspecting .github/workflows/opencode-review.yml.","summary":"Reviewed scripts/ci/opencode_review_normalize_output.py, scripts/ci/test_strix_quick_gate.sh, and current head evidence; no blocking review findings were identified.","findings":[]}
-->

But that is not meticulous.

We should request changes.
EOF

	set +e
	gate_result="$(
		bash "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" \
			"abc123" "42" "1" "$output_file" "$normalized_json"
	)"
	rc=$?
	set -e

	assert_equals "0" "$rc" "opencode publish sanitizer accepts the first valid control block"
	assert_equals "APPROVE" "$gate_result" "opencode publish sanitizer preserves the valid gate result"

	{
		printf '%s\n\n' "$sentinel"
		printf '<!-- opencode-review-control-v1\n'
		cat "$normalized_json"
		printf -- '-->\n'
	} >"$comment_body_file"

	assert_file_contains "$comment_body_file" '"result":"APPROVE"' "opencode publish sanitizer keeps normalized approval JSON"
	assert_file_not_contains "$comment_body_file" "But that is not meticulous." "opencode publish sanitizer drops trailing model prose"
	assert_file_not_contains "$comment_body_file" "We should request changes." "opencode publish sanitizer drops contradictory trailing model prose"

	rm -rf "$tmp_dir"
}

assert_opencode_review_gate_rejects_missing_structural_exploration_approval() {
	local tmp_dir
	local output_file
	local rc
	local gate_result
	tmp_dir="$(mktemp -d)"
	output_file="$tmp_dir/opencode-output.md"

	cat >"$output_file" <<'EOF'
OpenCode transcript text before the review control block.

{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"APPROVE","reason":"No blockers found, but structural exploration was not possible.","summary":"This docs-only PR does not require structural review and the evidence was truncated.","findings":[]}
EOF

	set +e
	python3 "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" \
		"abc123" "42" "1" "$output_file" >"$tmp_dir/normalize.out" 2>"$tmp_dir/normalize.err"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode normalizer rejects approvals that admit missing structural exploration"
	assert_file_contains "$tmp_dir/normalize.err" "NO_CONCLUSION" "opencode normalizer reports no valid conclusion for missing structural exploration"

	cat >"$output_file" <<'EOF'
<!-- opencode-review-gate head_sha=abc123 run_id=42 run_attempt=1 -->

<!-- opencode-review-control-v1
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"APPROVE","reason":"No blockers found, but structural exploration was not possible.","summary":"This docs-only PR does not require structural review and the evidence was truncated.","findings":[]}
-->
EOF

	set +e
	gate_result="$(
		bash "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" \
			"abc123" "42" "1" "$output_file"
	)"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode approval gate rejects approvals that admit missing structural exploration"
	assert_equals "NO_CONCLUSION" "$gate_result" "missing structural exploration rejection gate result"

	cat >"$output_file" <<'EOF'
OpenCode transcript text before the review control block.

{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"APPROVE","reason":"No blockers found after structural exploration of changed files.","summary":"CodeGraph evidence was insufficient for one generated artifact, but local inspection covered the changed workflow, scripts, and tests.","findings":[]}
EOF

	set +e
	python3 "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" \
		"abc123" "42" "1" "$output_file" >"$tmp_dir/normalize-valid.out" 2>"$tmp_dir/normalize-valid.err"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode normalizer rejects approvals that omit concrete changed-file evidence"

	cat >"$output_file" <<'EOF'
OpenCode transcript text before the review control block.

{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"APPROVE","reason":"No blockers found after structural exploration of .github/workflows/opencode-review.yml.","summary":"CodeGraph evidence was insufficient for one generated artifact, but local inspection covered scripts/ci/test_strix_quick_gate.sh and the changed workflow.","findings":[]}
EOF

	set +e
	python3 "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" \
		"abc123" "42" "1" "$output_file" >"$tmp_dir/normalize-valid.out" 2>"$tmp_dir/normalize-valid.err"
	rc=$?
	set -e

	assert_equals "0" "$rc" "opencode normalizer accepts approvals that name concrete changed-file evidence after structural inspection"

	rm -rf "$tmp_dir"
}

assert_opencode_review_gate_rejects_no_changes_approval() {
	local tmp_dir
	local output_file
	local rc
	local gate_result
	tmp_dir="$(mktemp -d)"
	output_file="$tmp_dir/opencode-output.md"

	cat >"$output_file" <<'EOF'
OpenCode transcript text before the review control block.

{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"APPROVE","reason":"No changes detected in the PR head source directory.","summary":"No files or changes were found in the PR head source directory, indicating no actionable changes to review.","findings":[]}
EOF

	set +e
	python3 "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" \
		"abc123" "42" "1" "$output_file" >"$tmp_dir/normalize.out" 2>"$tmp_dir/normalize.err"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode normalizer rejects no-changes approvals"
	assert_file_contains "$tmp_dir/normalize.err" "NO_CONCLUSION" "opencode normalizer reports no valid conclusion for no-changes approval"

	cat >"$output_file" <<'EOF'
<!-- opencode-review-gate head_sha=abc123 run_id=42 run_attempt=1 -->

<!-- opencode-review-control-v1
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"APPROVE","reason":"No changes detected in the PR head source directory.","summary":"No files or changes were found in the PR head source directory, indicating no actionable changes to review.","findings":[]}
-->
EOF

	set +e
	gate_result="$(
		bash "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" \
			"abc123" "42" "1" "$output_file"
	)"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode approval gate rejects no-changes approvals"
	assert_equals "NO_CONCLUSION" "$gate_result" "no-changes approval rejection gate result"
	assert_file_contains "$REPO_ROOT/.github/workflows/opencode-review.yml" "Never approve with a reason or summary that says no changes" "opencode prompt rejects no-changes approvals when bounded evidence lists changed files"

	rm -rf "$tmp_dir"
}

assert_opencode_review_gate_rejects_approve_without_changed_file_evidence() {
	local tmp_dir
	local output_file
	local rc
	local gate_result
	tmp_dir="$(mktemp -d)"
	output_file="$tmp_dir/opencode-output.md"

	cat >"$output_file" <<'EOF'
OpenCode transcript text before the review control block.

{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"APPROVE","reason":"No blocking issues found; changes improve CI configuration and documentation.","summary":"PR enhances OpenCode review workflow with clearer guidance and validation. Changes are well-contained with no security or functional regressions detected.","findings":[]}
EOF

	set +e
	python3 "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" \
		"abc123" "42" "1" "$output_file" >"$tmp_dir/normalize.out" 2>"$tmp_dir/normalize.err"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode normalizer rejects approvals without changed-file evidence"
	assert_file_contains "$tmp_dir/normalize.err" "NO_CONCLUSION" "opencode normalizer reports no valid conclusion for approvals without changed-file evidence"

	cat >"$output_file" <<'EOF'
<!-- opencode-review-gate head_sha=abc123 run_id=42 run_attempt=1 -->

<!-- opencode-review-control-v1
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"APPROVE","reason":"No blocking issues found; changes improve CI configuration and documentation.","summary":"PR enhances OpenCode review workflow with clearer guidance and validation. Changes are well-contained with no security or functional regressions detected.","findings":[]}
-->
EOF

	set +e
	gate_result="$(
		bash "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" \
			"abc123" "42" "1" "$output_file"
	)"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode approval gate rejects approvals without changed-file evidence"
	assert_equals "NO_CONCLUSION" "$gate_result" "missing changed-file evidence rejection gate result"
	assert_file_contains "$REPO_ROOT/.github/workflows/opencode-review.yml" "Before APPROVE, the summary must include at least one exact changed file path inspected as changed-file evidence" "opencode prompt requires changed-file evidence before approval"

	rm -rf "$tmp_dir"
}

assert_opencode_review_gate_rejects_line_zero_findings() {
	local tmp_dir
	local output_file
	local rc
	local gate_result
	tmp_dir="$(mktemp -d)"
	output_file="$tmp_dir/opencode-output.md"

	cat >"$output_file" <<'EOF'
<!-- opencode-review-gate head_sha=abc123 run_id=42 run_attempt=1 -->

<!-- opencode-review-control-v1
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"REQUEST_CHANGES","reason":"Generic blocker","summary":"Generic finding with no real source line.","findings":[{"path":"scripts/ci/example.sh","line":0,"severity":"HIGH","title":"Generic finding","problem":"Line zero is not actionable.","root_cause":"The review did not inspect a concrete line.","fix_direction":"Inspect the actual file and cite a positive line number.","regression_test_direction":"Add a gate test for line zero rejection.","suggested_diff":"diff --git a/scripts/ci/example.sh b/scripts/ci/example.sh\n--- a/scripts/ci/example.sh\n+++ b/scripts/ci/example.sh\n@@ -1 +1 @@\n-old\n+new"}]}
-->
EOF

	set +e
	gate_result="$(
		bash "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" \
			"abc123" "42" "1" "$output_file"
	)"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode approval gate rejects line zero findings"
	assert_equals "NO_CONCLUSION" "$gate_result" "line zero rejection gate result"

	set +e
	python3 "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" \
		"abc123" "42" "1" "$output_file" >"$tmp_dir/normalize.out" 2>"$tmp_dir/normalize.err"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode normalizer rejects line zero findings"
	assert_file_contains "$tmp_dir/normalize.err" "NO_CONCLUSION" "opencode normalizer reports no valid conclusion for line zero findings"

	cat >"$output_file" <<'EOF'
OpenCode transcript text before the review control block.

{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"REQUEST_CHANGES","reason":"Boolean line blocker","summary":"Boolean line values are not concrete source locations.","findings":[{"path":"scripts/ci/example.sh","line":true,"severity":"HIGH","title":"Boolean line","problem":"Boolean line values are not actionable.","root_cause":"The review did not inspect a concrete line.","fix_direction":"Inspect the actual file and cite a positive integer line number.","regression_test_direction":"Add a gate test for boolean line rejection.","suggested_diff":"diff --git a/scripts/ci/example.sh b/scripts/ci/example.sh\n--- a/scripts/ci/example.sh\n+++ b/scripts/ci/example.sh\n@@ -1 +1 @@\n-old\n+new"}]}
EOF

	set +e
	python3 "$REPO_ROOT/scripts/ci/opencode_review_normalize_output.py" \
		"abc123" "42" "1" "$output_file" >"$tmp_dir/bool-line.out" 2>"$tmp_dir/bool-line.err"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode normalizer rejects boolean line findings"
	assert_file_contains "$tmp_dir/bool-line.err" "NO_CONCLUSION" "opencode normalizer reports no valid conclusion for boolean line findings"

	rm -rf "$tmp_dir"
}

assert_opencode_review_gate_rejects_placeholder_findings() {
	local tmp_dir
	local output_file
	local rc
	local gate_result
	tmp_dir="$(mktemp -d)"
	output_file="$tmp_dir/opencode-output.md"

	cat >"$output_file" <<'EOF'
<!-- opencode-review-gate head_sha=abc123 run_id=42 run_attempt=1 -->

<!-- opencode-review-control-v1
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"REQUEST_CHANGES","reason":"File inaccessible","summary":"Bogus inaccessible finding.","findings":[{"path":"N/A","line":1,"severity":"BLOCKER","title":"Missing file","problem":"File inaccessible.","root_cause":"The review did not inspect focused hunks.","fix_direction":"Make files accessible.","regression_test_direction":"Add coverage.","suggested_diff":"Cannot provide diff - original file inaccessible"}]}
-->
EOF

	set +e
	gate_result="$(
		bash "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" \
			"abc123" "42" "1" "$output_file"
	)"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode approval gate rejects placeholder findings"
	assert_equals "NO_CONCLUSION" "$gate_result" "placeholder finding rejection gate result"

	rm -rf "$tmp_dir"
}

assert_opencode_review_gate_rejects_non_source_backed_findings() {
	local tmp_dir
	local output_file
	local rc
	local gate_result
	tmp_dir="$(mktemp -d)"
	output_file="$tmp_dir/opencode-output.md"

	cat >"$output_file" <<'EOF'
<!-- opencode-review-gate head_sha=abc123 run_id=42 run_attempt=1 -->

<!-- opencode-review-control-v1
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"REQUEST_CHANGES","reason":"Hallucinated blocker","summary":"Finding cites code that is not present in the source file.","findings":[{"path":"scripts/ci/opencode_review_approve_gate.sh","line":1,"severity":"HIGH","title":"Non-source-backed finding","problem":"The finding removes a line that is not in the cited file.","root_cause":"The review did not inspect current source before suggesting a diff.","fix_direction":"Only cite lines present in the current source.","regression_test_direction":"Reject request-changes findings whose removed diff lines are absent from the cited file.","suggested_diff":"diff --git a/scripts/ci/opencode_review_approve_gate.sh b/scripts/ci/opencode_review_approve_gate.sh\n--- a/scripts/ci/opencode_review_approve_gate.sh\n+++ b/scripts/ci/opencode_review_approve_gate.sh\n@@ -1 +1 @@\n-  return Math.random().toString(36)\n+  return crypto.getRandomValues(new Uint8Array(32))"}]}
-->
EOF

	set +e
	gate_result="$(
		bash "$REPO_ROOT/scripts/ci/opencode_review_approve_gate.sh" \
			"abc123" "42" "1" "$output_file"
	)"
	rc=$?
	set -e

	assert_equals "4" "$rc" "opencode approval gate rejects non-source-backed findings"
	assert_equals "NO_CONCLUSION" "$gate_result" "non-source-backed finding rejection gate result"

	rm -rf "$tmp_dir"
}

assert_opencode_failed_check_review_validator_rejects_unrelated_findings() {
	local tmp_dir
	local control_json
	local failed_checks_file
	local evidence_file
	local rc
	tmp_dir="$(mktemp -d)"
	control_json="$tmp_dir/control.json"
	failed_checks_file="$tmp_dir/failed-checks.txt"
	evidence_file="$tmp_dir/failed-check-evidence.md"

	cat >"$failed_checks_file" <<'EOF'
- Strix Security Scan/strix: FAILURE (https://github.com/example/repo/actions/runs/1/job/2)
EOF
	cat >"$evidence_file" <<'EOF'
## Failed check: Strix Security Scan/strix

### Failed job steps

- step 6: Self-test Strix gate script (failure)

### Strix vulnerability report window 1

Model github-models/openai/gpt-5 Vulnerabilities 1
│  Vulnerability Report                                                        │
│  Title: Authentication Bypass via X-Dev-User Header                          │
│  Severity: CRITICAL                                                          │
│  Endpoint: /api/me                                                           │
│  Method: GET                                                                 │
│    Location 1: backend/app/auth.py:132-135                                   │

### Strix vulnerability report window 2

Model deepseek/deepseek-v3-0324 Vulnerabilities 1
│  Vulnerability Report                                                        │
│  Title: Frontend Security Issues: XSS, Hardcoded Credentials, and Insecure   │
│  Severity: HIGH                                                              │

### Failed log excerpt

FAIL: strix workflow defaults PR Strix scans to GitHub Models GPT-5 (missing 'github.event.inputs.strix_llm || 'openai/gpt-5'')
FAIL: strix workflow rejects unsupported model inputs (missing 'STRIX_LLM must select GitHub Models openai/gpt-5 or newer, direct OpenAI GPT-5.4 or newer, or an approved organization Vertex AI model')
FAIL: opencode review tries GitHub Models GPT-5 first (missing 'MODEL: github-models/openai/gpt-5')
EOF
	cat >"$control_json" <<'EOF'
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"REQUEST_CHANGES","reason":"Generic security concern","summary":"Generic speculative CI issues.","findings":[{"path":"scripts/ci/collect_failed_check_evidence.sh","line":15,"severity":"HIGH","title":"Generic finding","problem":"Speculative input validation issue unrelated to failed checks.","root_cause":"The review did not use the failed Strix evidence.","fix_direction":"Add generic validation.","regression_test_direction":"Add a generic test.","suggested_diff":"diff --git a/scripts/ci/collect_failed_check_evidence.sh b/scripts/ci/collect_failed_check_evidence.sh\n--- a/scripts/ci/collect_failed_check_evidence.sh\n+++ b/scripts/ci/collect_failed_check_evidence.sh\n@@ -1 +1 @@\n-old\n+new"}]}
EOF

	set +e
	bash "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" \
		"$control_json" "$failed_checks_file" "$evidence_file" >"$tmp_dir/bad.out" 2>"$tmp_dir/bad.err"
	rc=$?
	set -e
	assert_equals "4" "$rc" "failed-check review validator rejects unrelated findings"
	assert_file_contains "$tmp_dir/bad.out" "FAILED_CHECK_EVIDENCE_NOT_REFERENCED" "failed-check validator explains unrelated finding rejection"

	cat >"$evidence_file" <<'EOF'
## Failed check: Strix Security Scan/strix

### Strix vulnerability report window 1

Model github-models/openai/gpt-5 Vulnerabilities 1
│  Vulnerability Report                                                        │
│  Title: Authentication Bypass via X-Dev-User Header                          │
│  Severity: CRITICAL                                                          │
│  Endpoint: /api/me                                                           │
│  Method: GET                                                                 │
│    Location 1: backend/app/auth.py:132-135                                   │

### Strix vulnerability report window 2

Model deepseek/deepseek-v3-0324 Vulnerabilities 1
│  Vulnerability Report                                                        │
│  Title: Authentication Bypass via X-Dev-User Header                          │
│  Severity: CRITICAL                                                          │
│  Endpoint: /api/me                                                           │
│  Method: GET                                                                 │
│    Location 1: backend/app/auth.py:132-135                                   │
EOF
	cat >"$control_json" <<'EOF'
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"REQUEST_CHANGES","reason":"Strix Security Scan/strix failed","summary":"Strix Security Scan/strix failed and reported github-models/openai/gpt-5 plus deepseek/deepseek-v3-0324 Authentication Bypass via X-Dev-User Header with Severity: CRITICAL, /api/me, Method: GET, backend/app/auth.py:132-135.","findings":[{"path":"backend/app/auth.py","line":132,"severity":"CRITICAL","title":"Authentication Bypass via X-Dev-User Header","problem":"Strix Security Scan/strix failed with github-models/openai/gpt-5 and deepseek/deepseek-v3-0324 reports for Authentication Bypass via X-Dev-User Header, Severity: CRITICAL, /api/me, Method: GET, backend/app/auth.py:132-135.","root_cause":"The review collapsed two Strix model reports into one finding.","fix_direction":"Remove the unauthenticated fallback at backend/app/auth.py:132-135.","regression_test_direction":"Add auth tests for both request paths.","suggested_diff":"diff --git a/backend/app/auth.py b/backend/app/auth.py\n--- a/backend/app/auth.py\n+++ b/backend/app/auth.py\n@@ -132 +132 @@\n-old\n+new"}]}
EOF
	set +e
	bash "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" \
		"$control_json" "$failed_checks_file" "$evidence_file" >"$tmp_dir/collapsed.out" 2>"$tmp_dir/collapsed.err"
	rc=$?
	set -e
	assert_equals "4" "$rc" "failed-check review validator rejects collapsed duplicate Strix model reports"
	assert_file_contains "$tmp_dir/collapsed.out" "FAILED_CHECK_EVIDENCE_NOT_REFERENCED" "failed-check validator requires one Strix-specific finding per model report"

	cat >"$control_json" <<'EOF'
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"REQUEST_CHANGES","reason":"Strix Security Scan/strix failed","summary":"Strix Security Scan/strix failed and mentioned github-models/openai/gpt-5 plus deepseek/deepseek-v3-0324, but the model reports were still collapsed.","findings":[{"path":".github/workflows/strix.yml","line":120,"severity":"HIGH","title":"Strix self-test failed","problem":"Strix Security Scan/strix failed in Self-test Strix gate script while github-models/openai/gpt-5 and deepseek/deepseek-v3-0324 model reports were present elsewhere in the evidence.","root_cause":"The workflow finding is about CI self-test evidence, not a distinct model vulnerability report.","fix_direction":"Fix the workflow default.","regression_test_direction":"Keep the self-test assertion.","suggested_diff":"diff --git a/.github/workflows/strix.yml b/.github/workflows/strix.yml\n--- a/.github/workflows/strix.yml\n+++ b/.github/workflows/strix.yml\n@@ -120 +120 @@\n-old\n+new"},{"path":"backend/app/auth.py","line":132,"severity":"CRITICAL","title":"Authentication Bypass via X-Dev-User Header","problem":"Strix Security Scan/strix failed with github-models/openai/gpt-5 and deepseek/deepseek-v3-0324 reports for Authentication Bypass via X-Dev-User Header, Severity: CRITICAL, /api/me, Method: GET, backend/app/auth.py:132-135.","root_cause":"This finding still collapses two Strix model reports into one item even though the titles and locations match.","fix_direction":"Remove the unauthenticated fallback at backend/app/auth.py:132-135.","regression_test_direction":"Add auth tests for both request paths.","suggested_diff":"diff --git a/backend/app/auth.py b/backend/app/auth.py\n--- a/backend/app/auth.py\n+++ b/backend/app/auth.py\n@@ -132 +132 @@\n-old\n+new"}]}
EOF
	set +e
	bash "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" \
		"$control_json" "$failed_checks_file" "$evidence_file" >"$tmp_dir/collapsed-with-count.out" 2>"$tmp_dir/collapsed-with-count.err"
	rc=$?
	set -e
	assert_equals "4" "$rc" "failed-check review validator rejects collapsed Strix reports even when finding count matches"
	assert_file_contains "$tmp_dir/collapsed-with-count.out" "FAILED_CHECK_EVIDENCE_NOT_REFERENCED" "failed-check validator requires distinct matching findings, not only matching counts"

	cat >"$evidence_file" <<'EOF'
## Failed check: Strix Security Scan/strix

### Failed job steps

- step 6: Self-test Strix gate script (failure)

### Strix vulnerability report window 1

Model github-models/openai/gpt-5 Vulnerabilities 1
│  Vulnerability Report                                                        │
│  Title: Authentication Bypass via X-Dev-User Header                          │
│  Severity: CRITICAL                                                          │
│  Endpoint: /api/me                                                           │
│  Method: GET                                                                 │
│    Location 1: backend/app/auth.py:132-135                                   │

### Strix vulnerability report window 2

Model deepseek/deepseek-v3-0324 Vulnerabilities 1
│  Vulnerability Report                                                        │
│  Title: Frontend Security Issues: XSS, Hardcoded Credentials, and Insecure   │
│  Severity: HIGH                                                              │

### Failed log excerpt

FAIL: strix workflow defaults PR Strix scans to GitHub Models GPT-5 (missing 'github.event.inputs.strix_llm || 'openai/gpt-5'')
FAIL: strix workflow rejects unsupported model inputs (missing 'STRIX_LLM must select GitHub Models openai/gpt-5 or newer, direct OpenAI GPT-5.4 or newer, or an approved organization Vertex AI model')
FAIL: opencode review tries GitHub Models GPT-5 first (missing 'MODEL: github-models/openai/gpt-5')
EOF

	cat >"$control_json" <<'EOF'
{"head_sha":"abc123","run_id":"42","run_attempt":"1","result":"REQUEST_CHANGES","reason":"Strix Security Scan/strix failed","summary":"Strix Security Scan/strix failed in Self-test Strix gate script and reported github-models/openai/gpt-5 Authentication Bypass via X-Dev-User Header with Severity: CRITICAL at backend/app/auth.py:132-135 plus deepseek/deepseek-v3-0324 Frontend Security Issues: XSS, Hardcoded Credentials, and Insecure with Severity: HIGH.","findings":[{"path":".github/workflows/strix.yml","line":120,"severity":"HIGH","title":"Strix workflow default is not visible to trusted self-test","problem":"Strix Security Scan/strix failed in Self-test Strix gate script: strix workflow defaults PR Strix scans to GitHub Models GPT-5 (missing 'github.event.inputs.strix_llm || 'openai/gpt-5''); strix workflow rejects unsupported model inputs (missing 'STRIX_LLM must select GitHub Models openai/gpt-5 or newer, direct OpenAI GPT-5.4 or newer, or an approved organization Vertex AI model'); opencode review tries GitHub Models GPT-5 first (missing 'MODEL: github-models/openai/gpt-5'). The same failed Strix evidence includes github-models/openai/gpt-5 report Authentication Bypass via X-Dev-User Header, Severity: CRITICAL, /api/me, Method: GET, backend/app/auth.py:132-135.","root_cause":"The failed check evidence shows Self-test Strix gate script could not find github.event.inputs.strix_llm, STRIX_LLM must select, and MODEL: github-models/openai/gpt-5 in trusted-base files, and the model report identifies the backend auth fallback line.","fix_direction":"Update the workflow lines that provide the Strix model default and OpenCode model env so the trusted self-test can find those exact strings, then remove the unauthenticated X-Dev-User fallback at backend/app/auth.py:132-135.","regression_test_direction":"Keep the static self-test assertions for all three missing strings and add auth tests proving /api/me rejects forged X-Dev-User requests without signed auth.","suggested_diff":"diff --git a/.github/workflows/strix.yml b/.github/workflows/strix.yml\n--- a/.github/workflows/strix.yml\n+++ b/.github/workflows/strix.yml\n@@ -120 +120 @@\n-          STRIX_MODEL: old\n+          STRIX_MODEL: ${{ github.event.inputs.strix_llm || 'openai/gpt-5' }}"},{"path":"frontend/src/app/page.tsx","line":1,"severity":"HIGH","title":"Strix frontend model report must be reviewed separately","problem":"Strix Security Scan/strix failed with a separate deepseek/deepseek-v3-0324 report: Frontend Security Issues: XSS, Hardcoded Credentials, and Insecure, Severity: HIGH.","root_cause":"The failed Strix evidence contains a second model vulnerability report, so OpenCode must not collapse it into the first backend finding.","fix_direction":"Inspect the frontend source lines responsible for token storage, hardcoded credentials, dynamic error rendering, and missing CSP, then remove or harden each concrete line before approval.","regression_test_direction":"Add frontend tests covering safe token/session handling, output encoding, and security headers for the affected route.","suggested_diff":"diff --git a/frontend/src/app/page.tsx b/frontend/src/app/page.tsx\n--- a/frontend/src/app/page.tsx\n+++ b/frontend/src/app/page.tsx\n@@ -1 +1 @@\n-export default function Page() { return null }\n+export default function Page() { return null }"}]}
EOF
	set +e
	bash "$REPO_ROOT/scripts/ci/validate_opencode_failed_check_review.sh" \
		"$control_json" "$failed_checks_file" "$evidence_file" >"$tmp_dir/good.out" 2>"$tmp_dir/good.err"
	rc=$?
	set -e
	assert_equals "0" "$rc" "failed-check review validator accepts Strix log-backed findings"

	rm -rf "$tmp_dir"
}

assert_opencode_failed_check_fallback_emits_each_strix_report() {
	local tmp_dir
	local fixture_repo
	local evidence_file
	local output_file
	tmp_dir="$(mktemp -d)"
	fixture_repo="$tmp_dir/repo"
	evidence_file="$tmp_dir/failed-check-evidence.md"
	output_file="$tmp_dir/fallback.md"
	mkdir -p "$fixture_repo/backend/services" "$fixture_repo/frontend/src/app/prompt-studio" "$fixture_repo/frontend"

	{
		for _ in $(seq 1 59); do
			printf '# filler\n'
		done
		printf 'filename = part.get_filename()\n'
	} >"$fixture_repo/backend/services/email_parser.py"
	{
		for _ in $(seq 1 28); do
			printf '// filler\n'
		done
		printf 'setTestResult(await apiClient.post("/prompt-studio", payload));\n'
	} >"$fixture_repo/frontend/src/app/prompt-studio/page.tsx"
	{
		for _ in $(seq 1 34); do
			printf '// filler\n'
		done
		printf 'const nextConfig = {};\n'
	} >"$fixture_repo/frontend/next.config.ts"

	cat >"$evidence_file" <<'EOF'
## Failed check: Strix Security Scan/strix

### Failed log signal summary

```text
strix	Run Strix (quick)	LLM CONNECTION FAILED
strix	Run Strix (quick)	Strix fallback model 'deepseek/deepseek-r1-0528' emitted provider infrastructure or failure-signal output; trying next configured fallback if available.
```

### Strix vulnerability report window 1

Model deepseek/deepseek-r1-0528 Vulnerabilities 2
│  Vulnerability Report                                                        │
│  Title: Path Traversal in Email Attachment Handling                          │
│  Severity: CRITICAL                                                          │
│  Endpoint: /services/email_parser.py                                         │
│    Location 1: backend/services/email_parser.py:60-72                        │
│  Vulnerability Report                                                        │
│  Title: Prompt Injection and XSS in AI Prompt Studio                         │
│  Severity: HIGH                                                              │
│  Endpoint: /prompt-studio                                                    │
│    Location 1: frontend/src/app/prompt-studio/page.tsx:29-32                 │

### Strix vulnerability report window 2

Model deepseek/deepseek-v3-0324 Vulnerabilities 1
│  Vulnerability Report                                                        │
│  Title: Missing Content Security Policy in Next.js Frontend                  │
│  Severity: HIGH                                                              │
│  Endpoint: all frontend pages                                                │
EOF

	bash "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" \
		"$evidence_file" "$fixture_repo" >"$output_file"

	assert_file_contains "$output_file" "Strix report from deepseek/deepseek-r1-0528: Path Traversal in Email Attachment Handling" "fallback includes first model report"
	assert_file_contains "$output_file" "backend/services/email_parser.py:60" "fallback maps first report to exact source line"
	assert_file_contains "$output_file" "Strix report from deepseek/deepseek-r1-0528: Prompt Injection and XSS in AI Prompt Studio" "fallback includes second report from same model"
	assert_file_contains "$output_file" "frontend/src/app/prompt-studio/page.tsx:29" "fallback maps second report to exact source line"
	assert_file_contains "$output_file" "Strix report from deepseek/deepseek-v3-0324: Missing Content Security Policy in Next.js Frontend" "fallback includes report from second model"
	assert_file_contains "$output_file" "frontend/next.config.ts:35" "fallback derives a concrete CSP hardening line"
	assert_file_contains "$output_file" "Suggested edit: change \`frontend/next.config.ts:35\`" "fallback provides a concrete suggested edit for model reports"
	assert_file_contains "$output_file" "Strix provider signal left current-head security evidence incomplete" "fallback still reports provider failure after vulnerability reports"
	assert_file_not_contains "$output_file" "failed before producing vulnerability reports" "fallback does not contradict preserved Strix report windows"

	rm -rf "$tmp_dir"
}

assert_opencode_failed_check_fallback_explains_trusted_base_strix_prs() {
	local tmp_dir
	local fixture_repo
	local evidence_file
	local output_file
	local base_sha
	local head_sha
	tmp_dir="$(mktemp -d)"
	fixture_repo="$tmp_dir/repo"
	evidence_file="$tmp_dir/failed-check-evidence.md"
	output_file="$tmp_dir/fallback.md"

	mkdir -p "$fixture_repo/.github/workflows"
	cat >"$fixture_repo/.github/workflows/strix.yml" <<'EOF'
name: Strix Security Scan
concurrency:
  cancel-in-progress: false
EOF

	git init -q "$fixture_repo" >/dev/null
	git -C "$fixture_repo" config user.email "copilot@example.com"
	git -C "$fixture_repo" config user.name "copilot"
	git -C "$fixture_repo" add .github/workflows/strix.yml
	git -C "$fixture_repo" commit -m "base" >/dev/null
	base_sha="$(git -C "$fixture_repo" rev-parse HEAD)"

	cat >"$fixture_repo/.github/workflows/strix.yml" <<'EOF'
name: Strix Security Scan
concurrency:
  group: strix-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: false
EOF
	git -C "$fixture_repo" add .github/workflows/strix.yml
	git -C "$fixture_repo" commit -m "head" >/dev/null
	head_sha="$(git -C "$fixture_repo" rev-parse HEAD)"

	cat >"$evidence_file" <<'EOF'
## Failed check: Strix Security Scan/strix

Conclusion: cancelled

No GitHub Actions job log is available for this failed workflow run.
EOF

	PR_BASE_SHA="$base_sha" PR_HEAD_SHA="$head_sha" \
		bash "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" \
		"$evidence_file" "$fixture_repo" >"$output_file"

	assert_file_contains "$output_file" "cancelled pull_request_target run still used the base branch copies" "fallback explains trusted-base workflow execution"
	assert_file_contains "$output_file" "Re-run Strix after the trusted base branch contains the workflow/gate change or capture equivalent temporary evidence tied to this head SHA" "fallback directs reviewers to trusted-base rerun or equivalent evidence"

	rm -rf "$tmp_dir"
}

assert_opencode_failed_check_fallback_does_not_treat_no_report_summary_as_report() {
	local tmp_dir
	local evidence_file
	local output_file
	tmp_dir="$(mktemp -d)"
	evidence_file="$tmp_dir/failed-check-evidence.md"
	output_file="$tmp_dir/fallback.md"

	cat >"$evidence_file" <<'EOF'
## Failed check: Strix Security Scan/strix

### Failed log signal summary

```text
strix	Run Strix (quick)	openai.RateLimitError: Too many requests.
strix	Run Strix (quick)	httpx.HTTPStatusError: Client error '401 Unauthorized' for url 'https://api.deepseek.com/beta/chat/completions'
strix	Run Strix (quick)	litellm.BadRequestError: DeepseekException - {"error":{"message":"Authentication Fails, Your api key is invalid"}}
strix	Run Strix (quick)	Configured model and fallback models were unavailable.
```

No Strix vulnerability report windows were detected in the failed log.
EOF

	bash "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" \
		"$evidence_file" "$REPO_ROOT" >"$output_file"

	assert_file_contains "$output_file" "Strix provider failure blocked current-head security evidence" "fallback treats no-report summary as provider blocker"
	assert_file_contains "$output_file" "api.deepseek.com" "fallback preserves direct DeepSeek endpoint failure evidence"
	assert_file_contains "$output_file" "Authentication Fails" "fallback preserves direct DeepSeek authentication failure evidence"
	assert_file_contains "$output_file" "github_models/deepseek/deepseek-r1-0528 github_models/deepseek/deepseek-v3-0324" "fallback gives exact GitHub Models fallback list"
	assert_file_contains "$output_file" "Suggested edit: \`.github/workflows/strix.yml" "fallback gives a line-specific suggested edit for provider routing"
	assert_file_not_contains "$output_file" "Strix provider signal left current-head security evidence incomplete" "fallback does not invent vulnerability report windows from a no-report summary"
	assert_file_not_contains "$output_file" "after vulnerability reports" "fallback does not contradict no-report evidence"

	rm -rf "$tmp_dir"
}

assert_opencode_failed_check_fallback_handles_deepseek_auth_only_signal() {
	local tmp_dir
	local evidence_file
	local output_file
	tmp_dir="$(mktemp -d)"
	evidence_file="$tmp_dir/failed-check-evidence.md"
	output_file="$tmp_dir/fallback.md"

	cat >"$evidence_file" <<'EOF'
## Failed check: Strix Security Scan/strix

### Failed log signal summary

```text
strix	Run Strix (quick)	httpx.HTTPStatusError: Client error '401 Unauthorized' for url 'https://api.deepseek.com/beta/chat/completions'
strix	Run Strix (quick)	litellm.BadRequestError: DeepseekException - {"error":{"message":"Authentication Fails, Your api key is invalid"}}
```

No Strix vulnerability report windows were detected in the failed log.
EOF

	bash "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" \
		"$evidence_file" "$REPO_ROOT" >"$output_file"

	assert_file_contains "$output_file" "Strix provider failure blocked current-head security evidence" "fallback treats DeepSeek auth-only logs as provider blockers"
	assert_file_contains "$output_file" "api.deepseek.com" "fallback preserves DeepSeek auth-only endpoint evidence"
	assert_file_contains "$output_file" "Authentication Fails" "fallback preserves DeepSeek auth-only failure evidence"
	assert_file_contains "$output_file" "Suggested edit: \`.github/workflows/strix.yml" "fallback gives suggested edit for DeepSeek auth-only provider routing"

	rm -rf "$tmp_dir"
}

assert_opencode_failed_check_fallback_handles_pg_erd_cloud_strix_log_shape() {
	local tmp_dir
	local fixture_repo
	local evidence_file
	local output_file
	tmp_dir="$(mktemp -d)"
	fixture_repo="$tmp_dir/repo"
	evidence_file="$tmp_dir/failed-check-evidence.md"
	output_file="$tmp_dir/fallback.md"

	mkdir -p "$fixture_repo/backend/app" "$fixture_repo/frontend"
	for line_number in $(seq 1 150); do
		printf '# auth fixture line %s\n' "$line_number"
	done >"$fixture_repo/backend/app/auth.py"
	cat >"$fixture_repo/frontend/next.config.ts" <<'EOF'
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [];
  },
};

export default nextConfig;
EOF

	cat >"$evidence_file" <<'EOF'
## Failed check: Strix Security Scan/strix

### Failed log signal summary

```text
strix	Run Strix (quick)	Strix run failed for model 'deepseek/deepseek-r1-0528' after 206s (exit code 2).
strix	Run Strix (quick)	Below-threshold findings detected, but infrastructure errors occurred during this pipeline run; refusing bypass due to potentially incomplete scan.
strix	Run Strix (quick)	Unable to map Strix findings to changed files; failing closed for pull request.
```

### Strix vulnerability report window 1

│  Vulnerability Report                                                        │
│  Title: Authentication Bypass via X-Dev-User Header                          │
│  Severity: CRITICAL                                                          │
│  Target: /workspace/strix-pr-scope.I4RF8w                                    │
│  Endpoint: /api/me                                                           │
│  Method: GET                                                                 │
│  Code Locations                                                              │
│    Location 1: backend/app/auth.py:132-135                                   │
│  Model deepseek/deepseek-r1-0528                                             │
│  Vulnerabilities 1                                                           │

### Strix vulnerability report window 2

│  Vulnerability Report                                                        │
│  Title: Frontend Security Issues: XSS, Hardcoded Credentials, and Insecure   │
│  Data Handling                                                               │
│  Severity: HIGH                                                              │
│  Target: /workspace/strix-pr-scope.I4RF8w/frontend                           │
│  Model deepseek/deepseek-v3-0324                                             │
│  Vulnerabilities 1                                                           │
EOF

	bash "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" \
		"$evidence_file" "$fixture_repo" >"$output_file"

	assert_file_contains "$output_file" "Strix report from deepseek/deepseek-r1-0528: Authentication Bypass via X-Dev-User Header" "fallback includes pg-erd-cloud first model report"
	assert_file_contains "$output_file" "backend/app/auth.py:132" "fallback maps pg-erd-cloud auth report to exact line"
	assert_file_contains "$output_file" "Endpoint: /api/me. Method: GET" "fallback preserves pg-erd-cloud endpoint and method"
	assert_file_contains "$output_file" "Strix report from deepseek/deepseek-v3-0324: Frontend Security Issues: XSS, Hardcoded Credentials, and Insecure Data Handling" "fallback preserves wrapped pg-erd-cloud frontend title"
	assert_file_contains "$output_file" "frontend/next.config.ts:3" "fallback anchors locationless frontend report to a concrete frontend hardening line"
	assert_file_contains "$output_file" "Suggested edit: change \`frontend/next.config.ts:3\`" "fallback provides pg-erd-cloud frontend suggested edit"
	assert_file_contains "$output_file" "Unable to map Strix findings" "fallback preserves failed Strix mapping signal"
	assert_file_contains "$output_file" "Strix provider signal left current-head security evidence incomplete" "fallback reports incomplete Strix evidence after model findings"
	assert_file_not_contains "$output_file" "failed before producing vulnerability reports" "fallback does not erase model findings after provider signals"

	rm -rf "$tmp_dir"
}

assert_opencode_failed_check_fallback_handles_split_code_location_lines() {
	local tmp_dir
	local fixture_repo
	local evidence_file
	local output_file
	local migration_file
	tmp_dir="$(mktemp -d)"
	fixture_repo="$tmp_dir/repo"
	evidence_file="$tmp_dir/failed-check-evidence.md"
	output_file="$tmp_dir/fallback.md"
	migration_file="$fixture_repo/backend/alembic/versions/0002_provider_writeback_retry_queue.py"

	mkdir -p "$(dirname "$migration_file")"
	for line_number in $(seq 1 80); do
		if [ "$line_number" -eq 43 ]; then
			printf '\tlegacy_index_execution_placeholder(statement)\n'
		else
			printf '# migration fixture line %s\n' "$line_number"
		fi
	done >"$migration_file"

	cat >"$evidence_file" <<'EOF'
## Failed check: Strix Security Scan/strix

### Failed log signal summary

```text
strix	Run Strix (quick)	Strix fallback model 'github_models/deepseek/deepseek-r1-0528' emitted provider infrastructure or failure-signal output; trying next configured fallback if available.
strix	Run Strix (quick)	Strix reported zero vulnerabilities before provider infrastructure failure; failing closed because provider infrastructure failures are not clean scan evidence.
```

### Strix vulnerability report window 1

│  Vulnerability Report                                                        │
│  Title: SQL Injection Vulnerability in Database Script                       │
│  Severity: HIGH                                                              │
│  Target:                                                                     │
│  /workspace/strix-pr-scope.e0AHf4/backend/alembic/versions/0002_provider_wr  │
│  iteback_retry_queue.py                                                      │
│  Code Locations                                                              │
│                                                                              │
│    Location 1:                                                               │
│  backend/alembic/versions/0002_provider_writeback_retry_queue.py:43          │
│    Vulnerable code location                                                  │
│    legacy_index_execution_placeholder(statement)                             │
│  Model openai/deepseek/deepseek-r1-0528                                      │
│  Vulnerabilities 1                                                           │
EOF

	bash "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" \
		"$evidence_file" "$fixture_repo" >"$output_file"

	assert_file_contains "$output_file" "Strix report from openai/deepseek/deepseek-r1-0528: SQL Injection Vulnerability in Database Script" "fallback includes split-location Strix report"
	assert_file_contains "$output_file" "backend/alembic/versions/0002_provider_writeback_retry_queue.py:43" "fallback maps split Code Locations path to exact line"
	assert_file_contains "$output_file" "Code location evidence: backend/alembic/versions/0002_provider_writeback_retry_queue.py:43" "fallback preserves split Code Locations evidence"
	assert_file_contains "$output_file" "Suggested edit: change \`backend/alembic/versions/0002_provider_writeback_retry_queue.py:43\`" "fallback gives suggested edit for split Code Locations"
	assert_file_not_contains "$output_file" "Strix report did not include a mappable Code Location" "fallback does not misclassify split Code Locations as unmapped"

	rm -rf "$tmp_dir"
}

assert_opencode_failed_check_fallback_does_not_anchor_unmapped_strix_reports_to_workflow() {
	local tmp_dir
	local fixture_repo
	local evidence_file
	local output_file
	tmp_dir="$(mktemp -d)"
	fixture_repo="$tmp_dir/repo"
	evidence_file="$tmp_dir/failed-check-evidence.md"
	output_file="$tmp_dir/fallback.md"

	mkdir -p "$fixture_repo/.github/workflows" "$fixture_repo/scripts/ci"
	cat >"$fixture_repo/.github/workflows/strix.yml" <<'EOF'
name: Strix Security Scan
jobs:
  strix:
    steps:
      - name: Run Strix
        env:
          STRIX_FALLBACK_MODELS: github_models/deepseek/deepseek-r1-0528 github_models/deepseek/deepseek-v3-0324
EOF

	cat >"$evidence_file" <<'EOF'
## Failed check: Strix Security Scan/strix

### Failed log signal summary

```text
strix	Run Strix (quick)	Below-threshold findings detected, but infrastructure errors occurred during this pipeline run; refusing bypass due to potentially incomplete scan.
strix	Run Strix (quick)	Unable to map Strix findings to changed files; failing closed for pull request.
```

### Strix vulnerability report window 1

│  Vulnerability Report                                                        │
│  Title: Insecure Direct Object Reference (IDOR) in User Profile API          │
│  Severity: MEDIUM                                                            │
│  Target: /workspace/strix-pr-scope.mVhTAV/backend                            │
│  Code Locations                                                              │
│    Location 1: backend/api/users.py:45-52                                    │
│  Model github_models/deepseek/deepseek-v3-0324                               │
│  Vulnerabilities 1                                                           │
EOF

	bash "$REPO_ROOT/scripts/ci/emit_opencode_failed_check_fallback_findings.sh" \
		"$evidence_file" "$fixture_repo" >"$output_file"

	assert_file_contains "$output_file" "Strix provider signal left current-head security evidence incomplete" "fallback reports incomplete Strix evidence for unmapped report"
	assert_file_contains "$output_file" "did not map to an existing repository file" "fallback explains unmapped Strix report"
	assert_file_contains "$output_file" "Insecure Direct Object Reference (IDOR) in User Profile API" "fallback preserves unmapped report title as diagnostic evidence"
	assert_file_not_contains "$output_file" "Strix report from github_models/deepseek/deepseek-v3-0324" "fallback does not convert unmapped report into source finding"
	assert_file_not_contains "$output_file" "Inspect and patch .github/workflows/strix.yml" "fallback does not anchor unmapped report to workflow line"
	assert_file_not_contains "$output_file" "backend/api/users.py:45" "fallback does not cite nonexistent source path as actionable line"

	rm -rf "$tmp_dir"
}

assert_internal_pr_scope_targets() {
	local target_log_file="$1"
	local repo_root_dir="$2"
	local expected_count="$3"

	if [ ! -f "$target_log_file" ]; then
		record_failure "internal PR scope target log should exist"
		return
	fi

	local actual_count=0
	local target_path
	while IFS= read -r target_path; do
		actual_count=$((actual_count + 1))
		case "$target_path" in
		"$repo_root_dir" | "$repo_root_dir"/*)
			record_failure "internal PR scope target should not reuse repository path: $target_path"
			;;
		esac
		case "$(basename -- "$target_path")" in
		strix-pr-scope.*)
			;;
		*)
			record_failure "internal PR scope target should be generated by build_pull_request_scope_dir: $target_path"
			;;
		esac
	done <"$target_log_file"

	assert_equals "$expected_count" "$actual_count" "internal PR scope target count"
}

run_gate_case() {
	local scenario="$1"
	local initial_model="$2"
	local fallback_models="$3"
	local expected_exit="$4"
	local expected_message="$5"
	local expected_calls="$6"
	local expected_model_sequence="${7:-}"
	local expected_api_base_sequence="${8:-}"
	local default_provider="${9-vertex_ai}"
	local raw_llm_api_base_override="${10-__DEFAULT__}"
	local initial_llm_api_base="${11-}"

	local raw_llm_api_base="https://example.invalid/generateContent"
	if [ "$raw_llm_api_base_override" != "__DEFAULT__" ]; then
		raw_llm_api_base="$raw_llm_api_base_override"
	fi
	local transient_retry_per_model="${12-0}"
	local min_fail_severity="${13-CRITICAL}"
	local transient_retry_backoff_seconds="${14:-0}"
	local custom_target_path="${15-}"
	local custom_source_dirs="${16-}"
	local process_timeout_seconds="${17-1200}"
	local total_timeout_seconds="${18-0}"
	local github_event_name="${19-}"
	local changed_files_override="${20-}"
	local event_name_override="${21-}"
	local legacy_scope_size_ignored="${22-}"
	local disable_pr_scoping="${23-0}"
	local test_pr_sca_status_override="${24-}"
	local current_pr_number="${25-}"
	local authoritative_sca_runs_json="${26-}"
	local gemini_fallback_models="${27-__SAME_AS_FALLBACK_MODELS__}"
	local generic_fallback_models="${28-}"
	local fail_on_provider_signal="${29-1}"

	local tmp_dir
	tmp_dir="$(mktemp -d)"
	# Separate bin/ (fake strix + helper files) from workspace/ (target path)
	# so grep -r over the target path never matches the fake strix script itself.
	local bin_dir="$tmp_dir/bin"
	local workspace_dir="$tmp_dir/workspace"
	local repo_root_dir="$workspace_dir/smart-crawling-server"
	mkdir -p "$bin_dir" "$repo_root_dir/src"
	mkdir -p "$repo_root_dir/scripts/ci"
	local gate_under_test="$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$GATE_SCRIPT" "$gate_under_test"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$gate_under_test"
	local fake_strix="$bin_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local api_base_log="$tmp_dir/api_base.log"
	local target_log="$tmp_dir/target.log"
	local runtime_env_log="$tmp_dir/runtime_env.log"
	local state_file="$tmp_dir/state.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"
	local llm_api_base_file="$tmp_dir/llm_api_base.txt"
	local output_log="$tmp_dir/output.log"
	local fake_gh="$bin_dir/gh"
	local gh_token_log="$tmp_dir/gh_token.log"
	local event_payload_file="$tmp_dir/github_event.json"

	# Resolve target path: use repo-local relative defaults to mirror the real workflow.
	local effective_target_path="."
	if [ "$custom_target_path" = "__USE_SUBDIR_SRC__" ]; then
		# Simulate STRIX_TARGET_PATH=./src with a repo-local relative path.
		effective_target_path="./src"
	elif [ -n "$custom_target_path" ]; then
		effective_target_path="$custom_target_path"
		# Ensure the custom target path exists
		mkdir -p "$effective_target_path"
	fi

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "${STRIX_LLM:-}" >> "${FAKE_STRIX_CALL_LOG:?}"
printf '%s\n' "${LLM_API_BASE:-<unset>}" >> "${FAKE_STRIX_API_BASE_LOG:?}"
if [ -n "${FAKE_STRIX_RUNTIME_ENV_LOG:-}" ]; then
	printf 'LLM_TIMEOUT=%s;STRIX_MEMORY_COMPRESSOR_TIMEOUT=%s;STRIX_REASONING_EFFORT=%s;STRIX_LLM_MAX_RETRIES=%s;GEMINI_LOCATION=%s;PYTHONWARNINGS=%s;NPM_CONFIG_IGNORE_SCRIPTS=%s;PNPM_CONFIG_IGNORE_SCRIPTS=%s;YARN_ENABLE_SCRIPTS=%s;UNRELATED_SECRET=%s\n' \
		"${LLM_TIMEOUT:-<unset>}" \
		"${STRIX_MEMORY_COMPRESSOR_TIMEOUT:-<unset>}" \
		"${STRIX_REASONING_EFFORT:-<unset>}" \
		"${STRIX_LLM_MAX_RETRIES:-<unset>}" \
		"${GEMINI_LOCATION:-<unset>}" \
		"${PYTHONWARNINGS:-<unset>}" \
		"${NPM_CONFIG_IGNORE_SCRIPTS:-<unset>}" \
		"${PNPM_CONFIG_IGNORE_SCRIPTS:-<unset>}" \
		"${YARN_ENABLE_SCRIPTS:-<unset>}" \
		"${UNRELATED_SECRET:-<unset>}" >> "${FAKE_STRIX_RUNTIME_ENV_LOG:?}"
fi

target_path=""
while [ "$#" -gt 0 ]; do
	if [ "$1" = "-t" ] && [ "$#" -ge 2 ]; then
		target_path="$2"
		break
	fi
	shift
done
if [ "$target_path" = "." ]; then
	target_path="$PWD"
fi
printf '%s\n' "$target_path" >> "${FAKE_STRIX_TARGET_LOG:?}"

STRIX_REPORTS_DIR="${STRIX_REPORTS_DIR:-strix_runs}"

case "${FAKE_STRIX_SCENARIO:?}" in
	success|runtime-env-forwarding|vertex-primary-success-timing-message|direct-openai-gpt-does-not-require-github-models-api-base)
		echo "scan ok"
		exit 0
		;;
	slow-timeout)
		sleep 2
		exit 0
		;;
	timeout-disabled-success)
		sleep 1
		echo "scan ok with timeout disabled"
		exit 0
		;;
	vertex-primary-notfound-fallback-success|github-models-fallback-success|github-models-fallback-success-deepseek-v3|github-models-fallback-requires-api-base|github-models-model-prefix-with-api-base-succeeds|github-models-meta-prefix-with-api-base-succeeds|github-models-mistral-prefix-with-api-base-succeeds)
		case "${STRIX_LLM:-}" in
		vertex_ai/missing-primary)
			echo "Error: litellm.NotFoundError: Vertex_aiException - x"
			echo '"status": "NOT_FOUND"'
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok with fallback"
			exit 0
			;;
		openai/gpt-5|openai/openai/gpt-5.4|openai/meta/test-github-model|openai/mistral-ai/test-github-model)
			echo "scan ok with GitHub Models fallback"
			exit 0
			;;
		openai/deepseek/deepseek-r1-0528)
			if [ "${FAKE_STRIX_SCENARIO:?}" = "github-models-fallback-success-deepseek-v3" ]; then
				echo "LLM CONNECTION FAILED"
				echo "Could not establish connection to the language model."
				echo "Error: litellm.BadRequestError: OpenAIException - Unavailable model: deepseek-r1-0528"
				exit 1
			fi
			echo "scan ok with GitHub Models fallback"
			exit 0
			;;
		openai/deepseek/deepseek-v3-0324)
			echo "scan ok with GitHub Models fallback"
			exit 0
			;;
		*)
			echo "unexpected model ${STRIX_LLM:-}" >&2
			exit 9
			;;
		esac
		;;
	vertex-all-notfound)
		echo "Error: litellm.NotFoundError: Vertex_aiException - x"
		echo '"status": "NOT_FOUND"'
		exit 1
		;;
	nonrecoverable)
		echo "Error: transport timeout"
		exit 1
		;;
	provider-prefix-required)
		if [ "${STRIX_LLM:-}" = "vertex_ai/gemini-2.5-pro" ]; then
			echo "scan ok with normalized provider"
			exit 0
		fi
		echo "Error: provider prefix not normalized (${STRIX_LLM:-})" >&2
		exit 10
		;;
	provider-prefix-fallback-normalization)
		case "${STRIX_LLM:-}" in
		vertex_ai/missing-primary)
			echo "Error: litellm.NotFoundError: Vertex_aiException - x"
			echo '"status": "NOT_FOUND"'
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after fallback normalization"
			exit 0
			;;
		*)
			echo "Error: fallback provider prefix not normalized (${STRIX_LLM:-})" >&2
			exit 11
			;;
		esac
		;;
	provider-prefix-required-resource-path-primary-implicit-default-provider | provider-prefix-required-resource-path-primary-explicit-empty-default-provider)
		if [ "${STRIX_LLM:-}" = "vertex_ai/gemini-2.5-pro" ]; then
			echo "scan ok with resource-path normalization"
			exit 0
		fi
		echo "Error: resource-path model not normalized (${STRIX_LLM:-})" >&2
		exit 12
		;;
	provider-prefix-resource-path-primary-notfound-fallback-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/missing-primary)
			echo "Error: litellm.NotFoundError: Vertex_aiException - x"
			echo '"status": "NOT_FOUND"'
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after resource-path fallback"
			exit 0
			;;
		*)
			echo "Error: resource-path fallback model not normalized (${STRIX_LLM:-})" >&2
			exit 13
			;;
		esac
		;;
	vertex-custom-model-resource-path)
		# projects/<p>/locations/<l>/models/<id> (no publishers/ segment)
		if [ "${STRIX_LLM:-}" = "vertex_ai/my-custom-model-123" ]; then
			echo "scan ok with custom model resource-path normalization"
			exit 0
		fi
		echo "Error: custom model resource-path not normalized (${STRIX_LLM:-})" >&2
		exit 40
		;;
	vertex-notfound-without-status-fallback-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/missing-primary)
			echo "Error: litellm.NotFoundError: Vertex_aiException - x"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after status-less not found fallback"
			exit 0
			;;
		*)
			echo "Error: status-less fallback model not normalized (${STRIX_LLM:-})" >&2
			exit 14
			;;
		esac
		;;
	vertex-notfound-compact-status-fallback-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/missing-primary)
			echo 'litellm.exceptions.NotFoundError: VertexAI error'
			echo '{"error":{"status":"NOT_FOUND"}}'
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after compact-status not found fallback"
			exit 0
			;;
		*)
			echo "Error: compact-status fallback model not normalized (${STRIX_LLM:-})" >&2
			exit 17
			;;
		esac
		;;
	nonvertex-slash-model-passthrough)
		if [ "${STRIX_LLM:-}" = "foo/bar" ]; then
			echo "scan ok with non-vertex slash model passthrough"
			exit 0
		fi
		echo "Error: non-vertex slash model was rewritten (${STRIX_LLM:-})" >&2
		exit 18
		;;
	primary-duplicate-in-fallback)
		case "${STRIX_LLM:-}" in
		vertex_ai/missing-primary)
			echo "Error: litellm.NotFoundError: Vertex_aiException - x"
			echo '"status": "NOT_FOUND"'
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after duplicate-primary skip"
			exit 0
			;;
		*)
			echo "Error: duplicate-primary path unexpected (${STRIX_LLM:-})" >&2
			exit 15
			;;
		esac
		;;
	multiline-fallback-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/missing-primary)
			echo "Error: litellm.NotFoundError: Vertex_aiException - x"
			echo '"status": "NOT_FOUND"'
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "Error: litellm.NotFoundError: Vertex_aiException - x"
			echo '"status": "NOT_FOUND"'
			exit 1
			;;
		vertex_ai/fallback-two)
			echo "scan ok after multiline fallback parsing"
			exit 0
			;;
		*)
			echo "Error: multiline fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 19
			;;
		esac
		;;
	vertex-primary-ratelimit-fallback-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/ratelimit-primary)
			echo "Penetration test failed: LLM request failed: RateLimitError"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after rate-limit fallback"
			exit 0
			;;
		*)
			echo "Error: ratelimit fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 21
			;;
		esac
		;;
	vertex-primary-resource-exhausted-fallback-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/resource-exhausted-primary)
			echo '{"error":{"status":"RESOURCE_EXHAUSTED"}}'
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after resource exhausted fallback"
			exit 0
			;;
		*)
			echo "Error: resource exhausted fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 23
			;;
		esac
		;;
	vertex-primary-429-fallback-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/http429-primary)
			echo "litellm: HTTP 429 Too Many Requests"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after 429 fallback"
			exit 0
			;;
		*)
			echo "Error: 429 fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 24
			;;
		esac
		;;
	vertex-primary-midstream-fallback-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/midstream-primary)
			echo "Penetration test failed: LLM request failed: MidStreamFallbackError"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after midstream fallback"
			exit 0
			;;
		*)
			echo "Error: midstream fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 25
			;;
		esac
		;;
	vertex-primary-midstream-retry-same-model-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/retry-midstream-primary)
			attempt="0"
			if [ -f "${FAKE_STRIX_STATE_FILE:?}" ]; then
				attempt="$(cat "${FAKE_STRIX_STATE_FILE:?}")"
			fi
			attempt="$((attempt + 1))"
			echo "$attempt" > "${FAKE_STRIX_STATE_FILE:?}"
			if [ "$attempt" -eq 1 ]; then
				echo "Penetration test failed: LLM request failed: MidStreamFallbackError"
				exit 1
			fi
			echo "scan ok after same-model retry"
			exit 0
			;;
		vertex_ai/fallback-one)
			echo "Error: fallback should not be needed for same-model retry scenario" >&2
			exit 30
			;;
		*)
			echo "Error: midstream fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 30
			;;
		esac
		;;
	vertex-primary-ratelimit-retry-same-model-success|vertex-primary-ratelimit-retry-reason-message)
		case "${STRIX_LLM:-}" in
		vertex_ai/retry-ratelimit-primary)
			attempt="0"
			if [ -f "${FAKE_STRIX_STATE_FILE:?}" ]; then
				attempt="$(cat "${FAKE_STRIX_STATE_FILE:?}")"
			fi
			attempt="$((attempt + 1))"
			echo "$attempt" > "${FAKE_STRIX_STATE_FILE:?}"
			if [ "$attempt" -eq 1 ]; then
				echo "Penetration test failed: LLM request failed: RateLimitError"
				exit 1
			fi
			echo "scan ok after same-model rate-limit retry"
			exit 0
			;;
		vertex_ai/fallback-one)
			echo "Error: fallback should not be needed for same-model rate-limit retry scenario" >&2
			exit 31
			;;
		*)
			echo "Error: rate-limit fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 31
			;;
		esac
		;;
	vertex-primary-api-connection-retry-same-model-success|github-models-internal-server-connection-retry-same-model-success)
		case "${STRIX_LLM:-}" in
		gemini/retry-api-connection-primary|vertex_ai/retry-api-connection-primary|openai/openai/retry-api-connection-primary)
			attempt="0"
			if [ -f "${FAKE_STRIX_STATE_FILE:?}" ]; then
				attempt="$(cat "${FAKE_STRIX_STATE_FILE:?}")"
			fi
			attempt="$((attempt + 1))"
			echo "$attempt" > "${FAKE_STRIX_STATE_FILE:?}"
			if [ "$attempt" -eq 1 ]; then
				if [ "${STRIX_LLM:-}" = "openai/openai/retry-api-connection-primary" ]; then
					echo "LLM CONNECTION FAILED"
					echo "Could not establish connection to the language model."
					echo "Error: litellm.InternalServerError: InternalServerError: OpenAIException - Connection error."
				else
					echo "LLM CONNECTION FAILED"
					echo "litellm.APIConnectionError: GeminiException - Server disconnected without sending a response."
				fi
				exit 1
			fi
			echo "scan ok after same-model api connection retry"
			exit 0
			;;
		vertex_ai/fallback-one)
			echo "Error: fallback should not be needed for API connection retry scenario" >&2
			exit 36
			;;
		*)
			echo "Error: API connection retry path unexpected (${STRIX_LLM:-})" >&2
			exit 36
			;;
		esac
		;;
	github-models-primary-unavailable-fallback-success|github-models-primary-denied-fallback-success)
		case "${STRIX_LLM:-}" in
		openai/gpt-5)
			echo "LLM CONNECTION FAILED"
			echo "Could not establish connection to the language model."
			if [ "${FAKE_STRIX_SCENARIO:?}" = "github-models-primary-denied-fallback-success" ]; then
				echo "openai.PermissionDeniedError: Error code: 403"
			else
				echo "Error: litellm.BadRequestError: OpenAIException - Unavailable model: gpt-5"
			fi
			exit 1
			;;
		openai/deepseek/deepseek-r1-0528)
			echo "scan ok after GitHub Models unavailable fallback"
			exit 0
			;;
		*)
			echo "Error: GitHub Models unavailable fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 37
			;;
		esac
		;;
	github-models-primary-ratelimit-fallback-success)
		case "${STRIX_LLM:-}" in
		openai/gpt-5)
			echo "LLM CONNECTION FAILED"
			echo "Could not establish connection to the language model."
			echo "Error: litellm.RateLimitError: RateLimitError: OpenAIException - Too many requests. For more on scraping GitHub and how it may affect your rights, please review our Terms of Service."
			exit 1
			;;
		openai/deepseek/deepseek-r1-0528)
			echo "scan ok after GitHub Models rate-limit fallback"
			exit 0
			;;
		*)
			echo "Error: GitHub Models rate-limit fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 38
			;;
		esac
		;;
	github-models-fallback-provider-signal-tries-next | github-models-fallback-vulnerability-before-next-success-blocks)
		case "${STRIX_LLM:-}" in
		openai/gpt-5)
			echo "LLM CONNECTION FAILED"
			echo "Could not establish connection to the language model."
			echo "Error: litellm.RateLimitError: RateLimitError: OpenAIException - Too many requests."
			exit 1
			;;
		openai/deepseek/deepseek-r1-0528)
			if [ "${FAKE_STRIX_SCENARIO:?}" = "github-models-fallback-vulnerability-before-next-success-blocks" ]; then
				mkdir -p "$STRIX_REPORTS_DIR/fake-pr-baseline-provider-signal/vulnerabilities"
				cat >"$STRIX_REPORTS_DIR/fake-pr-baseline-provider-signal/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
Location 1:
sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java:5
EOS
			else
				echo "LLM CONNECTION FAILED"
				echo "Could not establish connection to the language model."
				echo "Error: litellm.BadRequestError: OpenAIException - Unavailable model: deepseek-r1-0528"
			fi
			exit 2
			;;
		openai/deepseek/deepseek-v3-0324)
			echo "scan ok after second GitHub Models fallback"
			exit 0
			;;
		*)
			echo "Error: GitHub Models provider-signal fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 38
			;;
		esac
		;;
	gemini-high-demand-retry-same-model-success)
		case "${STRIX_LLM:-}" in
		gemini/retry-high-demand-primary)
			attempt="0"
			if [ -f "${FAKE_STRIX_STATE_FILE:?}" ]; then
				attempt="$(cat "${FAKE_STRIX_STATE_FILE:?}")"
			fi
			attempt="$((attempt + 1))"
			echo "$attempt" > "${FAKE_STRIX_STATE_FILE:?}"
			if [ "$attempt" -eq 1 ]; then
				echo "LLM CONNECTION FAILED"
				echo 'litellm.ServiceUnavailableError: GeminiException - {"error":{"code":503,"message":"This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.","status":"UNAVAILABLE"}}'
				exit 1
			fi
			echo "scan ok after same-model high-demand retry"
			exit 0
			;;
		*)
			echo "Error: high-demand retry path unexpected (${STRIX_LLM:-})" >&2
			exit 37
			;;
		esac
		;;
	gemini-timeout-direct-fallback-success)
		case "${STRIX_LLM:-}" in
		gemini/retry-timeout-primary)
			echo "LLM CONNECTION FAILED"
			echo "Error: litellm.Timeout: Connection timed out after None seconds."
			exit 1
			;;
		gemini/fallback-one)
			echo "scan ok after timeout fallback"
			exit 0
			;;
		*)
			echo "Error: gemini timeout fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 38
			;;
		esac
		;;
	gemini-timeout-fallback-success|gemini-generic-fallback-success)
		case "${STRIX_LLM:-}" in
		gemini/timeout-fallback-primary)
			echo "LLM CONNECTION FAILED"
			echo "Error: litellm.Timeout: Connection timed out after None seconds."
			exit 1
			;;
		gemini/fallback-one)
			echo "scan ok after gemini fallback"
			exit 0
			;;
		*)
			echo "Error: gemini timeout fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 39
			;;
		esac
		;;
	gemini-zero-findings-timeout-fallback-allows-pr)
		case "${STRIX_LLM:-}" in
		gemini/zero-timeout-primary|gemini/fallback-one)
			echo "Vulnerabilities 0"
			echo "LLM CONNECTION FAILED"
			echo "Error: litellm.Timeout: Connection timed out after None seconds."
			exit 1
			;;
		*)
			echo "Error: gemini zero-finding fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 40
			;;
		esac
		;;
	pr-scope-zero-finding-does-not-leak)
		if [ -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" ]; then
			echo "Vulnerabilities 0"
			echo "LLM CONNECTION FAILED"
			echo "Error: litellm.Timeout: Connection timed out after None seconds."
			exit 1
		fi
		if [ -f "$target_path/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java" ]; then
			echo "LLM CONNECTION FAILED"
			echo "Error: litellm.Timeout: Connection timed out after None seconds."
			exit 1
		fi
		echo "Error: unexpected PR scope zero-finding leak target layout ($target_path)" >&2
		exit 41
		;;
	service-unavailable-no-llm-marker-nonrecoverable)
		echo 'ServiceUnavailableError: {"error":{"code":503,"status":"UNAVAILABLE"}}'
		echo 'target application high demand response'
		exit 1
		;;
	server-disconnect-no-llm-marker-nonrecoverable)
		echo "ConnectionError: Server disconnected without sending a response."
		exit 1
		;;
	vertex-all-ratelimited)
		echo "Penetration test failed: LLM request failed: RateLimitError"
		exit 1
		;;
	vertex-primary-hallucinated-endpoint-fallback-success|target-path-src-default-source-dirs)
		case "${STRIX_LLM:-}" in
		vertex_ai/hallucination-primary)
			mkdir -p "$STRIX_REPORTS_DIR/fake-hallucinated/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/fake-hallucinated/vulnerabilities/vuln-0001.md" <<'EOS'
**Endpoint:** /api/ghost-admin
EOS
			echo "Penetration test failed: CRITICAL finding on /api/ghost-admin"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after hallucinated-endpoint fallback"
			exit 0
			;;
		*)
			echo "Error: hallucinated-endpoint fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 26
			;;
		esac
		;;
	vertex-primary-existing-endpoint-nonrecoverable|multi-source-dirs-existing-endpoint)
		case "${STRIX_LLM:-}" in
		vertex_ai/existing-endpoint-primary|vertex_ai/multi-dir-primary)
			mkdir -p "$STRIX_REPORTS_DIR/fake-existing-endpoint/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/fake-existing-endpoint/vulnerabilities/vuln-0001.md" <<'EOS'
**Endpoint:** /api/status
EOS
			echo "Penetration test failed: CRITICAL finding on /api/status"
			exit 1
			;;
		vertex_ai/fallback-one|vertex_ai/fallback-two)
			echo "Error: existing endpoint findings must remain non-recoverable (${STRIX_LLM:-})" >&2
			exit 27
			;;
		*)
			echo "Error: existing-endpoint scenario unexpected model (${STRIX_LLM:-})" >&2
			exit 28
			;;
		esac
		;;
	pr-stale-source-claim-fallback-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/stale-source-primary)
			mkdir -p "$STRIX_REPORTS_DIR/fake-stale-source/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/fake-stale-source/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** HIGH
**Target:** backend/db/models.py

The `WorkspaceRunnerConfig.registration_token` field stores the token as plain text.
The vulnerable line is `registration_token: Mapped[str | None] = mapped_column(String, nullable=True)`.
EOS
			echo "Penetration test failed: stale HIGH finding on backend/db/models.py"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after stale-source fallback"
			exit 0
			;;
		*)
			echo "Error: stale-source scenario unexpected model (${STRIX_LLM:-})" >&2
			exit 30
			;;
		esac
		;;
	pr-stale-source-plus-real-finding-blocks)
		case "${STRIX_LLM:-}" in
		vertex_ai/stale-source-primary)
			mkdir -p "$STRIX_REPORTS_DIR/fake-mixed-findings/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/fake-mixed-findings/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** HIGH
**Target:** backend/db/models.py

The `WorkspaceRunnerConfig.registration_token` field stores the token as plain text.
The vulnerable line is `registration_token: Mapped[str | None] = mapped_column(String, nullable=True)`.
EOS
			cat >"$STRIX_REPORTS_DIR/fake-mixed-findings/vulnerabilities/vuln-0002.md" <<'EOS'
**Severity:** HIGH
**Target:** backend/api/emails.py

This is a concrete changed-file finding that must remain blocking.
EOS
			echo "Penetration test failed: mixed stale and real HIGH findings"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "Error: mixed real findings must not reach fallback" >&2
			exit 31
			;;
		*)
			echo "Error: mixed-findings scenario unexpected model (${STRIX_LLM:-})" >&2
			exit 32
			;;
		esac
		;;
	pr-changed-finding-with-retry-marker-blocks)
		case "${STRIX_LLM:-}" in
		vertex_ai/changed-finding-primary)
			mkdir -p "$STRIX_REPORTS_DIR/fake-changed-retry-marker/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/fake-changed-retry-marker/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** HIGH
**Target:** backend/api/emails.py

This changed-file finding must remain blocking even when the model log also contains retryable provider text.
EOS
			echo "litellm.exceptions.Timeout: provider timed out after writing a HIGH changed-file finding"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "Error: changed-file findings with retry markers must not reach fallback" >&2
			exit 33
			;;
		*)
			echo "Error: changed-retry-marker scenario unexpected model (${STRIX_LLM:-})" >&2
			exit 34
			;;
		esac
		;;
	pr-stale-report-plus-inline-changed-finding-blocks)
		case "${STRIX_LLM:-}" in
		vertex_ai/stale-inline-primary)
			mkdir -p "$STRIX_REPORTS_DIR/fake-stale-report-inline-changed/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/fake-stale-report-inline-changed/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** HIGH
**Target:** backend/db/models.py

The `WorkspaceRunnerConfig.registration_token` field stores the token as plain text.
The vulnerable line is `registration_token: Mapped[str | None] = mapped_column(String, nullable=True)`.
EOS
			echo "Severity: HIGH"
			echo "Target: backend/api/emails.py"
			echo "Penetration test failed: stale report plus inline changed-file HIGH finding"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "Error: inline changed-file findings must not reach fallback" >&2
			exit 35
			;;
		*)
			echo "Error: stale-inline scenario unexpected model (${STRIX_LLM:-})" >&2
			exit 36
			;;
		esac
		;;
	endpoint-in-excluded-dir)
		case "${STRIX_LLM:-}" in
		vertex_ai/excluded-dir-primary)
			mkdir -p "$STRIX_REPORTS_DIR/fake-excluded-dir/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/fake-excluded-dir/vulnerabilities/vuln-0001.md" <<'EOS'
**Endpoint:** /api/hidden-secret
EOS
			echo "Penetration test failed: CRITICAL finding on /api/hidden-secret"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after excluded-dir hallucination fallback"
			exit 0
			;;
		*)
			echo "Error: excluded-dir scenario unexpected model (${STRIX_LLM:-})" >&2
			exit 29
			;;
		esac
		;;
	empty-fallback-models)
		# Output must match is_vertex_not_found_error() patterns so the gate
		# proceeds to the fallback loop (where empty array triggers the message).
		echo "Publisher Model vertex_ai/empty-fb-primary was not found in project."
		exit 1
		;;
	high-vuln-below-threshold)
		mkdir -p "$STRIX_REPORTS_DIR/fake-high/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-high/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: HIGH
EOS
		echo "Penetration test failed: simulated high finding"
		exit 1
		;;
	inline-medium-below-threshold)
		echo "╭─ VULN-0001 ──────────────────────────────────────────────────────────────────╮"
		echo "│  Vulnerability Report                                                        │"
		echo "│  Severity: MEDIUM                                                            │"
		echo "╰──────────────────────────────────────────────────────────────────────────────╯"
		echo "Penetration test failed: simulated inline medium finding"
		exit 2
		;;
	medium-vuln-default-threshold)
		mkdir -p "$STRIX_REPORTS_DIR/fake-medium-default/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-medium-default/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: MEDIUM
EOS
		echo "Penetration test failed: simulated medium finding"
		exit 1
		;;
	critical-vuln-at-threshold)
		mkdir -p "$STRIX_REPORTS_DIR/fake-critical/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-critical/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
EOS
		echo "Penetration test failed: simulated critical finding"
		exit 1
		;;
	malformed-severity-marker-nonrecoverable)
		mkdir -p "$STRIX_REPORTS_DIR/fake-malformed/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-malformed/vulnerabilities/vuln-0001.md" <<'EOS'
Severity details: high confidence marker only
EOS
		echo "Penetration test failed: malformed severity marker"
		exit 1
		;;
	model-disagreement-critical-in-earlier-report)
		case "${STRIX_LLM:-}" in
		vertex_ai/model-a)
			mkdir -p "$STRIX_REPORTS_DIR/run-001/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/run-001/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
EOS
			echo "Error: litellm.NotFoundError: Vertex_aiException - x"
			echo '"status": "NOT_FOUND"'
			echo "Penetration test failed: CRITICAL finding by model-a"
			exit 1
			;;
		vertex_ai/model-b)
			mkdir -p "$STRIX_REPORTS_DIR/run-002/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/run-002/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: LOW
EOS
			echo "Error: litellm.NotFoundError: Vertex_aiException - x"
			echo '"status": "NOT_FOUND"'
			echo "Penetration test failed: LOW finding by model-b"
			exit 1
			;;
		*)
			echo "Error: model-disagreement unexpected model (${STRIX_LLM:-})" >&2
			exit 32
			;;
		esac
		;;
	nonvertex-slash-model-not-rewritten)
		if [ "${STRIX_LLM:-}" = "deepseek/models/deepseek-r1" ]; then
			echo "scan ok with deepseek model passthrough"
			exit 0
		fi
		echo "Error: deepseek model was rewritten (${STRIX_LLM:-})" >&2
		exit 33
		;;
	preserve-existing-api-base)
		if [ "${LLM_API_BASE:-}" = "https://preexisting.invalid" ]; then
			echo "scan ok with preserved api base"
			exit 0
		fi
		echo "Error: existing LLM_API_BASE was not preserved (${LLM_API_BASE:-<unset>})" >&2
		exit 20
		;;
	default-fallback-order-fast-first)
		case "${STRIX_LLM:-}" in
		vertex_ai/missing-primary)
			echo "Error: litellm.NotFoundError: Vertex_aiException - x"
			echo '"status": "NOT_FOUND"'
			exit 1
			;;
		vertex_ai/gemini-2.5-pro)
			echo "scan ok with default fast fallback"
			exit 0
			;;
		*)
			echo "Error: default fallback order unexpected (${STRIX_LLM:-})" >&2
			exit 16
			;;
		esac
		;;
	vertex-primary-timeout-retry-same-model-success|vertex-primary-timeout-retry-reason-message)
		case "${STRIX_LLM:-}" in
		vertex_ai/retry-timeout-primary)
			echo "litellm.exceptions.Timeout: litellm.Timeout: Connection timed out after None seconds."
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after timeout fallback"
			exit 0
			;;
		*)
			echo "Error: timeout fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 34
			;;
		esac
		;;
	all-fallbacks-same-as-primary)
		# Bug 13: All fallback models are the same as the primary model.
		# The gate should emit an ERROR and exit 1.
		echo "Error: litellm.NotFoundError: Vertex_aiException - x"
		echo '"status": "NOT_FOUND"'
		exit 1
		;;
	vertex-primary-timeout-exhausted-fallback-success)
		# Primary always times out (even after retries). Fallback succeeds.
		case "${STRIX_LLM:-}" in
		vertex_ai/timeout-exhaust-primary)
			echo "litellm.exceptions.Timeout: litellm.Timeout: Connection timed out after None seconds."
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after timeout-exhausted fallback"
			exit 0
			;;
		*)
			echo "Error: timeout-exhausted-fallback unexpected model (${STRIX_LLM:-})" >&2
			exit 35
			;;
		esac
		;;
	zero-findings-timeout-all-models|strict-zero-findings-timeout-fails-pr)
		case "${STRIX_LLM:-}" in
		vertex_ai/zero-timeout-primary|vertex_ai/fallback-one)
			echo "╭─ STRIX ──────────────────────────────────────────────────────────────────────╮"
			echo "│  Penetration test in progress                                                │"
			echo "│  Vulnerabilities 0                                                           │"
			echo "╰──────────────────────────────────────────────────────────────────────────────╯"
			sleep 4
			exit 0
			;;
		*)
			echo "Error: zero-findings-timeout unexpected model (${STRIX_LLM:-})" >&2
			exit 57
			;;
		esac
		;;
	zero-findings-sticky-across-fallback)
		case "${STRIX_LLM:-}" in
		vertex_ai/zero-sticky-primary)
			echo "╭─ STRIX ──────────────────────────────────────────────────────────────────────╮"
			echo "│  Penetration test in progress                                                │"
			echo "│  Vulnerabilities 0                                                           │"
			echo "╰──────────────────────────────────────────────────────────────────────────────╯"
			sleep 4
			exit 0
			;;
		vertex_ai/fallback-one)
			sleep 4
			exit 0
			;;
		*)
			echo "Error: zero-findings-sticky unexpected model (${STRIX_LLM:-})" >&2
			exit 58
			;;
		esac
		;;
	zero-findings-with-low-report-timeout)
		case "${STRIX_LLM:-}" in
		vertex_ai/zero-low-primary)
			mkdir -p "$STRIX_REPORTS_DIR/fake-zero-low/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/fake-zero-low/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: LOW
EOS
			echo "╭─ STRIX ──────────────────────────────────────────────────────────────────────╮"
			echo "│  Penetration test in progress                                                │"
			echo "│  Vulnerabilities 0                                                           │"
			echo "╰──────────────────────────────────────────────────────────────────────────────╯"
			sleep 4
			exit 0
			;;
		vertex_ai/fallback-one)
			sleep 4
			exit 0
			;;
		*)
			echo "Error: zero-findings-with-low-report unexpected model (${STRIX_LLM:-})" >&2
			exit 59
			;;
		esac
		;;
	provider-fatal-success-signal)
		echo "Fatal: provider stream aborted"
		exit 0
		;;
	provider-warning-success-signal)
		echo "Warning: provider response included incomplete scan state"
		exit 0
		;;
	provider-denied-success-signal)
		echo "Denied: provider credentials were rejected"
		exit 0
		;;
	report-known-internal-warning-sanitized)
		mkdir -p "$STRIX_REPORTS_DIR/fake-known-internal-warning"
		cat >"$STRIX_REPORTS_DIR/fake-known-internal-warning/strix.log" <<'EOS'
2026-06-18 13:08:05.986 WARNING strix-pr-scope-example - strix.core.execution: agent a9fb4033 produced non-lifecycle final output in non-interactive mode; forcing tool continuation (1/500): internal agent coordination note
2026-06-18 13:10:44.089 INFO    strix-pr-scope-example - strix.tools.finish.tool: finish_scan: completed scan with 0 vulnerability report(s)
EOS
		outside_report_dir="${FAKE_STRIX_OUTSIDE_REPORT_DIR:-$(dirname -- "$STRIX_REPORTS_DIR")/outside-strix-report}"
		mkdir -p "$outside_report_dir"
		cat >"$outside_report_dir/strix.log" <<'EOS'
2026-06-18 13:08:05.986 WARNING strix-pr-scope-example - strix.core.execution: agent a9fb4033 produced non-lifecycle final output in non-interactive mode; forcing tool continuation (1/500): outside report should not be rewritten
EOS
		ln -s "$outside_report_dir" "$STRIX_REPORTS_DIR/fake-known-internal-warning/linked-outside"
		echo "scan ok with sanitized internal Strix report notice"
		exit 0
		;;
	report-unknown-warning-fails)
		mkdir -p "$STRIX_REPORTS_DIR/fake-unknown-warning"
		cat >"$STRIX_REPORTS_DIR/fake-unknown-warning/strix.log" <<'EOS'
2026-06-18 13:08:05.986 WARNING strix-pr-scope-example - strix.provider: provider returned incomplete scan state
EOS
		echo "scan ok but unknown report warning remains"
		exit 0
		;;
	bare-timeout-with-provider-marker)
		# Emit bare "Connection timed out" alongside a provider marker so
		# is_timeout_error() matches the Tier 3 branch gated on
		# LLM_PROVIDER_ONLY_REGEX.  Does NOT include
		# litellm.exceptions.Timeout / httpx.ReadTimeout to ensure we
		# exercise the provider-marker fallback path specifically.
		# Primary times out; fallback model succeeds.
		case "${STRIX_LLM:-}" in
		vertex_ai/bare-timeout-primary)
			echo "Connection timed out"
			echo "vertex_ai model invocation failed"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after bare-timeout fallback"
			exit 0
			;;
		*)
			echo "Error: bare-timeout fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 47
			;;
		esac
		;;
	bare-timeout-no-provider-marker)
		# Emit "Connection timed out" with transport library names (httpx,
		# httpcore, requests) but WITHOUT any real LLM provider marker.
		# is_timeout_error() Tier 3 uses LLM_PROVIDER_ONLY_REGEX which
		# excludes transport libs, so this should NOT match.
		echo "Connection timed out"
		echo "httpx transport layer connection reset"
		echo "httpcore pool timeout"
		echo "requests transport timeout"
		exit 1
		;;
	below-threshold-with-timeout)
		# Produce a below-threshold (LOW) finding but also emit a timeout error
		# so the infrastructure guard detects an incomplete scan.
		mkdir -p "$STRIX_REPORTS_DIR/fake-low-timeout/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-low-timeout/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: LOW
EOS
		echo "litellm.exceptions.Timeout: litellm.Timeout: Connection timed out after None seconds."
		echo "Penetration test failed: simulated timeout with low finding"
		exit 1
		;;
	below-threshold-with-ratelimit)
		# Produce a below-threshold (LOW) finding but also emit a rate-limit error.
		mkdir -p "$STRIX_REPORTS_DIR/fake-low-ratelimit/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-low-ratelimit/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: LOW
EOS
		echo "Penetration test failed: LLM request failed: RateLimitError"
		echo "Penetration test failed: simulated ratelimit with low finding"
		exit 1
		;;
	below-threshold-with-connection-error)
		# Produce a below-threshold (INFO) finding but also emit a
		# ConnectionError WITH an LLM-provider context marker so the
		# infrastructure guard detects an incomplete scan.
		# The two-grep guard requires BOTH a transport error class AND an
		# LLM_PROVIDER_ONLY_REGEX marker (litellm, openai, anthropic, etc.).
		mkdir -p "$STRIX_REPORTS_DIR/fake-info-conn/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-info-conn/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: INFO
EOS
		echo "litellm.exceptions.APIConnectionError: ConnectionError - connection refused"
		echo "Penetration test failed: simulated connection error with info finding"
		exit 1
		;;
	below-threshold-with-connection-error-no-provider)
		# Produce a below-threshold (INFO) finding and emit a ConnectionError
		# WITHOUT any LLM-provider context marker.  The infra-error detector
		# should NOT match because the log lacks provider markers like
		# "litellm", "openai", "anthropic", etc.  This validates that the
		# two-grep guard avoids false positives from target-application logs.
		mkdir -p "$STRIX_REPORTS_DIR/fake-info-conn-noprov/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-info-conn-noprov/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: INFO
EOS
		echo "ConnectionError: target server refused connection on port 8443"
		echo "Penetration test failed: simulated app-level connection error"
		exit 1
		;;
	below-threshold-with-requests-connection-error)
		# Produce a below-threshold (INFO) finding with a
		# requests.exceptions.ConnectionError — the transport library prefix
		# "requests" matches the broad PROVIDER_CONTEXT_REGEX but is
		# intentionally excluded from LLM_PROVIDER_ONLY_REGEX.
		#
		# Before commit 0e90d48, the connection-error path used
		# has_provider_context_marker() (PROVIDER_CONTEXT_REGEX) and would
		# have incorrectly classified this as an LLM infrastructure error.
		# After that fix, LLM_PROVIDER_ONLY_REGEX is used, so "requests"
		# alone does NOT satisfy the provider check → below-threshold bypass
		# succeeds → exit 0.
		mkdir -p "$STRIX_REPORTS_DIR/fake-info-conn-requests/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-info-conn-requests/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: INFO
EOS
		echo "requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.example.com', port=443): Max retries exceeded with url: /v1/scan"
		echo "Penetration test failed: simulated requests transport error"
		exit 1
		;;
	below-threshold-with-midstream)
		# Produce a below-threshold (MEDIUM) finding below CRITICAL threshold
		# but also emit a MidStreamFallbackError.
		mkdir -p "$STRIX_REPORTS_DIR/fake-medium-midstream/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-medium-midstream/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: MEDIUM
EOS
		echo "Penetration test failed: LLM request failed: MidStreamFallbackError"
		echo "Penetration test failed: simulated midstream with medium finding"
		exit 1
		;;
	bare-timeout-provider-marker-exhausted-fallback)
		# Bare "Connection timed out" + provider marker: primary fails once,
		# then the gate falls back to fallback-one which succeeds.
		case "${STRIX_LLM:-}" in
		vertex_ai/bare-timeout-exhaust-primary)
			echo "Connection timed out"
			echo "vertex_ai model invocation failed"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after bare-timeout-exhaust fallback"
			exit 0
			;;
		*)
			echo "Error: bare-timeout-exhaust-fallback unexpected model (${STRIX_LLM:-})" >&2
			exit 35
			;;
		esac
		;;
	httpx-read-timeout-with-provider-marker)
		# Tier 2: httpx.ReadTimeout + provider-context marker (litellm).
		# Primary times out; fallback model succeeds.
		case "${STRIX_LLM:-}" in
		vertex_ai/httpx-timeout-primary)
			echo "httpx.ReadTimeout: timed out"
			echo "litellm.proxy: connection to upstream model failed"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after httpx-timeout fallback"
			exit 0
			;;
		*)
			echo "Error: httpx-timeout fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 45
			;;
		esac
		;;
	httpx-read-timeout-no-provider-marker)
		# Tier 2 negative: httpx.ReadTimeout WITHOUT any provider-context
		# marker.  Should NOT be classified as retryable timeout.
		echo "httpx.ReadTimeout: timed out"
		echo "application server connection pool exhausted"
		exit 1
		;;
	httpcore-read-timeout-with-provider-marker)
		# Tier 2b: httpcore.ReadTimeout + provider-context marker.
		# Primary times out; fallback model succeeds.
		case "${STRIX_LLM:-}" in
		vertex_ai/httpcore-timeout-primary)
			echo "httpcore.ReadTimeout: timed out"
			echo "litellm.proxy: connection to upstream model failed"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after httpcore-timeout fallback"
			exit 0
			;;
		*)
			echo "Error: httpcore-timeout fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 46
			;;
		esac
		;;
	httpcore-read-timeout-no-provider-marker)
		# Tier 2b negative: httpcore.ReadTimeout WITHOUT any provider-context
		# marker.  Should NOT be classified as retryable timeout.
		echo "httpcore.ReadTimeout: timed out"
		echo "application server connection pool exhausted"
		exit 1
		;;
	infra-error-sticky-flag)
		# Sticky flag test: first call hits infra error (rate limit),
		# second call fails on the first fallback model but produces a
		# LOW finding report.  After exhausting retries, the gate checks
		# has_only_below_threshold_vulnerabilities — which finds LOW
		# findings but sees INFRA_ERROR_DETECTED=1 (set from the first
		# call's rate-limit error) and refuses the below-threshold bypass.
		case "${STRIX_LLM:-}" in
		vertex_ai/sticky-flag-primary)
			touch "$FAKE_STRIX_STATE_FILE"
			echo "RateLimitError: rate limit exceeded"
			echo "litellm.proxy: rate limit on vertex_ai model"
			exit 1
			;;
		vertex_ai/gemini-2.5-pro)
			mkdir -p "$STRIX_REPORTS_DIR/run-sticky/vulnerabilities"
			cat > "$STRIX_REPORTS_DIR/run-sticky/vulnerabilities/vuln-0001.md" <<'FINDINGS'
Severity: LOW
FINDINGS
			echo "non-retryable scan error with partial results"
			exit 1
			;;
		*)
			echo "Error: infra-error-sticky-flag unexpected model (${STRIX_LLM:-})" >&2
			exit 35
			;;
		esac
		;;
	pr-baseline-critical-unchanged)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-baseline/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-baseline/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
Location 1:
sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java:5
EOS
		echo "Penetration test failed: baseline critical finding"
		exit 1
		;;
	pr-critical-changed)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-changed/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-changed/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
Location 1:
sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java:12
EOS
		echo "Penetration test failed: changed critical finding"
		exit 1
		;;
	pr-critical-changed-bracketed-next-route)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-changed-bracketed-next-route/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-changed-bracketed-next-route/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
Location 1:
frontend/src/app/labels/[slug]/page.tsx:12
EOS
		echo "Penetration test failed: changed bracketed Next.js route finding"
		exit 1
		;;
	pr-critical-changed-xml-file-location)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-changed-xml/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-changed-xml/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: HIGH
<parameter=code_locations>
  <location>
	    <file>sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java</file>
    <start_line>120</start_line>
    <end_line>124</end_line>
  </location>
</parameter=code_locations>
EOS
		echo "Penetration test failed: changed XML file location finding"
		exit 1
		;;
	pr-critical-changed-xml-file-location-space)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-changed-xml-space/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-changed-xml-space/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: HIGH
<parameter=code_locations>
  <location>
	    <file>src/unsafe name.py</file>
    <start_line>7</start_line>
    <end_line>9</end_line>
  </location>
</parameter=code_locations>
EOS
		echo "Penetration test failed: changed XML file location finding with space"
		exit 1
		;;
	pr-baseline-critical-narrative-backticked-service-file)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-baseline-narrative-service/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-baseline-narrative-service/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
Technical Analysis
The `backend/services/email_parser.py` file extracts HTML email bodies without sanitizing script tags.
EOS
		echo "Penetration test failed: baseline critical narrative service finding"
		exit 1
		;;
	pr-critical-unmapped-arbitrary-backticked-service-file)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-unmapped-arbitrary-backtick/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-unmapped-arbitrary-backtick/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
Description: location data unavailable, but the report also mentions `backend/services/email_parser.py` as unrelated context.
EOS
		echo "Penetration test failed: unmapped critical finding with arbitrary backticked file mention"
		exit 1
		;;
	pr-critical-unmapped)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-unmapped/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-unmapped/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
Description: location data unavailable
EOS
		echo "Penetration test failed: unmapped critical finding"
		exit 1
		;;
	pr-baseline-critical-absolute-target)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-baseline-absolute/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-baseline-absolute/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** File: /workspace/smart-crawling-server/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java
EOS
		echo "Penetration test failed: baseline critical finding with absolute target"
		exit 1
		;;
	pr-baseline-critical-extensionless-dockerfile-target)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-baseline-dockerfile/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-baseline-dockerfile/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** File: /workspace/smart-crawling-server/Dockerfile
EOS
		echo "Penetration test failed: baseline critical finding with extensionless Dockerfile target"
		exit 1
		;;
	pr-baseline-critical-subdir-target)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-baseline-subdir/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-baseline-subdir/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** File: /workspace/flyway/V16__hash_oauth2_registered_client_secret.sql
EOS
		echo "Penetration test failed: baseline critical finding with narrowed subdir target"
		exit 1
		;;
	pr-baseline-critical-subdir-boxed-target)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-baseline-subdir-boxed-target/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-baseline-subdir-boxed-target/vulnerabilities/vuln-0001.md" <<'EOS'
│  Severity: CRITICAL                                                          │
│  Target: /workspace/flyway/V16__hash_oauth2_registered_client_secret.sql     │
│  Endpoint: N/A (database migration script)                                   │
EOS
		echo "Penetration test failed: baseline critical finding with boxed narrowed subdir target"
		exit 1
		;;
	pr-baseline-critical-subdir-endpoint)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-baseline-subdir-endpoint/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-baseline-subdir-endpoint/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** Local Codebase: /workspace/flyway
**Endpoint:** /workspace/flyway/V16__hash_oauth2_registered_client_secret.sql
EOS
		echo "Penetration test failed: baseline critical finding with narrowed subdir endpoint"
		exit 1
		;;
	pr-baseline-critical-subdir-endpoint-bare-filename)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-baseline-subdir-endpoint-bare-filename/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-baseline-subdir-endpoint-bare-filename/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** Local Codebase: /workspace/flyway
**Endpoint:** V16__hash_oauth2_registered_client_secret.sql
EOS
		echo "Penetration test failed: baseline critical finding with narrowed subdir bare filename endpoint"
		exit 1
		;;
	pr-baseline-critical-subdir-narrative-backticked-file)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-baseline-subdir-narrative-backticked-file/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-baseline-subdir-narrative-backticked-file/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** Local Codebase: /workspace/flyway
The issue appears in file `V4__ccf_scenario.sql`.
EOS
		echo "Penetration test failed: baseline critical finding with narrowed subdir narrative backticked file"
		exit 1
		;;
	pr-critical-relative-path-escape-subdir-narrative-backticked-file)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-relative-path-escape-subdir-narrative/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-relative-path-escape-subdir-narrative/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** Local Codebase: /workspace/flyway
The issue appears in file `../V24__update_search_expression_team_keyword_id.sql`.
EOS
		echo "Penetration test failed: relative path escape critical finding with narrowed subdir narrative backticked file"
		exit 1
		;;
	pr-critical-changed-absolute-target)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-changed-absolute/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-changed-absolute/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** File: /workspace/smart-crawling-server/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java
EOS
		echo "Penetration test failed: changed critical finding with absolute target"
		exit 1
		;;
	pr-critical-changed-subdir-target)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-changed-subdir/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-changed-subdir/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** File: /workspace/flyway/V24__update_search_expression_team_keyword_id.sql
EOS
		echo "Penetration test failed: changed critical finding with narrowed subdir target"
		exit 1
		;;
	pr-critical-changed-subdir-endpoint)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-changed-subdir-endpoint/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-changed-subdir-endpoint/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** Local Codebase: /workspace/flyway
**Endpoint:** /workspace/flyway/V24__update_search_expression_team_keyword_id.sql
EOS
		echo "Penetration test failed: changed critical finding with narrowed subdir endpoint"
		exit 1
		;;
	pr-critical-path-escape-subdir-target)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-path-escape-subdir/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-path-escape-subdir/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** File: /workspace/flyway/../../../../../smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java
EOS
		echo "Penetration test failed: path escape critical finding with narrowed subdir target"
		exit 1
		;;
	pr-critical-unmapped-narrative-target)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-unmapped-narrative/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-unmapped-narrative/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** Multiple files in the codebase, particularly `org.empasy.sync.common.system.util.JwtUtil.java` (for signing) and its callers.
EOS
		echo "Penetration test failed: unmapped narrative critical finding"
		exit 1
		;;
	pr-critical-unmapped-other-workspace-repo)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-other-workspace-repo/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-other-workspace-repo/vulnerabilities/vuln-0001.md" <<'EOS'
	**Severity:** CRITICAL
	**Target:** File: /workspace/other-repo/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java
EOS
		echo "Penetration test failed: other workspace repo target"
		exit 1
		;;
	pr-critical-manifest-only-pom|pr-critical-manifest-only-pom-test-override|pr-critical-manifest-only-pom-same-head-different-pr|pr-critical-manifest-only-pom-current-pr-authoritative)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-manifest-only/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-manifest-only/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
Location 1:
pom.xml:8
EOS
		echo "Penetration test failed: manifest-only critical finding"
		exit 1
		;;
	pr-critical-manifest-only-pom-after-fallback-authoritative)
		case "${STRIX_LLM:-}" in
		vertex_ai/timeout-primary)
			echo "litellm.exceptions.Timeout: primary model timed out"
			exit 1
			;;
		vertex_ai/fallback-one)
			mkdir -p "$STRIX_REPORTS_DIR/fake-pr-manifest-only-after-fallback/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/fake-pr-manifest-only-after-fallback/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: CRITICAL
Location 1:
pom.xml:8
EOS
			echo "Penetration test failed: manifest-only critical finding after fallback"
			exit 1
			;;
		*)
			echo "Error: pr-critical-manifest-only-pom-after-fallback-authoritative unexpected model (${STRIX_LLM:-})" >&2
			exit 53
			;;
		esac
		;;
	pr-critical-manifest-only-pom-console-only-after-fallback-authoritative)
		case "${STRIX_LLM:-}" in
		vertex_ai/timeout-primary)
			echo "litellm.exceptions.Timeout: primary model timed out"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "Severity: CRITICAL"
			echo "Location 1:"
			echo "pom.xml:59"
			echo "Penetration test failed: manifest-only critical finding after fallback (console-only)"
			exit 1
			;;
		*)
			echo "Error: pr-critical-manifest-only-pom-console-only-after-fallback-authoritative unexpected model (${STRIX_LLM:-})" >&2
			exit 54
			;;
		esac
		;;
	pr-critical-manifest-only-pom-console-target-only-after-fallback-authoritative)
		case "${STRIX_LLM:-}" in
		vertex_ai/timeout-primary)
			echo "litellm.exceptions.Timeout: primary model timed out"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "Severity: CRITICAL"
			echo "Target: /workspace/$(basename "$target_path")/pom.xml"
			echo "Penetration test failed: manifest-only critical finding after fallback (console target-only)"
			exit 1
			;;
		*)
			echo "Error: pr-critical-manifest-only-pom-console-target-only-after-fallback-authoritative unexpected model (${STRIX_LLM:-})" >&2
			exit 56
			;;
		esac
		;;
	pr-low-markdown-plus-console-critical-manifest-after-fallback-authoritative)
		case "${STRIX_LLM:-}" in
		vertex_ai/timeout-primary)
			echo "litellm.exceptions.Timeout: primary model timed out"
			exit 1
			;;
		vertex_ai/fallback-one)
			mkdir -p "$STRIX_REPORTS_DIR/fake-pr-manifest-mixed-after-fallback/vulnerabilities"
			cat >"$STRIX_REPORTS_DIR/fake-pr-manifest-mixed-after-fallback/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: LOW
Location 1:
pom.xml:8
EOS
			echo "Severity: CRITICAL"
			echo "Location 1:"
			echo "pom.xml:59"
			echo "Penetration test failed: manifest-only critical finding after fallback (mixed file+console)"
			exit 1
			;;
		*)
			echo "Error: pr-low-markdown-plus-console-critical-manifest-after-fallback-authoritative unexpected model (${STRIX_LLM:-})" >&2
			exit 55
			;;
		esac
		;;
	pr-changed-scope-bounded)
		if [ -z "$target_path" ]; then
			echo "Error: target path missing" >&2
			exit 41
		fi
		if [ ! -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" ]; then
			echo "Error: changed file missing from bounded target path ($target_path)" >&2
			exit 42
		fi
		if [ -e "$target_path/sync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java" ]; then
			echo "Error: unrelated file leaked into bounded target path ($target_path)" >&2
			exit 43
		fi
		echo "scan ok with bounded changed-file scope"
		exit 0
		;;
	pr-python-scope-context)
		if [ ! -f "$target_path/backend/api/emails.py" ]; then
			echo "Error: changed backend file missing from scoped target ($target_path)" >&2
			exit 57
		fi
		if [ ! -f "$target_path/backend/core/config.py" ]; then
			echo "Error: backend core config context missing from scoped target ($target_path)" >&2
			exit 58
		fi
		if [ ! -f "$target_path/backend/core/runtime_secrets.py" ]; then
			echo "Error: backend runtime secrets context missing from scoped target ($target_path)" >&2
			exit 62
		fi
		if [ ! -f "$target_path/backend/api/search.py" ]; then
			echo "Error: backend search router context missing from scoped target ($target_path)" >&2
			exit 63
		fi
		if [ ! -f "$target_path/backend/db/session.py" ]; then
			echo "Error: backend db session context missing from scoped target ($target_path)" >&2
			exit 59
		fi
		if [ ! -f "$target_path/backend/services/exceptions.py" ]; then
			echo "Error: backend service exceptions context missing from scoped target ($target_path)" >&2
			exit 60
		fi
		if ! grep -Fq -- 'ensure_organization_access(auth_context, config.organization_id)' "$target_path/backend/api/runner_config.py"; then
			echo "Error: backend organization access context missing from scoped target ($target_path)" >&2
			exit 61
		fi
		echo "scan ok with python dependency scope"
		exit 0
		;;
	pr-changed-scope-full)
		attempt="0"
		if [ -f "${FAKE_STRIX_STATE_FILE:?}" ]; then
			attempt="$(cat "${FAKE_STRIX_STATE_FILE:?}")"
		fi
		attempt="$((attempt + 1))"
		echo "$attempt" > "${FAKE_STRIX_STATE_FILE:?}"
		if [ "$attempt" -eq 1 ]; then
			if [ ! -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" ]; then
				echo "Error: full-set scope missing controller file ($target_path)" >&2
				exit 44
			fi
			if [ ! -f "$target_path/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java" ]; then
				echo "Error: full-set scope missing playwright file ($target_path)" >&2
				exit 45
			fi
			if [ ! -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java" ]; then
				echo "Error: full-set scope missing service impl file ($target_path)" >&2
				exit 46
			fi
			echo "scan ok with full changed-file scope"
			exit 0
		fi
		echo "Error: unexpected full-scope scan attempt $attempt" >&2
		exit 50
		;;
	pr-changed-scope-full-set)
		attempt="0"
		if [ -f "${FAKE_STRIX_STATE_FILE:?}" ]; then
			attempt="$(cat "${FAKE_STRIX_STATE_FILE:?}")"
		fi
		attempt="$((attempt + 1))"
		echo "$attempt" > "${FAKE_STRIX_STATE_FILE:?}"
		if [ "$attempt" -eq 1 ] && \
		   [ -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" ] && \
		   [ -f "$target_path/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java" ] && \
		   [ -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java" ] && \
		   [ -f "$target_path/sync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java" ]; then
			echo "scan ok with full configured PR scope"
			exit 0
		fi
		echo "Error: PR changed-file scope did not include the complete changed-file set on one scan attempt $attempt ($target_path)" >&2
		exit 54
		;;
	pr-large-scope-full-set)
		echo "scan ok with large full PR scope"
		exit 0
		;;
	pr-changed-scope-includes-ci-dependency)
		if [ -f "$target_path/scripts/ci/strix_quick_gate.sh" ] && [ -f "$target_path/scripts/ci/strix_model_utils.sh" ]; then
			echo "scan ok with CI support dependency"
			exit 0
		fi
		echo "Error: PR changed-file scope missing CI support dependency ($target_path)" >&2
		exit 55
		;;
	pr-deployment-scope-entrypoint-context)
		if [ ! -f "$target_path/Dockerfile" ]; then
			echo "Error: deployment scope missing Dockerfile ($target_path)" >&2
			exit 56
		fi
		if [ ! -f "$target_path/backend/scripts/docker_entrypoint.sh" ]; then
			echo "Error: deployment scope missing backend/scripts/docker_entrypoint.sh ($target_path)" >&2
			exit 57
		fi
		if [ ! -f "$target_path/backend/core/runtime_secrets.py" ]; then
			echo "Error: deployment scope missing backend/core/runtime_secrets.py ($target_path)" >&2
			exit 60
		fi
		if ! grep -Fq -- 'CMD ["/app/scripts/docker_entrypoint.sh"]' "$target_path/Dockerfile"; then
			echo "Error: deployment Dockerfile does not reference docker_entrypoint.sh ($target_path)" >&2
			exit 58
		fi
		if ! grep -Fq -- 'Starting backend (uvicorn :8000)' "$target_path/backend/scripts/docker_entrypoint.sh"; then
			echo "Error: deployment entrypoint context did not include trusted script content ($target_path)" >&2
			exit 59
		fi
		echo "scan ok with deployment entrypoint context"
		exit 0
		;;
	*)
		echo "unknown scenario ${FAKE_STRIX_SCENARIO:?}" >&2
		exit 8
		;;
esac
EOF
	chmod +x "$fake_strix"

	cat >"$fake_gh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "${GH_TOKEN-<unset>}" >> "${FAKE_GH_TOKEN_LOG:?}"

if [ "${1-}" != "api" ]; then
	echo "unexpected gh command: $*" >&2
	exit 90
fi

if [ -z "${FAKE_GH_API_RESPONSE_FILE:-}" ]; then
	echo "missing FAKE_GH_API_RESPONSE_FILE" >&2
	exit 91
fi

cat -- "${FAKE_GH_API_RESPONSE_FILE}"
EOF
	chmod +x "$fake_gh"

	local effective_event_name="$github_event_name"
	if [ -z "$effective_event_name" ]; then
		effective_event_name="$event_name_override"
	fi

	# Scenario-specific source-tree setup so is_hallucinated_endpoint_finding()
	# can locate "real" endpoints inside the self-contained temp workspace.
	if [ "$effective_event_name" = "pull_request" ]; then
		mkdir -p "$repo_root_dir/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller"
		mkdir -p "$repo_root_dir/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl"
		mkdir -p "$repo_root_dir/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service"
		mkdir -p "$repo_root_dir/sync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util"
		echo '<project />' >"$repo_root_dir/pom.xml"
		mkdir -p "$repo_root_dir/sync-module-system/smart-crawling-server/src/main/resources/flyway"
		echo 'class ChangedController {}' >"$repo_root_dir/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"
		echo 'class BaselineUserService {}' >"$repo_root_dir/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java"
		echo 'class ChangedPlaywright {}' >"$repo_root_dir/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java"
		echo 'class ChangedJwtUtil {}' >"$repo_root_dir/sync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java"
		mkdir -p "$repo_root_dir/frontend/src/app/labels/[slug]"
		echo 'export default function Page() { return null }' >"$repo_root_dir/frontend/src/app/labels/[slug]/page.tsx"
		mkdir -p "$repo_root_dir/src"
		echo 'print("unsafe name")' >"$repo_root_dir/src/unsafe name.py"
		mkdir -p "$repo_root_dir/backend/services"
		echo 'async def send_email(*args, **kwargs): return None' >"$repo_root_dir/backend/services/email_client.py"
		echo 'def parse_eml(*args): return {}' >"$repo_root_dir/backend/services/email_parser.py"
		if [ -n "$current_pr_number" ]; then
			cat >"$event_payload_file" <<EOF
{
  "pull_request": {
    "number": $current_pr_number,
    "base": {
      "sha": "test-base-sha"
    },
    "head": {
      "sha": "test-head-sha"
    }
  }
}
EOF
		fi
		echo '-- older flyway file' >"$repo_root_dir/sync-module-system/smart-crawling-server/src/main/resources/flyway/V4__ccf_scenario.sql"
		echo '-- legacy flyway file' >"$repo_root_dir/sync-module-system/smart-crawling-server/src/main/resources/flyway/V16__hash_oauth2_registered_client_secret.sql"
		echo '-- changed flyway file' >"$repo_root_dir/sync-module-system/smart-crawling-server/src/main/resources/flyway/V24__update_search_expression_team_keyword_id.sql"
	fi

	if [ "$scenario" = "vertex-primary-existing-endpoint-nonrecoverable" ]; then
		echo 'GET /api/status' >"$repo_root_dir/src/routes.txt"
	elif [ "$scenario" = "multi-source-dirs-existing-endpoint" ]; then
		# Endpoint lives in api/ (not src/), validating multi-dir scanning.
		mkdir -p "$repo_root_dir/api"
		echo 'GET /api/status' >"$repo_root_dir/api/routes.txt"
	elif [ "$scenario" = "endpoint-in-excluded-dir" ]; then
		# Endpoint /api/hidden-secret exists ONLY inside excluded directories
		# (.git/ and node_modules/). The grep excludes must prevent matching,
		# so the finding is treated as hallucinated → fallback allowed.
		mkdir -p "$repo_root_dir/.git/refs"
		echo 'GET /api/hidden-secret' >"$repo_root_dir/.git/refs/leaked.txt"
		mkdir -p "$repo_root_dir/node_modules/fake-pkg"
		echo 'GET /api/hidden-secret' >"$repo_root_dir/node_modules/fake-pkg/index.js"
	elif [ "$scenario" = "pr-stale-source-claim-fallback-success" ]; then
		mkdir -p "$repo_root_dir/backend/db"
		cat >"$repo_root_dir/backend/db/models.py" <<'EOS'
from sqlalchemy.orm import Mapped, mapped_column

class EncryptedString:
    pass

class WorkspaceRunnerConfig:
    registration_token: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
EOS
	elif [ "$scenario" = "pr-stale-source-plus-real-finding-blocks" ]; then
		mkdir -p "$repo_root_dir/backend/db" "$repo_root_dir/backend/api"
		cat >"$repo_root_dir/backend/db/models.py" <<'EOS'
from sqlalchemy.orm import Mapped, mapped_column

class EncryptedString:
    pass

class WorkspaceRunnerConfig:
    registration_token: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
EOS
		echo 'def real_changed_endpoint(): pass' >"$repo_root_dir/backend/api/emails.py"
	elif [ "$scenario" = "pr-changed-finding-with-retry-marker-blocks" ]; then
		mkdir -p "$repo_root_dir/backend/api"
		echo 'def real_changed_endpoint(): pass' >"$repo_root_dir/backend/api/emails.py"
	elif [ "$scenario" = "pr-stale-report-plus-inline-changed-finding-blocks" ]; then
		mkdir -p "$repo_root_dir/backend/db" "$repo_root_dir/backend/api"
		cat >"$repo_root_dir/backend/db/models.py" <<'EOS'
from sqlalchemy.orm import Mapped, mapped_column

class EncryptedString:
    pass

class WorkspaceRunnerConfig:
    registration_token: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
EOS
		echo 'def real_changed_endpoint(): pass' >"$repo_root_dir/backend/api/emails.py"
	elif [ "$scenario" = "pr-changed-scope-bounded" ]; then
		echo 'class Unrelated {}' >"$repo_root_dir/sync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java"
	elif [ "$scenario" = "pr-python-scope-context" ]; then
		mkdir -p "$repo_root_dir/backend/api" "$repo_root_dir/backend/core" "$repo_root_dir/backend/db" "$repo_root_dir/backend/services"
		touch "$repo_root_dir/backend/api/__init__.py"
		touch "$repo_root_dir/backend/core/__init__.py"
		touch "$repo_root_dir/backend/db/__init__.py"
		touch "$repo_root_dir/backend/services/__init__.py"
		echo 'from db.session import get_db' >"$repo_root_dir/backend/api/emails.py"
		echo 'from api.auth import ensure_organization_access' >"$repo_root_dir/backend/api/runner_config.py"
		echo 'ensure_organization_access(auth_context, config.organization_id)' >>"$repo_root_dir/backend/api/runner_config.py"
		echo 'router = object()' >"$repo_root_dir/backend/api/search.py"
		echo 'TRUSTED_CONFIG = True' >"$repo_root_dir/backend/core/config.py"
		echo 'class LocalError(Exception): pass' >"$repo_root_dir/backend/core/exceptions.py"
		echo 'def validate_auth_session_hmac_secret_value(value): return value' >"$repo_root_dir/backend/core/runtime_secrets.py"
		echo 'engine = object()' >"$repo_root_dir/backend/db/session.py"
		echo 'class Email: pass' >"$repo_root_dir/backend/db/models.py"
		echo 'class ServiceError(Exception): pass' >"$repo_root_dir/backend/services/exceptions.py"
		echo 'async def extract_backup_async(*args): return []' >"$repo_root_dir/backend/services/archive.py"
		echo 'def parse_eml(*args): return {}' >"$repo_root_dir/backend/services/email_parser.py"
		echo 'async def generate_embeddings(*args): return []' >"$repo_root_dir/backend/services/embedding.py"
		echo 'async def assign_thread_id(*args, **kwargs): return "thread"' >"$repo_root_dir/backend/services/threading_service.py"
		echo 'async def send_email(*args, **kwargs): return None' >"$repo_root_dir/backend/services/email_client.py"
		echo 'pytest==0' >"$repo_root_dir/backend/requirements.txt"
	elif [ "$scenario" = "pr-deployment-scope-entrypoint-context" ] || [ "$scenario" = "pr-baseline-critical-extensionless-dockerfile-target" ]; then
		mkdir -p "$repo_root_dir/.github/workflows" "$repo_root_dir/backend/api" "$repo_root_dir/backend/core" "$repo_root_dir/backend/scripts" "$repo_root_dir/frontend"
		echo 'name: OpenCode Review' >"$repo_root_dir/.github/workflows/opencode-review.yml"
		cat >"$repo_root_dir/Dockerfile" <<'EOS'
FROM python:3.11-slim AS backend-runtime
WORKDIR /app
COPY backend /app/
FROM backend-runtime
RUN chmod +x /app/scripts/docker_entrypoint.sh
CMD ["/app/scripts/docker_entrypoint.sh"]
EOS
		cat >"$repo_root_dir/backend/scripts/docker_entrypoint.sh" <<'EOS'
#!/usr/bin/env bash
echo "Starting backend (uvicorn :8000)"
EOS
		echo 'router = object()' >"$repo_root_dir/backend/api/auth.py"
		echo 'class Settings: pass' >"$repo_root_dir/backend/core/config.py"
		echo 'def validate_auth_session_hmac_secret_value(value): return value' >"$repo_root_dir/backend/core/runtime_secrets.py"
		echo 'app = object()' >"$repo_root_dir/backend/main.py"
		touch "$repo_root_dir/frontend/Dockerfile"
		echo '{"scripts":{"start":"next start"}}' >"$repo_root_dir/frontend/package.json"
		touch "$repo_root_dir/frontend/next.config.ts"
		touch "$repo_root_dir/frontend/postcss.config.mjs"
		touch "$repo_root_dir/docker-compose.yml"
		touch "$repo_root_dir/render.yaml"
		echo '0.0.0' >"$repo_root_dir/VERSION"
	elif [ "$scenario" = "pr-large-scope-full-set" ]; then
		mkdir -p "$repo_root_dir/backend/large-scope"
		local large_scope_index
		for large_scope_index in $(seq 1 38); do
			printf 'file %s\n' "$large_scope_index" >"$repo_root_dir/backend/large-scope/file-$large_scope_index.py"
		done
	fi

	set +e
	local env_cmd=(
		PATH="$bin_dir:$PATH"
		STRIX_INPUT_FILE_ROOT="$tmp_dir"
		GITHUB_EVENT_NAME=""
		GITHUB_EVENT_PATH=""
		FAKE_STRIX_SCENARIO="$scenario"
		FAKE_STRIX_CALL_LOG="$call_log"
		FAKE_STRIX_API_BASE_LOG="$api_base_log"
		FAKE_STRIX_TARGET_LOG="$target_log"
		FAKE_STRIX_RUNTIME_ENV_LOG="$runtime_env_log"
		STRIX_LLM_DEFAULT_PROVIDER="$default_provider"
		FAKE_STRIX_STATE_FILE="$state_file"
		STRIX_TRANSIENT_RETRY_PER_MODEL="$transient_retry_per_model"
		STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS="$transient_retry_backoff_seconds"
		STRIX_PROCESS_TIMEOUT_SECONDS="$process_timeout_seconds"
		STRIX_TOTAL_TIMEOUT_SECONDS="$total_timeout_seconds"
		STRIX_FAIL_ON_MIN_SEVERITY="$min_fail_severity"
		STRIX_REPORTS_DIR="$repo_root_dir/strix_runs"
		STRIX_TARGET_PATH="$effective_target_path"
	)
	if [ "$scenario" = "runtime-env-forwarding" ]; then
		env_cmd+=(
			LLM_TIMEOUT="90"
			STRIX_MEMORY_COMPRESSOR_TIMEOUT="10"
			STRIX_REASONING_EFFORT="minimal"
			STRIX_LLM_MAX_RETRIES="1"
			GEMINI_LOCATION="GLOBAL"
			UNRELATED_SECRET="should-not-forward"
		)
	fi
	if [ "$scenario" = "report-known-internal-warning-sanitized" ]; then
		env_cmd+=(
			FAKE_STRIX_OUTSIDE_REPORT_DIR="$repo_root_dir/outside-strix-report"
		)
	fi
	if [ "$min_fail_severity" = "__UNSET__" ]; then
		local next_env_cmd=()
		local env_pair
		for env_pair in "${env_cmd[@]}"; do
			case "$env_pair" in
			STRIX_FAIL_ON_MIN_SEVERITY=*)
				continue
				;;
			esac
			next_env_cmd+=("$env_pair")
		done
		env_cmd=("${next_env_cmd[@]}")
	fi
	printf '%s' "$initial_model" >"$strix_llm_file"
	env_cmd+=(STRIX_LLM_FILE="$strix_llm_file")
	printf '%s' 'dummy' >"$llm_api_key_file"
	env_cmd+=(LLM_API_KEY_FILE="$llm_api_key_file")
	env_cmd+=(STRIX_DISABLE_PR_SCOPING="$disable_pr_scoping")
	env_cmd+=(STRIX_FAIL_ON_PROVIDER_SIGNAL="$fail_on_provider_signal")
	local llm_api_base_source="$raw_llm_api_base"
	if [ -z "$llm_api_base_source" ] && [ -n "$initial_llm_api_base" ]; then
		llm_api_base_source="$initial_llm_api_base"
	fi
	if [ -n "$llm_api_base_source" ]; then
		printf '%s' "$llm_api_base_source" >"$llm_api_base_file"
		env_cmd+=(LLM_API_BASE_FILE="$llm_api_base_file")
	fi
	# Only export fallback variables when a non-empty value is provided so the
	# gate's ${VAR+x} checks correctly distinguish "unset → use defaults" from
	# "set to empty → disable fallbacks".
	if [ -n "$fallback_models" ]; then
		env_cmd+=(STRIX_VERTEX_FALLBACK_MODELS="$fallback_models")
	fi
	case "$gemini_fallback_models" in
	__SAME_AS_FALLBACK_MODELS__)
		if [ -n "$fallback_models" ]; then
			env_cmd+=(STRIX_GEMINI_FALLBACK_MODELS="$fallback_models")
		fi
		;;
	__UNSET__)
		;;
	*)
		if [ -n "$gemini_fallback_models" ]; then
			env_cmd+=(STRIX_GEMINI_FALLBACK_MODELS="$gemini_fallback_models")
		fi
		;;
	esac
	if [ -n "$generic_fallback_models" ]; then
		env_cmd+=(STRIX_FALLBACK_MODELS="$generic_fallback_models")
	fi
	if [ -n "$custom_source_dirs" ]; then
		env_cmd+=(STRIX_SOURCE_DIRS="$custom_source_dirs")
	fi
	: "$legacy_scope_size_ignored"
	if [ -n "$github_event_name" ]; then
		env_cmd+=(GITHUB_EVENT_NAME="$github_event_name")
	fi
	if [ -n "$event_name_override" ]; then
		env_cmd+=(EVENT_NAME="$event_name_override")
	fi
	if [ -n "$test_pr_sca_status_override" ]; then
		env_cmd+=(STRIX_TEST_PR_SCA_STATUS_OVERRIDE="$test_pr_sca_status_override")
	fi
	if [ -n "$current_pr_number" ]; then
		env_cmd+=(GITHUB_EVENT_PATH="$event_payload_file")
		env_cmd+=(GITHUB_REPOSITORY="octo-org/smart-crawling-server")
		env_cmd+=(PR_BASE_SHA="test-base-sha")
		env_cmd+=(PR_HEAD_SHA="test-head-sha")
		env_cmd+=(GH_TOKEN="ghs_test_token")
	fi
	if [ -n "$authoritative_sca_runs_json" ]; then
		local gh_api_response_file="$tmp_dir/gh-api-response.json"
		printf '%s\n' "$authoritative_sca_runs_json" >"$gh_api_response_file"
		env_cmd+=(FAKE_GH_API_RESPONSE_FILE="$gh_api_response_file")
		env_cmd+=(FAKE_GH_TOKEN_LOG="$gh_token_log")
	fi
	if [ "$changed_files_override" = "__SET_EMPTY__" ]; then
		env_cmd+=(STRIX_TEST_CHANGED_FILES_OVERRIDE="")
	elif [ -n "$changed_files_override" ]; then
		env_cmd+=(STRIX_TEST_CHANGED_FILES_OVERRIDE="$changed_files_override")
	fi
	(
		cd "$repo_root_dir"
		env \
			-u GITHUB_EVENT_NAME \
			-u GITHUB_EVENT_PATH \
			-u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			-u STRIX_VERTEX_FALLBACK_MODELS \
			-u STRIX_GEMINI_FALLBACK_MODELS \
			-u STRIX_FALLBACK_MODELS \
			"${env_cmd[@]}" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "$expected_exit" "$rc" "scenario=$scenario exit code"

	if [ -n "$expected_message" ]; then
		case "$expected_message" in
		REGEX:*)
			assert_file_matches "$output_log" "${expected_message#REGEX:}" "scenario=$scenario output"
			;;
		*)
			assert_file_contains "$output_log" "$expected_message" "scenario=$scenario output"
			;;
		esac
	fi

	local call_count
	call_count="0"
	if [ -f "$call_log" ]; then
		call_count="$(wc -l <"$call_log" | tr -d ' ')"
	fi
	assert_equals "$expected_calls" "$call_count" "scenario=$scenario strix call count"

	if [ -n "$expected_model_sequence" ]; then
		local actual_model_sequence=""
		if [ -f "$call_log" ]; then
			while IFS= read -r model; do
				if [ -n "$actual_model_sequence" ]; then
					actual_model_sequence="${actual_model_sequence}|$model"
				else
					actual_model_sequence="$model"
				fi
			done <"$call_log"
		fi

		assert_equals "$expected_model_sequence" "$actual_model_sequence" "scenario=$scenario STRIX_LLM sequence"
	fi

	if [ -n "$expected_api_base_sequence" ]; then
		local actual_api_base_sequence=""
		if [ -f "$api_base_log" ]; then
			while IFS= read -r api_base; do
				if [ -n "$actual_api_base_sequence" ]; then
					actual_api_base_sequence="${actual_api_base_sequence}|$api_base"
				else
					actual_api_base_sequence="$api_base"
				fi
			done <"$api_base_log"
		fi

		assert_equals "$expected_api_base_sequence" "$actual_api_base_sequence" "scenario=$scenario LLM_API_BASE sequence"
	fi

	if [ "$scenario" = "runtime-env-forwarding" ]; then
		assert_file_contains \
			"$runtime_env_log" \
			"LLM_TIMEOUT=90;STRIX_MEMORY_COMPRESSOR_TIMEOUT=10;STRIX_REASONING_EFFORT=minimal;STRIX_LLM_MAX_RETRIES=1;GEMINI_LOCATION=GLOBAL;PYTHONWARNINGS=ignore:Pydantic serializer warnings:UserWarning:pydantic.main;NPM_CONFIG_IGNORE_SCRIPTS=true;PNPM_CONFIG_IGNORE_SCRIPTS=true;YARN_ENABLE_SCRIPTS=false;UNRELATED_SECRET=<unset>" \
			"scenario=$scenario runtime env forwarding"
	fi

	if [ "$scenario" = "report-known-internal-warning-sanitized" ]; then
		assert_file_not_contains \
			"$repo_root_dir/strix_runs/fake-known-internal-warning/strix.log" \
			"produced non-lifecycle final output" \
			"scenario=$scenario strips the known internal Strix warning from published artifacts"
		assert_file_contains \
			"$repo_root_dir/strix_runs/fake-known-internal-warning/strix.log" \
			"finish_scan: completed scan with 0 vulnerability report(s)" \
			"scenario=$scenario keeps non-warning Strix report evidence"
		assert_file_contains \
			"$repo_root_dir/outside-strix-report/strix.log" \
			"outside report should not be rewritten" \
			"scenario=$scenario does not rewrite logs through symlinked report directories"
	fi

	if [ "$scenario" = "pr-changed-scope-full-set" ]; then
		assert_internal_pr_scope_targets "$target_log" "$repo_root_dir" "$expected_calls"
	fi

	rm -rf "$tmp_dir"
}

run_gate_case_with_provider_signal_mode() {
	local provider_signal_mode="$1"
	shift
	local args=("$@")
	local default_args=(
		"vertex_ai"
		"__DEFAULT__"
		""
		"0"
		"CRITICAL"
		"0"
		""
		""
		"1200"
		"0"
		""
		""
		""
		""
		"0"
		""
		""
		""
		"__SAME_AS_FALLBACK_MODELS__"
		""
	)

	while [ "${#args[@]}" -lt 28 ]; do
		args+=("${default_args[${#args[@]} - 8]}")
	done
	args+=("$provider_signal_mode")
	run_gate_case "${args[@]}"
}

run_gate_case_allow_provider_signal() {
	run_gate_case_with_provider_signal_mode "0" "$@"
}

run_pull_request_target_head_scope_case() {
	local case_name="$1"
	local changed_file="$2"
	local base_content="$3"
	local head_content="$4"
	local disable_pr_scoping="${5-0}"
	local make_head_executable="${6-0}"
	local target_path="${7-.}"

	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local fake_strix="$bin_dir/strix"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

target_path=""
while [ "$#" -gt 0 ]; do
	if [ "$1" = "-t" ] && [ "$#" -ge 2 ]; then
		target_path="$2"
		break
	fi
	shift
done

scoped_file="$target_path/${FAKE_STRIX_EXPECTED_CHANGED_FILE:?}"
if [ ! -f "$scoped_file" ]; then
	echo "Error: PR head scoped file missing ($scoped_file)" >&2
	exit 61
fi
if ! grep -Fq -- "${FAKE_STRIX_EXPECTED_HEAD_CONTENT:?}" "$scoped_file"; then
	echo "Error: PR head scoped file did not contain head content" >&2
	cat -- "$scoped_file" >&2
	exit 62
fi
if [ -n "${FAKE_STRIX_UNEXPECTED_BASE_CONTENT:-}" ] && grep -Fq -- "$FAKE_STRIX_UNEXPECTED_BASE_CONTENT" "$scoped_file"; then
	echo "Error: PR head scoped file leaked base checkout content" >&2
	cat -- "$scoped_file" >&2
	exit 63
fi
if [ -x "$scoped_file" ]; then
	echo "Error: PR head scoped file must be copied as non-executable data" >&2
	exit 64
fi
unchanged_file="$target_path/${FAKE_STRIX_EXPECTED_UNCHANGED_FILE:?}"
if [ "${FAKE_STRIX_EXPECT_FULL_HEAD_SCOPE:-0}" = "1" ]; then
	if [ ! -f "$unchanged_file" ]; then
		echo "Error: full PR head scoped file missing ($unchanged_file)" >&2
		exit 65
	fi
	if ! grep -Fq -- "${FAKE_STRIX_EXPECTED_UNCHANGED_CONTENT:?}" "$unchanged_file"; then
		echo "Error: full PR head scoped file did not contain head-tree content" >&2
		cat -- "$unchanged_file" >&2
		exit 66
	fi
	if [ -x "$unchanged_file" ]; then
		echo "Error: full PR head scoped file must be copied as non-executable data" >&2
		exit 67
	fi
else
	if [ -e "$unchanged_file" ]; then
		echo "Error: unrelated PR head file leaked into bounded scope ($unchanged_file)" >&2
		exit 68
	fi
fi
echo "scan ok with PR head content"
EOF
	chmod +x "$fake_strix"
	printf '%s' 'gemini/test-model' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	(
		cd "$repo_root_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		echo 'seed' >README.md
		mkdir -p docs
		printf '%s\n' 'BASE_FULL_SCOPE_CONTEXT_SHOULD_NOT_BE_SCANNED' >docs/full-scope-context.md
		if [ "$base_content" != "__ABSENT__" ]; then
			mkdir -p "$(dirname -- "$changed_file")"
			printf '%s\n' "$base_content" >"$changed_file"
		fi
		git add .
		git commit -qm 'base commit'
	)
	local base_sha
	base_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	(
		cd "$repo_root_dir"
		printf '%s\n' 'HEAD_FULL_SCOPE_CONTEXT_SHOULD_BE_SCANNED' >docs/full-scope-context.md
		mkdir -p "$(dirname -- "$changed_file")"
		printf '%s\n' "$head_content" >"$changed_file"
		if [ "$make_head_executable" = "1" ]; then
			chmod +x "$changed_file"
		fi
		git add .
		git commit -qm 'head commit'
	)
	local head_sha
	head_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	git -C "$repo_root_dir" checkout -q "$base_sha"

	local unexpected_base_content=""
	if [ "$base_content" != "__ABSENT__" ]; then
		unexpected_base_content="$base_content"
	fi

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request_target" \
			PR_BASE_SHA="$base_sha" \
			PR_HEAD_SHA="$head_sha" \
			STRIX_TEST_CHANGED_FILES_OVERRIDE="$changed_file" \
			FAKE_STRIX_EXPECTED_CHANGED_FILE="$changed_file" \
			FAKE_STRIX_EXPECTED_HEAD_CONTENT="$head_content" \
			FAKE_STRIX_UNEXPECTED_BASE_CONTENT="$unexpected_base_content" \
			FAKE_STRIX_EXPECTED_UNCHANGED_FILE="docs/full-scope-context.md" \
			FAKE_STRIX_EXPECTED_UNCHANGED_CONTENT="HEAD_FULL_SCOPE_CONTEXT_SHOULD_BE_SCANNED" \
			FAKE_STRIX_EXPECT_FULL_HEAD_SCOPE="$disable_pr_scoping" \
			STRIX_DISABLE_PR_SCOPING="$disable_pr_scoping" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="$target_path" \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "0" "$rc" "case=$case_name exit code"
	assert_file_contains "$output_log" "scan ok with PR head content" "case=$case_name output"

	rm -rf "$tmp_dir"
}

run_pull_request_target_plaintext_runner_token_fails_closed_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local fake_strix="$bin_dir/strix"
	local output_log="$tmp_dir/output.log"
	local call_log="$tmp_dir/calls.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"
	local changed_file="backend/db/models.py"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

printf '%s\n' "${STRIX_LLM:-}" >> "${FAKE_STRIX_CALL_LOG:?}"
case "${STRIX_LLM:-}" in
vertex_ai/stale-source-primary)
	mkdir -p "${STRIX_REPORTS_DIR:?}/fake-pr-head-plaintext/vulnerabilities"
	cat >"$STRIX_REPORTS_DIR/fake-pr-head-plaintext/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** HIGH
**Target:** backend/db/models.py

The `WorkspaceRunnerConfig.registration_token` field stores the token as plain text.
The vulnerable line is `registration_token: Mapped[str | None] = mapped_column(String, nullable=True)`.
EOS
	echo "Penetration test failed: PR-head plaintext token finding"
	exit 1
	;;
vertex_ai/fallback-one)
	echo "Error: PR-head plaintext findings must not reach fallback" >&2
	exit 31
	;;
*)
	echo "Error: unexpected model (${STRIX_LLM:-})" >&2
	exit 32
	;;
esac
EOF
	chmod +x "$fake_strix"
	printf '%s' 'vertex_ai/stale-source-primary' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	(
		cd "$repo_root_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		mkdir -p "$(dirname -- "$changed_file")"
		cat >"$changed_file" <<'EOS'
from sqlalchemy.orm import Mapped, mapped_column

class EncryptedString:
    pass

class WorkspaceRunnerConfig:
    registration_token: Mapped[str | None] = mapped_column(
        EncryptedString, nullable=True
    )
EOS
		git add .
		git commit -qm 'base commit'
	)
	local base_sha
	base_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	(
		cd "$repo_root_dir"
		cat >"$changed_file" <<'EOS'
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

class WorkspaceRunnerConfig:
    registration_token: Mapped[str | None] = mapped_column(String, nullable=True)
EOS
		git add .
		git commit -qm 'head commit'
	)
	local head_sha
	head_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	git -C "$repo_root_dir" checkout -q "$base_sha"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request_target" \
			PR_BASE_SHA="$base_sha" \
			PR_HEAD_SHA="$head_sha" \
			STRIX_TEST_CHANGED_FILES_OVERRIDE="$changed_file" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_VERTEX_FALLBACK_MODELS="vertex_ai/fallback-one" \
			STRIX_FAIL_ON_MIN_SEVERITY="HIGH" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "1" "$rc" "case=pull-request-target-plaintext-runner-token-fails-closed exit code"
	assert_file_contains "$output_log" "Strix finding intersects files changed in this pull request." "case=pull-request-target-plaintext-runner-token-fails-closed output"
	local call_count="0"
	if [ -f "$call_log" ]; then
		call_count="$(wc -l <"$call_log" | tr -d ' ')"
	fi
	assert_equals "1" "$call_count" "case=pull-request-target-plaintext-runner-token-fails-closed strix call count"

	rm -rf "$tmp_dir"
}

run_pull_request_target_bounded_head_context_scope_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local fake_strix="$bin_dir/strix"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"
	local changed_file="backend/api/emails.py"
	local context_file="backend/core/only_in_head.py"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

target_path=""
while [ "$#" -gt 0 ]; do
	if [ "$1" = "-t" ] && [ "$#" -ge 2 ]; then
		target_path="$2"
		break
	fi
	shift
done

changed_file="$target_path/${FAKE_STRIX_EXPECTED_CHANGED_FILE:?}"
context_file="$target_path/${FAKE_STRIX_EXPECTED_CONTEXT_FILE:?}"
if ! grep -Fq -- "${FAKE_STRIX_EXPECTED_HEAD_CONTENT:?}" "$changed_file"; then
	echo "Error: PR head changed file content was not scanned" >&2
	cat -- "$changed_file" >&2
	exit 65
fi
if [ -e "$context_file" ]; then
	echo "Error: unrelated PR head backend context leaked into bounded scope" >&2
	cat -- "$context_file" >&2
	exit 66
fi
echo "scan ok with bounded PR head backend context"
EOF
	chmod +x "$fake_strix"
	printf '%s' 'gemini/test-model' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	(
		cd "$repo_root_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		mkdir -p "$(dirname -- "$changed_file")"
		printf '%s\n' 'BASE_CHANGED_CONTENT_SHOULD_NOT_BE_SCANNED' >"$changed_file"
		git add .
		git commit -qm 'base commit'
	)
	local base_sha
	base_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	(
		cd "$repo_root_dir"
		mkdir -p "$(dirname -- "$context_file")"
		printf '%s\n' 'HEAD_CHANGED_CONTENT_SHOULD_BE_SCANNED' >"$changed_file"
		printf '%s\n' 'UNTRUSTED_HEAD_CONTEXT_SHOULD_NOT_BE_SCANNED' >"$context_file"
		chmod +x "$context_file"
		git add .
		git commit -qm 'head commit'
	)
	local head_sha
	head_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	git -C "$repo_root_dir" checkout -q "$base_sha"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request_target" \
			PR_BASE_SHA="$base_sha" \
			PR_HEAD_SHA="$head_sha" \
			STRIX_TEST_CHANGED_FILES_OVERRIDE="$changed_file" \
			FAKE_STRIX_EXPECTED_CHANGED_FILE="$changed_file" \
			FAKE_STRIX_EXPECTED_CONTEXT_FILE="$context_file" \
			FAKE_STRIX_EXPECTED_HEAD_CONTENT="HEAD_CHANGED_CONTENT_SHOULD_BE_SCANNED" \
			FAKE_STRIX_EXPECTED_HEAD_CONTEXT="UNTRUSTED_HEAD_CONTEXT_SHOULD_NOT_BE_SCANNED" \
			FAKE_STRIX_UNEXPECTED_BASE_CONTEXT="TRUSTED_BASE_CONTEXT_SHOULD_NOT_BE_SCANNED" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "0" "$rc" "case=pull-request-target-backend-context-uses-bounded-head-scope exit code"
	assert_file_contains "$output_log" "scan ok with bounded PR head backend context" "case=pull-request-target-backend-context-uses-bounded-head-scope output"

	rm -rf "$tmp_dir"
}

run_pull_request_target_changed_context_scope_uses_pr_head_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local fake_strix="$bin_dir/strix"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"
	local state_file="$tmp_dir/state.log"
	local changed_file="backend/api/emails.py"
	local context_file="backend/core/config.py"
	local requirements_file="backend/requirements.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

target_path=""
while [ "$#" -gt 0 ]; do
	if [ "$1" = "-t" ] && [ "$#" -ge 2 ]; then
		target_path="$2"
		break
	fi
	shift
done

attempt="0"
if [ -f "${FAKE_STRIX_STATE_FILE:?}" ]; then
	attempt="$(cat "${FAKE_STRIX_STATE_FILE:?}")"
fi
attempt="$((attempt + 1))"
echo "$attempt" >"${FAKE_STRIX_STATE_FILE:?}"

context_file="$target_path/${FAKE_STRIX_EXPECTED_CONTEXT_FILE:?}"
if ! grep -Fq -- "${FAKE_STRIX_EXPECTED_HEAD_CONTEXT:?}" "$context_file"; then
	echo "Error: changed backend context did not use PR head content" >&2
	cat -- "$context_file" >&2
	exit 68
fi
if grep -Fq -- "${FAKE_STRIX_UNEXPECTED_BASE_CONTEXT:?}" "$context_file"; then
	echo "Error: changed backend context leaked trusted base content" >&2
	cat -- "$context_file" >&2
	exit 69
fi

requirements_file="$target_path/${FAKE_STRIX_EXPECTED_REQUIREMENTS_FILE:?}"
if ! grep -Fq -- "${FAKE_STRIX_EXPECTED_HEAD_REQUIREMENTS:?}" "$requirements_file"; then
	echo "Error: changed filtered backend context did not use PR head content" >&2
	cat -- "$requirements_file" >&2
	exit 72
fi
if grep -Fq -- "${FAKE_STRIX_UNEXPECTED_BASE_REQUIREMENTS:?}" "$requirements_file"; then
	echo "Error: changed filtered backend context leaked trusted base content" >&2
	cat -- "$requirements_file" >&2
	exit 73
fi

if [ "$attempt" -eq 1 ]; then
	changed_file="$target_path/${FAKE_STRIX_EXPECTED_CHANGED_FILE:?}"
	if ! grep -Fq -- "${FAKE_STRIX_EXPECTED_HEAD_CONTENT:?}" "$changed_file"; then
		echo "Error: PR head changed file content was not scanned" >&2
		cat -- "$changed_file" >&2
		exit 70
	fi
	echo "scan ok with changed PR head backend context"
	exit 0
fi

echo "Error: unexpected changed context scan attempt $attempt" >&2
exit 71
EOF
	chmod +x "$fake_strix"
	printf '%s' 'gemini/test-model' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	(
		cd "$repo_root_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		mkdir -p "$(dirname -- "$changed_file")" "$(dirname -- "$context_file")" "$(dirname -- "$requirements_file")"
		printf '%s\n' 'BASE_CHANGED_CONTENT_SHOULD_NOT_BE_SCANNED' >"$changed_file"
		printf '%s\n' 'BASE_CONTEXT_SHOULD_NOT_BE_SCANNED' >"$context_file"
		printf '%s\n' 'BASE_REQUIREMENTS_SHOULD_NOT_BE_SCANNED' >"$requirements_file"
		git add .
		git commit -qm 'base commit'
	)
	local base_sha
	base_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	(
		cd "$repo_root_dir"
		printf '%s\n' 'HEAD_CHANGED_CONTENT_SHOULD_BE_SCANNED' >"$changed_file"
		printf '%s\n' 'HEAD_CONTEXT_SHOULD_BE_SCANNED' >"$context_file"
		printf '%s\n' 'HEAD_REQUIREMENTS_SHOULD_BE_SCANNED' >"$requirements_file"
		git add .
		git commit -qm 'head commit'
	)
	local head_sha
	head_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	git -C "$repo_root_dir" checkout -q "$base_sha"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request_target" \
			PR_BASE_SHA="$base_sha" \
			PR_HEAD_SHA="$head_sha" \
			STRIX_TEST_CHANGED_FILES_OVERRIDE="$(printf '%s\n%s\n%s' "$changed_file" "$context_file" "$requirements_file")" \
			FAKE_STRIX_EXPECTED_CHANGED_FILE="$changed_file" \
			FAKE_STRIX_EXPECTED_CONTEXT_FILE="$context_file" \
			FAKE_STRIX_EXPECTED_REQUIREMENTS_FILE="$requirements_file" \
			FAKE_STRIX_EXPECTED_HEAD_CONTENT="HEAD_CHANGED_CONTENT_SHOULD_BE_SCANNED" \
			FAKE_STRIX_EXPECTED_HEAD_CONTEXT="HEAD_CONTEXT_SHOULD_BE_SCANNED" \
			FAKE_STRIX_EXPECTED_HEAD_REQUIREMENTS="HEAD_REQUIREMENTS_SHOULD_BE_SCANNED" \
			FAKE_STRIX_UNEXPECTED_BASE_CONTEXT="BASE_CONTEXT_SHOULD_NOT_BE_SCANNED" \
			FAKE_STRIX_UNEXPECTED_BASE_REQUIREMENTS="BASE_REQUIREMENTS_SHOULD_NOT_BE_SCANNED" \
			FAKE_STRIX_STATE_FILE="$state_file" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "0" "$rc" "case=pull-request-target-changed-context-uses-pr-head exit code"
	assert_file_contains "$output_log" "scan ok with changed PR head backend context" "case=pull-request-target-changed-context-uses-pr-head output"

	printf '0' >"$state_file"
	(
		cd "$repo_root_dir"
		git checkout -q "$head_sha"
	)
	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request" \
			STRIX_TEST_CHANGED_FILES_OVERRIDE="$(printf '%s\n%s' '../outside.py' "$changed_file")" \
			FAKE_STRIX_EXPECTED_CHANGED_FILE="$changed_file" \
			FAKE_STRIX_EXPECTED_CONTEXT_FILE="$context_file" \
			FAKE_STRIX_EXPECTED_REQUIREMENTS_FILE="$requirements_file" \
			FAKE_STRIX_EXPECTED_HEAD_CONTENT="HEAD_CHANGED_CONTENT_SHOULD_BE_SCANNED" \
			FAKE_STRIX_EXPECTED_HEAD_CONTEXT="HEAD_CONTEXT_SHOULD_BE_SCANNED" \
			FAKE_STRIX_EXPECTED_HEAD_REQUIREMENTS="HEAD_REQUIREMENTS_SHOULD_BE_SCANNED" \
			FAKE_STRIX_UNEXPECTED_BASE_CONTEXT="BASE_CONTEXT_SHOULD_NOT_BE_SCANNED" \
			FAKE_STRIX_UNEXPECTED_BASE_REQUIREMENTS="BASE_REQUIREMENTS_SHOULD_NOT_BE_SCANNED" \
			FAKE_STRIX_STATE_FILE="$state_file" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	rc=$?
	set -e

	assert_equals "0" "$rc" "case=pull-request-unsafe-changed-file-does-not-abort-context exit code"
	assert_file_contains "$output_log" "scan ok with changed PR head backend context" "case=pull-request-unsafe-changed-file-does-not-abort-context output"

	rm -rf "$tmp_dir"
}

run_pull_request_target_changed_backend_context_scope_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local fake_strix="$bin_dir/strix"
	local output_log="$tmp_dir/output.log"
	local call_log="$tmp_dir/calls.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

printf 'called\n' >> "${FAKE_STRIX_CALL_LOG:?}"

target_path=""
while [ "$#" -gt 0 ]; do
	if [ "$1" = "-t" ] && [ "$#" -ge 2 ]; then
		target_path="$2"
		break
	fi
	shift
done

matched_backend_context=0
if [ -f "$target_path/backend/api/calendar.py" ]; then
	if [ ! -f "$target_path/backend/services/calendar_service.py" ]; then
		echo "Error: calendar service backend dependency context missing from PR scope ($target_path)" >&2
		exit 72
	fi
	if ! grep -Fq -- 'BASE_CALENDAR_SERVICE_SHOULD_BE_SCANNED' "$target_path/backend/services/calendar_service.py"; then
		echo "Error: calendar service backend dependency context did not use trusted base content" >&2
		cat -- "$target_path/backend/services/calendar_service.py" >&2
		exit 73
	fi
	echo "scan ok with calendar service backend context"
	matched_backend_context=1
fi

if [ -f "$target_path/backend/api/emails.py" ]; then
	if [ ! -f "$target_path/backend/api/mailbox_scope.py" ]; then
		echo "Error: changed backend dependency context missing from PR scope ($target_path)" >&2
		exit 68
	fi
	if [ ! -f "$target_path/backend/api/runner_config.py" ]; then
		echo "Error: runner config backend dependency context missing from PR scope ($target_path)" >&2
		exit 70
	fi
	if ! grep -Fq -- 'HEAD_MAILBOX_SCOPE_SHOULD_BE_SCANNED' "$target_path/backend/api/mailbox_scope.py"; then
		echo "Error: changed backend dependency context did not use PR-head content" >&2
		cat -- "$target_path/backend/api/mailbox_scope.py" >&2
		exit 69
	fi
	if ! grep -Fq -- 'HEAD_RUNNER_CONFIG_SHOULD_BE_SCANNED' "$target_path/backend/api/runner_config.py"; then
		echo "Error: runner config backend dependency context did not use PR-head content" >&2
		cat -- "$target_path/backend/api/runner_config.py" >&2
		exit 71
	fi
	echo "scan ok with PR-head backend dependency context"
	matched_backend_context=1
fi

if [ -f "$target_path/backend/api/llm_providers.py" ]; then
	if [ ! -f "$target_path/backend/services/llm_provider_urls.py" ]; then
		echo "Error: LLM provider URL validation context missing from PR scope ($target_path)" >&2
		exit 74
	fi
	if ! grep -Fq -- 'HEAD_LLM_PROVIDER_URLS_SHOULD_BE_SCANNED' "$target_path/backend/services/llm_provider_urls.py"; then
		echo "Error: LLM provider URL validation context did not use PR-head content" >&2
		cat -- "$target_path/backend/services/llm_provider_urls.py" >&2
		exit 75
	fi
	echo "scan ok with PR-head LLM provider URL validation context"
	matched_backend_context=1
fi

if [ -f "$target_path/backend/services/email_parser.py" ]; then
	if [ ! -f "$target_path/backend/services/text_safety.py" ]; then
		echo "Error: email parser text safety context missing from PR scope ($target_path)" >&2
		exit 76
	fi
	if ! grep -Fq -- 'HEAD_TEXT_SAFETY_SHOULD_BE_SCANNED' "$target_path/backend/services/text_safety.py"; then
		echo "Error: email parser text safety context did not use PR-head content" >&2
		cat -- "$target_path/backend/services/text_safety.py" >&2
		exit 77
	fi
	echo "scan ok with PR-head email parser text safety context"
	matched_backend_context=1
fi

if [ "$matched_backend_context" -eq 1 ]; then
	exit 0
fi

echo "scan ok with non-email backend scope"
EOF
	chmod +x "$fake_strix"
	printf '%s' 'gemini/test-model' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	(
		cd "$repo_root_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		echo 'seed' >README.md
		mkdir -p backend/api backend/services
		printf '%s\n' 'BASE_AUTH_CONTENT_SHOULD_NOT_BE_SCANNED' >backend/api/auth.py
		printf '%s\n' 'BASE_EMAILS_CONTENT_SHOULD_NOT_BE_SCANNED' >backend/api/emails.py
		printf '%s\n' 'BASE_CALENDAR_SERVICE_SHOULD_BE_SCANNED' >backend/services/calendar_service.py
		printf '%s\n' 'BASE_LLM_PROVIDER_URLS_SHOULD_NOT_BE_SCANNED' >backend/services/llm_provider_urls.py
		git add .
		git commit -qm 'base commit'
	)
	local base_sha
	base_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	(
		cd "$repo_root_dir"
		cat >backend/api/auth.py <<'EOF'
HEAD_AUTH_CONTENT_SHOULD_BE_SCANNED
EOF
		cat >backend/api/calendar.py <<'EOF'
HEAD_CALENDAR_CONTENT_SHOULD_BE_SCANNED
EOF
		cat >backend/api/emails.py <<'EOF'
from api.mailbox_scope import require_owned_mailbox_account
HEAD_EMAILS_CONTENT_SHOULD_BE_SCANNED
EOF
		cat >backend/api/execution_items.py <<'EOF'
HEAD_EXECUTION_ITEMS_CONTENT_SHOULD_BE_SCANNED
EOF
		cat >backend/api/llm.py <<'EOF'
HEAD_LLM_CONTENT_SHOULD_BE_SCANNED
EOF
		cat >backend/api/llm_providers.py <<'EOF'
HEAD_LLM_PROVIDERS_CONTENT_SHOULD_BE_SCANNED
EOF
		cat >backend/services/llm_provider_urls.py <<'EOF'
def validate_llm_provider_base_url_async():
	return 'HEAD_LLM_PROVIDER_URLS_SHOULD_BE_SCANNED'
EOF
		cat >backend/services/email_parser.py <<'EOF'
from services.text_safety import strip_html_markup
HEAD_EMAIL_PARSER_SHOULD_BE_SCANNED
EOF
		cat >backend/services/text_safety.py <<'EOF'
def strip_html_markup(value):
	return 'HEAD_TEXT_SAFETY_SHOULD_BE_SCANNED'
EOF
		cat >backend/api/mailbox_accounts.py <<'EOF'
HEAD_MAILBOX_ACCOUNTS_CONTENT_SHOULD_BE_SCANNED
EOF
		cat >backend/api/mailbox_scope.py <<'EOF'
def require_owned_mailbox_account():
	return 'HEAD_MAILBOX_SCOPE_SHOULD_BE_SCANNED'
EOF
		cat >backend/api/runner_config.py <<'EOF'
def require_workspace_admin():
	return 'HEAD_RUNNER_CONFIG_SHOULD_BE_SCANNED'
EOF
		git add .
		git commit -qm 'head commit'
	)
	local head_sha
	head_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	git -C "$repo_root_dir" checkout -q "$base_sha"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request_target" \
			PR_BASE_SHA="$base_sha" \
			PR_HEAD_SHA="$head_sha" \
			STRIX_DISABLE_PR_SCOPING="0" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "0" "$rc" "case=pull-request-target-changed-backend-context-uses-head-blob exit code"
	assert_file_contains "$output_log" "scan ok with calendar service backend context" "case=pull-request-target-changed-backend-context-includes-calendar-service output"
	assert_file_contains "$output_log" "scan ok with PR-head backend dependency context" "case=pull-request-target-changed-backend-context-uses-head-blob output"
	assert_file_contains "$output_log" "scan ok with PR-head LLM provider URL validation context" "case=pull-request-target-changed-backend-context-includes-llm-provider-url-validation output"
	assert_file_contains "$output_log" "scan ok with PR-head email parser text safety context" "case=pull-request-target-changed-backend-context-includes-email-parser-text-safety output"
	assert_equals "1" "$(wc -l <"$call_log" | tr -d ' ')" "case=pull-request-target-changed-backend-context-uses-head-blob strix call count"

	rm -rf "$tmp_dir"
}

run_pull_request_target_frontend_email_context_scope_case() {
	local changed_file="${1:?changed file is required}"
	local case_name="pull-request-target-frontend-email-context:$changed_file"
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local fake_strix="$bin_dir/strix"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

target_path=""
while [ "$#" -gt 0 ]; do
	if [ "$1" = "-t" ] && [ "$#" -ge 2 ]; then
		target_path="$2"
		break
	fi
	shift
done

changed_file="$target_path/${FAKE_STRIX_EXPECTED_CHANGED_FILE:?}"
if ! grep -Fq -- 'HEAD_FRONTEND_EMAIL_FLOW_SHOULD_BE_SCANNED' "$changed_file"; then
	echo "Error: frontend email retrieval PR-head content was not scanned" >&2
	cat -- "$changed_file" >&2
	exit 74
fi

if [ ! -f "$target_path/backend/api/emails.py" ]; then
	echo "Error: email API backend context missing from frontend email PR scope" >&2
	exit 75
fi
if [ ! -f "$target_path/backend/api/auth.py" ]; then
	echo "Error: auth backend context missing from frontend email PR scope" >&2
	exit 76
fi
if [ ! -f "$target_path/backend/db/models.py" ]; then
	echo "Error: email model backend context missing from frontend email PR scope" >&2
	exit 77
fi
if [ ! -f "$target_path/backend/core/config.py" ]; then
	echo "Error: backend config context missing from frontend email PR scope" >&2
	exit 80
fi
if [ ! -f "$target_path/backend/main.py" ]; then
	echo "Error: backend router registration context missing from frontend email PR scope" >&2
	exit 81
fi
if [ ! -f "$target_path/backend/services/threading_service.py" ]; then
	echo "Error: threading backend context missing from frontend email PR scope" >&2
	exit 78
fi
if ! grep -Fq -- 'BASE_EMAIL_API_CONTEXT_SHOULD_BE_SCANNED' "$target_path/backend/api/emails.py"; then
	echo "Error: email API trusted backend context did not use base content" >&2
	cat -- "$target_path/backend/api/emails.py" >&2
	exit 79
fi
if grep -Fq -- 'HEAD_EMAIL_API_CONTEXT_SHOULD_NOT_BE_SCANNED' "$target_path/backend/api/emails.py"; then
	echo "Error: email API trusted backend context leaked PR-head content" >&2
	cat -- "$target_path/backend/api/emails.py" >&2
	exit 87
fi
if ! grep -Fq -- 'BASE_AUTH_CONTEXT_SHOULD_BE_SCANNED' "$target_path/backend/api/auth.py"; then
	echo "Error: auth trusted backend context did not use base content" >&2
	cat -- "$target_path/backend/api/auth.py" >&2
	exit 82
fi
if grep -Fq -- 'HEAD_AUTH_CONTEXT_SHOULD_NOT_BE_SCANNED' "$target_path/backend/api/auth.py"; then
	echo "Error: auth trusted backend context leaked PR-head content" >&2
	cat -- "$target_path/backend/api/auth.py" >&2
	exit 88
fi
if ! grep -Fq -- 'BASE_EMAIL_MODEL_SHOULD_BE_SCANNED' "$target_path/backend/db/models.py"; then
	echo "Error: email model trusted backend context did not use base content" >&2
	cat -- "$target_path/backend/db/models.py" >&2
	exit 83
fi
if grep -Fq -- 'HEAD_EMAIL_MODEL_SHOULD_NOT_BE_SCANNED' "$target_path/backend/db/models.py"; then
	echo "Error: email model trusted backend context leaked PR-head content" >&2
	cat -- "$target_path/backend/db/models.py" >&2
	exit 89
fi
if ! grep -Fq -- 'BASE_CONFIG_CONTEXT_SHOULD_BE_SCANNED' "$target_path/backend/core/config.py"; then
	echo "Error: backend config trusted context did not use base content" >&2
	cat -- "$target_path/backend/core/config.py" >&2
	exit 84
fi
if grep -Fq -- 'HEAD_CONFIG_CONTEXT_SHOULD_NOT_BE_SCANNED' "$target_path/backend/core/config.py"; then
	echo "Error: backend config trusted context leaked PR-head content" >&2
	cat -- "$target_path/backend/core/config.py" >&2
	exit 90
fi
if ! grep -Fq -- 'BASE_ROUTER_CONTEXT_SHOULD_BE_SCANNED' "$target_path/backend/main.py"; then
	echo "Error: backend router registration trusted context did not use base content" >&2
	cat -- "$target_path/backend/main.py" >&2
	exit 85
fi
if grep -Fq -- 'HEAD_ROUTER_CONTEXT_SHOULD_NOT_BE_SCANNED' "$target_path/backend/main.py"; then
	echo "Error: backend router registration trusted context leaked PR-head content" >&2
	cat -- "$target_path/backend/main.py" >&2
	exit 91
fi
if ! grep -Fq -- 'BASE_THREADING_SERVICE_SHOULD_BE_SCANNED' "$target_path/backend/services/threading_service.py"; then
	echo "Error: threading trusted backend context did not use base content" >&2
	cat -- "$target_path/backend/services/threading_service.py" >&2
	exit 86
fi
if grep -Fq -- 'HEAD_THREADING_SERVICE_SHOULD_NOT_BE_SCANNED' "$target_path/backend/services/threading_service.py"; then
	echo "Error: threading trusted backend context leaked PR-head content" >&2
	cat -- "$target_path/backend/services/threading_service.py" >&2
	exit 92
fi

echo "scan ok with frontend email trusted backend authorization context"
EOF
	chmod +x "$fake_strix"
	printf '%s' 'gemini/test-model' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	(
		cd "$repo_root_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		mkdir -p "$(dirname -- "$changed_file")" backend/api backend/core backend/db backend/services
		printf '%s\n' 'BASE_FRONTEND_EMAIL_FLOW_SHOULD_NOT_BE_SCANNED' >"$changed_file"
		printf '%s\n' 'BASE_EMAIL_API_CONTEXT_SHOULD_BE_SCANNED' >backend/api/emails.py
		printf '%s\n' 'BASE_AUTH_CONTEXT_SHOULD_BE_SCANNED' >backend/api/auth.py
		printf '%s\n' 'BASE_CONFIG_CONTEXT_SHOULD_BE_SCANNED' >backend/core/config.py
		printf '%s\n' 'BASE_EMAIL_MODEL_SHOULD_BE_SCANNED' >backend/db/models.py
		printf '%s\n' 'BASE_ROUTER_CONTEXT_SHOULD_BE_SCANNED' >backend/main.py
		printf '%s\n' 'BASE_THREADING_SERVICE_SHOULD_BE_SCANNED' >backend/services/threading_service.py
		git add .
		git commit -qm 'base commit'
	)
	local base_sha
	base_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	(
	cd "$repo_root_dir"
	printf '%s\n' 'HEAD_FRONTEND_EMAIL_FLOW_SHOULD_BE_SCANNED' >"$changed_file"
	printf '%s\n' 'HEAD_EMAIL_API_CONTEXT_SHOULD_NOT_BE_SCANNED' >backend/api/emails.py
	printf '%s\n' 'HEAD_AUTH_CONTEXT_SHOULD_NOT_BE_SCANNED' >backend/api/auth.py
	printf '%s\n' 'HEAD_CONFIG_CONTEXT_SHOULD_NOT_BE_SCANNED' >backend/core/config.py
	printf '%s\n' 'HEAD_EMAIL_MODEL_SHOULD_NOT_BE_SCANNED' >backend/db/models.py
	printf '%s\n' 'HEAD_ROUTER_CONTEXT_SHOULD_NOT_BE_SCANNED' >backend/main.py
	printf '%s\n' 'HEAD_THREADING_SERVICE_SHOULD_NOT_BE_SCANNED' >backend/services/threading_service.py
	git add .
	git commit -qm 'head commit'
	)
	local head_sha
	head_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	git -C "$repo_root_dir" checkout -q "$base_sha"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request_target" \
			PR_BASE_SHA="$base_sha" \
			PR_HEAD_SHA="$head_sha" \
			STRIX_TEST_CHANGED_FILES_OVERRIDE="$changed_file" \
			STRIX_DISABLE_PR_SCOPING="0" \
			FAKE_STRIX_EXPECTED_CHANGED_FILE="$changed_file" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "0" "$rc" "case=$case_name exit code"
	assert_file_contains "$output_log" "scan ok with frontend email trusted backend authorization context" "case=$case_name output"

	rm -rf "$tmp_dir"
}

run_pull_request_target_shallow_head_merge_base_fallback_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local origin_repo_dir="$tmp_dir/origin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$origin_repo_dir" "$repo_root_dir/scripts/ci"

	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local fake_strix="$bin_dir/strix"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "scan ok"
exit 0
EOF
	chmod +x "$fake_strix"
	printf '%s' 'gemini/test-model' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	(
		cd "$origin_repo_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		mkdir -p src
		printf '%s\n' 'BASE_CONTENT' >src/app.py
		git add .
		git commit -qm 'base commit'
		printf '%s\n' 'MID_CONTENT' >src/app.py
		git add .
		git commit -qm 'mid commit'
		printf '%s\n' 'HEAD_CONTENT' >src/app.py
		git add .
		git commit -qm 'head commit'
	)
	local base_sha
	base_sha="$(git -C "$origin_repo_dir" rev-list --max-parents=0 HEAD)"
	local head_sha
	head_sha="$(git -C "$origin_repo_dir" rev-parse HEAD)"

	(
		cd "$repo_root_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		git remote add origin "$origin_repo_dir"
		git fetch -q --depth=1 origin "$base_sha"
		git checkout -q FETCH_HEAD
		git fetch -q --depth=1 origin "$head_sha"
	)

	set +e
	(
		cd "$repo_root_dir"
		git diff --name-only "$base_sha...$head_sha" -- >/dev/null 2>&1
	)
	local merge_base_diff_rc=$?
	set -e
	if [ "$merge_base_diff_rc" -eq 0 ]; then
		record_failure "case=pull-request-target-shallow-head expected base...head diff to fail"
	fi

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request_target" \
			PR_BASE_SHA="$base_sha" \
			PR_HEAD_SHA="$head_sha" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "0" "$rc" "case=pull-request-target-shallow-head exit code"
	assert_file_contains "$output_log" "falling back to direct base/head diff" "case=pull-request-target-shallow-head output"

	rm -rf "$tmp_dir"
}

run_pull_request_target_aborts_on_pr_head_blob_failure_case() {
	local case_name="$1"
	local changed_file="$2"
	local base_content="$3"
	local head_content="$4"
	local fake_git_fail_command="$5"
	local disable_pr_scoping="${6-0}"
	local expected_exit="1"
	if [ "$fake_git_fail_command" = "show" ] || [ "$fake_git_fail_command" = "cat-file" ] || [ "$fake_git_fail_command" = "diff" ] || [ "$disable_pr_scoping" = "1" ]; then
		expected_exit="2"
	fi
	local expected_message="pull request changed file could not be read from PR head; failing closed"
	if [ "$disable_pr_scoping" = "1" ] && [ "$fake_git_fail_command" = "cat-file" ]; then
		expected_message="pull request head blob could not be copied; failing closed"
	fi
	if [ "$fake_git_fail_command" = "diff" ]; then
		expected_message="pull request changed file list could not be read; failing closed"
	fi

	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local real_git
	real_git="$(command -v git)"
	local fake_git="$bin_dir/git"
cat >"$fake_git" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
fake_git_fail_command="${FAKE_GIT_FAIL_COMMAND:-}"
if [ -n "$fake_git_fail_command" ] && [ "${1:-}" = "$fake_git_fail_command" ]; then
	printf 'PARTIAL_PR_HEAD_BLOB_SHOULD_BE_DISCARDED'
	exit 1
fi
exec "${REAL_GIT_PATH:?}" "$@"
EOF
	chmod +x "$fake_git"

	local fake_strix="$bin_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'called\n' >> "${FAKE_STRIX_CALL_LOG:?}"
echo "Error: Strix should not run after a PR-head blob failure" >&2
exit 64
EOF
	chmod +x "$fake_strix"
	printf '%s' 'gemini/test-model' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	(
		cd "$repo_root_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		echo 'seed' >README.md
		if [ "$base_content" != "__ABSENT__" ]; then
			mkdir -p "$(dirname -- "$changed_file")"
			printf '%s\n' "$base_content" >"$changed_file"
		fi
		git add .
		git commit -qm 'base commit'
	)
	local base_sha
	base_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	(
		cd "$repo_root_dir"
		mkdir -p "$(dirname -- "$changed_file")"
		printf '%s\n' "$head_content" >"$changed_file"
		git add .
		git commit -qm 'head commit'
	)
	local head_sha
	head_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	git -C "$repo_root_dir" checkout -q "$base_sha"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			REAL_GIT_PATH="$real_git" \
			FAKE_GIT_FAIL_COMMAND="$fake_git_fail_command" \
			GITHUB_EVENT_NAME="pull_request_target" \
			PR_BASE_SHA="$base_sha" \
			PR_HEAD_SHA="$head_sha" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_DISABLE_PR_SCOPING="$disable_pr_scoping" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "$expected_exit" "$rc" "case=$case_name PR-head blob failure exits closed"
	assert_file_contains "$output_log" "$expected_message" "case=$case_name PR-head failure output"
	local call_count="0"
	if [ -f "$call_log" ]; then
		call_count="$(wc -l <"$call_log" | tr -d ' ')"
	fi
	assert_equals "0" "$call_count" "case=$case_name PR-head blob failure must not invoke Strix"

	rm -rf "$tmp_dir"
}

run_pull_request_target_rejects_invalid_sha_case() {
	local case_name="$1"
	local invalid_side="$2"

	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local fake_strix="$bin_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'called\n' >> "${FAKE_STRIX_CALL_LOG:?}"
echo "Error: Strix should not run after invalid pull request SHA metadata" >&2
exit 67
EOF
	chmod +x "$fake_strix"
	printf '%s' 'gemini/test-model' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	(
		cd "$repo_root_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		echo 'seed' >README.md
		git add .
		git commit -qm 'base commit'
	)
	local base_sha
	base_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	(
		cd "$repo_root_dir"
		echo 'head' >>README.md
		git add .
		git commit -qm 'head commit'
	)
	local head_sha
	head_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	git -C "$repo_root_dir" checkout -q "$base_sha"

	local injection_marker="STRIX_SHA_INJECTION_MARKER"
	local malicious_sha='0000000000000000000000000000000000000000$(echo STRIX_SHA_INJECTION_MARKER)'
	local expected_message="pull request $invalid_side commit SHA is invalid; failing closed"
	if [ "$invalid_side" = "base" ]; then
		base_sha="$malicious_sha"
	else
		head_sha="$malicious_sha"
	fi

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request_target" \
			PR_BASE_SHA="$base_sha" \
			PR_HEAD_SHA="$head_sha" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=$case_name invalid PR SHA exits closed"
	assert_file_contains "$output_log" "$expected_message" "case=$case_name invalid PR SHA output"
	assert_file_not_contains "$output_log" "$injection_marker" "case=$case_name invalid PR SHA must not echo untrusted value"
	local call_count="0"
	if [ -f "$call_log" ]; then
		call_count="$(wc -l <"$call_log" | tr -d ' ')"
	fi
	assert_equals "0" "$call_count" "case=$case_name invalid PR SHA must not invoke Strix"

	rm -rf "$tmp_dir"
}

run_pull_request_target_irregular_head_entry_fails_closed_case() {
	local case_name="$1"
	local changed_file="$2"

	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local fake_strix="$bin_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'called\n' >> "${FAKE_STRIX_CALL_LOG:?}"
echo "Error: Strix should not run after an irregular PR-head entry" >&2
exit 66
EOF
	chmod +x "$fake_strix"
	printf '%s' 'gemini/test-model' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	(
		cd "$repo_root_dir"
		git init -q
		git config user.name 'Strix Test'
		git config user.email 'strix-test@example.invalid'
		echo 'seed' >README.md
		mkdir -p "$(dirname -- "$changed_file")"
		printf '%s\n' 'BASE_CONTENT_SHOULD_NOT_BE_SCANNED' >"$changed_file"
		git add .
		git commit -qm 'base commit'
	)
	local base_sha
	base_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	(
		cd "$repo_root_dir"
		rm -f -- "$changed_file"
		ln -s ../outside-secret "$changed_file"
		git add .
		git commit -qm 'head symlink commit'
	)
	local head_sha
	head_sha="$(git -C "$repo_root_dir" rev-parse HEAD)"
	git -C "$repo_root_dir" checkout -q "$base_sha"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request_target" \
			PR_BASE_SHA="$base_sha" \
			PR_HEAD_SHA="$head_sha" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=$case_name irregular PR-head entry exits closed"
	assert_file_contains "$output_log" "pull request changed file is not a regular PR-head file; failing closed" "case=$case_name output"
	local call_count="0"
	if [ -f "$call_log" ]; then
		call_count="$(wc -l <"$call_log" | tr -d ' ')"
	fi
	assert_equals "0" "$call_count" "case=$case_name irregular PR-head entry must not invoke Strix"

	rm -rf "$tmp_dir"
}

run_pull_request_target_rejects_unsafe_changed_path_case() {
	local case_name="$1"
	local changed_file="$2"

	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/repo"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	local fake_strix="$bin_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"
	local event_payload_file="$tmp_dir/github_event.json"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'called\n' >> "${FAKE_STRIX_CALL_LOG:?}"
echo "Error: Strix should not run for unsafe changed paths" >&2
exit 65
EOF
	chmod +x "$fake_strix"
	printf '%s' 'gemini/test-model' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"
	cat >"$event_payload_file" <<'EOF'
{
  "pull_request": {
    "base": {"sha": "base-sha"},
    "head": {"sha": "head-sha"}
  }
}
EOF

	set +e
	(
		cd "$repo_root_dir"
		env -u STRIX_TEST_PR_SCA_STATUS_OVERRIDE \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			GITHUB_EVENT_NAME="pull_request_target" \
			GITHUB_EVENT_PATH="$event_payload_file" \
			STRIX_TEST_CHANGED_FILES_OVERRIDE="$changed_file" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_TARGET_PATH="." \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=$case_name unsafe changed path exits closed"
	assert_file_contains "$output_log" "pull request changed file path is unsafe" "case=$case_name unsafe path output"
	assert_file_not_contains "$output_log" "No scannable changed files" "case=$case_name must not skip unsafe path"
	local call_count="0"
	if [ -f "$call_log" ]; then
		call_count="$(wc -l <"$call_log" | tr -d ' ')"
	fi
	assert_equals "0" "$call_count" "case=$case_name unsafe changed path must not invoke Strix"

	rm -rf "$tmp_dir"
}

assert_pid_not_running() {
	local pid_file="$1"
	local message="$2"

	if [ ! -f "$pid_file" ]; then
		record_failure "$message (missing pid file)"
		return
	fi

	local pid
	pid="$(tr -d '[:space:]' <"$pid_file")"
	if [ -z "$pid" ]; then
		record_failure "$message (empty pid)"
		return
	fi

	if kill -0 "$pid" 2>/dev/null; then
		record_failure "$message (pid $pid still running)"
		kill "$pid" 2>/dev/null || true
	fi
}

run_timeout_cleanup_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local workspace_dir="$tmp_dir/workspace"
	local repo_root_dir="$workspace_dir/smart-crawling-server"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	local fake_strix="$bin_dir/strix"
	local child_pid_file="$tmp_dir/child.pid"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

sleep 30 &
child_pid=$!
printf '%s' "$child_pid" > "${FAKE_STRIX_CHILD_PID_FILE:?}"
sleep 5
EOF
	chmod +x "$fake_strix"
	printf '%s' 'vertex_ai/timeout-cleanup-primary' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE -u STRIX_INPUT_FILE_ROOT \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			STRIX_DISABLE_PR_SCOPING="0" \
			FAKE_STRIX_CHILD_PID_FILE="$child_pid_file" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_PROCESS_TIMEOUT_SECONDS="1" \
			STRIX_VERTEX_FALLBACK_MODELS="" \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			STRIX_TARGET_PATH="." \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "1" "$rc" "timeout cleanup exit code"
	assert_file_contains "$output_log" "Strix run timed out after 1s." "timeout cleanup output"
	local _
	for _ in $(seq 1 12); do
		if [ -f "$child_pid_file" ]; then
			break
		fi
		sleep 0.25
	done
	for _ in $(seq 1 12); do
		if [ -f "$child_pid_file" ]; then
			local child_pid
			child_pid="$(tr -d '[:space:]' <"$child_pid_file")"
			if [ -n "$child_pid" ] && kill -0 "$child_pid" 2>/dev/null; then
				sleep 0.5
				continue
			fi
		fi
		break
	done
	assert_pid_not_running "$child_pid_file" "timeout cleanup child process"

	rm -rf "$tmp_dir"
}

run_vertex_model_ignores_untrusted_llm_api_base_file_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local repo_root_dir="$tmp_dir/workspace/smart-crawling-server"
	local allowed_input_dir="$tmp_dir/runner-temp"
	local outside_dir="$tmp_dir/outside"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local strix_llm_file="$allowed_input_dir/strix_llm.txt"
	local llm_api_key_file="$allowed_input_dir/llm_api_key.txt"
	local llm_api_base_file="$outside_dir/llm_api_base.txt"

	mkdir -p "$repo_root_dir/scripts/ci" "$allowed_input_dir" "$outside_dir"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [ "${LLM_API_BASE+x}" = "x" ]; then
	echo "Error: Vertex scan should not receive LLM_API_BASE" >&2
	exit 64
fi
printf 'called\n' >"${FAKE_STRIX_CALL_LOG:?}"
echo "vertex scan ok without external LLM_API_BASE"
exit 0
EOF
	chmod +x "$fake_strix"
	printf '%s' 'vertex_ai/gemini-2.5-pro' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"
	printf '%s' 'https://example.invalid/generateContent' >"$llm_api_base_file"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE -u STRIX_INPUT_FILE_ROOT \
			PATH="$tmp_dir:$PATH" \
			RUNNER_TEMP="$allowed_input_dir" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			LLM_API_BASE_FILE="$llm_api_base_file" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "0" "$rc" "case=vertex-ignores-untrusted-llm-api-base-file exit code"
	assert_file_contains "$output_log" "vertex scan ok without external LLM_API_BASE" "case=vertex-ignores-untrusted-llm-api-base-file output"
	assert_file_contains "$call_log" "called" "case=vertex-ignores-untrusted-llm-api-base-file strix invocation"

	rm -rf "$tmp_dir"
}

run_total_timeout_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local workspace_dir="$tmp_dir/workspace"
	local repo_root_dir="$workspace_dir/smart-crawling-server"
	mkdir -p "$bin_dir" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	local fake_strix="$bin_dir/strix"
	local output_log="$tmp_dir/output.log"
	local call_count_file="$tmp_dir/calls.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "1" >> "${FAKE_STRIX_CALL_COUNT_FILE:?}"
sleep 30
EOF
	chmod +x "$fake_strix"
	printf '%s' 'vertex_ai/total-timeout-primary' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE -u STRIX_INPUT_FILE_ROOT \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			STRIX_DISABLE_PR_SCOPING="0" \
			FAKE_STRIX_CALL_COUNT_FILE="$call_count_file" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			STRIX_PROCESS_TIMEOUT_SECONDS="30" \
			STRIX_TOTAL_TIMEOUT_SECONDS="8" \
			STRIX_VERTEX_FALLBACK_MODELS="vertex_ai/fallback-one" \
			STRIX_TRANSIENT_RETRY_PER_MODEL="2" \
			STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS="0" \
			STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
			STRIX_TARGET_PATH="." \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "1" "$rc" "total timeout exit code"
	assert_file_contains "$output_log" "Strix quick scan exceeded total timeout of 8s." "total timeout output"
	local actual_calls="0"
	if [ -f "$call_count_file" ]; then
		actual_calls="$(wc -l <"$call_count_file" | tr -d ' ')"
	fi
	assert_equals "1" "$actual_calls" "total timeout should stop additional strix invocations"
	if grep -Fq -- "Retrying model 'vertex_ai/total-timeout-primary'" "$output_log"; then
		record_failure "total timeout should stop same-model retries"
	fi
	if grep -Fq -- "Primary Vertex model unavailable; retrying with fallback" "$output_log"; then
		record_failure "total timeout should stop fallback retries"
	fi
	if grep -Fq -- "Configured Vertex model and fallback models were unavailable." "$output_log"; then
		record_failure "total timeout should not be reported as model unavailability"
	fi

	rm -rf "$tmp_dir"
}

run_missing_config_case() {
	local case_name="$1"
	local strix_llm="$2"
	local llm_api_key="$3"
	local expected_message="$4"

	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local output_log="$tmp_dir/output.log"
	local call_count_file="$tmp_dir/strix_calls"
	local fake_strix="$tmp_dir/strix"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "1" >> "${STRIX_CALL_COUNT_FILE:?}"
exit 0
EOF
	chmod +x "$fake_strix"
	if [ -n "$strix_llm" ]; then
		printf '%s' "$strix_llm" >"$strix_llm_file"
	fi
	if [ -n "$llm_api_key" ]; then
		printf '%s' "$llm_api_key" >"$llm_api_key_file"
	fi

	set +e
	env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
		PATH="$tmp_dir:$PATH" \
		STRIX_INPUT_FILE_ROOT="$tmp_dir" \
		STRIX_DISABLE_PR_SCOPING="0" \
		STRIX_LLM_FILE="$strix_llm_file" \
		LLM_API_KEY_FILE="$llm_api_key_file" \
		STRIX_CALL_COUNT_FILE="$call_count_file" \
		bash "$GATE_SCRIPT" >"$output_log" 2>&1
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=$case_name exit code"
	assert_file_contains "$output_log" "$expected_message" "case=$case_name output"

	local actual_calls="0"
	if [ -f "$call_count_file" ]; then
		actual_calls="$(wc -l <"$call_count_file" | tr -d ' ')"
	fi
	assert_equals "0" "$actual_calls" "case=$case_name strix call count"

	rm -rf "$tmp_dir"
}

run_strix_llm_file_command_substitution_literal_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local output_log="$tmp_dir/output.log"
	local call_count_file="$tmp_dir/strix_calls"
	local marker_file="$tmp_dir/strix_marker"
	local fake_strix="$tmp_dir/strix"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "1" >> "${STRIX_CALL_COUNT_FILE:?}"
exit 0
EOF
	chmod +x "$fake_strix"
	printf 'openai-direct/gpt-5.4 $(touch %s)' "$marker_file" >"$strix_llm_file"
	printf '%s' 'dummy-key' >"$llm_api_key_file"

	set +e
	env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
		PATH="$tmp_dir:$PATH" \
		STRIX_INPUT_FILE_ROOT="$tmp_dir" \
		STRIX_TARGET_PATH="-" \
		STRIX_DISABLE_PR_SCOPING="0" \
		STRIX_LLM_FILE="$strix_llm_file" \
		LLM_API_KEY_FILE="$llm_api_key_file" \
		STRIX_CALL_COUNT_FILE="$call_count_file" \
		bash "$GATE_SCRIPT" >"$output_log" 2>&1
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=strix-llm-file-command-substitution-literal exit code"
	assert_file_contains "$output_log" "ERROR: STRIX_TARGET_PATH contains unsupported path syntax" "case=strix-llm-file-command-substitution-literal output"
	if [ -e "$marker_file" ]; then
		record_failure "case=strix-llm-file-command-substitution-literal must not execute model file content"
	fi

	local actual_calls="0"
	if [ -f "$call_count_file" ]; then
		actual_calls="$(wc -l <"$call_count_file" | tr -d ' ')"
	fi
	assert_equals "0" "$actual_calls" "case=strix-llm-file-command-substitution-literal strix call count"

	rm -rf "$tmp_dir"
}

run_vertex_without_llm_api_key_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local output_log="$tmp_dir/output.log"
	local call_count_file="$tmp_dir/strix_calls"
	local fake_strix="$tmp_dir/strix"
	local strix_llm_file="$tmp_dir/strix_llm.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "1" >> "${FAKE_STRIX_CALL_COUNT_FILE:?}"
if [ "${LLM_API_KEY+x}" = "x" ]; then
	echo "unexpected LLM_API_KEY for Vertex" >&2
	exit 1
fi
if [ "${LLM_API_KEY_FILE+x}" = "x" ]; then
	echo "unexpected LLM_API_KEY_FILE for Vertex" >&2
	exit 1
fi
exit 0
EOF
	chmod +x "$fake_strix"
	printf '%s' "vertex_ai/ready-primary" >"$strix_llm_file"

	set +e
	env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
		PATH="$tmp_dir:$PATH" \
		STRIX_INPUT_FILE_ROOT="$tmp_dir" \
		STRIX_DISABLE_PR_SCOPING="0" \
		STRIX_LLM_FILE="$strix_llm_file" \
		FAKE_STRIX_CALL_COUNT_FILE="$call_count_file" \
		bash "$GATE_SCRIPT" >"$output_log" 2>&1
	local rc=$?
	set -e

	assert_equals "0" "$rc" "case=vertex-without-llm-api-key exit code"
	assert_file_contains "$output_log" "Strix run succeeded for model 'vertex_ai/ready-primary'" "case=vertex-without-llm-api-key output"

	local actual_calls="0"
	if [ -f "$call_count_file" ]; then
		actual_calls="$(wc -l <"$call_count_file" | tr -d ' ')"
	fi
	assert_equals "1" "$actual_calls" "case=vertex-without-llm-api-key strix call count"

	rm -rf "$tmp_dir"
}

run_vertex_with_llm_api_key_file_does_not_forward_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local output_log="$tmp_dir/output.log"
	local call_count_file="$tmp_dir/strix_calls"
	local fake_strix="$tmp_dir/strix"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "1" >> "${FAKE_STRIX_CALL_COUNT_FILE:?}"
if [ "${LLM_API_KEY+x}" = "x" ]; then
	echo "unexpected LLM_API_KEY for Vertex" >&2
	exit 1
fi
if [ "${LLM_API_KEY_FILE+x}" = "x" ]; then
	echo "unexpected LLM_API_KEY_FILE for Vertex" >&2
	exit 1
fi
exit 0
EOF
	chmod +x "$fake_strix"
	printf '%s' "vertex_ai/ready-primary" >"$strix_llm_file"
	printf '%s' "openai-key-should-not-reach-vertex" >"$llm_api_key_file"

	set +e
	env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
		PATH="$tmp_dir:$PATH" \
		STRIX_INPUT_FILE_ROOT="$tmp_dir" \
		STRIX_DISABLE_PR_SCOPING="0" \
		STRIX_LLM_FILE="$strix_llm_file" \
		LLM_API_KEY_FILE="$llm_api_key_file" \
		FAKE_STRIX_CALL_COUNT_FILE="$call_count_file" \
		bash "$GATE_SCRIPT" >"$output_log" 2>&1
	local rc=$?
	set -e

	assert_equals "0" "$rc" "case=vertex-with-llm-api-key-file-not-forwarded exit code"
	assert_file_contains "$output_log" "Strix run succeeded for model 'vertex_ai/ready-primary'" "case=vertex-with-llm-api-key-file-not-forwarded output"

	local actual_calls="0"
	if [ -f "$call_count_file" ]; then
		actual_calls="$(wc -l <"$call_count_file" | tr -d ' ')"
	fi
	assert_equals "1" "$actual_calls" "case=vertex-with-llm-api-key-file-not-forwarded strix call count"

	rm -rf "$tmp_dir"
}

run_invalid_min_fail_severity_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "unexpected strix execution" >&2
exit 99
EOF
	chmod +x "$fake_strix"
	printf '%s' 'vertex_ai/ready-primary' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"

	set +e
	env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
		PATH="$tmp_dir:$PATH" \
		STRIX_INPUT_FILE_ROOT="$tmp_dir" \
		STRIX_DISABLE_PR_SCOPING="0" \
		STRIX_LLM_FILE="$strix_llm_file" \
		LLM_API_KEY_FILE="$llm_api_key_file" \
		STRIX_FAIL_ON_MIN_SEVERITY="BOGUS" \
		bash "$GATE_SCRIPT" >"$output_log" 2>&1
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=invalid-min-fail-severity exit code"
	assert_file_contains "$output_log" "STRIX_FAIL_ON_MIN_SEVERITY must be one of CRITICAL/HIGH/MEDIUM/LOW/INFO/INFORMATIONAL" "case=invalid-min-fail-severity output"
	if grep -Fq -- "unexpected strix execution" "$output_log"; then
		record_failure "case=invalid-min-fail-severity should not invoke strix"
	fi
	if [ "$rc" = "99" ]; then
		record_failure "case=invalid-min-fail-severity should fail before fake strix exit code"
	fi

	rm -rf "$tmp_dir"
}

run_llm_api_base_file_outside_input_root_fails_closed_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local repo_root_dir="$tmp_dir/workspace/smart-crawling-server"
	local allowed_input_dir="$tmp_dir/runner-temp"
	local outside_dir="$tmp_dir/outside"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local strix_llm_file="$allowed_input_dir/strix_llm.txt"
	local llm_api_key_file="$allowed_input_dir/llm_api_key.txt"
	local llm_api_base_file="$outside_dir/llm_api_base.txt"

	mkdir -p "$repo_root_dir/scripts/ci" "$allowed_input_dir" "$outside_dir"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'called\n' >"${FAKE_STRIX_CALL_LOG:?}"
exit 0
EOF
	chmod +x "$fake_strix"
	printf '%s' 'openai/gpt-4o-mini' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"
	printf '%s' 'https://example.invalid/generateContent' >"$llm_api_base_file"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE -u STRIX_INPUT_FILE_ROOT \
			PATH="$tmp_dir:$PATH" \
			RUNNER_TEMP="$allowed_input_dir" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			LLM_API_BASE_FILE="$llm_api_base_file" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=llm-api-base-file-outside-input-root exit code"
	assert_file_contains "$output_log" "LLM_API_BASE_FILE must be inside the trusted input file root" "case=llm-api-base-file-outside-input-root output"
	if [ -f "$call_log" ]; then
		record_failure "case=llm-api-base-file-outside-input-root should reject before invoking strix"
	fi

	rm -rf "$tmp_dir"
}

run_pr_scoped_llm_api_base_file_config_failure_exits_2_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local repo_root_dir="$tmp_dir/workspace/smart-crawling-server"
	local allowed_input_dir="$tmp_dir/runner-temp"
	local outside_dir="$tmp_dir/outside"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local strix_llm_file="$allowed_input_dir/strix_llm.txt"
	local llm_api_key_file="$allowed_input_dir/llm_api_key.txt"
	local llm_api_base_file="$outside_dir/llm_api_base.txt"

	mkdir -p "$repo_root_dir/scripts/ci" "$repo_root_dir/src" "$allowed_input_dir" "$outside_dir"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	printf '%s\n' 'print("one")' >"$repo_root_dir/src/one.py"
	printf '%s\n' 'print("two")' >"$repo_root_dir/src/two.py"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'called\n' >"${FAKE_STRIX_CALL_LOG:?}"
exit 0
EOF
	chmod +x "$fake_strix"
	printf '%s' 'openai/gpt-4o-mini' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"
	printf '%s' 'https://example.invalid/generateContent' >"$llm_api_base_file"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_PATH -u STRIX_INPUT_FILE_ROOT \
			PATH="$tmp_dir:$PATH" \
			RUNNER_TEMP="$allowed_input_dir" \
			GITHUB_EVENT_NAME="pull_request" \
			STRIX_TEST_CHANGED_FILES_OVERRIDE=$'src/one.py\nsrc/two.py' \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			LLM_API_BASE_FILE="$llm_api_base_file" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=pr-scoped-llm-api-base-file-config-failure exit code"
	assert_file_contains "$output_log" "LLM_API_BASE_FILE must be inside the trusted input file root" "case=pr-scoped-llm-api-base-file-config-failure output"
	if [ -f "$call_log" ]; then
		record_failure "case=pr-scoped-llm-api-base-file-config-failure should reject before invoking strix"
	fi

	rm -rf "$tmp_dir"
}

run_required_input_file_outside_input_root_fails_closed_case() {
	local file_env="$1"
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local repo_root_dir="$tmp_dir/workspace/smart-crawling-server"
	local allowed_input_dir="$tmp_dir/runner-temp"
	local outside_dir="$tmp_dir/outside"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local strix_llm_file="$allowed_input_dir/strix_llm.txt"
	local llm_api_key_file="$allowed_input_dir/llm_api_key.txt"
	local llm_api_base_file="$allowed_input_dir/llm_api_base.txt"
	local outside_file="$outside_dir/${file_env}.txt"

	mkdir -p "$repo_root_dir/scripts/ci" "$allowed_input_dir" "$outside_dir"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'called\n' >"${FAKE_STRIX_CALL_LOG:?}"
exit 0
EOF
	chmod +x "$fake_strix"
	printf '%s' 'openai/gpt-4o-mini' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"
	printf '%s' 'https://example.invalid/generateContent' >"$llm_api_base_file"
	case "$file_env" in
	STRIX_LLM_FILE)
		printf '%s' 'openai/gpt-4o-mini' >"$outside_file"
		strix_llm_file="$outside_file"
		;;
	LLM_API_KEY_FILE)
		printf '%s' 'dummy' >"$outside_file"
		llm_api_key_file="$outside_file"
		;;
	*)
		record_failure "unsupported required input file env: $file_env"
		rm -rf "$tmp_dir"
		return
		;;
	esac

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE -u STRIX_INPUT_FILE_ROOT \
			PATH="$tmp_dir:$PATH" \
			RUNNER_TEMP="$allowed_input_dir" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			LLM_API_BASE_FILE="$llm_api_base_file" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=$file_env-outside-input-root exit code"
	assert_file_contains "$output_log" "$file_env must be inside the trusted input file root" "case=$file_env-outside-input-root output"
	if [ -f "$call_log" ]; then
		record_failure "case=$file_env-outside-input-root should reject before invoking strix"
	fi

	rm -rf "$tmp_dir"
}

run_input_file_root_override_takes_precedence_over_runner_temp_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local repo_root_dir="$tmp_dir/workspace/smart-crawling-server"
	local explicit_input_root="$tmp_dir/explicit-input-root"
	local inherited_runner_temp="$tmp_dir/inherited-runner-temp"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local strix_llm_file="$explicit_input_root/strix_llm.txt"
	local llm_api_key_file="$explicit_input_root/llm_api_key.txt"
	local llm_api_base_file="$explicit_input_root/llm_api_base.txt"

	mkdir -p "$repo_root_dir/scripts/ci" "$explicit_input_root" "$inherited_runner_temp"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf 'called\n' >"${FAKE_STRIX_CALL_LOG:?}"
exit 0
EOF
	chmod +x "$fake_strix"
	printf '%s' 'openai/gpt-4o-mini' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"
	printf '%s' 'https://example.invalid/generateContent' >"$llm_api_base_file"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			PATH="$tmp_dir:$PATH" \
			RUNNER_TEMP="$inherited_runner_temp" \
			STRIX_INPUT_FILE_ROOT="$explicit_input_root" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			LLM_API_BASE_FILE="$llm_api_base_file" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "0" "$rc" "case=input-file-root-override-precedence exit code"
	assert_file_contains "$call_log" "called" "case=input-file-root-override-precedence strix invocation"

	rm -rf "$tmp_dir"
}

run_stale_report_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local repo_root_dir="$tmp_dir/workspace/smart-crawling-server"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local stale_report_dir="$repo_root_dir/strix_runs/stale/vulnerabilities"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"
	local llm_api_base_file="$tmp_dir/llm_api_base.txt"

	mkdir -p "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	mkdir -p "$stale_report_dir"
	cat >"$stale_report_dir/vuln-0001.md" <<'EOF'
Severity: LOW
EOF

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "Error: transport timeout"
exit 1
EOF
	chmod +x "$fake_strix"
	printf '%s' 'openai/gpt-4o-mini' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"
	printf '%s' 'https://example.invalid/generateContent' >"$llm_api_base_file"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			PATH="$tmp_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			LLM_API_BASE_FILE="$llm_api_base_file" \
			STRIX_REPORTS_DIR="strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "1" "$rc" "case=stale-report-does-not-bypass exit code"
	assert_file_contains "$output_log" "Strix quick scan failed with a non-recoverable error." "case=stale-report-does-not-bypass output"

	rm -rf "$tmp_dir"
}

run_symlink_report_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local repo_root_dir="$tmp_dir/workspace/smart-crawling-server"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local external_report_dir="$tmp_dir/external/vulnerabilities"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"
	local llm_api_base_file="$tmp_dir/llm_api_base.txt"

	mkdir -p "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	mkdir -p "$external_report_dir" "$repo_root_dir/strix_runs"
	cat >"$external_report_dir/vuln-0001.md" <<'EOF'
Severity: LOW
EOF
	ln -s "$tmp_dir/external" "$repo_root_dir/strix_runs/latest"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "Error: transport timeout"
exit 1
EOF
	chmod +x "$fake_strix"
	printf '%s' 'openai/gpt-4o-mini' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"
	printf '%s' 'https://example.invalid/generateContent' >"$llm_api_base_file"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			PATH="$tmp_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			STRIX_DISABLE_PR_SCOPING="0" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			LLM_API_BASE_FILE="$llm_api_base_file" \
			STRIX_REPORTS_DIR="strix_runs" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "1" "$rc" "case=symlink-report-does-not-bypass exit code"
	assert_file_contains "$output_log" "Strix quick scan failed with a non-recoverable error." "case=symlink-report-does-not-bypass output"

	rm -rf "$tmp_dir"
}

run_unsafe_target_path_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local repo_root_dir="$tmp_dir/workspace/smart-crawling-server"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"
	local llm_api_base_file="$tmp_dir/llm_api_base.txt"

	mkdir -p "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' called >>"${FAKE_STRIX_CALL_LOG:?}"
exit 0
EOF
	chmod +x "$fake_strix"
	printf '%s' 'openai/gpt-4o-mini' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"
	printf '%s' 'https://example.invalid/generateContent' >"$llm_api_base_file"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			PATH="$tmp_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			STRIX_DISABLE_PR_SCOPING="0" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			LLM_API_BASE_FILE="$llm_api_base_file" \
			STRIX_TARGET_PATH="../../../../../etc/passwd" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=unsafe-target-path exit code"
	assert_file_contains "$output_log" "contains unsupported path syntax" "case=unsafe-target-path output"
	if [ -f "$call_log" ]; then
		record_failure "case=unsafe-target-path should reject before invoking strix"
	fi

	rm -rf "$tmp_dir"
}

run_absolute_outside_target_path_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local bin_dir="$tmp_dir/bin"
	local repo_root_dir="$tmp_dir/workspace/smart-crawling-server"
	mkdir -p "$bin_dir" "$repo_root_dir/src" "$repo_root_dir/scripts/ci"
	cp "$GATE_SCRIPT" "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	cp "$REPO_ROOT/scripts/ci/strix_model_utils.sh" "$repo_root_dir/scripts/ci/strix_model_utils.sh"
	chmod +x "$repo_root_dir/scripts/ci/strix_quick_gate.sh"
	local fake_strix="$bin_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local output_log="$tmp_dir/output.log"
	local strix_llm_file="$tmp_dir/strix_llm.txt"
	local llm_api_key_file="$tmp_dir/llm_api_key.txt"
	local llm_api_base_file="$tmp_dir/llm_api_base.txt"

	cat >"$fake_strix" <<'EOF'
#!/bin/bash
printf 'called\n' >"${FAKE_STRIX_CALL_LOG:?}"
exit 0
EOF
	chmod +x "$fake_strix"
	printf '%s' 'openai/gpt-4o-mini' >"$strix_llm_file"
	printf '%s' 'dummy' >"$llm_api_key_file"
	printf '%s' 'https://example.invalid/generateContent' >"$llm_api_base_file"

	set +e
	(
		cd "$repo_root_dir"
		env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
			PATH="$bin_dir:$PATH" \
			STRIX_INPUT_FILE_ROOT="$tmp_dir" \
			FAKE_STRIX_CALL_LOG="$call_log" \
			STRIX_LLM_FILE="$strix_llm_file" \
			LLM_API_KEY_FILE="$llm_api_key_file" \
			LLM_API_BASE_FILE="$llm_api_base_file" \
			STRIX_TARGET_PATH="$tmp_dir/strix-pr-scope.attacker" \
			bash "./scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
	)
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=absolute-outside-target-path exit code"
	assert_file_contains "$output_log" "contains unsupported path syntax" "case=absolute-outside-target-path output"
	if [ -f "$call_log" ]; then
		record_failure "case=absolute-outside-target-path should reject before invoking strix"
	fi

	rm -rf "$tmp_dir"
}

assert_strix_workflow_pr_trigger_hardened

assert_strix_pr_scope_includes_deployment_context

assert_strix_gpt54_model_guard_cases

assert_strix_gate_target_scope_separated

assert_changed_file_membership_uses_cached_normalized_paths

assert_absent_endpoint_search_uses_canonical_target_path

assert_strix_llm_file_read_is_literal_data

assert_strix_child_target_uses_constant_argument

assert_opencode_review_uses_codegraph_and_gpt5_fallback

assert_opencode_review_posts_suggested_diffs_inline

assert_opencode_review_normalizer_accepts_transcript_json

assert_opencode_review_publish_body_discards_trailing_model_prose

assert_opencode_review_gate_rejects_missing_structural_exploration_approval

assert_opencode_review_gate_rejects_no_changes_approval

assert_opencode_review_gate_rejects_approve_without_changed_file_evidence

assert_opencode_review_gate_rejects_line_zero_findings

assert_opencode_review_gate_rejects_placeholder_findings

assert_opencode_review_gate_rejects_non_source_backed_findings

assert_opencode_failed_check_review_validator_rejects_unrelated_findings

assert_opencode_failed_check_fallback_emits_each_strix_report

assert_opencode_failed_check_fallback_explains_trusted_base_strix_prs

assert_opencode_failed_check_fallback_does_not_treat_no_report_summary_as_report

assert_opencode_failed_check_fallback_handles_deepseek_auth_only_signal

assert_opencode_failed_check_fallback_handles_pg_erd_cloud_strix_log_shape

assert_opencode_failed_check_fallback_handles_split_code_location_lines

assert_opencode_failed_check_fallback_does_not_anchor_unmapped_strix_reports_to_workflow

run_pull_request_target_head_scope_case \
	"pull-request-target-modified-file-uses-head-blob" \
	"src/app.py" \
	"BASE_CONTENT_SHOULD_NOT_BE_SCANNED" \
	"HEAD_CONTENT_SHOULD_BE_SCANNED"

run_pull_request_target_head_scope_case \
	"pull-request-target-pr-scope-sentinel-uses-head-blob" \
	"src/sentinel.py" \
	"BASE_SENTINEL_CONTENT_SHOULD_NOT_BE_SCANNED" \
	"HEAD_SENTINEL_CONTENT_SHOULD_BE_SCANNED" \
	"0" \
	"0" \
	"__PR_SCOPE__"

run_pull_request_target_head_scope_case \
	"pull-request-target-added-file-uses-head-blob" \
	"src/new_module.py" \
	"__ABSENT__" \
	"HEAD_ONLY_NEW_FILE_SHOULD_BE_SCANNED"

run_pull_request_target_head_scope_case \
	"pull-request-target-source-file-with-space-uses-head-blob" \
	"src/unsafe name.py" \
	"BASE_CONTENT_WITH_SPACE_SHOULD_NOT_BE_SCANNED" \
	"HEAD_CONTENT_WITH_SPACE_SHOULD_BE_SCANNED"

run_pull_request_target_head_scope_case \
	"pull-request-target-nextjs-bracket-route-uses-head-blob" \
	"frontend/src/app/labels/[slug]/page.tsx" \
	"BASE_BRACKET_ROUTE_CONTENT_SHOULD_NOT_BE_SCANNED" \
	"HEAD_BRACKET_ROUTE_CONTENT_SHOULD_BE_SCANNED"

run_pull_request_target_head_scope_case \
	"pull-request-target-executable-file-copied-nonexecutable" \
	"scripts/ci/untrusted.sh" \
	"__ABSENT__" \
	"HEAD_EXECUTABLE_SHOULD_BE_SCANNED_AS_DATA" \
	"0" \
	"1"

run_pull_request_target_plaintext_runner_token_fails_closed_case

run_pull_request_target_shallow_head_merge_base_fallback_case

run_pull_request_target_rejects_unsafe_changed_path_case \
	"pull-request-target-parent-directory-changed-path-fails-closed" \
	"../outside.py"

run_pull_request_target_rejects_unsafe_changed_path_case \
	"pull-request-target-pathspec-changed-path-fails-closed" \
	":(glob)src/**"

run_pull_request_target_rejects_unsafe_changed_path_case \
	"pull-request-target-trailing-space-changed-path-fails-closed" \
	"src/evil.py "

run_pull_request_target_rejects_unsafe_changed_path_case \
	"pull-request-target-leading-space-changed-path-fails-closed" \
	" src/evil.py"

run_pull_request_target_head_scope_case \
	"pull-request-target-disabled-pr-scoping-nested-file-uses-head-blob" \
	"backend/app/existing.py" \
	"BASE_NESTED_CONTENT_SHOULD_NOT_BE_SCANNED" \
	"HEAD_NESTED_CONTENT_SHOULD_BE_SCANNED" \
	"1"

run_pull_request_target_bounded_head_context_scope_case

run_pull_request_target_changed_context_scope_uses_pr_head_case
run_pull_request_target_changed_backend_context_scope_case

run_pull_request_target_frontend_email_context_scope_case \
	"frontend/src/components/EmailDetail.tsx"

run_pull_request_target_frontend_email_context_scope_case \
	"frontend/src/components/EmailList.tsx"

run_pull_request_target_frontend_email_context_scope_case \
	"frontend/src/app/page.tsx"

run_pull_request_target_frontend_email_context_scope_case \
	"frontend/src/lib/api-client.ts"

run_pull_request_target_frontend_email_context_scope_case \
	"frontend/src/lib/email-threading.ts"

run_pull_request_target_aborts_on_pr_head_blob_failure_case \
	"pull-request-target-added-file-pr-head-blob-read-failure" \
	"src/new_module.py" \
	"__ABSENT__" \
	"HEAD_CONTENT_SHOULD_NOT_BECOME_PARTIAL_SCAN_INPUT" \
	"show"

run_pull_request_target_aborts_on_pr_head_blob_failure_case \
	"pull-request-target-modified-file-pr-head-blob-read-failure" \
	"src/existing.py" \
	"BASE_CONTENT_MUST_NOT_BE_USED_AFTER_HEAD_READ_FAILURE" \
	"HEAD_CONTENT_SHOULD_NOT_BECOME_PARTIAL_SCAN_INPUT" \
	"show"

run_pull_request_target_irregular_head_entry_fails_closed_case \
	"pull-request-target-symlink-head-entry-fails-closed" \
	"src/app.py"

run_pull_request_target_irregular_head_entry_fails_closed_case \
	"pull-request-target-symlink-readme-head-entry-fails-closed" \
	"README.md"

run_pull_request_target_irregular_head_entry_fails_closed_case \
	"pull-request-target-symlink-test-head-entry-fails-closed" \
	"tests/app_test.py"

run_pull_request_target_irregular_head_entry_fails_closed_case \
	"pull-request-target-symlink-infra-head-entry-fails-closed" \
	"infra/deploy.sh"

run_pull_request_target_aborts_on_pr_head_blob_failure_case \
	"pull-request-target-modified-file-pr-head-tree-lookup-failure" \
	"src/existing.py" \
	"BASE_CONTENT_MUST_NOT_BE_USED_AFTER_HEAD_LOOKUP_FAILURE" \
	"HEAD_CONTENT_SHOULD_NOT_BECOME_PARTIAL_SCAN_INPUT" \
	"ls-tree" \
	"1"

run_pull_request_target_aborts_on_pr_head_blob_failure_case \
	"pull-request-target-changed-file-list-diff-failure" \
	"src/existing.py" \
	"BASE_CONTENT_MUST_NOT_BE_USED_AFTER_DIFF_FAILURE" \
	"HEAD_CONTENT_SHOULD_NOT_BECOME_PARTIAL_SCAN_INPUT" \
	"diff"

run_pull_request_target_rejects_invalid_sha_case \
	"pull-request-target-invalid-base-sha-fails-closed" \
	"base"

run_pull_request_target_rejects_invalid_sha_case \
	"pull-request-target-invalid-head-sha-fails-closed" \
	"head"

run_pull_request_target_aborts_on_pr_head_blob_failure_case \
	"pull-request-target-disabled-pr-scope-pr-head-blob-read-failure" \
	"src/existing.py" \
	"BASE_CONTENT_MUST_NOT_BE_USED_AFTER_DISABLED_SCOPE_HEAD_FAILURE" \
	"HEAD_CONTENT_SHOULD_NOT_BECOME_PARTIAL_SCAN_INPUT" \
	"cat-file" \
	"1"

run_gate_case "success" \
	"vertex_ai/ready-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"scan ok" \
	"1" \
	"vertex_ai/ready-primary" \
	"<unset>"

run_gate_case "runtime-env-forwarding" \
	"gemini/gemini-pro-3.1-preview" \
	"" \
	"0" \
	"scan ok" \
	"1" \
	"gemini/gemini-pro-3.1-preview" \
	"<unset>" \
	"gemini" \
	""

run_gate_case "vertex-primary-notfound-fallback-success" \
	"vertex_ai/missing-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/missing-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

run_gate_case "vertex-all-notfound" \
	"vertex_ai/missing-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Configured Vertex model and fallback models were unavailable." \
	"3" \
	"vertex_ai/missing-primary|vertex_ai/fallback-one|vertex_ai/fallback-two" \
	"<unset>|<unset>|<unset>"

run_gate_case "nonrecoverable" \
	"openai/gpt-4o-mini" \
	"vertex_ai/fallback-one" \
	"1" \
	"Strix quick scan failed with a non-recoverable error." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid"

run_gate_case "provider-prefix-required" \
	"gemini-2.5-pro" \
	"vertex_ai/fallback-one" \
	"0" \
	"Normalized STRIX_LLM to provider-qualified model 'vertex_ai/gemini-2.5-pro'." \
	"1" \
	"vertex_ai/gemini-2.5-pro" \
	"<unset>"

run_gate_case "provider-prefix-fallback-normalization" \
	"missing-primary" \
	"fallback-one fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/missing-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

run_gate_case "provider-prefix-required-resource-path-primary-implicit-default-provider" \
	"projects/p1/locations/us-central1/publishers/google/models/gemini-2.5-pro" \
	"vertex_ai/fallback-one" \
	"0" \
	"Normalized STRIX_LLM to provider-qualified model 'vertex_ai/gemini-2.5-pro'." \
	"1" \
	"vertex_ai/gemini-2.5-pro" \
	"<unset>"

run_gate_case "provider-prefix-required-resource-path-primary-explicit-empty-default-provider" \
	"projects/p1/locations/us-central1/publishers/google/models/gemini-2.5-pro" \
	"vertex_ai/fallback-one" \
	"0" \
	"Normalized STRIX_LLM to provider-qualified model 'vertex_ai/gemini-2.5-pro'." \
	"1" \
	"vertex_ai/gemini-2.5-pro" \
	"<unset>" \
	""

run_gate_case "provider-prefix-resource-path-primary-notfound-fallback-success" \
	"projects/p1/locations/us-central1/publishers/google/models/missing-primary" \
	"projects/p1/locations/us-central1/publishers/google/models/fallback-one projects/p1/locations/us-central1/publishers/google/models/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/missing-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

# Regression: Vertex custom model resource path projects/<p>/locations/<l>/models/<id>
# (no publishers/ segment) must be recognized as a Vertex resource path and
# normalized to vertex_ai/<model_id>.
run_gate_case "vertex-custom-model-resource-path" \
	"projects/my-proj/locations/us-central1/models/my-custom-model-123" \
	"vertex_ai/fallback-one" \
	"0" \
	"Normalized STRIX_LLM to provider-qualified model 'vertex_ai/my-custom-model-123'." \
	"1" \
	"vertex_ai/my-custom-model-123" \
	"<unset>"

run_gate_case "vertex-notfound-without-status-fallback-success" \
	"vertex_ai/missing-primary" \
	"vertex_ai/fallback-one" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/missing-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

run_gate_case "vertex-notfound-compact-status-fallback-success" \
	"vertex_ai/missing-primary" \
	"vertex_ai/fallback-one" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/missing-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

run_gate_case "nonvertex-slash-model-passthrough" \
	"foo/bar" \
	"vertex_ai/fallback-one" \
	"0" \
	"scan ok with non-vertex slash model passthrough" \
	"1" \
	"foo/bar" \
	"https://example.invalid"

run_gate_case "primary-duplicate-in-fallback" \
	"missing-primary" \
	"vertex_ai/missing-primary fallback-one" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/missing-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

run_gate_case "multiline-fallback-success" \
	"vertex_ai/missing-primary" \
	$'vertex_ai/fallback-one\nvertex_ai/fallback-two' \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-two' in [0-9]+s\\." \
	"3" \
	"vertex_ai/missing-primary|vertex_ai/fallback-one|vertex_ai/fallback-two" \
	"<unset>|<unset>|<unset>"

run_gate_case_allow_provider_signal "vertex-primary-ratelimit-fallback-success" \
	"vertex_ai/ratelimit-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/ratelimit-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

run_gate_case_allow_provider_signal "vertex-primary-resource-exhausted-fallback-success" \
	"vertex_ai/resource-exhausted-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/resource-exhausted-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

run_gate_case_allow_provider_signal "vertex-primary-429-fallback-success" \
	"vertex_ai/http429-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/http429-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

run_gate_case_allow_provider_signal "vertex-primary-midstream-fallback-success" \
	"vertex_ai/midstream-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/midstream-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

run_gate_case_allow_provider_signal "vertex-primary-midstream-retry-same-model-success" \
	"vertex_ai/retry-midstream-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"scan ok after same-model retry" \
	"2" \
	"vertex_ai/retry-midstream-primary|vertex_ai/retry-midstream-primary" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

# Bug 9: Rate-limit transient same-model retry (previously untested path)
run_gate_case_allow_provider_signal "vertex-primary-ratelimit-retry-same-model-success" \
	"vertex_ai/retry-ratelimit-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"scan ok after same-model rate-limit retry" \
	"2" \
	"vertex_ai/retry-ratelimit-primary|vertex_ai/retry-ratelimit-primary" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

run_gate_case_allow_provider_signal "vertex-primary-api-connection-retry-same-model-success" \
	"gemini/retry-api-connection-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"scan ok after same-model api connection retry" \
	"2" \
	"gemini/retry-api-connection-primary|gemini/retry-api-connection-primary" \
	"https://example.invalid|https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

run_gate_case_allow_provider_signal "github-models-internal-server-connection-retry-same-model-success" \
	"openai/openai/retry-api-connection-primary" \
	"" \
	"0" \
	"scan ok after same-model api connection retry" \
	"2" \
	"openai/openai/retry-api-connection-primary|openai/openai/retry-api-connection-primary" \
	"https://models.github.ai/inference|https://models.github.ai/inference" \
	"openai" \
	"https://models.github.ai/inference" \
	"" \
	"1"

run_gate_case "github-models-primary-unavailable-fallback-success" \
	"openai/gpt-5" \
	"" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'deepseek/deepseek-r1-0528' in [0-9]+s\\." \
	"2" \
	"openai/gpt-5|openai/deepseek/deepseek-r1-0528" \
	"https://models.github.ai/inference|https://models.github.ai/inference" \
	"openai" \
	"https://models.github.ai/inference" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"" \
	"" \
	"" \
	"" \
	"0" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"deepseek/deepseek-r1-0528 deepseek/deepseek-v3-0324" \
	"1"

run_gate_case "github-models-primary-denied-fallback-success" \
	"openai/gpt-5" \
	"" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'deepseek/deepseek-r1-0528' in [0-9]+s\\." \
	"2" \
	"openai/gpt-5|openai/deepseek/deepseek-r1-0528" \
	"https://models.github.ai/inference|https://models.github.ai/inference" \
	"openai" \
	"https://models.github.ai/inference" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"" \
	"" \
	"" \
	"" \
	"0" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"deepseek/deepseek-r1-0528 deepseek/deepseek-v3-0324" \
	"1"

run_gate_case "github-models-primary-ratelimit-fallback-success" \
	"openai/gpt-5" \
	"" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'deepseek/deepseek-r1-0528' in [0-9]+s\\." \
	"4" \
	"openai/gpt-5|openai/gpt-5|openai/gpt-5|openai/deepseek/deepseek-r1-0528" \
	"https://models.github.ai/inference|https://models.github.ai/inference|https://models.github.ai/inference|https://models.github.ai/inference" \
	"openai" \
	"https://models.github.ai/inference" \
	"" \
	"2" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"" \
	"" \
	"" \
	"" \
	"0" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"deepseek/deepseek-r1-0528 deepseek/deepseek-v3-0324" \
	"1"

run_gate_case "github-models-fallback-provider-signal-tries-next" \
	"openai/gpt-5" \
	"" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'deepseek/deepseek-v3-0324' in [0-9]+s\\." \
	"3" \
	"openai/gpt-5|openai/deepseek/deepseek-r1-0528|openai/deepseek/deepseek-v3-0324" \
	"https://models.github.ai/inference|https://models.github.ai/inference|https://models.github.ai/inference" \
	"openai" \
	"https://models.github.ai/inference" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" \
	"" \
	"" \
	"0" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"deepseek/deepseek-r1-0528 deepseek/deepseek-v3-0324" \
	"1"

run_gate_case "github-models-fallback-vulnerability-before-next-success-blocks" \
	"openai/gpt-5" \
	"" \
	"1" \
	"Strix model reported threshold vulnerabilities before fallback success; failing closed so every model-reported vulnerability is reviewed." \
	"2" \
	"openai/gpt-5|openai/deepseek/deepseek-r1-0528" \
	"https://models.github.ai/inference|https://models.github.ai/inference" \
	"openai" \
	"https://models.github.ai/inference" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" \
	"" \
	"" \
	"0" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"deepseek/deepseek-r1-0528 deepseek/deepseek-v3-0324" \
	"1"

run_gate_case_allow_provider_signal "gemini-high-demand-retry-same-model-success" \
	"gemini/retry-high-demand-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"scan ok after same-model high-demand retry" \
	"2" \
	"gemini/retry-high-demand-primary|gemini/retry-high-demand-primary" \
	"https://example.invalid|https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

run_gate_case_allow_provider_signal "gemini-timeout-direct-fallback-success" \
	"gemini/retry-timeout-primary" \
	"gemini/fallback-one gemini/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'gemini/fallback-one' in [0-9]+s\\." \
	"2" \
	"gemini/retry-timeout-primary|gemini/fallback-one" \
	"https://example.invalid|https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

run_gate_case_allow_provider_signal "gemini-timeout-fallback-success" \
	"gemini/timeout-fallback-primary" \
	"gemini/fallback-one gemini/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'gemini/fallback-one' in [0-9]+s\\." \
	"2" \
	"gemini/timeout-fallback-primary|gemini/fallback-one" \
	"https://example.invalid|https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

run_gate_case_allow_provider_signal "gemini-generic-fallback-success" \
	"gemini/timeout-fallback-primary" \
	"" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'gemini/fallback-one' in [0-9]+s\\." \
	"2" \
	"gemini/timeout-fallback-primary|gemini/fallback-one" \
	"https://example.invalid|https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"" \
	"" \
	"" \
	"" \
	"0" \
	"" \
	"" \
	"" \
	"__UNSET__" \
	"gemini/fallback-one gemini/fallback-two"

run_gate_case_allow_provider_signal "gemini-zero-findings-timeout-fallback-allows-pr" \
	"gemini/zero-timeout-primary" \
	"gemini/fallback-one" \
	"1" \
	"Strix reported zero vulnerabilities before provider infrastructure failure; failing closed because provider infrastructure failures are not clean scan evidence." \
	"2" \
	"gemini/zero-timeout-primary|gemini/fallback-one" \
	"https://example.invalid|https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"

run_gate_case_allow_provider_signal "pr-scope-zero-finding-does-not-leak" \
	"gemini/scope-zero-leak-primary" \
	"" \
	"1" \
	"Strix reported zero vulnerabilities before provider infrastructure failure; failing closed because provider infrastructure failures are not clean scan evidence." \
	"1" \
	"gemini/scope-zero-leak-primary" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	$'sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java\nsync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java' \
	"" \
	"1"

run_gate_case "service-unavailable-no-llm-marker-nonrecoverable" \
	"custom/service-unavailable-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Strix quick scan failed with a non-recoverable error." \
	"1" \
	"custom/service-unavailable-primary" \
	"https://example.invalid" \
	"custom" \
	"__DEFAULT__" \
	"" \
	"1"

run_gate_case "server-disconnect-no-llm-marker-nonrecoverable" \
	"vertex_ai/app-server-disconnect-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Strix quick scan failed with a non-recoverable error." \
	"1" \
	"vertex_ai/app-server-disconnect-primary" \
	"<unset>"

# Bug 11: Timeout should move directly to fallback instead of retrying the same model.
run_gate_case_allow_provider_signal "vertex-primary-timeout-retry-same-model-success" \
	"vertex_ai/retry-timeout-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"scan ok after timeout fallback" \
	"2" \
	"vertex_ai/retry-timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

# Bug 11b: Timeout → immediate fallback model succeeds.
run_gate_case_allow_provider_signal "vertex-primary-timeout-exhausted-fallback-success" \
	"vertex_ai/timeout-exhaust-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"scan ok after timeout-exhausted fallback" \
	"2" \
	"vertex_ai/timeout-exhaust-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

run_gate_case_allow_provider_signal "zero-findings-timeout-all-models" \
	"vertex_ai/zero-timeout-primary" \
	"vertex_ai/fallback-one" \
	"1" \
	"Strix reported zero vulnerabilities before provider infrastructure failure; failing closed because provider infrastructure failures are not clean scan evidence." \
	"2" \
	"vertex_ai/zero-timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"2" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"

run_gate_case_allow_provider_signal "zero-findings-timeout-all-models" \
	"vertex_ai/zero-timeout-primary" \
	"vertex_ai/fallback-one" \
	"1" \
	"Configured Vertex model and fallback models were unavailable." \
	"2" \
	"vertex_ai/zero-timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"2" \
	"0" \
	"push"

run_gate_case_allow_provider_signal "zero-findings-sticky-across-fallback" \
	"vertex_ai/zero-sticky-primary" \
	"vertex_ai/fallback-one" \
	"1" \
	"Strix reported zero vulnerabilities before provider infrastructure failure; failing closed because provider infrastructure failures are not clean scan evidence." \
	"2" \
	"vertex_ai/zero-sticky-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"2" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"

run_gate_case_allow_provider_signal "zero-findings-with-low-report-timeout" \
	"vertex_ai/zero-low-primary" \
	"vertex_ai/fallback-one" \
	"1" \
	"Configured Vertex model and fallback models were unavailable." \
	"2" \
	"vertex_ai/zero-low-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"2" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"

run_gate_case "strict-zero-findings-timeout-fails-pr" \
	"vertex_ai/zero-timeout-primary" \
	" " \
	"1" \
	"failing closed" \
	"1" \
	"vertex_ai/zero-timeout-primary" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"2" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"" \
	"1"

run_gate_case "provider-fatal-success-signal" \
	"vertex_ai/provider-fatal-success-signal" \
	"" \
	"1" \
	"Strix run emitted provider infrastructure or failure-signal output; failing closed." \
	"1" \
	"vertex_ai/provider-fatal-success-signal" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"" \
	"1"

run_gate_case "provider-warning-success-signal" \
	"vertex_ai/provider-warning-success-signal" \
	"" \
	"1" \
	"Strix run emitted provider infrastructure or failure-signal output; failing closed." \
	"1" \
	"vertex_ai/provider-warning-success-signal" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"" \
	"1"

run_gate_case "report-known-internal-warning-sanitized" \
	"vertex_ai/report-known-internal-warning-sanitized" \
	"" \
	"0" \
	"Strix run succeeded for model 'vertex_ai/report-known-internal-warning-sanitized'" \
	"1" \
	"vertex_ai/report-known-internal-warning-sanitized" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"" \
	"1"

run_gate_case "report-unknown-warning-fails" \
	"vertex_ai/report-unknown-warning-fails" \
	"" \
	"1" \
	"Strix report artifacts emitted warning/fatal/denied/timeout output; failing closed." \
	"1" \
	"vertex_ai/report-unknown-warning-fails" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"" \
	"1"

run_gate_case "provider-denied-success-signal" \
	"vertex_ai/provider-denied-success-signal" \
	"" \
	"1" \
	"Strix run emitted provider infrastructure or failure-signal output; failing closed." \
	"1" \
	"vertex_ai/provider-denied-success-signal" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"__SAME_AS_FALLBACK_MODELS__" \
	"" \
	"1"

run_gate_case_allow_provider_signal "vertex-all-ratelimited" \
	"vertex_ai/ratelimit-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Configured Vertex model and fallback models were unavailable." \
	"3" \
	"vertex_ai/ratelimit-primary|vertex_ai/fallback-one|vertex_ai/fallback-two" \
	"<unset>|<unset>|<unset>"

run_gate_case "vertex-primary-hallucinated-endpoint-fallback-success" \
	"vertex_ai/hallucination-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/hallucination-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

run_gate_case "vertex-primary-existing-endpoint-nonrecoverable" \
	"vertex_ai/existing-endpoint-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Strix quick scan failed with a non-recoverable error." \
	"1" \
	"vertex_ai/existing-endpoint-primary" \
	"<unset>"

run_gate_case "pr-stale-source-claim-fallback-success" \
	"vertex_ai/stale-source-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"scan ok after stale-source fallback" \
	"2" \
	"vertex_ai/stale-source-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"HIGH" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"backend/db/models.py"

run_gate_case "pr-stale-source-plus-real-finding-blocks" \
	"vertex_ai/stale-source-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Strix finding intersects files changed in this pull request." \
	"1" \
	"vertex_ai/stale-source-primary" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"HIGH" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	$'backend/db/models.py\nbackend/api/emails.py'

run_gate_case_allow_provider_signal "pr-changed-finding-with-retry-marker-blocks" \
	"vertex_ai/changed-finding-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Strix finding intersects files changed in this pull request." \
	"1" \
	"vertex_ai/changed-finding-primary" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"HIGH" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"backend/api/emails.py"

run_gate_case "pr-stale-report-plus-inline-changed-finding-blocks" \
	"vertex_ai/stale-inline-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Strix finding intersects files changed in this pull request." \
	"1" \
	"vertex_ai/stale-inline-primary" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"HIGH" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	$'backend/db/models.py\nbackend/api/emails.py'

run_gate_case "high-vuln-below-threshold" \
	"vertex_ai/high-vuln-primary" \
	"" \
	"0" \
	"below configured fail threshold 'CRITICAL'" \
	"1" \
	"vertex_ai/high-vuln-primary" \
	"<unset>"

run_gate_case "inline-medium-below-threshold" \
	"vertex_ai/inline-medium-primary" \
	"" \
	"0" \
	"below configured fail threshold 'CRITICAL'" \
	"1" \
	"vertex_ai/inline-medium-primary" \
	"<unset>"

run_gate_case "medium-vuln-default-threshold" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Strix quick scan failed with a non-recoverable error." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"__UNSET__"

# Infrastructure error guard: below-threshold findings must NOT pass when the
# strix log contains evidence of infrastructure-level errors (timeout,
# rate-limit, transport failures) because the scan was likely incomplete.

# Guard test 1: LOW finding + timeout → should fail (exit 1).
# The below-threshold check runs first but detects infrastructure errors in the
# strix log and refuses bypass.  The timeout is also vertex-retryable, so the
# gate continues into the fallback loop.  All attempts see the same timeout.
run_gate_case_allow_provider_signal "below-threshold-with-timeout" \
	"vertex_ai/low-timeout-primary" \
	"vertex_ai/gemini-2.5-pro vertex_ai/gemini-2.5-flash" \
	"1" \
	"infrastructure errors occurred during this pipeline run; refusing bypass" \
	"3" \
	"vertex_ai/low-timeout-primary|vertex_ai/gemini-2.5-pro|vertex_ai/gemini-2.5-flash" \
	"<unset>|<unset>|<unset>"

# Guard test 2: LOW finding + rate-limit → should fail (exit 1).
# Below-threshold check refuses bypass due to infra errors.
# Rate-limit is vertex-retryable, so the gate also tries fallback models.
run_gate_case_allow_provider_signal "below-threshold-with-ratelimit" \
	"vertex_ai/low-ratelimit-primary" \
	"vertex_ai/gemini-2.5-pro vertex_ai/gemini-2.5-flash" \
	"1" \
	"infrastructure errors occurred during this pipeline run; refusing bypass" \
	"3" \
	"vertex_ai/low-ratelimit-primary|vertex_ai/gemini-2.5-pro|vertex_ai/gemini-2.5-flash" \
	"<unset>|<unset>|<unset>"

# Guard test 3: INFO finding + ConnectionError → should fail (exit 1).
# ConnectionError is NOT vertex-retryable, so only the primary model is tried.
run_gate_case_allow_provider_signal "below-threshold-with-connection-error" \
	"vertex_ai/info-conn-primary" \
	"" \
	"1" \
	"infrastructure errors occurred during this pipeline run; refusing bypass" \
	"1" \
	"vertex_ai/info-conn-primary" \
	"<unset>"

# Guard test 3b: INFO finding + ConnectionError WITHOUT provider marker → should
# PASS (exit 0).  The two-grep infra-error detector requires both a transport
# error class AND an LLM_PROVIDER_ONLY_REGEX marker (litellm, openai,
# anthropic, VertexAI, etc.).  Note: transport libraries (requests, httpx,
# httpcore) are intentionally excluded from LLM_PROVIDER_ONLY_REGEX to avoid
# false positives — see guard test 3c below.
# A bare "ConnectionError" from the target application lacks the marker, so
# has_detected_infrastructure_error() returns 1 (no infra error) and the
# below-threshold bypass succeeds.
run_gate_case "below-threshold-with-connection-error-no-provider" \
	"vertex_ai/info-conn-noprov-primary" \
	"" \
	"0" \
	"below configured fail threshold" \
	"1" \
	"vertex_ai/info-conn-noprov-primary" \
	"<unset>"

# Guard test 3c: INFO finding + requests.exceptions.ConnectionError → should
# PASS (exit 0).  The "requests" transport library matches the broad
# PROVIDER_CONTEXT_REGEX but is intentionally excluded from LLM_PROVIDER_ONLY_REGEX.
# Before commit 0e90d48 the connection-error path used PROVIDER_CONTEXT_REGEX
# and would have mis-classified this as an LLM infrastructure error; now it
# correctly uses LLM_PROVIDER_ONLY_REGEX, so below-threshold bypass succeeds.
run_gate_case "below-threshold-with-requests-connection-error" \
	"vertex_ai/info-conn-requests-primary" \
	"" \
	"0" \
	"below configured fail threshold" \
	"1" \
	"vertex_ai/info-conn-requests-primary" \
	"<unset>"

# Guard test 4: MEDIUM finding + MidStreamFallbackError → should fail (exit 1).
# Midstream is vertex-retryable, so the gate also tries fallback models
# (after the below-threshold check refuses bypass due to infra errors).
run_gate_case_allow_provider_signal "below-threshold-with-midstream" \
	"vertex_ai/medium-midstream-primary" \
	"vertex_ai/gemini-2.5-pro vertex_ai/gemini-2.5-flash" \
	"1" \
	"infrastructure errors occurred during this pipeline run; refusing bypass" \
	"3" \
	"vertex_ai/medium-midstream-primary|vertex_ai/gemini-2.5-pro|vertex_ai/gemini-2.5-flash" \
	"<unset>|<unset>|<unset>"

run_gate_case "critical-vuln-at-threshold" \
	"vertex_ai/critical-vuln-primary" \
	"" \
	"1" \
	"Strix quick scan failed with a non-recoverable error." \
	"1" \
	"vertex_ai/critical-vuln-primary" \
	"<unset>"

run_gate_case "malformed-severity-marker-nonrecoverable" \
	"vertex_ai/malformed-severity-primary" \
	"" \
	"1" \
	"Strix quick scan failed with a non-recoverable error." \
	"1" \
	"vertex_ai/malformed-severity-primary" \
	"<unset>"

# Bug 7: Model disagreement — primary produces CRITICAL, fallback produces LOW.
# The CRITICAL from the earlier report must NOT be ignored.
# Both models produce NOT_FOUND errors, so the gate exhausts fallbacks and
# reports "Configured Vertex model and fallback models were unavailable."
# The key assertion is exit 1: the CRITICAL finding is NOT downgraded to pass.
run_gate_case "model-disagreement-critical-in-earlier-report" \
	"vertex_ai/model-a" \
	"vertex_ai/model-b" \
	"1" \
	"Strix quick scan failed with a non-recoverable error." \
	"2" \
	"vertex_ai/model-a|vertex_ai/model-b" \
	"<unset>|<unset>"

# Bug 4: deepseek/models/deepseek-r1 must NOT be rewritten to vertex_ai/deepseek-r1
run_gate_case "nonvertex-slash-model-not-rewritten" \
	"deepseek/models/deepseek-r1" \
	"vertex_ai/fallback-one" \
	"0" \
	"scan ok with deepseek model passthrough" \
	"1" \
	"deepseek/models/deepseek-r1" \
	"https://example.invalid"

# Regression: STRIX_TARGET_PATH=<dir>/src with default STRIX_SOURCE_DIRS (now ".")
# must resolve to <dir>/src/. (i.e. <dir>/src itself), NOT <dir>/src/src.
# The hallucinated-endpoint scenario writes a vuln report with a fake endpoint;
# the gate should detect it's absent from source and trigger fallback — which
# requires the source dir to actually exist and be scanned.
run_gate_case "target-path-src-default-source-dirs" \
	"vertex_ai/hallucination-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/hallucination-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1" \
	"CRITICAL" \
	"0" \
	"__USE_SUBDIR_SRC__" \
	""

# Bug 2 follow-up: multi-entry STRIX_SOURCE_DIRS test.
# Endpoint /api/status lives in api/ (not src/).  With STRIX_SOURCE_DIRS="src api"
# the gate must find the endpoint in the api/ dir and treat the finding as
# non-hallucinated → non-recoverable failure (exit 1).
run_gate_case "multi-source-dirs-existing-endpoint" \
	"vertex_ai/multi-dir-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Strix quick scan failed with a non-recoverable error." \
	"1" \
	"vertex_ai/multi-dir-primary" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"src api"

run_gate_case "preserve-existing-api-base" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"scan ok with preserved api base" \
	"1" \
	"openai/gpt-4o-mini" \
	"https://preexisting.invalid" \
	"vertex_ai" \
	"" \
	"https://preexisting.invalid"

run_gate_case "default-fallback-order-fast-first" \
	"vertex_ai/missing-primary" \
	"" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/gemini-2[.]5-pro' in [0-9]+s\\." \
	"2" \
	"vertex_ai/missing-primary|vertex_ai/gemini-2.5-pro" \
	"<unset>|<unset>"

# Bug 13: All fallback models are the same as the primary model.
# The gate should detect that no distinct fallback was tried and emit an ERROR.
run_gate_case "all-fallbacks-same-as-primary" \
	"vertex_ai/same-primary" \
	"vertex_ai/same-primary vertex_ai/same-primary" \
	"1" \
	"ERROR: All configured fallback models are the same as the primary model" \
	"1" \
	"vertex_ai/same-primary" \
	"<unset>"

# Bug 14: Timeout should fall back rather than emit a same-model retry message.
run_gate_case_allow_provider_signal "vertex-primary-timeout-retry-reason-message" \
	"vertex_ai/retry-timeout-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one' in [0-9]+s\\." \
	"2" \
	"vertex_ai/retry-timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"2"

# Bug 14: Retry reason messages — rate-limit retry should say "due to rate limit".
run_gate_case_allow_provider_signal "vertex-primary-ratelimit-retry-reason-message" \
	"vertex_ai/retry-ratelimit-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"Retrying model 'vertex_ai/retry-ratelimit-primary' due to rate limit" \
	"2" \
	"vertex_ai/retry-ratelimit-primary|vertex_ai/retry-ratelimit-primary" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"2"

# Bug 14: Timing message — success should log elapsed time.
run_gate_case "vertex-primary-success-timing-message" \
	"vertex_ai/ready-primary" \
	"" \
	"0" \
	"REGEX:Strix run succeeded for model 'vertex_ai/ready-primary' in [0-9]+s\\." \
	"1" \
	"vertex_ai/ready-primary" \
	"<unset>"

# is_timeout_error() provider-context marker test:
# Bare "Connection timed out" without any LLM provider marker should NOT
# be treated as a timeout error. The gate should fail without retrying.
# The fake strix now also emits "httpx", "httpcore", and "requests" strings
# to verify that transport library names alone do NOT qualify as provider markers.
# Model name deliberately avoids containing any provider marker string
# (litellm, openai, anthropic, VertexAI, vertex.ai, google.cloud).
run_gate_case "bare-timeout-no-provider-marker" \
	"custom/bare-timeout-model" \
	"" \
	"1" \
	"" \
	"1" \
	"custom/bare-timeout-model" \
	"https://example.invalid" \
	"custom" \
	"__DEFAULT__" \
	"" \
	"1"

# is_timeout_error() Tier 2: httpx.ReadTimeout + provider-context marker.
# The timeout should be classified for fallback, not same-model retry.
run_gate_case_allow_provider_signal "httpx-read-timeout-with-provider-marker" \
	"vertex_ai/httpx-timeout-primary" \
	"vertex_ai/fallback-one" \
	"0" \
	"scan ok after httpx-timeout fallback" \
	"2" \
	"vertex_ai/httpx-timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

# Negative: httpx.ReadTimeout WITHOUT provider-context marker should NOT
# be classified as a retryable timeout (the gate should treat it as a
# non-recoverable scan failure).
run_gate_case "httpx-read-timeout-no-provider-marker" \
	"custom/httpx-timeout-no-ctx" \
	"" \
	"1" \
	"non-recoverable error" \
	"1" \
	"custom/httpx-timeout-no-ctx" \
	"https://example.invalid" \
	"custom" \
	"__DEFAULT__" \
	"" \
	"1"

# is_timeout_error() Tier 2b: httpcore.ReadTimeout + provider-context marker.
# Mirrors the httpx.ReadTimeout positive case above, but falls back immediately.
run_gate_case_allow_provider_signal "httpcore-read-timeout-with-provider-marker" \
	"vertex_ai/httpcore-timeout-primary" \
	"vertex_ai/fallback-one" \
	"0" \
	"scan ok after httpcore-timeout fallback" \
	"2" \
	"vertex_ai/httpcore-timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

# Negative: httpcore.ReadTimeout WITHOUT provider-context marker should NOT
# be classified as a retryable timeout (the gate should treat it as a
# non-recoverable scan failure).
run_gate_case "httpcore-read-timeout-no-provider-marker" \
	"custom/httpcore-timeout-no-ctx" \
	"" \
	"1" \
	"non-recoverable error" \
	"1" \
	"custom/httpcore-timeout-no-ctx" \
	"https://example.invalid" \
	"custom" \
	"__DEFAULT__" \
	"" \
	"1"

# is_timeout_error() positive branch for "Connection timed out" + provider marker:
# When "Connection timed out" appears alongside an LLM provider marker, the
# gate should classify it as a timeout and move to fallback.
run_gate_case_allow_provider_signal "bare-timeout-with-provider-marker" \
	"vertex_ai/bare-timeout-primary" \
	"vertex_ai/fallback-one" \
	"0" \
	"scan ok after bare-timeout fallback" \
	"2" \
	"vertex_ai/bare-timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

# Bare "Connection timed out" + provider marker: primary fails once,
# then gate falls back to fallback-one which succeeds.
run_gate_case_allow_provider_signal "bare-timeout-provider-marker-exhausted-fallback" \
	"vertex_ai/bare-timeout-exhaust-primary" \
	"vertex_ai/fallback-one" \
	"0" \
	"scan ok after bare-timeout-exhaust fallback" \
	"2" \
	"vertex_ai/bare-timeout-exhaust-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

# Sticky INFRA_ERROR_DETECTED flag: first call hits rate-limit (infra error),
# second call fails with a non-retryable error but leaves a partial LOW report.
# The gate must refuse the below-threshold bypass because an infrastructure
# error was detected during this pipeline run.
run_gate_case_allow_provider_signal "infra-error-sticky-flag" \
	"vertex_ai/sticky-flag-primary" \
	"" \
	"1" \
	"infrastructure errors occurred" \
	"3" \
	"vertex_ai/sticky-flag-primary|vertex_ai/sticky-flag-primary|vertex_ai/gemini-2.5-pro" \
	"<unset>|<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1"

run_invalid_min_fail_severity_case
run_required_input_file_outside_input_root_fails_closed_case "STRIX_LLM_FILE"
run_required_input_file_outside_input_root_fails_closed_case "LLM_API_KEY_FILE"
run_vertex_model_ignores_untrusted_llm_api_base_file_case
run_llm_api_base_file_outside_input_root_fails_closed_case
run_pr_scoped_llm_api_base_file_config_failure_exits_2_case
run_input_file_root_override_takes_precedence_over_runner_temp_case
run_stale_report_case
run_symlink_report_case
run_unsafe_target_path_case
run_absolute_outside_target_path_case

run_gate_case_allow_provider_signal "slow-timeout" \
	"vertex_ai/slow-primary" \
	"" \
	"1" \
	"Strix run timed out after 1s." \
	"3" \
	"vertex_ai/slow-primary|vertex_ai/gemini-2.5-pro|vertex_ai/gemini-2.5-flash" \
	"<unset>|<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1"

run_gate_case "timeout-disabled-success" \
	"vertex_ai/timeout-disabled-primary" \
	"" \
	"0" \
	"scan ok with timeout disabled" \
	"1" \
	"vertex_ai/timeout-disabled-primary" \
	"<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"0"

run_timeout_cleanup_case

run_total_timeout_case

run_gate_case "pr-changed-scope-bounded" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"scan ok with bounded changed-file scope" \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"

run_gate_case "pr-python-scope-context" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"scan ok with python dependency scope" \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"backend/api/emails.py"

run_gate_case "pr-changed-scope-full" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Scoped pull request Strix scan to 3 changed file(s)." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	$'sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java\nsync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java\nsync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java'

run_gate_case "pr-changed-scope-full-set" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"scan ok with full configured PR scope" \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	$'sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java\nsync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java\nsync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java\nsync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java' \
	"" \
	"2"

large_pr_changed_files=""
for large_pr_index in $(seq 1 38); do
	large_pr_path="backend/large-scope/file-$large_pr_index.py"
	if [ -n "$large_pr_changed_files" ]; then
		large_pr_changed_files+=$'\n'
	fi
	large_pr_changed_files+="$large_pr_path"
done

run_gate_case "pr-large-scope-full-set" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"scan ok with large full PR scope" \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"$large_pr_changed_files" \
	"" \
	"12"

run_gate_case "pr-changed-scope-includes-ci-dependency" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"scan ok with CI support dependency" \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"scripts/ci/strix_quick_gate.sh"

run_gate_case "pr-ci-test-harness-only-skip" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"No scannable changed files in pull request; skipping Strix quick scan." \
	"0" \
	"" \
	"" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"scripts/ci/test_strix_quick_gate.sh"

run_gate_case "pr-deployment-scope-entrypoint-context" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"scan ok with deployment entrypoint context" \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	".github/workflows/opencode-review.yml"

run_gate_case "pr-empty-diff-skip" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"No scannable changed files in pull request; skipping Strix quick scan." \
	"0" \
	"" \
	"" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"__SET_EMPTY__"

run_gate_case "pr-baseline-critical-unchanged" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix findings are limited to unchanged files in this pull request; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"

run_gate_case "pr-baseline-critical-absolute-target" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix findings are limited to unchanged files in this pull request; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"

run_gate_case "pr-baseline-critical-extensionless-dockerfile-target" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix findings are limited to unchanged files in this pull request; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	".github/workflows/opencode-review.yml"

run_gate_case "pr-baseline-critical-subdir-target" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix findings are limited to unchanged files in this pull request; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-server/src/main/resources/flyway/V24__update_search_expression_team_keyword_id.sql" \
	"" \
	"" \
	"1"

run_gate_case "pr-baseline-critical-subdir-boxed-target" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix findings are limited to unchanged files in this pull request; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-server/src/main/resources/flyway/V24__update_search_expression_team_keyword_id.sql" \
	"" \
	"" \
	"1"

run_gate_case "pr-baseline-critical-subdir-endpoint" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix findings are limited to unchanged files in this pull request; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-server/src/main/resources/flyway/V24__update_search_expression_team_keyword_id.sql" \
	"" \
	"" \
	"1"

run_gate_case "pr-baseline-critical-subdir-endpoint-bare-filename" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix findings are limited to unchanged files in this pull request; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-server/src/main/resources/flyway/V24__update_search_expression_team_keyword_id.sql" \
	"" \
	"" \
	"1"

run_gate_case "pr-baseline-critical-subdir-narrative-backticked-file" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix findings are limited to unchanged files in this pull request; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-server/src/main/resources/flyway/V24__update_search_expression_team_keyword_id.sql" \
	"" \
	"" \
	"1"

run_gate_case "pr-critical-relative-path-escape-subdir-narrative-backticked-file" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Unable to map Strix findings to changed files; failing closed for pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-server/src/main/resources/flyway/V24__update_search_expression_team_keyword_id.sql" \
	"" \
	"" \
	"1"

run_gate_case "pr-critical-changed" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Strix finding intersects files changed in this pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"

run_gate_case "pr-critical-changed-bracketed-next-route" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Strix finding intersects files changed in this pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"frontend/src/app/labels/[slug]/page.tsx"

run_gate_case "pr-critical-changed-xml-file-location" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Strix finding intersects files changed in this pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"MEDIUM" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"

run_gate_case "pr-critical-changed-xml-file-location-space" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Strix finding intersects files changed in this pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"MEDIUM" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"src/unsafe name.py"

run_gate_case "pr-baseline-critical-narrative-backticked-service-file" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix findings are limited to unchanged files in this pull request; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"backend/services/email_client.py"

run_gate_case "pr-critical-unmapped-arbitrary-backticked-service-file" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Unable to map Strix findings to changed files; failing closed for pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"backend/services/email_client.py"

run_gate_case "pr-critical-changed-absolute-target" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Strix finding intersects files changed in this pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java"

run_gate_case "pr-critical-changed-subdir-target" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Strix finding intersects files changed in this pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-server/src/main/resources/flyway/V24__update_search_expression_team_keyword_id.sql" \
	"" \
	"" \
	"1"

run_gate_case "pr-critical-changed-subdir-endpoint" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Strix finding intersects files changed in this pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-server/src/main/resources/flyway/V24__update_search_expression_team_keyword_id.sql" \
	"" \
	"" \
	"1"

run_gate_case "pr-critical-path-escape-subdir-target" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Unable to map Strix findings to changed files; failing closed for pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-server/src/main/resources/flyway/V24__update_search_expression_team_keyword_id.sql" \
	"" \
	"" \
	"1"

run_gate_case "pr-critical-unmapped" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Unable to map Strix findings to changed files; failing closed for pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"

run_gate_case "pr-critical-unmapped-narrative-target" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Unable to map Strix findings to changed files; failing closed for pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java"

run_gate_case "pr-critical-unmapped-other-workspace-repo" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Unable to map Strix findings to changed files; failing closed for pull request." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java"

run_gate_case "pr-critical-manifest-only-pom" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Strix changed-manifest finding requires verified authoritative SCA checks on this PR head; failing closed." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"pom.xml"

run_gate_case "pr-critical-manifest-only-pom-test-override" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix changed-manifest finding is covered by verified authoritative SCA checks on this PR head; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"pom.xml" \
	"" \
	"" \
	"0" \
	"passed"

run_gate_case "pr-critical-manifest-only-pom-same-head-different-pr" \
	"openai/gpt-4o-mini" \
	"" \
	"1" \
	"Strix changed-manifest finding requires verified authoritative SCA checks on this PR head; failing closed." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"pom.xml" \
	"" \
	"" \
	"0" \
	"" \
	"123" \
	'{"workflow_runs":[{"id":201,"name":"Dependency review","path":".github/workflows/dependency-review.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":456}]},{"id":202,"name":"OSV-Scanner","path":".github/workflows/osvscanner.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":456}]}]}'

run_gate_case "pr-critical-manifest-only-pom-current-pr-authoritative" \
	"openai/gpt-4o-mini" \
	"" \
	"0" \
	"Strix changed-manifest finding is covered by verified authoritative SCA checks on this PR head; allowing pipeline continuation." \
	"1" \
	"openai/gpt-4o-mini" \
	"https://example.invalid" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"pom.xml" \
	"" \
	"" \
	"0" \
	"" \
	"123" \
	'{"workflow_runs":[{"id":301,"name":"Dependency review","path":".github/workflows/dependency-review.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":123}]},{"id":302,"name":"OSV-Scanner","path":".github/workflows/osvscanner.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":123}]}]}'

run_gate_case_allow_provider_signal "pr-critical-manifest-only-pom-after-fallback-authoritative" \
	"vertex_ai/timeout-primary" \
	"vertex_ai/fallback-one" \
	"0" \
	"Strix changed-manifest finding is covered by verified authoritative SCA checks on this PR head; allowing pipeline continuation." \
	"2" \
	"vertex_ai/timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"pom.xml" \
	"" \
	"" \
	"0" \
	"" \
	"123" \
	'{"workflow_runs":[{"id":401,"name":"Dependency review","path":".github/workflows/dependency-review.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":123}]},{"id":402,"name":"OSV-Scanner","path":".github/workflows/osvscanner.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":123}]}]}'

run_gate_case_allow_provider_signal "pr-critical-manifest-only-pom-console-only-after-fallback-authoritative" \
	"vertex_ai/timeout-primary" \
	"vertex_ai/fallback-one" \
	"0" \
	"Strix changed-manifest finding is covered by verified authoritative SCA checks on this PR head; allowing pipeline continuation." \
	"2" \
	"vertex_ai/timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"pom.xml" \
	"" \
	"" \
	"0" \
	"" \
	"123" \
	'{"workflow_runs":[{"id":403,"name":"Dependency review","path":".github/workflows/dependency-review.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":123}]},{"id":404,"name":"OSV-Scanner","path":".github/workflows/osvscanner.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":123}]}]}'

run_gate_case_allow_provider_signal "pr-critical-manifest-only-pom-console-target-only-after-fallback-authoritative" \
	"vertex_ai/timeout-primary" \
	"vertex_ai/fallback-one" \
	"0" \
	"Strix changed-manifest finding is covered by verified authoritative SCA checks on this PR head; allowing pipeline continuation." \
	"2" \
	"vertex_ai/timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"pom.xml" \
	"" \
	"" \
	"0" \
	"" \
	"123" \
	'{"workflow_runs":[{"id":405,"name":"Dependency review","path":".github/workflows/dependency-review.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":123}]},{"id":406,"name":"OSV-Scanner","path":".github/workflows/osvscanner.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":123}]}]}'

run_gate_case_allow_provider_signal "pr-low-markdown-plus-console-critical-manifest-after-fallback-authoritative" \
	"vertex_ai/timeout-primary" \
	"vertex_ai/fallback-one" \
	"0" \
	"Strix changed-manifest finding is covered by verified authoritative SCA checks on this PR head; allowing pipeline continuation." \
	"2" \
	"vertex_ai/timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"0" \
	"CRITICAL" \
	"0" \
	"" \
	"" \
	"1200" \
	"0" \
	"pull_request" \
	"pom.xml" \
	"" \
	"" \
	"0" \
	"" \
	"123" \
	'{"workflow_runs":[{"id":405,"name":"Dependency review","path":".github/workflows/dependency-review.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":123}]},{"id":406,"name":"OSV-Scanner","path":".github/workflows/osvscanner.yml","head_sha":"test-head-sha","status":"completed","conclusion":"success","pull_requests":[{"number":123}]}]}'

run_missing_config_case "missing-strix-llm" "" "dummy" "ERROR: STRIX_LLM_FILE must reference a regular file containing the model."
run_missing_config_case "missing-llm-api-key" "openai/gpt-5.4" "" "ERROR: LLM_API_KEY_FILE must reference a regular file containing the API key."
run_missing_config_case "whitespace-only-strix-llm" "   " "dummy" "ERROR: STRIX_LLM_FILE must contain a non-empty model value."
run_missing_config_case "whitespace-only-llm-api-key" "openai/gpt-5.4" $'\t  ' "ERROR: LLM_API_KEY_FILE must contain a non-empty API key."
run_strix_llm_file_command_substitution_literal_case
run_vertex_without_llm_api_key_case
run_vertex_with_llm_api_key_file_does_not_forward_case

# ── Segment boundary enforcement for is_vertex_resource_path / extract_vertex_model_id ──
# Shell glob '*' matches '/' so the old case-pattern implementation accepted
# malformed paths with extra segments (e.g. "projects/a/b/locations/…").
# These tests verify that only paths with the exact expected segment count match.
#
# The gate script cannot be sourced directly (it has top-level side effects),
# so the shared helper script exposes the pure model/path functions directly.
# shellcheck source=scripts/ci/strix_model_utils.sh
# shellcheck disable=SC1091  # source path is repo-local; local lint may omit -x
. "$REPO_ROOT/scripts/ci/strix_model_utils.sh"

assert_vertex_path() {
	local label="$1" path="$2" expect_rc="$3"
	local actual_rc
	if is_vertex_resource_path "$path"; then
		actual_rc=0
	else
		actual_rc=1
	fi
	if [ "$actual_rc" -ne "$expect_rc" ]; then
		echo "FAIL: is_vertex_resource_path($label): got rc=$actual_rc want $expect_rc" >&2
		FAILURES=$((FAILURES + 1))
	fi
}

assert_vertex_extract() {
	local label="$1" path="$2" expected="$3"
	local actual rc
	set +e
	actual="$(extract_vertex_model_id "$path")"
	rc=$?
	set -e
	if [ "$rc" -ne 0 ]; then
		record_failure "extract_vertex_model_id($label) rc=$rc path='$path'"
		return
	fi
	if [ "$actual" != "$expected" ]; then
		echo "FAIL: extract_vertex_model_id($label): got '$actual' want '$expected'" >&2
		FAILURES=$((FAILURES + 1))
	fi
}

assert_normalized_model() {
	local label="$1" model="$2" default_provider="$3" expected="$4"
	local actual rc old_default_provider="${DEFAULT_PROVIDER-__UNSET__}"
	if [ "$old_default_provider" = "__UNSET__" ]; then
		unset DEFAULT_PROVIDER
	else
		DEFAULT_PROVIDER="$old_default_provider"
	fi

	DEFAULT_PROVIDER="$default_provider"
	set +e
	actual="$(normalize_model "$model")"
	rc=$?
	set -e

	if [ "$old_default_provider" = "__UNSET__" ]; then
		unset DEFAULT_PROVIDER
	else
		DEFAULT_PROVIDER="$old_default_provider"
	fi

	if [ "$rc" -ne 0 ]; then
		record_failure "normalize_model($label) rc=$rc model='$model'"
		return
	fi
	if [ "$actual" != "$expected" ]; then
		record_failure "normalize_model($label): got '$actual' want '$expected'"
	fi
}

assert_model_requires_vertex_auth() {
	local label="$1" model="$2" default_provider="$3" expected_rc="$4"
	local rc old_default_provider="${DEFAULT_PROVIDER-__UNSET__}"
	if [ "$old_default_provider" = "__UNSET__" ]; then
		unset DEFAULT_PROVIDER
	else
		DEFAULT_PROVIDER="$old_default_provider"
	fi

	DEFAULT_PROVIDER="$default_provider"
	set +e
	model_requires_vertex_auth "$model"
	rc=$?
	set -e

	if [ "$old_default_provider" = "__UNSET__" ]; then
		unset DEFAULT_PROVIDER
	else
		DEFAULT_PROVIDER="$old_default_provider"
	fi

	assert_equals "$expected_rc" "$rc" "model_requires_vertex_auth($label)"
}

# Valid paths — should return 0
assert_vertex_path "models/<id>" "models/gemini-2.5-pro" 0
assert_vertex_path "publishers/<p>/models/<id>" "publishers/google/models/gemini-2.5-pro" 0
assert_vertex_path "projects/<p>/locations/<l>/models/<id>" "projects/my-proj/locations/us-central1/models/gemini-2.5-pro" 0
assert_vertex_path "projects/<p>/locations/<l>/publishers/<pub>/models/<id>" "projects/my-proj/locations/us-central1/publishers/google/models/gemini-2.5-pro" 0

# Malformed paths — extra segments that '*' used to match across '/'
assert_vertex_path "extra-segment-in-project" "projects/a/b/locations/us/models/foo" 1
assert_vertex_path "extra-segment-in-location" "projects/a/locations/b/c/models/foo" 1
assert_vertex_path "extra-segment-in-publisher" "projects/a/locations/b/publishers/c/d/models/foo" 1
assert_vertex_path "extra-segment-after-models" "projects/a/locations/b/models/foo/bar" 1
assert_vertex_path "empty-model-id" "models/" 1
assert_vertex_path "empty-project" "projects//locations/us/models/foo" 1
assert_vertex_path "plain-model-name" "gemini-2.5-pro" 1
assert_vertex_path "non-vertex-provider-slash" "deepseek/models/deepseek-r1" 1
assert_vertex_path "empty-string" "" 1

# extract_vertex_model_id — valid paths
assert_vertex_extract "models/<id>" "models/gemini-2.5-pro" "gemini-2.5-pro"
assert_vertex_extract "publishers/<p>/models/<id>" "publishers/google/models/gemini-2.5-pro" "gemini-2.5-pro"
assert_vertex_extract "projects/<p>/locations/<l>/models/<id>" "projects/my-proj/locations/us-central1/models/gemini-2.5-pro" "gemini-2.5-pro"
assert_vertex_extract "projects/…/publishers/…/models/<id>" "projects/my-proj/locations/us-central1/publishers/google/models/gemini-2.5-pro" "gemini-2.5-pro"

# extract_vertex_model_id — non-vertex paths return as-is
assert_vertex_extract "non-vertex-passthrough" "deepseek/models/deepseek-r1" "deepseek/models/deepseek-r1"
assert_vertex_extract "plain-model-passthrough" "gemini-2.5-pro" "gemini-2.5-pro"

# Explicit Vertex resource paths must remain Vertex models even when the default
# provider points at a non-Vertex provider.
assert_normalized_model \
	"vertex-resource-ignores-nonvertex-default-provider" \
	"projects/my-proj/locations/us-central1/publishers/google/models/gemini-2.5-pro" \
	"anthropic" \
	"vertex_ai/gemini-2.5-pro"

assert_model_requires_vertex_auth "explicit-vertex" "vertex_ai/gemini-2.5-pro" "gemini" "0"
assert_model_requires_vertex_auth "explicit-vertex-beta" "vertex_ai_beta/gemini-2.5-pro" "gemini" "0"
assert_model_requires_vertex_auth "vertex-resource-path" "projects/my-proj/locations/us-central1/models/gemini-2.5-pro" "anthropic" "0"
assert_model_requires_vertex_auth "implicit-vertex-default" "gemini-2.5-pro" "vertex_ai" "0"
assert_model_requires_vertex_auth "nonvertex-provider" "gemini/gemini-2.5-pro" "gemini" "1"

# Whitespace in paths — must be rejected (SAST word-splitting guard)
assert_vertex_path "space-in-project" "projects/my proj/locations/us/models/foo" 1
assert_vertex_path "tab-in-model-id" $'models/gemini\t2.5' 1
assert_vertex_path "space-in-model-id" "models/my model" 1

run_gate_case "github-models-model-prefix-requires-api-base" \
	"openai/openai/gpt-5.4" \
	"" \
	"2" \
	"GitHub Models Strix scans require LLM_API_BASE_FILE" \
	"0" \
	"" \
	"" \
	"openai" \
	""

run_gate_case "github-models-api-base-rejected-for-direct-openai" \
	"openai/o4-mini" \
	"" \
	"2" \
	"LLM_API_BASE may route through GitHub Models only when STRIX_LLM uses a GitHub Models-compatible model" \
	"0" \
	"" \
	"" \
	"openai" \
	"https://models.github.ai/inference"

run_gate_case "github-models-openai-gpt-requires-api-base" \
	"openai/gpt-5" \
	"" \
	"2" \
	"GitHub Models Strix scans require LLM_API_BASE_FILE" \
	"0" \
	"" \
	"" \
	"openai" \
	""

run_gate_case "direct-openai-gpt-does-not-require-github-models-api-base" \
	"openai_direct/gpt-5.4" \
	"" \
	"0" \
	"scan ok" \
	"1" \
	"openai/gpt-5.4" \
	"<unset>" \
	"openai" \
	""

run_gate_case "github-models-model-prefix-with-api-base-succeeds" \
	"openai/gpt-5" \
	"" \
	"0" \
	"scan ok" \
	"1" \
	"openai/gpt-5" \
	"https://models.github.ai/inference" \
	"openai" \
	"https://models.github.ai/inference"

run_gate_case "github-models-meta-prefix-with-api-base-succeeds" \
	"openai/meta/test-github-model" \
	"" \
	"0" \
	"scan ok" \
	"1" \
	"openai/meta/test-github-model" \
	"https://models.github.ai/inference" \
	"openai" \
	"https://models.github.ai/inference"

run_gate_case "github-models-mistral-prefix-with-api-base-succeeds" \
	"openai/mistral-ai/test-github-model" \
	"" \
	"0" \
	"scan ok" \
	"1" \
	"openai/mistral-ai/test-github-model" \
	"https://models.github.ai/inference" \
	"openai" \
	"https://models.github.ai/inference"

run_gate_case "github-models-fallback-requires-api-base" \
	"vertex_ai/missing-primary" \
	"openai/openai/gpt-5.4" \
	"2" \
	"GitHub Models Strix scans require LLM_API_BASE_FILE" \
	"1" \
	"vertex_ai/missing-primary" \
	"<unset>" \
	"vertex_ai" \
	""

run_gate_case "github-models-fallback-success" \
	"vertex_ai/missing-primary" \
	"github_models/deepseek/deepseek-r1-0528 github_models/deepseek/deepseek-v3-0324" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'github_models/deepseek/deepseek-r1-0528' in [0-9]+s\\." \
	"2" \
	"vertex_ai/missing-primary|openai/deepseek/deepseek-r1-0528" \
	"<unset>|https://models.github.ai/inference" \
	"vertex_ai" \
	"https://models.github.ai/inference" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	0

run_gate_case "github-models-fallback-success-deepseek-v3" \
	"vertex_ai/missing-primary" \
	"github_models/deepseek/deepseek-r1-0528 github_models/deepseek/deepseek-v3-0324" \
	"0" \
	"REGEX:Strix quick scan succeeded with fallback model 'github_models/deepseek/deepseek-v3-0324' in [0-9]+s\\." \
	"3" \
	"vertex_ai/missing-primary|openai/deepseek/deepseek-r1-0528|openai/deepseek/deepseek-v3-0324" \
	"<unset>|https://models.github.ai/inference|https://models.github.ai/inference" \
	"vertex_ai" \
	"https://models.github.ai/inference" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	"" \
	0

# Endpoint only exists in excluded directories (.git/, node_modules/).
# The grep --exclude-dir patterns must prevent matching, so the finding
# is treated as hallucinated and fallback is allowed → exit 0.
run_gate_case "endpoint-in-excluded-dir" \
	"vertex_ai/excluded-dir-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"scan ok after excluded-dir hallucination fallback" \
	"2" \
	"vertex_ai/excluded-dir-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>"

# Whitespace-only fallback models: STRIX_VERTEX_FALLBACK_MODELS set to "  ".
# This bypasses the :- default but produces an empty array from read -r -a.
# The gate should emit "No fallback models configured" (not the misleading
# "All configured fallback models are the same as the primary model").
run_gate_case "empty-fallback-models" \
	"vertex_ai/empty-fb-primary" \
	"   " \
	"1" \
	"No fallback models configured" \
	"1" \
	"vertex_ai/empty-fb-primary" \
	"<unset>"

if [ "$FAILURES" -ne 0 ]; then
	echo "test_strix_quick_gate: ${FAILURES} failure(s)" >&2
	exit 1
fi

echo "test_strix_quick_gate: PASS"
