# LLM via Contextual Orchestrator

pg-erd-cloud's LLM features (`reversing-spec.md?mode=llm-draft`,
`index-design.md?mode=llm-draft`) call an **OpenAI-compatible** chat-completions
endpoint (`app/spec/llm.py`: `POST {base}/chat/completions`, `Authorization:
Bearer`, `{model, messages}`). [contextual-orchestrator](https://github.com/ContextualWisdomLab/contextual-orchestrator)
exposes exactly that interface (`/v1/chat/completions`) while routing,
delegating, verifying, and synthesizing across a pool of model agents.

So the integration is **configuration only — no code change**.

## Point pg-erd-cloud at the orchestrator

```bash
LLM_API_BASE_URL=https://<orchestrator-host>/v1
LLM_API_KEY=<orchestrator inference bearer token>   # NOT the OpenAI key
LLM_MODEL=contextual-orchestrator
```

pg-erd-cloud calls `${LLM_API_BASE_URL}/chat/completions` → the orchestrator's
`/v1/chat/completions`. The orchestrator authenticates the Bearer token,
orchestrates, and returns an OpenAI-shaped response.

## Secret isolation (why this is better than calling OpenAI directly)

The real **OpenAI API key lives only in the orchestrator's agent pool**, backed
by the org Secret — pg-erd-cloud never holds it. pg-erd holds only the
orchestrator's inference token.

Orchestrator agent config (on the orchestrator side, env-backed key):

```json
{
  "agents": [
    {
      "id": "coding_agent",
      "endpoint": "https://api.openai.com/v1",
      "api_key_env": "OPENAI_API_KEY",
      "model": "gpt-4o"
    }
  ]
}
```

Run: `python -m contextual_orchestrator --serve --agents agents.json \
--inference-token "$CONTEXTUAL_ORCHESTRATOR_TOKEN" --port 8000` with
`OPENAI_API_KEY` supplied from the org Secret at deploy time.

## Fallback

Unset `LLM_API_*` → the LLM-draft endpoints raise `LlmConfigurationError`
(503); the non-LLM `mode=markdown|llm-prompt` paths are unaffected. The
integration is fully opt-in.
