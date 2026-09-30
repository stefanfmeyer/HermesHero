---
name: hermes-compression-debugging
description: Debug why Hermes compression fires early despite high threshold config
triggers:
  - context too large compressing
  - compression threshold not respected
  - gateway hygiene compression unexpected
---

# Hermes Compression Debugging

## Symptom
`🗜️ Context too large (~116,838 tokens) — compressing (1/3)...` fires despite `compression.threshold: 0.95` in config.yaml.

## Root Cause
Hermes has **two independent compression systems** — only one reads `config.yaml`.

### 1. Agent Compressor (`run_agent.py`)
- Reads `compression.threshold` from config.yaml at line 1557
- Fires during the agent tool loop based on real API-reported `prompt_tokens`
- threshold_percent correctly set from config

### 2. Gateway Hygiene (`gateway/run.py`, lines 4102–4347)
- Fires **before the agent starts** on incoming gateway messages
- **Hardcodes `_hyg_threshold_pct = 0.85`** at line 4131
- Only reads `compression.enabled` from config — `threshold` is ignored
- Uses rough token estimate: `estimate_messages_tokens_rough()` = `(total_chars + 3) // 4`
  - **Overestimates by 30–50% on code/JSON-heavy content**
  - A real ~80k-token session may report ~116k, triggering compression early

### 3. The (1/3) Counter
`max_compression_attempts = 3` is in the API error recovery loop (run_agent.py line 9110).
The counter increments each time compression is attempted and still fails. If compression saves <10% per pass (tracked by `_ineffective_compression_count`), it backs off after 2 failures.

## Investigation Commands
```bash
# Check what context length Hermes thinks the model has
cd ~/.hermes/hermes-agent && source venv/bin/activate && python3 -c "
from agent.model_metadata import get_model_context_length
ctx = get_model_context_length('minimax-m2.7:cloud')
print(f'Context: {ctx:,}, 95% threshold: {int(ctx * 0.95):,}')
"

# Find the hardcoded hygiene threshold
grep -n "_hyg_threshold_pct = " ~/.hermes/hermes-agent/gateway/run.py

# Find where agent compressor reads config
grep -n "compression_threshold\|threshold_percent" ~/.hermes/hermes-agent/run_agent.py | head -10
```

## Fix Options

### Option A: Patch gateway hygiene to respect config threshold
In `gateway/run.py` line 4166–4170, after reading `_comp_cfg`:
```python
# Replace the hardcoded line 4131:
# _hyg_threshold_pct = 0.85
# With:
_hyg_threshold_pct = float(_comp_cfg.get("threshold", 0.85)) if isinstance(_comp_cfg, dict) else 0.85
```

### Option B: Patch rough token estimator (reduces false positives)
The `estimate_messages_tokens_rough()` overestimates on code. A better formula for code-heavy content:
```python
# chars / 4.5 or smarter: detect code vs prose
total_chars = sum(len(str(msg)) for msg in messages)
return int(total_chars / 4.5)  # if mostly code
```

## Related Code
- `~/.hermes/hermes-agent/agent/context_compressor.py` — ContextCompressor class
- `~/.hermes/hermes-agent/agent/context_engine.py` — base class, defaults `threshold_percent = 0.75`
- `~/.hermes/hermes-agent/run_agent.py` lines 1557, 1704–1710 — agent compressor init
- `~/.hermes/hermes-agent/gateway/run.py` lines 4102–4347 — gateway hygiene
- `~/.hermes/hermes-agent/agent/model_metadata.py` line 1167 — rough estimator
