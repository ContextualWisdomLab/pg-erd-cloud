#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(CDPATH= cd -P -- "$(dirname -- "$0")" && pwd -P)"
REPO_ROOT="$(CDPATH= cd -P -- "$SCRIPT_DIR/../.." && pwd -P)"
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
	local attempt_timeout_seconds="${12-}"
	local fake_hang_seconds="${13-2}"
	local transient_retry_per_model="${14-0}"
	local min_fail_severity="${15-CRITICAL}"

	local tmp_dir
	tmp_dir="$(mktemp -d)"
	# Create src/ so is_hallucinated_endpoint_finding() has a directory to scan,
	# making the test self-contained regardless of the repo's actual layout.
	mkdir -p "$tmp_dir/src"
	local fake_strix="$tmp_dir/strix"
	local call_log="$tmp_dir/calls.log"
	local api_base_log="$tmp_dir/api_base.log"
	local state_file="$tmp_dir/state.log"
	local output_log="$tmp_dir/output.log"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

echo "${STRIX_LLM:-}" >> "${FAKE_STRIX_CALL_LOG:?}"
echo "${LLM_API_BASE:-<unset>}" >> "${FAKE_STRIX_API_BASE_LOG:?}"

STRIX_REPORTS_DIR="${STRIX_REPORTS_DIR:-strix_runs}"

case "${FAKE_STRIX_SCENARIO:?}" in
	success)
		echo "scan ok"
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
			echo "HTTP 429 Too Many Requests"
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
		*)
			echo "Error: same-model retry path unexpected (${STRIX_LLM:-})" >&2
			exit 30
			;;
		esac
		;;
	vertex-all-ratelimited)
		echo "Penetration test failed: LLM request failed: RateLimitError"
		exit 1
		;;
	vertex-primary-timeout-fallback-success)
		case "${STRIX_LLM:-}" in
		vertex_ai/timeout-primary)
			sleep "${FAKE_STRIX_HANG_SECONDS:-2}"
			echo "litellm.exceptions.Timeout: litellm.Timeout: Connection timed out after None seconds."
			exit 1
			;;
		vertex_ai/fallback-one)
			echo "scan ok after timeout fallback"
			exit 0
			;;
		*)
			echo "Error: timeout fallback path unexpected (${STRIX_LLM:-})" >&2
			exit 22
			;;
		esac
		;;
	vertex-all-timeout)
		sleep "${FAKE_STRIX_HANG_SECONDS:-2}"
		echo "litellm.exceptions.Timeout: litellm.Timeout: Connection timed out after None seconds."
		exit 1
		;;
	vertex-primary-hallucinated-endpoint-fallback-success)
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
	vertex-primary-existing-endpoint-nonrecoverable)
		case "${STRIX_LLM:-}" in
		vertex_ai/existing-endpoint-primary)
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
	high-vuln-below-threshold)
		mkdir -p "$STRIX_REPORTS_DIR/fake-high/vulnerabilities"
		cat >"$STRIX_REPORTS_DIR/fake-high/vulnerabilities/vuln-0001.md" <<'EOS'
Severity: HIGH
EOS
		echo "Penetration test failed: simulated high finding"
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
	*)
		echo "unknown scenario ${FAKE_STRIX_SCENARIO:?}" >&2
		exit 8
		;;
esac
EOF
	chmod +x "$fake_strix"

	# Scenario-specific source-tree setup so is_hallucinated_endpoint_finding()
	# can locate "real" endpoints inside the self-contained temp workspace.
	if [ "$scenario" = "vertex-primary-existing-endpoint-nonrecoverable" ]; then
		echo 'GET /api/status' >"$tmp_dir/src/routes.txt"
	fi

	set +e
	PATH="$tmp_dir:$PATH" \
		FAKE_STRIX_SCENARIO="$scenario" \
		FAKE_STRIX_CALL_LOG="$call_log" \
		FAKE_STRIX_API_BASE_LOG="$api_base_log" \
		STRIX_LLM="$initial_model" \
		STRIX_LLM_DEFAULT_PROVIDER="$default_provider" \
		LLM_API_KEY="dummy" \
		RAW_LLM_API_BASE="$raw_llm_api_base" \
		LLM_API_BASE="$initial_llm_api_base" \
		STRIX_ATTEMPT_TIMEOUT_SECONDS="$attempt_timeout_seconds" \
		FAKE_STRIX_HANG_SECONDS="$fake_hang_seconds" \
		FAKE_STRIX_STATE_FILE="$state_file" \
		STRIX_TRANSIENT_RETRY_PER_MODEL="$transient_retry_per_model" \
		STRIX_FAIL_ON_MIN_SEVERITY="$min_fail_severity" \
		STRIX_VERTEX_FALLBACK_MODELS="$fallback_models" \
		STRIX_REPORTS_DIR="$tmp_dir/strix_runs" \
		STRIX_TARGET_PATH="$tmp_dir" \
		bash "$GATE_SCRIPT" >"$output_log" 2>&1
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
	PATH="$tmp_dir:$PATH" \
		STRIX_LLM="vertex_ai/ready-primary" \
		LLM_API_KEY="dummy" \
		STRIX_FAIL_ON_MIN_SEVERITY="BOGUS" \
		bash "$GATE_SCRIPT" >"$output_log" 2>&1
	local rc=$?
	set -e

	assert_equals "2" "$rc" "case=invalid-min-fail-severity exit code"
	assert_file_contains "$output_log" "STRIX_FAIL_ON_MIN_SEVERITY must be one of CRITICAL/HIGH/MEDIUM/LOW/INFO/INFORMATIONAL" "case=invalid-min-fail-severity output"

	rm -rf "$tmp_dir"
}

run_stale_report_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local stale_report_dir="$tmp_dir/strix_runs/stale/vulnerabilities"

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
	PATH="$tmp_dir:$PATH" \
		STRIX_LLM="openai/gpt-4o-mini" \
		LLM_API_KEY="dummy" \
		RAW_LLM_API_BASE="https://example.invalid/generateContent" \
		STRIX_REPORTS_DIR="$tmp_dir/strix_runs" \
		bash "$GATE_SCRIPT" >"$output_log" 2>&1
	local rc=$?
	set -e

	assert_equals "1" "$rc" "case=stale-report-does-not-bypass exit code"
	assert_file_contains "$output_log" "Strix quick scan failed with a non-recoverable error." "case=stale-report-does-not-bypass output"

	rm -rf "$tmp_dir"
}

run_symlink_report_case() {
	local tmp_dir
	tmp_dir="$(mktemp -d)"
	local output_log="$tmp_dir/output.log"
	local fake_strix="$tmp_dir/strix"
	local external_report_dir="$tmp_dir/external/vulnerabilities"

	mkdir -p "$external_report_dir" "$tmp_dir/strix_runs"
	cat >"$external_report_dir/vuln-0001.md" <<'EOF'
Severity: LOW
EOF
	ln -s "$tmp_dir/external" "$tmp_dir/strix_runs/latest"

	cat >"$fake_strix" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "Error: transport timeout"
exit 1
EOF
	chmod +x "$fake_strix"

	set +e
	PATH="$tmp_dir:$PATH" \
		STRIX_LLM="openai/gpt-4o-mini" \
		LLM_API_KEY="dummy" \
		RAW_LLM_API_BASE="https://example.invalid/generateContent" \
		STRIX_REPORTS_DIR="$tmp_dir/strix_runs" \
		bash "$GATE_SCRIPT" >"$output_log" 2>&1
	local rc=$?
	set -e

	assert_equals "1" "$rc" "case=symlink-report-does-not-bypass exit code"
	assert_file_contains "$output_log" "Strix quick scan failed with a non-recoverable error." "case=symlink-report-does-not-bypass output"

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
	"scan ok after same-model retry" \
	"2" \
	"vertex_ai/retry-midstream-primary|vertex_ai/retry-midstream-primary" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"" \
	"2" \
	"1"

run_gate_case "vertex-all-ratelimited" \
	"vertex_ai/ratelimit-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Configured Vertex model and fallback models were unavailable." \
	"3" \
	"vertex_ai/ratelimit-primary|vertex_ai/fallback-one|vertex_ai/fallback-two" \
	"<unset>|<unset>|<unset>"

run_gate_case "vertex-primary-timeout-fallback-success" \
	"vertex_ai/timeout-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"0" \
	"Strix run timed out for model 'vertex_ai/timeout-primary' after 1s." \
	"2" \
	"vertex_ai/timeout-primary|vertex_ai/fallback-one" \
	"<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1" \
	"2"

run_gate_case "vertex-all-timeout" \
	"vertex_ai/timeout-primary" \
	"vertex_ai/fallback-one vertex_ai/fallback-two" \
	"1" \
	"Configured Vertex model and fallback models were unavailable." \
	"3" \
	"vertex_ai/timeout-primary|vertex_ai/fallback-one|vertex_ai/fallback-two" \
	"<unset>|<unset>|<unset>" \
	"vertex_ai" \
	"__DEFAULT__" \
	"" \
	"1" \
	"2"

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

run_invalid_min_fail_severity_case
run_stale_report_case
run_symlink_report_case

run_missing_config_case "missing-strix-llm" "" "dummy" "ERROR: STRIX_LLM is required."
run_missing_config_case "missing-llm-api-key" "vertex_ai/ready-primary" "" "ERROR: LLM_API_KEY is required."
run_missing_config_case "whitespace-only-strix-llm" "   " "dummy" "ERROR: STRIX_LLM is required."
run_missing_config_case "whitespace-only-llm-api-key" "vertex_ai/ready-primary" $'\t  ' "ERROR: LLM_API_KEY is required."

if [ "$FAILURES" -ne 0 ]; then
	echo "test_strix_quick_gate: ${FAILURES} failure(s)" >&2
	exit 1
fi

echo "test_strix_quick_gate: PASS"
