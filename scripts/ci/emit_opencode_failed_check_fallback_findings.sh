#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
	echo "usage: $0 <failed-check-evidence-file> [repo-root]" >&2
	exit 64
fi

EVIDENCE_FILE="$1"
REPO_ROOT="${2:-${GITHUB_WORKSPACE:-$PWD}}"
finding_index=0
tmp_files=()

cleanup() {
	rm -f "${tmp_files[@]}"
}
trap cleanup EXIT

normalize_source_path() {
	local raw_path="$1"
	local candidate

	candidate="$(printf '%s' "$raw_path" | sed -E 's#^/workspace/[^/]+/##; s#^/tmp/strix-pr-scope\.[^/]+/##; s#^\./##; s#^/##')"
	case "$candidate" in
		services/*.py)
			candidate="backend/$candidate"
			;;
		src/*)
			if [ -e "${REPO_ROOT%/}/frontend/$candidate" ]; then
				candidate="frontend/$candidate"
			fi
			;;
	esac
	printf '%s' "$candidate"
}

first_existing_line() {
	local path="$1"
	local pattern="${2:-}"
	local match=""

	if [ ! -f "${REPO_ROOT%/}/$path" ]; then
		printf '1'
		return 0
	fi
	if [ -n "$pattern" ]; then
		match="$(grep -nE -- "$pattern" "${REPO_ROOT%/}/$path" | head -n 1 || true)"
		if [ -n "$match" ]; then
			printf '%s' "${match%%:*}"
			return 0
		fi
	fi
	printf '1'
}

has_strix_vulnerability_report_window() {
	local strix_evidence_file="$1"

	grep -Eq '^### Strix vulnerability report window[[:space:]]' "$strix_evidence_file"
}

derive_location_from_report() {
	local title="$1"
	local endpoint="$2"
	local target="$3"
	local raw_location="$4"
	local clean_location=""
	local path=""
	local line=""
	local line_range=""

	if [ -n "$raw_location" ]; then
		clean_location="$(normalize_source_path "$raw_location")"
		path="${clean_location%:*}"
		line_range="${clean_location##*:}"
		line="${line_range%%-*}"
		if [ -f "${REPO_ROOT%/}/$path" ] && [[ "$line" =~ ^[0-9]+$ ]]; then
			printf '%s\t%s\t%s' "$path" "$line" "$raw_location"
			return 0
		fi
	fi

	if [[ "$target" =~ (backend/[^[:space:]]+|frontend/[^[:space:]]+|\.github/[^[:space:]]+|scripts/[^[:space:]]+) ]]; then
		path="$(normalize_source_path "${BASH_REMATCH[1]}")"
	elif [[ "$endpoint" =~ ^/services/.*\.py$ ]]; then
		path="$(normalize_source_path "${endpoint#/}")"
	fi

	if [ -n "$path" ] && [ -f "${REPO_ROOT%/}/$path" ]; then
		line="$(first_existing_line "$path")"
		printf '%s\t%s\t%s' "$path" "$line" "target/endpoint: ${target:-$endpoint}"
		return 0
	fi

	case "$title" in
		*"docker_entrypoint.sh"*|*"Docker Runtime Failure"*)
			path="Dockerfile"
			line="$(first_existing_line "$path" '^CMD \["/app/scripts/docker_entrypoint\.sh"\]|^ENTRYPOINT .*docker_entrypoint\.sh')"
			;;
		*"Path Traversal"*Attachment*|*"attachment"*filename*)
			path="backend/services/email_parser.py"
			line="$(first_existing_line "$path" 'filename = part\.get_filename\(\)|"filename":')"
			;;
		*"OIDC"*|*"session token"*|*"Session Token"*)
			path="frontend/src/lib/oidc-session.ts"
			line="$(first_existing_line "$path" 'sessionStorage\.setItem')"
			;;
		*"Prompt"*Studio*|*"Prompt Injection"*)
			path="frontend/src/app/prompt-studio/page.tsx"
			line="$(first_existing_line "$path" "apiClient\\.post|testResult|setTestResult")"
			;;
		*"Frontend Security Issues"*|*"Hardcoded Credentials"*|*"Insecure Data Handling"*)
			path="frontend/next.config.ts"
			line="$(first_existing_line "$path" 'const nextConfig|headers|Content-Security-Policy')"
			if [ ! -f "${REPO_ROOT%/}/$path" ]; then
				path="frontend/src/app/page.tsx"
				line="$(first_existing_line "$path")"
			fi
			;;
		*"Content Security Policy"*|*"security headers"*|*"Security Headers"*)
			path="frontend/next.config.ts"
			line="$(first_existing_line "$path" 'const nextConfig|headers')"
			;;
		*"JWT"*|*"Authentication"*)
			path="backend/api/auth.py"
			line="$(first_existing_line "$path" 'jwt\.decode|JWT_DECODE_REQUIRED_CLAIMS|_build_oidc_jwks_client')"
			;;
	esac

	if [ -n "$path" ] && [ -f "${REPO_ROOT%/}/$path" ] && [[ "$line" =~ ^[0-9]+$ ]]; then
		printf '%s\t%s\t%s' "$path" "$line" "derived from Strix title: $title"
		return 0
	fi

	printf 'unknown\t1\tStrix report did not include a mappable Code Location'
}

extract_strix_failed_check_block() {
	local source_file="$1"
	local output_file="$2"

	awk '
		/^## Failed check: / {
			in_strix = ($0 ~ /^## Failed check: .*Strix/)
		}
		in_strix { print }
	' "$source_file" >"$output_file"
}

extract_strix_reports() {
	local source_file="$1"
	perl -CS -ne '
		sub clean {
			my ($line) = @_;
			$line =~ s/\r//g;
			$line =~ s/\x1b\[[0-9;?]*[A-Za-z]//g;
			if ($line =~ /│/) {
				$line =~ s/^.*?│[[:space:]]*//;
				$line =~ s/[[:space:]]*│.*$//;
			} else {
				$line =~ s/^.*?[0-9]Z[[:space:]]+//;
			}
			$line =~ s/[[:space:]]+/ /g;
			$line =~ s/^[[:space:]]+|[[:space:]]+$//g;
			return $line;
		}
		sub starts_new_field {
			my ($line) = @_;
			return $line =~ /^(Title|Severity|CVSS Score|CVSS Vector|Target|Endpoint|Method|Description|Impact|Technical Analysis|PoC Description|PoC Code|Code Locations|Remediation)\b/i;
		}
		sub finish_report {
			return unless defined $title && length $title;
			push @reports, {
				model => $report_model,
				title => $title,
				severity => $severity,
				endpoint => $endpoint,
				method => $method,
				target => $target,
				location => $location,
			};
			($report_model, $title, $severity, $endpoint, $method, $target, $location) = ("", "", "", "", "", "", "");
		}
		sub finish_window {
			finish_report();
			for my $report (@reports) {
				my $model = $report->{model} || $window_model || $current_model || "unknown-model";
				for my $field ($model, @$report{qw(title severity endpoint method target location)}) {
					$field //= "";
					$field =~ s/\t/ /g;
				}
				print join("\x1f", $model, @$report{qw(title severity endpoint method target location)}), "\n";
			}
			@reports = ();
			$window_model = "";
		}
		my $line = clean($_);
		if ($line =~ /^### Strix vulnerability report window/i) {
			finish_window();
			$in_window = 1;
			if ($line =~ m{(?:model|for model)[[:space:]]+((?:github[-_]models|openai|deepseek|vertex_ai)/[A-Za-z0-9._/-]+)}i) {
				$window_model = $1;
				$current_model = $1;
			}
			next;
		}
		if ($line =~ m{(?:^|[[:space:]])Model[[:space:]]+((?:github[-_]models|openai|deepseek|vertex_ai)/[A-Za-z0-9._/-]+)}i ||
			$line =~ m{Strix run failed for model '\''([^'\'']+)'\''}) {
			$current_model = $1;
			$window_model ||= $1 if $in_window;
			$report_model = $1 if defined $title && length $title;
		}
		next unless $in_window;
		if (defined $continuation_field && length $continuation_field) {
			if (!length $line) {
				$continuation_field = "";
			} elsif (!starts_new_field($line) && $line !~ /^[╭╰─]+/ && $line !~ /^Vulnerability Report$/i) {
				if ($continuation_field eq "title") {
					$title .= " " . $line;
				} elsif ($continuation_field eq "endpoint") {
					$endpoint .= " " . $line;
				} elsif ($continuation_field eq "target") {
					$target .= " " . $line;
				}
				next;
			} else {
				$continuation_field = "";
			}
		}
		if ($line =~ /^Title:[[:space:]]+(.+)/i) {
			finish_report();
			$title = $1;
			$report_model = $window_model || $current_model || "";
			$continuation_field = "title";
			next;
		}
		if ($line =~ /^Severity:[[:space:]]+(CRITICAL|HIGH|MEDIUM|LOW|NONE)\b/i) {
			$severity = uc($1);
			next;
		}
		if ($line =~ /^Endpoint:[[:space:]]+(.+)/i) {
			$endpoint = $1;
			$continuation_field = "endpoint";
			next;
		}
		if ($line =~ /^Method:[[:space:]]+(.+)/i) {
			$method = $1;
			$continuation_field = "";
			next;
		}
		if ($line =~ /^Target:[[:space:]]+(.+)/i) {
			$target = $1;
			$continuation_field = "target";
			next;
		}
		if ($line =~ /(?:Code[[:space:]]+)?Location(?:s)?(?:[[:space:]]+[0-9]+)?[[:space:]]*:[[:space:]]*(.+?:[0-9]+(?:-[0-9]+)?)/i) {
			$location ||= $1;
			next;
		}
		END {
			finish_window();
		}
	' "$source_file"
}

emit_known_missing_string_finding() {
	local evidence_file="$1"
	local needle="$2"
	local title="$3"
	local preferred_path
	local match=""
	local path=""
	local line=""

	if ! grep -Fq -- "$needle" "$evidence_file"; then
		return 0
	fi

	shift 3
	for preferred_path in "$@"; do
		if [ -f "${REPO_ROOT%/}/$preferred_path" ]; then
			match="$(grep -nF -- "$needle" "${REPO_ROOT%/}/$preferred_path" | head -n 1 || true)"
			if [ -n "$match" ]; then
				path="$preferred_path"
				line="${match%%:*}"
				break
			fi
		fi
	done

	finding_index=$((finding_index + 1))
	if [ -n "$path" ] && [ -n "$line" ]; then
		printf '### %s. HIGH %s:%s - %s\n' "$finding_index" "$path" "$line" "$title"
		printf -- '- Problem: Strix failed because the trusted self-test log reported missing "%s".\n' "$needle"
		printf -- '- Root cause: The failed check is executing trusted-base workflow material, so this exact line must exist in the trusted workflow/test contract before the check can pass.\n'
		printf -- '- Fix: Keep or add the current-head line at "%s:%s" so trusted-base Strix/OpenCode evidence contains "%s".\n' "$path" "$line" "$needle"
		printf -- '- Regression test: Keep scripts/ci/test_strix_quick_gate.sh assertions covering this exact string.\n\n'
	else
		printf '### %s. HIGH unknown:1 - %s\n' "$finding_index" "$title"
		printf -- '- Problem: Strix failed because the trusted self-test log reported missing "%s".\n' "$needle"
		printf -- '- Root cause: No current-head line containing this exact string was found in the expected workflow/test files.\n'
		printf -- '- Fix: Add the exact string "%s" to the relevant workflow or test contract line.\n' "$needle"
		printf -- '- Regression test: Add a static assertion for this exact string.\n\n'
	fi
}

emit_strix_report_findings() {
	local strix_evidence_file="$1"
	local reports_file
	local model
	local title
	local severity
	local endpoint
	local method
	local target
	local location
	local mapped
	local path
	local line
	local source_detail

	if ! has_strix_vulnerability_report_window "$strix_evidence_file"; then
		return 0
	fi

	reports_file="$(mktemp)"
	tmp_files+=("$reports_file")
	extract_strix_reports "$strix_evidence_file" >"$reports_file"

	while IFS=$'\037' read -r model title severity endpoint method target location; do
		if [ -z "$title" ] || [ "$severity" = "NONE" ]; then
			continue
		fi
		mapped="$(derive_location_from_report "$title" "$endpoint" "$target" "$location")"
		IFS=$'\t' read -r path line source_detail <<<"$mapped"
		if [ "$path" = "unknown" ]; then
			path=".github/workflows/strix.yml"
			line="$(first_existing_line "$path" 'STRIX_FAIL_ON_MIN_SEVERITY|STRIX_FALLBACK_MODELS')"
			source_detail="$source_detail; fallback anchored to Strix workflow because the report omitted a repository Code Location"
		fi

		finding_index=$((finding_index + 1))
		printf '### %s. %s %s:%s - Strix report from %s: %s\n' "$finding_index" "${severity:-HIGH}" "$path" "$line" "$model" "$title"
		printf -- '- Problem: Strix Security Scan failed and %s reported "%s" with severity %s. Endpoint: %s. Method: %s. Code location evidence: %s.\n' "$model" "$title" "${severity:-UNKNOWN}" "${endpoint:-N/A}" "${method:-N/A}" "$source_detail"
		printf -- '- Root cause: The failed Strix evidence contains a distinct model vulnerability report, so OpenCode must not collapse it into provider-quota or generic check-failure text.\n'
		printf -- '- Fix: Inspect and patch %s:%s for this exact report before approval; apply the remediation described by Strix for "%s" and keep the review finding tied to this line.\n' "$path" "$line" "$title"
		printf -- '- Regression test: Add or update coverage that exercises the reported endpoint/path and proves the %s finding cannot recur.\n\n' "${severity:-Strix}"
	done <"$reports_file"
}

emit_strix_provider_failure_finding() {
	local strix_evidence_file="$1"
	local match=""
	local path=".github/workflows/strix.yml"
	local line="1"

	if ! grep -Eq "LLM CONNECTION FAILED|RateLimitError|Too many requests|budget limit|Configured model and fallback models were unavailable|provider infrastructure|Below-threshold findings detected|Unable to map Strix findings" "$strix_evidence_file"; then
		return 0
	fi

	if [ -f "${REPO_ROOT%/}/$path" ]; then
		match="$(grep -nE -- "^[[:space:]]*STRIX_FALLBACK_MODELS:" "${REPO_ROOT%/}/$path" | head -n 1 || true)"
		if [ -n "$match" ]; then
			line="${match%%:*}"
		fi
	fi

	finding_index=$((finding_index + 1))
	if has_strix_vulnerability_report_window "$strix_evidence_file"; then
		printf '### %s. HIGH %s:%s - Strix provider signal left current-head security evidence incomplete\n' "$finding_index" "$path" "$line"
		printf -- '- Problem: Strix produced one or more vulnerability report windows, then the failed log still reported provider infrastructure/failure-signal output such as LLM CONNECTION FAILED, RateLimitError, budget-limit, "Below-threshold findings detected", "Unable to map Strix findings", or fallback provider signal.\n'
		printf -- '- Root cause: The scanner evidence is incomplete even after model reports were emitted; OpenCode must include every model report above and must not approve until a clean current-head Strix run or equivalent manual evidence exists.\n'
		printf -- '- Fix: Re-run Strix after GitHub Models capacity recovers or run an explicitly configured manual provider evidence scan with valid credentials; keep %s:%s aligned with the approved fallback model list.\n' "$path" "$line"
		printf -- '- Regression test: Keep failed-check evidence and validation covering provider-signal failures after vulnerability reports so partial reports cannot be downgraded to approval.\n\n'
	else
		printf '### %s. HIGH %s:%s - Strix provider access blocked current-head security evidence\n' "$finding_index" "$path" "$line"
		printf -- '- Problem: Strix failed before producing vulnerability reports. The failed log reported provider setup or access failure such as LLM CONNECTION FAILED, no_access, RateLimitError, Too many requests, budget-limit output, or unavailable configured fallback models.\n'
		printf -- '- Root cause: The configured provider credentials, model access, capacity, or budget could not produce Strix evidence for this run; no Strix Vulnerability Report window was produced, so there is no application source line to patch from this evidence.\n'
		printf -- '- Fix: Do not approve from this failed scan. Re-run Strix after GitHub Models quota recovers or run an explicitly configured manual provider evidence scan with valid credentials; keep the configured fallback line at %s:%s aligned with the approved model list.\n' "$path" "$line"
		printf -- '- Regression test: Keep the failed-check evidence collector preserving RateLimitError, budget-limit, provider infrastructure, and unavailable-model lines so OpenCode reviews can distinguish external provider blockers from code vulnerabilities.\n\n'
	fi
}

emit_strix_cancelled_without_log_finding() {
	local strix_evidence_file="$1"
	local match=""
	local path=".github/workflows/strix.yml"
	local line="1"

	if ! grep -Fq "Conclusion:" "$strix_evidence_file" ||
		! grep -Fq "cancelled" "$strix_evidence_file" ||
		! grep -Fq "No GitHub Actions job log is available for this failed workflow run." "$strix_evidence_file"; then
		return 0
	fi

	if [ -f "${REPO_ROOT%/}/$path" ]; then
		match="$(grep -nF -- "cancel-in-progress: false" "${REPO_ROOT%/}/$path" | head -n 1 || true)"
		if [ -n "$match" ]; then
			line="${match%%:*}"
		fi
	fi

	finding_index=$((finding_index + 1))
	printf '### %s. HIGH %s:%s - Current-head Strix evidence is missing because the workflow run was cancelled before logs\n' "$finding_index" "$path" "$line"
	printf -- '- Problem: Strix Security Scan reported a current-head workflow_run conclusion of cancelled, but GitHub emitted no failed job log and no Strix Vulnerability Report window.\n'
	printf -- '- Root cause: The security gate has no usable Strix evidence for this head SHA. This is a workflow execution/queue state, not an application vulnerability finding, so OpenCode must not invent a source-code fix.\n'
	printf -- '- Fix: Do not approve from this cancelled run. Re-run the current-head Strix Security Scan after stale runs complete or are cancelled, then review the resulting job log; keep the workflow concurrency line at %s:%s so stale runs do not silently replace current-head evidence.\n' "$path" "$line"
	printf -- '- Regression test: Keep failed-check evidence collection explicit for cancelled workflow runs with no job log so reviewers see that the blocker is missing scanner evidence.\n\n'
}

strix_evidence_file="$(mktemp)"
tmp_files+=("$strix_evidence_file")
extract_strix_failed_check_block "$EVIDENCE_FILE" "$strix_evidence_file"

emit_known_missing_string_finding \
	"$EVIDENCE_FILE" \
	"github.event.inputs.strix_llm || 'openai/gpt-5'" \
	"Strix PR scans must default to GitHub Models GPT-5" \
	".github/workflows/strix.yml" \
	"scripts/ci/test_strix_quick_gate.sh"
emit_known_missing_string_finding \
	"$EVIDENCE_FILE" \
	"STRIX_LLM must select GitHub Models openai/gpt-5 or newer, direct OpenAI GPT-5.4 or newer, or an approved organization Vertex AI model" \
	"Strix unsupported-model errors must name the allowed providers" \
	".github/workflows/strix.yml" \
	"scripts/ci/test_strix_quick_gate.sh"
emit_known_missing_string_finding \
	"$EVIDENCE_FILE" \
	"MODEL: github-models/openai/gpt-5" \
	"OpenCode review must try GitHub Models GPT-5 first" \
	".github/workflows/opencode-review.yml" \
	"scripts/ci/test_strix_quick_gate.sh"

emit_strix_report_findings "$strix_evidence_file"
emit_strix_provider_failure_finding "$strix_evidence_file"
emit_strix_cancelled_without_log_finding "$strix_evidence_file"

if [ "$finding_index" -eq 0 ]; then
	printf 'No deterministic missing-string markers or Strix report locations were recognized. Use the failed-check evidence below to map each failed check to exact local source lines before approving.\n\n'
fi
