---
name: ollama-cloud-scripts
description: How to call Ollama cloud models from custom Node.js scripts — use /v1/chat/completions with Bearer auth instead of /api/generate
tags: [ollama, cloud, api, nodejs, scripts]
---

# Ollama Cloud Model API from Scripts

## The Problem

Custom scripts calling Ollama via `POST /api/generate` (using `prompt`/`num_predict` format) silently fail with cloud models (`deepseek-v4-flash:cloud`, `minimax-m2.7:cloud`, etc.) because:

1. Cloud models use the OpenAI-compatible `/v1/chat/completions` endpoint, not `/api/generate`
2. Cloud models need Bearer token authentication
3. Request format uses `messages` array (not `prompt`)
4. `max_tokens` replaces `num_predict`

## The Fix — Replace Your queryLLM Function

```javascript
const http = require('http');
const { URL } = require('url');

const OLLAMA_URL = process.env.OLLAMA_URL || 'http://127.0.0.1:11434';

// Read API key — set env OLLAMA_API_KEY or let script read from config
async function queryLLM(prompt, model = 'glm-5.3-flash:cloud') {   // current sanctioned model 2026-09-20
  const apiKey = process.env.OLLAMA_API_KEY;
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({
      model,
      messages: [{ role: 'user', content: prompt }],
      stream: false,
      options: { temperature: 0.3, max_tokens: 500 }
    });
    const opts = {
      hostname: '127.0.0.1', port: 11434,
      path: '/v1/chat/completions', method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': apiKey ? `Bearer ${apiKey}` : '',
        'Content-Length': Buffer.byteLength(data)
      },
      timeout: 60000
    };
    const req = http.request(opts, (res) => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => {
        try {
          const parsed = JSON.parse(body);
          resolve(parsed.choices?.[0]?.message?.content?.trim() || '');
        } catch (e) {
          reject(new Error(`Parse failed`));
        }
      });
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.write(data);
    req.end();
  });
}
```

## Key Changes from `/api/generate`

| Aspect | `/api/generate` (old) | `/v1/chat/completions` (new) |
|--------|----------------------|------------------------------|
| Endpoint path | `/api/generate` | `/v1/chat/completions` |
| Body format | `model` + `prompt` + stream | `model` + `messages[]` + stream |
| Tokens param | `options.num_predict` | `options.max_tokens` |
| Auth header | None | `Authorization: Bearer <key>` |
| Response field | `response` or `thinking` | `choices[0].message.content` |

## Which models need this?

All models with `:cloud` suffix: `deepseek-v4-flash:cloud`, `deepseek-v4-pro:cloud`, `minimax-m2.7:cloud`, `glm-5.1:cloud`, `gemma3:12b-cloud`, `kimi-k2.6:cloud`.

Local models (no `:cloud` suffix) still work with the old `/api/generate` endpoint.

## Python Pattern — Unified Provider (Anthropic + Ollama)

For Python projects that need to support both Anthropic Claude and Ollama cloud models, use a provider abstraction that routes based on model name. Built for a document parser service (2026-07-07):

```python
import json, os, urllib.request, base64

def is_claude_model(model: str) -> bool:
    return model.startswith("claude-")

def call_llm_text(model, system_prompt, messages, max_tokens=8000, temperature=0.0):
    """Route to Anthropic SDK or Ollama OpenAI-compatible API based on model name."""
    if is_claude_model(model):
        return _call_anthropic_text(model, system_prompt, messages, max_tokens, temperature)
    return _call_ollama_text(model, system_prompt, messages, max_tokens, temperature)

def _call_ollama_text(model, system_prompt, messages, max_tokens, temperature):
    """Ollama cloud via /v1/chat/completions."""
    api_key = os.environ["OLLAMA_API_KEY"]
    base_url = os.environ.get("OLLAMA_BASE_URL", "https://ollama.com/v1")
    full_messages = [{"role": "system", "content": system_prompt}] + messages
    body = json.dumps({"model": model, "messages": full_messages,
                       "max_tokens": max_tokens, "temperature": temperature,
                       "stream": False}).encode("utf-8")
    req = urllib.request.Request(f"{base_url}/chat/completions", data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return text, {"input": usage.get("prompt_tokens", 0), "output": usage.get("completion_tokens", 0)}
```

### Vision (image) calls with Ollama

Ollama cloud supports vision via the OpenAI `image_url` content type with base64 data URIs:

```python
def _call_ollama_vision(model, image_data, mime_type, text_prompt, max_tokens=4096):
    image_b64 = base64.standard_b64encode(image_data).decode("utf-8")
    data_uri = f"data:{mime_type};base64,{image_b64}"
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": data_uri}},
        {"type": "text", "text": text_prompt},
    ]}], "max_tokens": max_tokens, "stream": False}).encode("utf-8")
    # ... same urllib.request pattern as _call_ollama_text
```

### Key env vars
- `OLLAMA_API_KEY` — required for Ollama cloud (find in Hermes config under `custom_providers[name=ollama].api_key`)
- `OLLAMA_BASE_URL` — defaults to `https://ollama.com/v1`
- `ANTHROPIC_API_KEY` — required for Claude models

### Model name format
- Ollama cloud uses bare model names: `glm-5.2`, `gemma4:31b`, `minimax-m3`, `kimi-k2.6` — NOT `:cloud` suffix
- Claude models: `claude-sonnet-4-6`, `claude-opus-4-6`, etc.

## Debugging

If a script calling an LLM produces empty results:
1. Set `OLLAMA_API_KEY` env var with the key from config
2. The response format for cloud models is `choices[0].message.content`
3. Check that the endpoint path ends with `/v1/chat/completions` (not `/api/generate`)
