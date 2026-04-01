#!/usr/bin/env bash
set -euo pipefail

TARGET_PATH="${STRIX_TARGET_PATH:-./}"
SCAN_MODE="${STRIX_SCAN_MODE:-quick}"
STRIX_LOG="$(mktemp)"
STRIX_REPORTS_DIR="${STRIX_REPORTS_DIR:-strix_runs}"
DEFAULT_PROVIDER="${STRIX_LLM_DEFAULT_PROVIDER:-}"
ORIGINAL_LLM_API_BASE="${LLM_API_BASE:-}"
STRIX_ATTEMPT_TIMEOUT_SECONDS="${STRIX_ATTEMPT_TIMEOUT_SECONDS:-480}"
STRIX_ATTEMPT_KILL_AFTER_SECONDS="${STRIX_ATTEMPT_KILL_AFTER_SECONDS:-20}"
STRIX_TRANSIENT_RETRY_PER_MODEL="${STRIX_TRANSIENT_RETRY_PER_MODEL:-0}"
STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS="${STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS:-3}"
STRIX_FAIL_ON_MIN_SEVERITY="${STRIX_FAIL_ON_MIN_SEVERITY:-CRITICAL}"
PREEXISTING_REPORT_DIRS=()

cleanup() {
	rm -f "$STRIX_LOG"
}
trap cleanup EXIT

trim_whitespace() {
	local value="$1"
	value="${value#"${value%%[![:space:]]*}"}"
	value="${value%"${value##*[![:space:]]}"}"
	echo "$value"
}

STRIX_LLM="$(trim_whitespace "${STRIX_LLM:-}")"
if [ -z "$STRIX_LLM" ]; then
	echo "ERROR: STRIX_LLM is required." >&2
	exit 2
fi

LLM_API_KEY="$(trim_whitespace "${LLM_API_KEY:-}")"
if [ -z "$LLM_API_KEY" ]; then
	echo "ERROR: LLM_API_KEY is required." >&2
	exit 2
fi
export STRIX_LLM
export LLM_API_KEY

require_positive_integer() {
	local value="$1"
	local label="$2"
	if ! [[ "$value" =~ ^[1-9][0-9]*$ ]]; then
		echo "ERROR: $label must be a positive integer, got '$value'." >&2
		exit 2
	fi
}

require_non_negative_integer() {
	local value="$1"
	local label="$2"
	if ! [[ "$value" =~ ^[0-9]+$ ]]; then
		echo "ERROR: $label must be a non-negative integer, got '$value'." >&2
		exit 2
	fi
}

severity_rank() {
	case "${1^^}" in
	CRITICAL)
		echo 4
		;;
	HIGH)
		echo 3
		;;
	MEDIUM)
		echo 2
		;;
	LOW)
		echo 1
		;;
	INFO | INFORMATIONAL | NONE)
		echo 0
		;;
	*)
		echo -1
		;;
	esac
}

capture_preexisting_report_dirs() {
	local run_dir
	for run_dir in "$STRIX_REPORTS_DIR"/*; do
		if [ ! -d "$run_dir" ]; then
			continue
		fi
		PREEXISTING_REPORT_DIRS+=("$run_dir")
	done
}

is_preexisting_report_dir() {
	local candidate="$1"
	local existing

	for existing in "${PREEXISTING_REPORT_DIRS[@]}"; do
		if [ "$candidate" = "$existing" ]; then
			return 0
		fi
	done

	return 1
}

resolve_timeout_bin() {
	if command -v timeout >/dev/null 2>&1; then
		echo "timeout"
		return 0
	fi

	if command -v gtimeout >/dev/null 2>&1; then
		echo "gtimeout"
		return 0
	fi

	echo ""
}

is_provider_qualified_model() {
	case "$1" in
	vertex_ai/* | vertex_ai_beta/* | openai/* | anthropic/* | azure/* | gemini/* | bedrock/* | groq/* | mistral/* | cohere/* | ollama/* | huggingface/* | xai/*)
		return 0
		;;
	*)
		return 1
		;;
	esac
}

is_vertex_resource_path() {
	case "$1" in
	projects/*/locations/*/publishers/*/models/* | projects/*/locations/*/models/* | publishers/*/models/* | models/*)
		return 0
		;;
	*)
		return 1
		;;
	esac
}

extract_vertex_model_id() {
	local raw_model="$1"
	local model_id="$raw_model"

	if [[ "$model_id" == projects/*/locations/*/publishers/*/models/* ]]; then
		model_id="${model_id##*/models/}"
		echo "$model_id"
		return 0
	fi

	# Vertex custom model resource paths: projects/<p>/locations/<l>/models/<id>
	if [[ "$model_id" == projects/*/locations/*/models/* ]]; then
		model_id="${model_id##*/models/}"
		echo "$model_id"
		return 0
	fi

	if [[ "$model_id" == */models/* ]]; then
		model_id="${model_id##*/models/}"
		echo "$model_id"
		return 0
	fi

	if [[ "$model_id" == models/* ]]; then
		echo "${model_id#models/}"
		return 0
	fi

	echo "$model_id"
}

normalize_model() {
	local raw_model="$1"
	raw_model="$(trim_whitespace "$raw_model")"
	if [ -z "$raw_model" ]; then
		echo "$raw_model"
		return 0
	fi

	if is_provider_qualified_model "$raw_model"; then
		echo "$raw_model"
		return 0
	fi

	if [[ "$raw_model" == */* ]] && ! is_vertex_resource_path "$raw_model"; then
		echo "$raw_model"
		return 0
	fi

	if is_vertex_resource_path "$raw_model"; then
		local vertex_provider="${DEFAULT_PROVIDER%/}"
		if [ "$vertex_provider" != "vertex_ai" ] && [ "$vertex_provider" != "vertex_ai_beta" ]; then
			vertex_provider="vertex_ai"
		fi

		echo "$vertex_provider/$(extract_vertex_model_id "$raw_model")"
		return 0
	fi

	if [ -z "$DEFAULT_PROVIDER" ]; then
		echo "$raw_model"
		return 0
	fi

	local normalized_model="$raw_model"
	local provider="${DEFAULT_PROVIDER%/}"
	if [ "$provider" = "vertex_ai" ] || [ "$provider" = "vertex_ai_beta" ]; then
		normalized_model="$(extract_vertex_model_id "$raw_model")"
	fi

	echo "$provider/$normalized_model"
}

PRIMARY_MODEL="$(normalize_model "$STRIX_LLM")"
if [ "$PRIMARY_MODEL" != "$STRIX_LLM" ]; then
	echo "Normalized STRIX_LLM to provider-qualified model '$PRIMARY_MODEL'."
fi

require_positive_integer "$STRIX_ATTEMPT_TIMEOUT_SECONDS" "STRIX_ATTEMPT_TIMEOUT_SECONDS"
require_positive_integer "$STRIX_ATTEMPT_KILL_AFTER_SECONDS" "STRIX_ATTEMPT_KILL_AFTER_SECONDS"
require_non_negative_integer "$STRIX_TRANSIENT_RETRY_PER_MODEL" "STRIX_TRANSIENT_RETRY_PER_MODEL"
require_non_negative_integer "$STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS" "STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS"

if [ "$(severity_rank "$STRIX_FAIL_ON_MIN_SEVERITY")" -lt 0 ]; then
	echo "ERROR: STRIX_FAIL_ON_MIN_SEVERITY must be one of CRITICAL/HIGH/MEDIUM/LOW/INFO/INFORMATIONAL/NONE, got '$STRIX_FAIL_ON_MIN_SEVERITY'." >&2
	exit 2
fi

capture_preexisting_report_dirs
TIMEOUT_BIN="$(resolve_timeout_bin)"

is_vertex_model() {
	case "$1" in
	vertex_ai/* | vertex_ai_beta/*)
		return 0
		;;
	*)
		return 1
		;;
	esac
}

prepare_llm_api_base() {
	local model="$1"

	if is_vertex_model "$model"; then
		unset LLM_API_BASE
		return 0
	fi

	local llm_api_base_value="${RAW_LLM_API_BASE:-$ORIGINAL_LLM_API_BASE}"
	llm_api_base_value="${llm_api_base_value%%/generateContent*}"
	llm_api_base_value="${llm_api_base_value%%:generateContent*}"
	if [ -n "$llm_api_base_value" ]; then
		export LLM_API_BASE="$llm_api_base_value"
	else
		unset LLM_API_BASE
	fi
}

run_strix_once() {
	local model="$1"
	local rc
	export STRIX_LLM="$model"
	export LLM_MODEL="$model"
	prepare_llm_api_base "$model"
	local start_epoch
	start_epoch="$(date +%s)"
	set -o pipefail
	set +e
	if [ -n "$TIMEOUT_BIN" ]; then
		"$TIMEOUT_BIN" --signal=TERM --kill-after="${STRIX_ATTEMPT_KILL_AFTER_SECONDS}s" "${STRIX_ATTEMPT_TIMEOUT_SECONDS}s" \
			strix -n -t "$TARGET_PATH" --scan-mode "$SCAN_MODE" 2>&1 | tee "$STRIX_LOG"
		rc=$?
	else
		strix -n -t "$TARGET_PATH" --scan-mode "$SCAN_MODE" 2>&1 | tee "$STRIX_LOG"
		rc=$?
	fi
	set -e
	local end_epoch
	end_epoch="$(date +%s)"
	local elapsed=$((end_epoch - start_epoch))

	if [ "$rc" -eq 0 ]; then
		printf "Strix run succeeded for model '%s' in %ds.\n" "$model" "$elapsed" >&2
		return 0
	fi

	if [ -n "$TIMEOUT_BIN" ] && { [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; }; then
		printf "Strix run timed out for model '%s' after %ds (limit %ss). Check whether sandbox image pull consumed part of the budget.\n" \
			"$model" "$elapsed" "$STRIX_ATTEMPT_TIMEOUT_SECONDS" | tee -a "$STRIX_LOG" >&2
	else
		printf "Strix run failed for model '%s' after %ds (exit code %d).\n" "$model" "$elapsed" "$rc" >&2
	fi

	return 1
}

is_transient_same_model_retry_error() {
	if is_rate_limit_error; then
		return 0
	fi

	if is_midstream_fallback_error; then
		return 0
	fi

	# Timeouts are transient — retry the same model before falling back.
	if is_timeout_error; then
		return 0
	fi

	return 1
}

run_strix_with_transient_retry() {
	local model="$1"
	local max_attempts=$((STRIX_TRANSIENT_RETRY_PER_MODEL + 1))
	local attempt=1

	while [ "$attempt" -le "$max_attempts" ]; do
		if run_strix_once "$model"; then
			return 0
		fi

		if [ "$attempt" -ge "$max_attempts" ]; then
			return 1
		fi

		if ! is_transient_same_model_retry_error; then
			return 1
		fi

		local retry_reason="transient error"
		if is_timeout_error; then
			retry_reason="timeout"
		elif is_rate_limit_error; then
			retry_reason="rate limit"
		elif is_midstream_fallback_error; then
			retry_reason="midstream fallback"
		fi
		echo "Retrying model '$model' due to $retry_reason (attempt $((attempt + 1))/$max_attempts)." >&2
		sleep "$STRIX_TRANSIENT_RETRY_BACKOFF_SECONDS"
		attempt=$((attempt + 1))
	done

	return 1
}

is_vertex_not_found_error() {
	# Match Vertex/LiteLLM model-not-found errors.
	# These functions are only called within the Vertex fallback path
	# (gated by is_vertex_model), so the risk of matching target-app
	# 404s is low — strix separates LLM errors from scan findings.
	if grep -Fq 'litellm.NotFoundError: Vertex_aiException' "$STRIX_LOG"; then
		return 0
	fi

	if grep -Fq 'litellm.NotFoundError' "$STRIX_LOG" && grep -Eq '"status"[[:space:]]*:[[:space:]]*"NOT_FOUND"' "$STRIX_LOG"; then
		return 0
	fi

	# Compact Vertex/GCP API error format — require a provider marker
	# (litellm, VertexAI, or Vertex) nearby so we don't misclassify
	# target-application 404 JSON responses as LLM provider errors.
	if grep -Eq '"status"[[:space:]]*:[[:space:]]*"NOT_FOUND"' "$STRIX_LOG" &&
		grep -Eiq '(litellm|VertexAI|Vertex_ai|vertex\.ai|google\.cloud)' "$STRIX_LOG"; then
		return 0
	fi

	if grep -Eq 'Publisher Model .*was not found' "$STRIX_LOG"; then
		return 0
	fi

	return 1
}

is_rate_limit_error() {
	if grep -Fq 'RateLimitError' "$STRIX_LOG"; then
		return 0
	fi

	if grep -Eq '"status"[[:space:]]*:[[:space:]]*"RESOURCE_EXHAUSTED"' "$STRIX_LOG"; then
		return 0
	fi

	# Bare HTTP 429 — require a provider marker so we don't misclassify
	# target-application rate-limit responses as LLM provider errors.
	if grep -Eq '(^|[^0-9])429([^0-9]|$)' "$STRIX_LOG" &&
		grep -Eiq '(litellm|RateLimitError|VertexAI|Vertex_ai|vertex\.ai|openai|anthropic)' "$STRIX_LOG"; then
		return 0
	fi

	return 1
}

is_timeout_error() {
	# Internal timeout marker written by run_strix_once() — always trusted.
	if grep -Fq 'Strix run timed out for model ' "$STRIX_LOG"; then
		return 0
	fi

	# litellm SDK timeout — provider-specific, always trusted.
	if grep -Fq 'litellm.exceptions.Timeout' "$STRIX_LOG"; then
		return 0
	fi

	# httpx/httpcore are litellm/openai SDK transport libraries, but their
	# timeout strings could appear in target-application logs too.
	# Require a provider-context marker nearby to avoid misclassification.
	if grep -Fq 'httpx.ReadTimeout' "$STRIX_LOG" &&
		grep -Eiq '(litellm|openai|anthropic|VertexAI|Vertex_ai|vertex\.ai|google\.cloud)' "$STRIX_LOG"; then
		return 0
	fi

	if grep -Fq 'httpcore.ReadTimeout' "$STRIX_LOG" &&
		grep -Eiq '(litellm|openai|anthropic|VertexAI|Vertex_ai|vertex\.ai|google\.cloud)' "$STRIX_LOG"; then
		return 0
	fi

	# Bare "Connection timed out" — require a provider-context marker so we
	# don't misclassify target-application or network timeouts as LLM errors.
	if grep -Fq 'Connection timed out' "$STRIX_LOG" &&
		grep -Eiq '(litellm|openai|anthropic|VertexAI|Vertex_ai|vertex\.ai|google\.cloud|httpx|httpcore)' "$STRIX_LOG"; then
		return 0
	fi

	return 1
}

is_midstream_fallback_error() {
	if grep -Fq 'MidStreamFallbackError' "$STRIX_LOG"; then
		return 0
	fi

	return 1
}

latest_strix_report_dir() {
	local latest=""
	local run_dir

	for run_dir in "$STRIX_REPORTS_DIR"/*; do
		if [ ! -d "$run_dir" ] || [ -L "$run_dir" ]; then
			continue
		fi

		if is_preexisting_report_dir "$run_dir"; then
			continue
		fi

		if [ -z "$latest" ] || [ "$run_dir" -nt "$latest" ]; then
			latest="$run_dir"
		fi
	done

	if [ -z "$latest" ]; then
		return 1
	fi

	echo "$latest"
}

has_only_below_threshold_vulnerabilities() {
	local threshold_rank
	threshold_rank="$(severity_rank "$STRIX_FAIL_ON_MIN_SEVERITY")"

	local found_any_report=0
	local found_any_vuln_file=0
	local global_max_rank=-1
	local saw_any_severity=0

	local run_dir
	for run_dir in "$STRIX_REPORTS_DIR"/*; do
		if [ ! -d "$run_dir" ] || [ -L "$run_dir" ]; then
			continue
		fi

		if is_preexisting_report_dir "$run_dir"; then
			continue
		fi

		local vulnerabilities_dir="$run_dir/vulnerabilities"
		if [ ! -d "$vulnerabilities_dir" ] || [ -L "$vulnerabilities_dir" ]; then
			continue
		fi

		found_any_report=1
		local vuln_file
		local line
		local severity
		local rank

		for vuln_file in "$vulnerabilities_dir"/*.md; do
			if [ ! -f "$vuln_file" ] || [ -L "$vuln_file" ]; then
				continue
			fi

			found_any_vuln_file=1

			while IFS= read -r line; do
				if [[ "${line^^}" =~ SEVERITY[[:space:]]*:[[:space:][:punct:]]*(CRITICAL|HIGH|MEDIUM|LOW|INFO|INFORMATIONAL|NONE)([[:space:][:punct:]]|$) ]]; then
					severity="${BASH_REMATCH[1]}"
				else
					continue
				fi

				rank="$(severity_rank "$severity")"
				if [ "$rank" -lt 0 ]; then
					continue
				fi

				saw_any_severity=1
				if [ "$rank" -gt "$global_max_rank" ]; then
					global_max_rank="$rank"
				fi
			done < <(grep -Ei 'severity[[:space:]]*:' "$vuln_file" || true)
		done
	done

	if [ "$found_any_report" -eq 0 ]; then
		return 1
	fi

	# Guard against incomplete/aborted scans: if reports exist but no
	# vulnerability files were found, the scan likely aborted before
	# completing its analysis — refuse the bypass.
	if [ "$found_any_vuln_file" -eq 0 ]; then
		echo "Reports exist but contain no vulnerability files; scan may be incomplete." >&2
		return 1
	fi

	if [ "$saw_any_severity" -eq 0 ]; then
		return 1
	fi

	if [ "$global_max_rank" -lt "$threshold_rank" ]; then
		echo "Strix findings are below configured fail threshold '$STRIX_FAIL_ON_MIN_SEVERITY'; allowing pipeline continuation." >&2
		return 0
	fi

	return 1
}

is_hallucinated_endpoint_finding() {
	# Configurable list of source directories to check for endpoints.
	# Defaults to "." (i.e. TARGET_PATH itself) so that both
	# STRIX_TARGET_PATH=./ and STRIX_TARGET_PATH=./src work correctly
	# without producing bogus double-nested paths like ./src/src.
	# Set STRIX_SOURCE_DIRS (space-separated) to override.
	local source_dirs_raw="${STRIX_SOURCE_DIRS:-.}"
	local resolved_dirs=()
	local dir_entry

	# Disable globbing so that entries like "*" or "[" in STRIX_SOURCE_DIRS
	# are not expanded by pathname expansion during word-splitting.
	set -f
	for dir_entry in $source_dirs_raw; do
		local candidate="${TARGET_PATH%/}/$dir_entry"
		if [ -d "$candidate" ] && [ ! -L "$candidate" ]; then
			resolved_dirs+=("$candidate")
		fi
	done
	set +f

	if [ "${#resolved_dirs[@]}" -eq 0 ]; then
		return 1
	fi

	local latest_report_dir
	if ! latest_report_dir="$(latest_strix_report_dir)"; then
		return 1
	fi

	local endpoint_seen=0
	local endpoint_present_in_source=0
	local endpoint
	local vuln_file

	for vuln_file in "$latest_report_dir"/vulnerabilities/*.md; do
		if [ ! -f "$vuln_file" ] || [ -L "$vuln_file" ]; then
			continue
		fi

		while IFS= read -r endpoint; do
			if [ -z "$endpoint" ]; then
				continue
			fi

			endpoint_seen=1
			local search_dir
			for search_dir in "${resolved_dirs[@]}"; do
				# Exclude the strix reports directory from the source search
				# to prevent matching endpoints inside vulnerability reports
				# themselves (especially when STRIX_TARGET_PATH=./).
				if grep -r -Fq --exclude-dir="$(basename "$STRIX_REPORTS_DIR")" -- "$endpoint" "$search_dir"; then
					endpoint_present_in_source=1
					break
				fi
			done
			if [ "$endpoint_present_in_source" -eq 1 ]; then
				break
			fi
		done < <(grep -Eo '/api/[[:alnum:]_./-]+' "$vuln_file" | sort -u)

		if [ "$endpoint_present_in_source" -eq 1 ]; then
			break
		fi
	done

	if [ "$endpoint_seen" -eq 0 ]; then
		return 1
	fi

	if [ "$endpoint_present_in_source" -eq 1 ]; then
		return 1
	fi

	echo "Detected Strix report endpoint(s) absent from source; treating as retryable model inconsistency." >&2
	return 0
}

is_vertex_retryable_error() {
	if is_vertex_not_found_error; then
		return 0
	fi

	if is_rate_limit_error; then
		return 0
	fi

	if is_timeout_error; then
		return 0
	fi

	if is_midstream_fallback_error; then
		return 0
	fi

	if is_hallucinated_endpoint_finding; then
		return 0
	fi

	return 1
}

if run_strix_with_transient_retry "$PRIMARY_MODEL"; then
	exit 0
fi

if has_only_below_threshold_vulnerabilities; then
	exit 0
fi

if ! is_vertex_model "$PRIMARY_MODEL"; then
	echo "Strix quick scan failed with a non-recoverable error." >&2
	exit 1
fi

if ! is_vertex_retryable_error; then
	echo "Strix quick scan failed with a non-recoverable error." >&2
	exit 1
fi

FALLBACK_MODELS_RAW="${STRIX_VERTEX_FALLBACK_MODELS:-vertex_ai/gemini-2.5-pro vertex_ai/gemini-2.5-flash}"
FALLBACK_MODELS_RAW="${FALLBACK_MODELS_RAW//$'\r'/ }"
FALLBACK_MODELS_RAW="${FALLBACK_MODELS_RAW//$'\n'/ }"
read -r -a FALLBACK_MODELS <<<"$FALLBACK_MODELS_RAW"

fallback_tried=0
for candidate_raw in "${FALLBACK_MODELS[@]}"; do
	candidate="$(normalize_model "$candidate_raw")"
	if [ -z "$candidate" ] || [ "$candidate" = "$PRIMARY_MODEL" ]; then
		if [ -n "$candidate" ]; then
			echo "Skipping fallback model '$candidate' — same as primary model." >&2
		fi
		continue
	fi

	fallback_tried=1
	echo "Primary Vertex model unavailable; retrying with fallback '$candidate'."
	if run_strix_with_transient_retry "$candidate"; then
		echo "Strix quick scan succeeded with fallback model '$candidate'."
		exit 0
	fi

	if has_only_below_threshold_vulnerabilities; then
		exit 0
	fi

	if ! is_vertex_retryable_error; then
		echo "Strix quick scan failed with a non-recoverable error." >&2
		exit 1
	fi
done

if [ "$fallback_tried" -eq 0 ]; then
	echo "ERROR: All configured fallback models are the same as the primary model '$PRIMARY_MODEL'. Configure distinct models in STRIX_VERTEX_FALLBACK_MODELS." >&2
fi

echo "Configured Vertex model and fallback models were unavailable." >&2
exit 1
