---
name: mlops-inference
description: "Local LLM inference serving — CPU/edge (llama.cpp/GGUF) and production GPU (vLLM). Covers model discovery on HuggingFace, quant selection, server deployment, and optimization."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [llm, inference, serving, llama.cpp, vllm, gguf, quantization, gpu, cpu]
    related_skills: [mlops-training, huggingface-hub]
---

# LLM Inference Serving

A unified skill for running large language model inference locally — from lightweight CPU/edge inference with llama.cpp to high-throughput production GPU serving with vLLM.

## Two Paradigms

| | llama.cpp | vLLM |
|-|-----------|------|
| **Hardware** | CPU, Apple Silicon, any GPU | GPU required (24GB+) |
| **Throughput** | Low (single-user) | 24x higher than naive |
| **Use case** | Prototyping, edge, local dev | Production APIs |
| **Quantization** | GGUF (file-level) | AWQ/GPTQ/FP8 (model-level) |
| **Interface** | llama-cli, llama-server, Python bindings | OpenAI-compatible REST |
| **Setup complexity** | Low | Medium |

## Quick Decision Guide

```
Need to run on CPU or Apple Silicon?      → llama.cpp
Need 100+ req/sec production API?         → vLLM
Have a single GGUF file?                  → llama.cpp
Need tensor parallelism across GPUs?      → vLLM
Prototyping or local development?         → llama.cpp
Serving OpenAI-compatible endpoints?      → vLLM
```

---

## llama.cpp — CPU / Edge / Apple Silicon

> **Skill:** `llama-cpp`

Run local GGUF models on CPU, Apple Silicon (Metal), AMD GPUs (ROCm), Intel GPUs, or NVIDIA GPUs.

### Model Discovery Workflow

Prefer URL workflows before asking for `hf`, Python, or custom scripts:

1. Search on HuggingFace:
   ```
   https://huggingface.co/models?apps=llama.cpp&sort=trending
   ```
2. Open the repo's llama.cpp view:
   ```
   https://huggingface.co/<repo>?local-app=llama.cpp
   ```
3. The llama.cpp section shows exact quant labels and recommended commands
4. Query the tree API to confirm exact filenames:
   ```
   https://huggingface.co/api/models/<repo>/tree/main?recursive=true
   ```

### Running Models

```bash
# Direct from HuggingFace Hub
llama-cli -hf bartowski/Llama-3.2-3B-Instruct-GGUF:Q8_0
llama-server -hf bartowski/Llama-3.2-3B-Instruct-GGUF:Q8_0

# Exact file from Hub
llama-server \
    --hf-repo microsoft/Phi-3-mini-4k-instruct-gguf \
    --hf-file Phi-3-mini-4k-instruct-q4.gguf \
    -c 4096
```

### Quant Selection Heuristics

| Quant | When to use |
|-------|-------------|
| `Q8_0` | Maximum quality, needs more RAM |
| `Q6_K` | Good quality for mid-range hardware |
| `Q5_K_M` | Balanced quality/perf — good default |
| `Q4_K_M` | **Good default for most use cases** |
| `Q3_K_M` | Tight RAM budget, acceptable quality loss |
| `IQ4_NL_XL` | Better than Q4 at similar size (use exact label from HF) |
| `Q2_K` | Minimum viable — only if RAM is critically constrained |

Always prefer the exact quant label that HF shows for your hardware profile. Do not normalize repo-native labels (e.g., `UD-Q4_K_M` stays `UD-Q4_K_M`).

### Python Bindings

```python
from llama_cpp import Llama

llm = Llama(
    model_path="./model-q4_k_m.gguf",
    n_ctx=4096,
    n_gpu_layers=35,   # 0 for CPU, 99 to offload everything
    n_threads=8,
)

out = llm("What is machine learning?", max_tokens=256, temperature=0.7)
print(out["choices"][0]["text"])

# Streaming
for chunk in llm("Explain quantum computing:", stream=True):
    print(chunk["choices"][0]["text"], end="", flush=True)
```

### Resources

- SKILL.md (this skill): `llama-cpp`
- Reference files: `references/advanced-usage.md`, `references/server.md`, `references/troubleshooting.md`, `references/optimization.md`, `references/hub-discovery.md`, `references/quantization.md`
- vLLM content: `references/vllm-integration.md` (from archived `serving-llms-vllm`)

---

## vLLM — Production GPU Serving

> **Source:** `references/vllm-integration.md` (sourced from archived `serving-llms-vllm`)

High-throughput LLM serving with PagedAttention and continuous batching. OpenAI-compatible API.

### Quick Start

```bash
pip install vllm

# OpenAI-compatible server
vllm serve meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --max-model-len 8192 \
  --port 8000

# Query
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"messages": [{"role": "user", "content": "Hello!"}]}'
```

### Common Configurations

```bash
# 7B-13B on single GPU
vllm serve meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --max-model-len 8192 \
  --port 8000

# 30B-70B with tensor parallelism (4 GPUs)
vllm serve meta-llama/Llama-2-70b-hf \
  --tensor-parallel-size 4 \
  --gpu-memory-utilization 0.9 \
  --quantization awq \
  --port 8000

# Production with metrics
vllm serve meta-llama/Llama-3-8B-Instruct \
  --enable-prefix-caching \
  --enable-metrics \
  --metrics-port 9090 \
  --port 8000 \
  --host 0.0.0.0
```

### Hardware Requirements

| Model size | GPU needed |
|------------|------------|
| 7B-13B | 1x A10 (24GB) or A100 (40GB) |
| 30B-40B | 2x A100 (40GB) with tensor parallelism |
| 70B+ | 4x A100 (40GB) or 2x A100 (80GB), use AWQ/GPTQ |

### Reference Files

- `references/vllm-integration.md` — full vLLM guide (server, batch, quantization, troubleshooting)

---

## Decision: Which Serving Approach?

```python
# Pseudocode decision tree
def choose_inference_stack():
    if has_gpu and throughput_needed > 50:
        return "vLLM"  # Production API, high throughput
    elif has_gpu and want_simple_setup:
        return "llama.cpp with GPU offload"  # llama-server with n_gpu_layers
    else:
        return "llama.cpp CPU"  # Edge, Apple Silicon, CPU-only
```

## Cross-Cutting Concerns

### HuggingFace Hub Integration

Both tools pull from HuggingFace. See `huggingface-hub` skill for:
- Downloading models
- Authentication
- Repo metadata
- File listing

### Quantization

- **llama.cpp GGUF:** File-level quantization, download and run directly
- **vLLM:** Model-level quantization (AWQ/GPTQ/FP8), applied during serving

### Monitoring

```bash
# vLLM metrics
curl http://localhost:9090/metrics | grep vllm

# llama.cpp — add logging to your application
# or run the server and check its log output
```

### Docker Deployment

```bash
# vLLM
docker run --gpus all -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --enable-prefix-caching
```

## Related Skills

| Skill | Role |
|-------|------|
| `huggingface-hub` | Download, search, manage HF models and datasets |
| `mlops-training` | Fine-tuning, LoRA, DPO training |
| `llama-cpp` | Full llama.cpp reference (CPU/GPU inference) |