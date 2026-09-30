---
name: hermes-provider-endpoints
description: "Switch Hermes Agent to a new LLM provider or custom OpenAI-compatible endpoint: key verification, config keys to set, aux-model pinning, and verification steps. Covers coding-plan keys with dedicated endpoints (Z.AI GLM etc.)."
version: 1.0.0
author: the user/the agent ops
license: MIT
platforms: [linux, macos, windows]
---

# Hermes Provider / Endpoint Switching

Class-level procedure for pointing Hermes at a new LLM provider or a
dedicated endpoint (API key the user provides in chat, coding-plan keys,
custom base URLs). Complements the bundled `hermes-agent` skill (protected;
its Providers table lists env vars but not this switching workflow).

## Trigger
- User provides an API key and says "use this provider/model"
- Model/provider migration (e.g. ollama-cloud → vendor direct)
- Aux tasks (compression, vision) falling back to the wrong provider

## Workflow

1. **Verify the key BEFORE editing config.** Raw curl both the standard
   endpoint and any dedicated/coding endpoint. Many "my key doesn't work"
   cases are endpoint mismatch, not a bad key (see references/zai-coding-plan.md).
2. **Identify which config keys matter.** For the main model:
   `model.default`, `model.provider`, `model.base_url`,
   `providers.<name>.base_url`, `providers.<name>.api_key`.
3. **Pin aux tasks that must follow the same provider** — especially
   `auxiliary.compression.*`. If left on `provider: auto` or pointing at a
   stale endpoint, compression silently uses an old key/endpoint or fails
   with confusing credit errors. Set `provider: custom`, explicit
   `base_url` + `model` + `api_key`, and clear any stale `key_env`.
4. **Set values with `hermes config set KEY VAL`**, never by hand-editing
   YAML. Chained `&&` in one terminal call keeps it atomic-ish.
5. **Verify with a real call:** `hermes chat -q "What is 2+2? Answer with just the number."`
   Confirm both content and that the session header shows the new model.
   A successful curl is NOT enough — the OpenAI-compat layer inside Hermes
   can differ (api_mode, streaming, reasoning fields).
6. **Gateway sessions need restart to pick up config.** Restart requires
   explicit user approval — never run `hermes gateway restart` unprompted.
   Tell the user the change is verified and ask.

## Pitfalls

- **Coding-plan / subscription keys are NOT standard API keys.** They are
  scoped to a dedicated endpoint path and return "insufficient balance" on
  the standard one. Always check the vendor's coding-plan docs for a
  dedicated base URL.
- **`provider: openai` is a rewrite trap for aux tasks**: in `auxiliary.*`
  sections, bare `openai` rewrites to api.openai.com and does NOT inherit
  your `providers.openai` base_url override. Use `provider: custom` +
  explicit base_url for aux tasks.
- **API keys pasted in chat**: store them in config.yaml/.env via
  `hermes config set` (values are redacted in output), and advise rotation
  if the user pasted them on a platform like Discord.
- **Leave the old provider key in place** if cheap: reverting is a one-line
  config change, useful when the new provider has balance/quota issues.
- After config changes, CLI sessions pick up on next launch; gateway needs
  the approved restart.

## Verification checklist

- [ ] curl works on the correct endpoint (right path!)
- [ ] `hermes chat -q` returns a correct answer
- [ ] `auxiliary.compression` points at the same endpoint
- [ ] gateway restart approved and done (or user informed it's pending)