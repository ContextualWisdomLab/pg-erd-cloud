#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
	echo "usage: $0 <output-file>" >&2
	exit 2
fi

: "${GH_REPOSITORY:?GH_REPOSITORY is required}"
: "${PR_NUMBER:?PR_NUMBER is required}"
: "${HEAD_SHA:?HEAD_SHA is required}"

OUTPUT_FILE="$1"
FAILED_CHECK_LOG_LINES="${FAILED_CHECK_LOG_LINES:-180}"

strip_ansi() {
	perl -pe 's/\x1b\[[0-9;?]*[A-Za-z]//g'
}

emit_bounded_file() {
	local file_path="$1"
	local max_lines="$2"
	local total_lines
	local head_lines
	local tail_lines

	total_lines="$(wc -l <"$file_path" | tr -d '[:space:]')"
	if [ -z "$total_lines" ] || [ "$total_lines" -le "$max_lines" ]; then
		sed -n "1,${max_lines}p" "$file_path"
		return 0
	fi

	head_lines=$((max_lines / 2))
	tail_lines=$((max_lines - head_lines))
	sed -n "1,${head_lines}p" "$file_path"
	printf '\n... truncated %s middle log lines ...\n\n' "$((total_lines - max_lines))"
	tail -n "$tail_lines" "$file_path"
}

emit_failure_signal_summary() {
	local log_file="$1"
	local summary_tmp

	summary_tmp="$(mktemp)"
	tmp_files+=("$summary_tmp")

	awk '
		/FAIL:/ ||
		/::error::/ ||
		/##\[error\]/ ||
		/Process completed with exit code/ ||
		/LLM CONNECTION FAILED/ ||
		/RateLimitError/ ||
		/Too many requests/ ||
		/budget limit/ ||
		/Configured model and fallback models were unavailable/ ||
		/provider infrastructure/ ||
		/[Ff]atal/ ||
		/[Dd]enied/ ||
		/[Tt]imeout/ ||
		/[Ww]arn/ {
			if (!seen[$0]++) {
				print
			}
		}
	' "$log_file" >"$summary_tmp"

	if [ ! -s "$summary_tmp" ]; then
		return 1
	fi

	printf '### Failed log signal summary\n\n'
	printf '```text\n'
	emit_bounded_file "$summary_tmp" 120
	printf '\n```\n\n'
}

emit_strix_vulnerability_evidence() {
	local log_file="$1"
	local summary_tmp
	local ranges_tmp
	local merged_ranges_tmp
	local report_index=0
	local start_line
	local end_line

	summary_tmp="$(mktemp)"
	ranges_tmp="$(mktemp)"
	merged_ranges_tmp="$(mktemp)"
	tmp_files+=("$summary_tmp" "$ranges_tmp" "$merged_ranges_tmp")

	awk '
		/Strix run failed for model/ ||
		/Primary model unavailable; retrying with fallback/ ||
		/Strix fallback model/ ||
		/LLM CONNECTION FAILED/ ||
		/RateLimitError/ ||
		/Too many requests/ ||
		/budget limit/ ||
		/Configured model and fallback models were unavailable/ ||
		/Below-threshold findings detected/ ||
		/Unable to map Strix findings/ ||
		/Model [[:alnum:]_.\/-]+/ ||
		/Vulnerabilities[[:space:]]+[0-9]/ ||
		/Vulnerabilities[[:space:]]+.*Total/ ||
		/(CRITICAL|HIGH|MEDIUM|LOW):[[:space:]]+[0-9]/ {
			if (!seen[$0]++) {
				print
			}
		}
	' "$log_file" >"$summary_tmp"

	awk '
		/Vulnerability Report/ {
			start = NR - 12
			if (start < 1) {
				start = 1
			}
			end = NR + 190
			print start, end
		}
	' "$log_file" >"$ranges_tmp"

	if [ ! -s "$summary_tmp" ] && [ ! -s "$ranges_tmp" ]; then
		return 1
	fi

	printf '### Strix model attempt and finding summary\n\n'
	if [ -s "$summary_tmp" ]; then
		printf '```text\n'
		emit_bounded_file "$summary_tmp" 180
		printf '\n```\n\n'
	else
		printf 'No model summary lines were detected in the failed Strix log.\n\n'
	fi

	if [ ! -s "$ranges_tmp" ]; then
		printf 'No Strix vulnerability report windows were detected in the failed log.\n\n'
		return 0
	fi

	awk '
		NR == 1 {
			start = $1
			end = $2
			next
		}
		$1 <= end + 5 {
			if ($2 > end) {
				end = $2
			}
			next
		}
		{
			print start, end
			start = $1
			end = $2
		}
		END {
			if (start != "") {
				print start, end
			}
		}
	' "$ranges_tmp" >"$merged_ranges_tmp"

	while read -r start_line end_line; do
		report_index=$((report_index + 1))
		printf '### Strix vulnerability report window %s (log lines %s-%s)\n\n' "$report_index" "$start_line" "$end_line"
		printf '```text\n'
		sed -n "${start_line},${end_line}p" "$log_file"
		printf '\n```\n\n'
	done <"$merged_ranges_tmp"
}

owner="${GH_REPOSITORY%%/*}"
repo="${GH_REPOSITORY#*/}"
failed_contexts="$(mktemp)"
workflow_run_contexts="$(mktemp)"
tmp_files=("$failed_contexts" "$workflow_run_contexts")
cleanup() {
	rm -f "${tmp_files[@]}"
}
trap cleanup EXIT

# shellcheck disable=SC2016
gh api graphql \
	-f owner="$owner" \
	-f name="$repo" \
	-F number="$PR_NUMBER" \
	-f query='
		query($owner:String!,$name:String!,$number:Int!) {
			repository(owner:$owner,name:$name) {
				pullRequest(number:$number) {
					statusCheckRollup {
						contexts(first: 100) {
							nodes {
								__typename
								... on CheckRun {
									databaseId
									name
									status
									conclusion
									detailsUrl
									checkSuite {
										workflowRun {
											databaseId
											workflow {
												name
											}
										}
									}
								}
								... on StatusContext {
									context
									state
									targetUrl
								}
							}
						}
					}
				}
			}
		}
	' \
	--jq '
		(.data.repository.pullRequest.statusCheckRollup.contexts.nodes // [])
		| map(
			if .__typename == "CheckRun" then
				select((.status // "") == "COMPLETED")
				| select((.conclusion // "" | ascii_upcase) as $c | ["FAILURE","TIMED_OUT","ACTION_REQUIRED","CANCELLED","STARTUP_FAILURE"] | index($c))
				| [
					"check_run",
					(((.checkSuite.workflowRun.workflow.name // "") + "/" + (.name // "check")) | gsub("^/"; "")),
					(.conclusion // "unknown"),
					(.detailsUrl // ""),
					((.checkSuite.workflowRun.databaseId // "") | tostring),
					((.databaseId // "") | tostring)
				]
			elif .__typename == "StatusContext" then
				select((.state // "" | ascii_upcase) as $s | ["FAILURE","ERROR"] | index($s))
				| [
					"status_context",
					(.context // "status"),
					(.state // "unknown"),
					(.targetUrl // ""),
					"",
					""
				]
			else
				empty
			end
		)
		| .[]
		| @tsv
		' >"$failed_contexts"

	HEAD_SHA="$HEAD_SHA" gh run list \
		--repo "$GH_REPOSITORY" \
		--commit "$HEAD_SHA" \
		--limit 100 \
		--json databaseId,workflowName,status,conclusion,url,event,headSha \
		--jq '
			.[]
			| select((.event // "") == "pull_request_target" or (.event // "") == "workflow_dispatch")
			| select((.headSha // "") == env.HEAD_SHA)
			| select((.workflowName // "") == "Strix Security Scan" or (.workflowName // "") == "Strix")
			| select((.status // "") == "completed")
			| select((.conclusion // "" | ascii_downcase) as $c | ["failure","timed_out","action_required","cancelled","startup_failure"] | index($c))
			| [
			"workflow_run",
			(if (.workflowName // "") != "" then .workflowName else "workflow run" end),
			(.conclusion // "unknown"),
			(.url // ""),
			((.databaseId // "") | tostring),
			""
		]
		| @tsv
	' >"$workflow_run_contexts"

while IFS=$'\t' read -r kind label conclusion details_url run_id check_run_id; do
	if [ -z "$run_id" ]; then
		continue
	fi
	if awk -F '\t' -v run_id="$run_id" '$5 == run_id { found = 1 } END { exit found ? 0 : 1 }' "$failed_contexts"; then
		continue
	fi
	printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$kind" "$label" "$conclusion" "$details_url" "$run_id" "$check_run_id" >>"$failed_contexts"
done <"$workflow_run_contexts"

{
	printf '# Failed GitHub Check Evidence\n\n'
	printf -- '- PR: #%s\n' "$PR_NUMBER"
	printf -- '- Head SHA: `%s`\n' "$HEAD_SHA"
	printf -- '- Repository: `%s`\n\n' "$GH_REPOSITORY"
	printf '## Line-specific repair contract\n\n'
	printf -- '- Treat the check logs and annotations below as diagnostic evidence, not as a complete review.\n'
	printf -- '- For each actionable failed check, inspect the local source or diff and identify the exact file line that must change.\n'
	printf -- '- OpenCode `REQUEST_CHANGES` findings must include `path`, `line`, `root_cause`, `fix_direction`, `regression_test_direction`, and `suggested_diff`.\n'
	printf -- '- Do not request changes with only a GitHub Actions URL or a generic check name.\n\n'
	printf -- '- When Strix logs contain multiple `Vulnerability Report` or `Model ... Vulnerabilities ...` sections, include every model-reported vulnerability in the review evidence and findings, including model name, title, severity, endpoint, and Code Locations/path:line evidence when present.\n'
	printf -- '- Create one OpenCode finding per Strix model vulnerability report; do not satisfy two model reports with one combined finding, even when titles or locations match.\n\n'

	if [ ! -s "$failed_contexts" ]; then
		printf 'No completed failed GitHub Checks were present when evidence was collected.\n'
		exit 0
	fi

	while IFS=$'\t' read -r kind label conclusion details_url run_id check_run_id; do
		printf '## Failed check: %s\n\n' "$label"
		printf -- '- Type: `%s`\n' "$kind"
		printf -- '- Conclusion: `%s`\n' "$conclusion"
		if [ -n "$details_url" ]; then
			printf -- '- Details URL: %s\n' "$details_url"
		fi
		if [ -n "$run_id" ]; then
			printf -- '- Workflow run id: `%s`\n' "$run_id"
		fi
		if [ -n "$check_run_id" ]; then
			printf -- '- Check run id: `%s`\n' "$check_run_id"
		fi
		printf '\n'

			if [ "$kind" = "workflow_run" ] && [ -n "$run_id" ]; then
				log_file="$(mktemp)"
				stripped_log_file="$(mktemp)"
				tmp_files+=("$log_file" "$stripped_log_file")
				if gh run view "$run_id" --repo "$GH_REPOSITORY" --log-failed >"$log_file" 2>&1; then
					strip_ansi <"$log_file" >"$stripped_log_file"
					if [ -s "$stripped_log_file" ]; then
						emit_failure_signal_summary "$stripped_log_file" || true
						printf '### Failed workflow run log excerpt\n\n'
						printf '```text\n'
						emit_bounded_file "$stripped_log_file" "$FAILED_CHECK_LOG_LINES"
						printf '\n```\n\n'
						if [[ "$label" == *Strix* ]]; then
							emit_strix_vulnerability_evidence "$stripped_log_file" || true
						fi
					else
						printf 'No GitHub Actions job log is available for this failed workflow run.\n\n'
						if [ "$conclusion" = "cancelled" ]; then
							printf 'The workflow run completed as cancelled before GitHub emitted a failed job log. Treat this as missing current-head security evidence, not as a source-code vulnerability report.\n\n'
						fi
					fi
				else
				strip_ansi <"$log_file" >"$stripped_log_file"
				printf 'No GitHub Actions job log is available for this failed workflow run.\n\n'
				printf '```text\n'
				emit_bounded_file "$stripped_log_file" 60
				printf '\n```\n\n'
			fi
			continue
		fi

		if [ "$kind" != "check_run" ] || [ -z "$check_run_id" ]; then
			printf 'No GitHub Actions job log is available for this status context.\n\n'
			continue
		fi

		job_json="$(mktemp)"
		tmp_files+=("$job_json")
		if gh api -X GET "repos/${GH_REPOSITORY}/actions/jobs/${check_run_id}" >"$job_json" 2>/dev/null; then
			failed_steps="$(
				jq -r '
					(.steps // [])
					| map(select((.conclusion // "" | ascii_downcase) as $c | ["failure","timed_out","cancelled","startup_failure"] | index($c)))
					| .[]
					| "- step " + ((.number // 0) | tostring) + ": " + (.name // "step") + " (" + (.conclusion // "unknown") + ")"
				' "$job_json"
			)"
			if [ -n "$failed_steps" ]; then
				printf '### Failed job steps\n\n'
				printf '%s\n\n' "$failed_steps"
			fi
		fi

		annotations_tmp="$(mktemp)"
		tmp_files+=("$annotations_tmp")
		if gh api -X GET "repos/${GH_REPOSITORY}/check-runs/${check_run_id}/annotations" --paginate \
			--jq '
				.[]?
				| "- " + (.path // "unknown") + ":" + ((.start_line // 0) | tostring) + "-" + ((.end_line // .start_line // 0) | tostring) + " [" + (.annotation_level // "annotation") + "] " + ((.message // .title // "") | gsub("\r|\n"; " "))
			' >"$annotations_tmp" 2>/dev/null; then
			if [ -s "$annotations_tmp" ]; then
				printf '### Check annotations\n\n'
				emit_bounded_file "$annotations_tmp" 40
				printf '\n'
			fi
		fi

		log_raw="$(mktemp)"
		log_clean="$(mktemp)"
		tmp_files+=("$log_raw" "$log_clean")
		if [ -n "$run_id" ] && gh run view "$run_id" \
			--repo "$GH_REPOSITORY" \
			--job "$check_run_id" \
			--log-failed >"$log_raw" 2>&1; then
			strip_ansi <"$log_raw" >"$log_clean"
			if [ -s "$log_clean" ]; then
				emit_failure_signal_summary "$log_clean" || true
				if emit_strix_vulnerability_evidence "$log_clean"; then
					printf '\n'
				fi
				printf '### Failed log excerpt\n\n'
				printf '```text\n'
				emit_bounded_file "$log_clean" "$FAILED_CHECK_LOG_LINES"
				printf '\n```\n\n'
			fi
		else
			printf '### Failed log excerpt\n\n'
			printf 'The failed job log could not be collected with `gh run view --log-failed`.\n\n'
			if [ -s "$log_raw" ]; then
				printf '```text\n'
				strip_ansi <"$log_raw" | sed -n '1,40p'
				printf '\n```\n\n'
			fi
		fi
	done <"$failed_contexts"
} >"$OUTPUT_FILE"
