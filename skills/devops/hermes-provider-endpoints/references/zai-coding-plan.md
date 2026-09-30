# Z.AI GLM Coding Plan — endpoint quirks (verified 2026-09-24)

Session-specific detail for the Z.AI GLM Coding Plan on Hermes
(`hermes-provider-endpoints` umbrella).

## Key facts

- Standard OpenAI-compatible endpoint: `https://api.z.ai/api/paas/v4`
- **Coding-plan endpoint: `https://api.z.ai/api/coding/paas/v4`** — keys
  tied to a GLM Coding Plan ONLY work here.
- On the standard endpoint a coding-plan key returns:
  `{"error":{"code":"1113","message":"Insufficient balance or no resource package. Please recharge."}}`
  This is an endpoint-mismatch error, not a billing problem — do not send
  the user to recharge.
- The coding endpoint also exposes an Anthropic-style API at
  `https://api.z.ai/api/anthropic/v1` (useful for Claude Code-style tools;
  returns `thinking` blocks).
- `glm-5.3-flash` is a reasoning model: with small `max_tokens` the whole
  budget goes to `reasoning_content` and `content` comes back empty
  (`finish_reason: length`). Allow generous max_tokens when probing with
  curl.
- Docs: https://docs.z.ai/guides/overview/quick-start

## Verified working config (Hermes, 2026-09-24)

```yaml
model:
  default: glm-5.3-flash
  provider: openai
  base_url: https://api.z.ai/api/coding/paas/v4
providers:
  openai:
    base_url: https://api.z.ai/api/coding/paas/v4
    api_key: <key>            # stored via hermes config set
    api_mode: chat_completions
auxiliary:
  compression:
    provider: custom
    model: glm-5.3-flash
    base_url: https://api.z.ai/api/coding/paas/v4
    api_key: <key>
```

## Commands used

```bash
# Key test on the coding endpoint (standard one fails with 1113)
curl -sS -m 60 -X POST "https://api.z.ai/api/coding/paas/v4/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $KEY" \
  -d '{"model":"glm-5.3-flash","messages":[{"role":"user","content":"Say OK"}],"max_tokens":512}'

# Config switch (main model + aux compression)
hermes config set model.default glm-5.3-flash
hermes config set model.base_url https://api.z.ai/api/coding/paas/v4
hermes config set providers.openai.base_url https://api.z.ai/api/coding/paas/v4
hermes config set providers.openai.api_key <KEY>
hermes config set auxiliary.compression.provider custom
hermes config set auxiliary.compression.model glm-5.3-flash
hermes config set auxiliary.compression.base_url https://api.z.ai/api/coding/paas/v4
hermes config set auxiliary.compression.api_key <KEY>

# Verify (twice is nice; watch content, not just exit code)
hermes chat -q "What is 2+2? Answer with just the number."
```

## Migration context

Replaced prior routing `glm-5.3-flash:cloud` via `https://ollama.com/v1`
(provider: openai). The old ollama key was left in config history for easy
revert but is unused. Gateway restart was requested per user-approval rule
and pending at session end.