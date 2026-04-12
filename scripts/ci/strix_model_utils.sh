#!/usr/bin/env bash

trim_whitespace() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  echo "$value"
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
  # Validate Vertex AI resource path formats with strict segment-boundary
  # enforcement. We split on '/' using `read -ra` (shellcheck-safe) to reject
  # malformed paths like "projects/a/b/locations/…".
  local path="$1"
  [[ -z "$path" || "$path" =~ [[:space:]] ]] && return 1

  local -a parts
  IFS='/' read -ra parts <<<"$path"

  local n=${#parts[@]}
  case "$n" in
    2) # models/<id>
      [[ "${parts[0]}" == "models" && -n "${parts[1]}" ]]
      return $?
      ;;
    4) # publishers/<p>/models/<id>
      [[ "${parts[0]}" == "publishers" && -n "${parts[1]}" && "${parts[2]}" == "models" && -n "${parts[3]}" ]]
      return $?
      ;;
    6) # projects/<p>/locations/<l>/models/<id>
      [[ "${parts[0]}" == "projects" && -n "${parts[1]}" && "${parts[2]}" == "locations" && -n "${parts[3]}" && "${parts[4]}" == "models" && -n "${parts[5]}" ]]
      return $?
      ;;
    8) # projects/<p>/locations/<l>/publishers/<pub>/models/<id>
      [[ "${parts[0]}" == "projects" && -n "${parts[1]}" && "${parts[2]}" == "locations" && -n "${parts[3]}" && "${parts[4]}" == "publishers" && -n "${parts[5]}" && "${parts[6]}" == "models" && -n "${parts[7]}" ]]
      return $?
      ;;
    *)
      return 1
      ;;
  esac
}

extract_vertex_model_id() {
  local raw_model="$1"
  [[ "$raw_model" =~ [[:space:]] ]] && {
    echo "$raw_model"
    return 0
  }

  local -a parts
  IFS='/' read -ra parts <<<"$raw_model"

  local n=${#parts[@]}
  case "$n" in
    8) # projects/<p>/locations/<l>/publishers/<pub>/models/<id>
      if [[ "${parts[0]}" == "projects" && "${parts[2]}" == "locations" && "${parts[4]}" == "publishers" && "${parts[6]}" == "models" ]]; then
        echo "${parts[7]}"
        return 0
      fi
      ;;
    6) # projects/<p>/locations/<l>/models/<id>
      if [[ "${parts[0]}" == "projects" && "${parts[2]}" == "locations" && "${parts[4]}" == "models" ]]; then
        echo "${parts[5]}"
        return 0
      fi
      ;;
    4) # publishers/<pub>/models/<id>
      if [[ "${parts[0]}" == "publishers" && "${parts[2]}" == "models" ]]; then
        echo "${parts[3]}"
        return 0
      fi
      ;;
    2) # models/<id>
      if [[ "${parts[0]}" == "models" ]]; then
        echo "${parts[1]}"
        return 0
      fi
      ;;
  esac

  echo "$raw_model"
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

  local provider="${DEFAULT_PROVIDER:-${STRIX_LLM_DEFAULT_PROVIDER:-}}"
  provider="${provider%/}"

  if is_vertex_resource_path "$raw_model"; then
    local vertex_provider="$provider"
    if [ "$vertex_provider" != "vertex_ai" ] && [ "$vertex_provider" != "vertex_ai_beta" ]; then
      vertex_provider="vertex_ai"
    fi

    echo "$vertex_provider/$(extract_vertex_model_id "$raw_model")"
    return 0
  fi

  if [ -z "$provider" ]; then
    echo "$raw_model"
    return 0
  fi

  local normalized_model="$raw_model"
  if [ "$provider" = "vertex_ai" ] || [ "$provider" = "vertex_ai_beta" ]; then
    normalized_model="$(extract_vertex_model_id "$raw_model")"
  fi

  echo "$provider/$normalized_model"
}
