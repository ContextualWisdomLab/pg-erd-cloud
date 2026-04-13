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
  local transient_retry_backoff_seconds="${14-0}"
  local custom_target_path="${15-}"
  local custom_source_dirs="${16-}"
  local process_timeout_seconds="${17-1200}"
  local total_timeout_seconds="${18-0}"
  local github_event_name="${19-}"
  local changed_files_override="${20-}"
  local event_name_override="${21-}"
  local pr_scope_max_files_per_batch="${22-}"

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
  local state_file="$tmp_dir/state.log"
  local output_log="$tmp_dir/output.log"

  # Resolve target path: use custom if provided, else default to $repo_root_dir.
  local effective_target_path="$repo_root_dir"
  if [ "$custom_target_path" = "__USE_SUBDIR_SRC__" ]; then
    # Simulate STRIX_TARGET_PATH=./src by using $repo_root_dir/src.
    effective_target_path="$repo_root_dir/src"
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

target_path=""
while [ "$#" -gt 0 ]; do
	if [ "$1" = "-t" ] && [ "$#" -ge 2 ]; then
		target_path="$2"
		break
	fi
	shift
done
printf '%s\n' "$target_path" >> "${FAKE_STRIX_TARGET_LOG:?}"

STRIX_REPORTS_DIR="${STRIX_REPORTS_DIR:-strix_runs}"

case "${FAKE_STRIX_SCENARIO:?}" in
	success|vertex-primary-success-timing-message)
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
	vertex-primary-notfound-fallback-success)
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
			echo "Penetration test failed: LLM request failed: MidStreamFallbackError"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after midstream fallback"
			exit 0
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
			echo "Penetration test failed: LLM request failed: RateLimitError"
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after rate-limit fallback"
			exit 0
			;;
		*)
			echo "Error: rate-limit fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 31
			;;
		esac
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
	pr-critical-changed-absolute-target)
		mkdir -p "$STRIX_REPORTS_DIR/fake-pr-changed-absolute/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-pr-changed-absolute/vulnerabilities/vuln-0001.md" <<'EOS'
**Severity:** CRITICAL
**Target:** File: /workspace/smart-crawling-server/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java
EOS
		echo "Penetration test failed: changed critical finding with absolute target"
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
	pr-changed-scope-batched)
		attempt="0"
		if [ -f "${FAKE_STRIX_STATE_FILE:?}" ]; then
			attempt="$(cat "${FAKE_STRIX_STATE_FILE:?}")"
		fi
		attempt="$((attempt + 1))"
		echo "$attempt" > "${FAKE_STRIX_STATE_FILE:?}"
		if [ "$attempt" -eq 1 ]; then
			if [ ! -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" ]; then
				echo "Error: first batch missing controller file ($target_path)" >&2
				exit 44
			fi
			if [ ! -f "$target_path/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java" ]; then
				echo "Error: first batch missing playwright file ($target_path)" >&2
				exit 45
			fi
			if [ -e "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java" ]; then
				echo "Error: first batch leaked second-batch file ($target_path)" >&2
				exit 46
			fi
			echo "scan ok with batched changed-file scope (batch 1)"
			exit 0
		fi
		if [ "$attempt" -eq 2 ]; then
			if [ -e "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" ]; then
				echo "Error: second batch leaked first-batch controller ($target_path)" >&2
				exit 47
			fi
			if [ -e "$target_path/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java" ]; then
				echo "Error: second batch leaked first-batch playwright file ($target_path)" >&2
				exit 48
			fi
			if [ ! -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java" ]; then
				echo "Error: second batch missing service impl file ($target_path)" >&2
				exit 49
			fi
			echo "scan ok with batched changed-file scope (batch 2)"
			exit 0
		fi
		echo "Error: unexpected batch attempt $attempt" >&2
		exit 50
		;;
	pr-changed-scope-rebalanced)
		if [ -z "$target_path" ]; then
			echo "Error: target path missing" >&2
			exit 51
		fi
		if [ -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" ] && \
		   [ -f "$target_path/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java" ] && \
		   [ -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java" ] && \
		   [ -f "$target_path/sync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java" ]; then
			exit 124
		fi
		if [ -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" ] && \
		   [ -f "$target_path/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java" ] && \
		   [ ! -e "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java" ] && \
		   [ ! -e "$target_path/sync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java" ]; then
			echo "scan ok after rebalance (first half)"
			exit 0
		fi
		if [ ! -e "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java" ] && \
		   [ ! -e "$target_path/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java" ] && \
		   [ -f "$target_path/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java" ] && \
		   [ -f "$target_path/sync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java" ]; then
			echo "scan ok after rebalance (second half)"
			exit 0
		fi
		echo "Error: unexpected rebalance target layout ($target_path)" >&2
		exit 52
		;;
	*)
		echo "unknown scenario ${FAKE_STRIX_SCENARIO:?}" >&2
		exit 8
		;;
esac
EOF
  chmod +x "$fake_strix"

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
    echo 'class ChangedController {}' >"$repo_root_dir/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java"
    echo 'class BaselineUserService {}' >"$repo_root_dir/sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java"
    echo 'class ChangedPlaywright {}' >"$repo_root_dir/sync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java"
    echo 'class ChangedJwtUtil {}' >"$repo_root_dir/sync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java"
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
  elif [ "$scenario" = "pr-changed-scope-bounded" ]; then
    echo 'class Unrelated {}' >"$repo_root_dir/sync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java"
  fi

  set +e
  local env_cmd=(
    PATH="$bin_dir:$PATH"
    GITHUB_EVENT_NAME=""
    GITHUB_EVENT_PATH=""
    FAKE_STRIX_SCENARIO="$scenario"
    FAKE_STRIX_CALL_LOG="$call_log"
    FAKE_STRIX_API_BASE_LOG="$api_base_log"
    FAKE_STRIX_TARGET_LOG="$target_log"
    STRIX_LLM="$initial_model"
    STRIX_LLM_DEFAULT_PROVIDER="$default_provider"
    LLM_API_KEY="dummy"
    RAW_LLM_API_BASE="$raw_llm_api_base"
    LLM_API_BASE="$initial_llm_api_base"
    FAKE_STRIX_STATE_FILE="$state_file"
    STRIX_TRANSIENT_RETRY_PER_MODEL="$transient_retry_per_model"
    STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS="$transient_retry_backoff_seconds"
    STRIX_PROCESS_TIMEOUT_SECONDS="$process_timeout_seconds"
    STRIX_TOTAL_TIMEOUT_SECONDS="$total_timeout_seconds"
    STRIX_REPO_ROOT="$repo_root_dir"
    STRIX_FAIL_ON_MIN_SEVERITY="$min_fail_severity"
    STRIX_REPORTS_DIR="$repo_root_dir/strix_runs"
    STRIX_TARGET_PATH="$effective_target_path"
  )
  # Only export STRIX_VERTEX_FALLBACK_MODELS when a non-empty value is
  # provided so that the gate's ${STRIX_VERTEX_FALLBACK_MODELS+x} check
  # correctly distinguishes "unset → use defaults" from "set to empty →
  # disable fallbacks".
  if [ -n "$fallback_models" ]; then
    env_cmd+=(STRIX_VERTEX_FALLBACK_MODELS="$fallback_models")
  fi
  if [ -n "$custom_source_dirs" ]; then
    env_cmd+=(STRIX_SOURCE_DIRS="$custom_source_dirs")
  fi
  if [ -n "$pr_scope_max_files_per_batch" ]; then
    env_cmd+=(STRIX_PR_SCOPE_MAX_FILES_PER_BATCH="$pr_scope_max_files_per_batch")
  fi
  if [ -n "$github_event_name" ]; then
    env_cmd+=(GITHUB_EVENT_NAME="$github_event_name")
  fi
  if [ -n "$event_name_override" ]; then
    env_cmd+=(EVENT_NAME="$event_name_override")
  fi
  if [ "$changed_files_override" = "__SET_EMPTY__" ]; then
    env_cmd+=(STRIX_TEST_CHANGED_FILES_OVERRIDE="")
  elif [ -n "$changed_files_override" ]; then
    env_cmd+=(STRIX_TEST_CHANGED_FILES_OVERRIDE="$changed_files_override")
  fi
  env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE "${env_cmd[@]}" \
    bash "$gate_under_test" >"$output_log" 2>&1
  local rc=$?
  set -e

  assert_equals "$expected_exit" "$rc" "scenario=$scenario exit code"

  if [ -n "$expected_message" ]; then
    assert_file_contains "$output_log" "$expected_message" "scenario=$scenario output"
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

  cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

sleep 30 &
child_pid=$!
printf '%s' "$child_pid" > "${FAKE_STRIX_CHILD_PID_FILE:?}"
sleep 5
EOF
  chmod +x "$fake_strix"

  set +e
  env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
    PATH="$bin_dir:$PATH" \
    FAKE_STRIX_CHILD_PID_FILE="$child_pid_file" \
    STRIX_LLM="vertex_ai/timeout-cleanup-primary" \
    LLM_API_KEY="dummy" \
    STRIX_PROCESS_TIMEOUT_SECONDS="1" \
    STRIX_VERTEX_FALLBACK_MODELS="" \
    STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
    STRIX_TARGET_PATH="$repo_root_dir" \
    bash "$repo_root_dir/scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
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

  cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "1" >> "${FAKE_STRIX_CALL_COUNT_FILE:?}"
sleep 5
EOF
  chmod +x "$fake_strix"

  set +e
  env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
    PATH="$bin_dir:$PATH" \
    FAKE_STRIX_CALL_COUNT_FILE="$call_count_file" \
    STRIX_LLM="vertex_ai/total-timeout-primary" \
    LLM_API_KEY="dummy" \
    STRIX_PROCESS_TIMEOUT_SECONDS="10" \
    STRIX_TOTAL_TIMEOUT_SECONDS="3" \
    STRIX_VERTEX_FALLBACK_MODELS="vertex_ai/fallback-one" \
    STRIX_TRANSIENT_RETRY_PER_MODEL="2" \
    STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS="0" \
    STRIX_REPORTS_DIR="$repo_root_dir/strix_runs" \
    STRIX_TARGET_PATH="$repo_root_dir" \
    bash "$repo_root_dir/scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
  local rc=$?
  set -e

  assert_equals "1" "$rc" "total timeout exit code"
  assert_file_contains "$output_log" "Strix quick scan exceeded total timeout of 3s." "total timeout output"
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

  cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "1" >> "${STRIX_CALL_COUNT_FILE:?}"
exit 0
EOF
  chmod +x "$fake_strix"

  set +e
  env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
    PATH="$tmp_dir:$PATH" \
    STRIX_LLM="$strix_llm" \
    LLM_API_KEY="$llm_api_key" \
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

run_invalid_min_fail_severity_case() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  local output_log="$tmp_dir/output.log"
  local fake_strix="$tmp_dir/strix"

  cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "unexpected strix execution" >&2
exit 99
EOF
  chmod +x "$fake_strix"

  set +e
  env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
    PATH="$tmp_dir:$PATH" \
    STRIX_LLM="vertex_ai/ready-primary" \
    LLM_API_KEY="dummy" \
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

run_stale_report_case() {
  local tmp_dir
  tmp_dir="$(mktemp -d)"
  local repo_root_dir="$tmp_dir/workspace/smart-crawling-server"
  local output_log="$tmp_dir/output.log"
  local fake_strix="$tmp_dir/strix"
  local stale_report_dir="$repo_root_dir/strix_runs/stale/vulnerabilities"

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

  set +e
  env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
    PATH="$tmp_dir:$PATH" \
    STRIX_LLM="openai/gpt-4o-mini" \
    LLM_API_KEY="dummy" \
    RAW_LLM_API_BASE="https://example.invalid/generateContent" \
    STRIX_REPORTS_DIR="strix_runs" \
    bash "$repo_root_dir/scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
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

  set +e
  env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
    PATH="$tmp_dir:$PATH" \
    STRIX_LLM="openai/gpt-4o-mini" \
    LLM_API_KEY="dummy" \
    RAW_LLM_API_BASE="https://example.invalid/generateContent" \
    STRIX_REPORTS_DIR="strix_runs" \
    bash "$repo_root_dir/scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
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

  set +e
  env -u GITHUB_EVENT_NAME -u GITHUB_EVENT_PATH -u STRIX_TEST_CHANGED_FILES_OVERRIDE \
    PATH="$tmp_dir:$PATH" \
    FAKE_STRIX_CALL_LOG="$call_log" \
    STRIX_LLM="openai/gpt-4o-mini" \
    LLM_API_KEY="dummy" \
    RAW_LLM_API_BASE="https://example.invalid/generateContent" \
    STRIX_TARGET_PATH="../../../../../etc/passwd" \
    bash "$repo_root_dir/scripts/ci/strix_quick_gate.sh" >"$output_log" 2>&1
  local rc=$?
  set -e

  assert_equals "2" "$rc" "case=unsafe-target-path exit code"
  assert_file_contains "$output_log" "contains unsupported path syntax" "case=unsafe-target-path output"
  if [ -f "$call_log" ]; then
    record_failure "case=unsafe-target-path should reject before invoking strix"
  fi

  rm -rf "$tmp_dir"
}

run_gate_case "success" \
  "vertex_ai/ready-primary" \
  "vertex_ai/fallback-one vertex_ai/fallback-two" \
  "0" \
  "scan ok" \
  "1" \
  "vertex_ai/ready-primary" \
  "<unset>"

run_gate_case "vertex-primary-notfound-fallback-success" \
  "vertex_ai/missing-primary" \
  "vertex_ai/fallback-one vertex_ai/fallback-two" \
  "0" \
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
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
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
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
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
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
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
  "2" \
  "vertex_ai/missing-primary|vertex_ai/fallback-one" \
  "<unset>|<unset>"

run_gate_case "vertex-notfound-compact-status-fallback-success" \
  "vertex_ai/missing-primary" \
  "vertex_ai/fallback-one" \
  "0" \
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
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
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
  "2" \
  "vertex_ai/missing-primary|vertex_ai/fallback-one" \
  "<unset>|<unset>"

run_gate_case "multiline-fallback-success" \
  "vertex_ai/missing-primary" \
  $'vertex_ai/fallback-one\nvertex_ai/fallback-two' \
  "0" \
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-two'." \
  "3" \
  "vertex_ai/missing-primary|vertex_ai/fallback-one|vertex_ai/fallback-two" \
  "<unset>|<unset>|<unset>"

run_gate_case "vertex-primary-ratelimit-fallback-success" \
  "vertex_ai/ratelimit-primary" \
  "vertex_ai/fallback-one vertex_ai/fallback-two" \
  "0" \
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
  "2" \
  "vertex_ai/ratelimit-primary|vertex_ai/fallback-one" \
  "<unset>|<unset>"

run_gate_case "vertex-primary-resource-exhausted-fallback-success" \
  "vertex_ai/resource-exhausted-primary" \
  "vertex_ai/fallback-one vertex_ai/fallback-two" \
  "0" \
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
  "2" \
  "vertex_ai/resource-exhausted-primary|vertex_ai/fallback-one" \
  "<unset>|<unset>"

run_gate_case "vertex-primary-429-fallback-success" \
  "vertex_ai/http429-primary" \
  "vertex_ai/fallback-one vertex_ai/fallback-two" \
  "0" \
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
  "2" \
  "vertex_ai/http429-primary|vertex_ai/fallback-one" \
  "<unset>|<unset>"

run_gate_case "vertex-primary-midstream-fallback-success" \
  "vertex_ai/midstream-primary" \
  "vertex_ai/fallback-one vertex_ai/fallback-two" \
  "0" \
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
  "2" \
  "vertex_ai/midstream-primary|vertex_ai/fallback-one" \
  "<unset>|<unset>"

run_gate_case "vertex-primary-midstream-retry-same-model-success" \
  "vertex_ai/retry-midstream-primary" \
  "vertex_ai/fallback-one vertex_ai/fallback-two" \
  "0" \
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
  "2" \
  "vertex_ai/retry-midstream-primary|vertex_ai/fallback-one" \
  "<unset>|<unset>" \
  "vertex_ai" \
  "__DEFAULT__" \
  "" \
  "1"

# Bug 9: Rate-limit transient same-model retry (previously untested path)
run_gate_case "vertex-primary-ratelimit-retry-same-model-success" \
  "vertex_ai/retry-ratelimit-primary" \
  "vertex_ai/fallback-one vertex_ai/fallback-two" \
  "0" \
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
  "2" \
  "vertex_ai/retry-ratelimit-primary|vertex_ai/fallback-one" \
  "<unset>|<unset>" \
  "vertex_ai" \
  "__DEFAULT__" \
  "" \
  "1"

# Bug 11: Timeout should move directly to fallback instead of retrying the same model.
run_gate_case "vertex-primary-timeout-retry-same-model-success" \
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
run_gate_case "vertex-primary-timeout-exhausted-fallback-success" \
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

run_gate_case "vertex-all-ratelimited" \
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
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
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

# Infrastructure error guard: below-threshold findings must NOT pass when the
# strix log contains evidence of infrastructure-level errors (timeout,
# rate-limit, transport failures) because the scan was likely incomplete.

# Guard test 1: LOW finding + timeout → should fail (exit 1).
# The below-threshold check runs first but detects infrastructure errors in the
# strix log and refuses bypass.  The timeout is also vertex-retryable, so the
# gate continues into the fallback loop.  All attempts see the same timeout.
run_gate_case "below-threshold-with-timeout" \
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
run_gate_case "below-threshold-with-ratelimit" \
  "vertex_ai/low-ratelimit-primary" \
  "vertex_ai/gemini-2.5-pro vertex_ai/gemini-2.5-flash" \
  "1" \
  "infrastructure errors occurred during this pipeline run; refusing bypass" \
  "3" \
  "vertex_ai/low-ratelimit-primary|vertex_ai/gemini-2.5-pro|vertex_ai/gemini-2.5-flash" \
  "<unset>|<unset>|<unset>"

# Guard test 3: INFO finding + ConnectionError → should fail (exit 1).
# ConnectionError is NOT vertex-retryable, so only the primary model is tried.
run_gate_case "below-threshold-with-connection-error" \
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
run_gate_case "below-threshold-with-midstream" \
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
  "Configured Vertex model and fallback models were unavailable." \
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
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
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
  "Strix quick scan succeeded with fallback model 'vertex_ai/gemini-2.5-pro'." \
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
run_gate_case "vertex-primary-timeout-retry-reason-message" \
  "vertex_ai/retry-timeout-primary" \
  "vertex_ai/fallback-one vertex_ai/fallback-two" \
  "0" \
  "Strix quick scan succeeded with fallback model 'vertex_ai/fallback-one'." \
  "2" \
  "vertex_ai/retry-timeout-primary|vertex_ai/fallback-one" \
  "<unset>|<unset>" \
  "vertex_ai" \
  "__DEFAULT__" \
  "" \
  "2"

# Bug 14: Retry reason messages — rate-limit retry should say "due to rate limit".
run_gate_case "vertex-primary-ratelimit-retry-reason-message" \
  "vertex_ai/retry-ratelimit-primary" \
  "vertex_ai/fallback-one vertex_ai/fallback-two" \
  "0" \
  "Primary Vertex model unavailable; retrying with fallback 'vertex_ai/fallback-one'." \
  "2" \
  "vertex_ai/retry-ratelimit-primary|vertex_ai/fallback-one" \
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
  "Strix run succeeded for model 'vertex_ai/ready-primary' in " \
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
run_gate_case "httpx-read-timeout-with-provider-marker" \
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
run_gate_case "httpcore-read-timeout-with-provider-marker" \
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
run_gate_case "bare-timeout-with-provider-marker" \
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
run_gate_case "bare-timeout-provider-marker-exhausted-fallback" \
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
run_gate_case "infra-error-sticky-flag" \
  "vertex_ai/sticky-flag-primary" \
  "" \
  "1" \
  "infrastructure errors occurred" \
  "2" \
  "vertex_ai/sticky-flag-primary|vertex_ai/gemini-2.5-pro" \
  "<unset>|<unset>" \
  "vertex_ai" \
  "__DEFAULT__" \
  "" \
  "1"

run_invalid_min_fail_severity_case
run_stale_report_case
run_symlink_report_case
run_unsafe_target_path_case

run_gate_case "slow-timeout" \
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

run_gate_case "pr-changed-scope-batched" \
  "openai/gpt-4o-mini" \
  "" \
  "0" \
  "Scoped pull request Strix scan to 3 changed file(s) across 2 batch(es)." \
  "2" \
  "openai/gpt-4o-mini|openai/gpt-4o-mini" \
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
  $'sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java\nsync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java\nsync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java' \
  "" \
  "2"

run_gate_case "pr-changed-scope-rebalanced" \
  "vertex_ai/gemini-2.5-flash" \
  "vertex_ai/gemini-2.5-pro" \
  "0" \
  "Rebalancing pull request Strix batch 1/1 into smaller batches after timeout." \
  "3" \
  "vertex_ai/gemini-2.5-flash|vertex_ai/gemini-2.5-flash|vertex_ai/gemini-2.5-flash" \
  "<unset>|<unset>|<unset>" \
  "vertex_ai" \
  "__DEFAULT__" \
  "" \
  "0" \
  "CRITICAL" \
  "0" \
  "" \
  "" \
  "1200" \
  "3000" \
  "pull_request" \
  $'sync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/controller/SysPositionController.java\nsync-module-system/smart-crawling-playwright/src/main/java/org/empasy/sync/mcp/service/PlayWrightService.java\nsync-module-system/smart-crawling-biz/src/main/java/org/empasy/sync/modules/system/service/impl/SysUserServiceImpl.java\nsync-module-system/smart-crawling-common/src/main/java/org/empasy/sync/common/system/util/JwtUtil.java' \
  "" \
  "4"

run_gate_case "success" \
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

run_gate_case "pr-baseline-critical-absolute-target" \
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

run_missing_config_case "missing-strix-llm" "" "dummy" "ERROR: STRIX_LLM is required."
run_missing_config_case "missing-llm-api-key" "vertex_ai/ready-primary" "" "ERROR: LLM_API_KEY is required."
run_missing_config_case "whitespace-only-strix-llm" "   " "dummy" "ERROR: STRIX_LLM is required."
run_missing_config_case "whitespace-only-llm-api-key" "vertex_ai/ready-primary" $'\t  ' "ERROR: LLM_API_KEY is required."

# ── Segment boundary enforcement for is_vertex_resource_path / extract_vertex_model_id ──
# Shell glob '*' matches '/' so the old case-pattern implementation accepted
# malformed paths with extra segments (e.g. "projects/a/b/locations/…").
# These tests verify that only paths with the exact expected segment count match.
#
# The gate script cannot be sourced directly (it has top-level side effects),
# so the shared helper script exposes the pure model/path functions directly.
# shellcheck source=scripts/ci/strix_model_utils.sh
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
  local actual
  actual="$(extract_vertex_model_id "$path")"
  if [ "$actual" != "$expected" ]; then
    echo "FAIL: extract_vertex_model_id($label): got '$actual' want '$expected'" >&2
    FAILURES=$((FAILURES + 1))
  fi
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

# Whitespace in paths — must be rejected (SAST word-splitting guard)
assert_vertex_path "space-in-project" "projects/my proj/locations/us/models/foo" 1
assert_vertex_path "tab-in-model-id" $'models/gemini\t2.5' 1
assert_vertex_extract "space-passthrough" "models/my model" "models/my model"

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
