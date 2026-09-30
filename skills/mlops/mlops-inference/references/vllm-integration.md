# vLLM — High-Performance LLM Serving

> Sourced from `serving-llms-vllm` skill. See the parent `llama-cpp` skill for the full inference landscape.

## When to use

Use vLLM when deploying **production LLM APIs**, optimizing inference latency/throughput, or serving models with limited GPU memory. Supports OpenAI-compatible endpoints, quantization (GPTQ/AWQ/FP8), and tensor parallelism.

**vs llama.cpp:** vLLM needs a GPU (24GB+). Use llama.cpp for CPU/edge inference or single-user scenarios.

vLLM achieves **24x higher throughput** than standard transformers through:
- **PagedAttention** — block-based KV cache management
- **Continuous batching** — mixing prefill/decode requests

## Quick start

```bash
pip install vllm
```

### Offline inference

```python
from vllm import LLM, SamplingParams

llm = LLM(model="meta-llama/Llama-3-8B-Instruct")
sampling = SamplingParams(temperature=0.7, max_tokens=256)

outputs = llm.generate(["Explain quantum computing"], sampling)
print(outputs[0].outputs[0].text)
```

### OpenAI-compatible server

```bash
vllm serve meta-llama/Llama-3-8B-Instruct

# Query with OpenAI SDK
python -c "
from openai import OpenAI
client = OpenAI(base_url='http://localhost:8000/v1', api_key='EMPTY')
print(client.chat.completions.create(
    model='meta-llama/Llama-3-8B-Instruct',
    messages=[{'role': 'user', 'content': 'Hello!'}]
).choices[0].message.content)
"
```

## Common workflows

### Production API deployment

**Step 1: Configure server**

```bash
# 7B-13B models on single GPU
vllm serve meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --max-model-len 8192 \
  --port 8000

# 30B-70B models with tensor parallelism
vllm serve meta-llama/Llama-2-70b-hf \
  --tensor-parallel-size 4 \
  --gpu-memory-utilization 0.9 \
  --quantization awq \
  --port 8000

# Production with caching and metrics
vllm serve meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --enable-prefix-caching \
  --enable-metrics \
  --metrics-port 9090 \
  --port 8000 \
  --host 0.0.0.0
```

**Step 2: Test with limited traffic**

```bash
pip install locust
# Run: locust -f test_load.py --host http://localhost:8000
```

Target: TTFT < 500ms, throughput > 100 req/sec.

**Step 3: Monitor**

```bash
curl http://localhost:9090/metrics | grep vllm
```

Key metrics:
- `vllm:time_to_first_token_seconds` — latency
- `vllm:num_requests_running` — active requests
- `vllm:gpu_cache_usage_perc` — KV cache utilization

**Step 4: Deploy to production**

```bash
docker run --gpus all -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model meta-llama/Llama-3-8B-Instruct \
  --gpu-memory-utilization 0.9 \
  --enable-prefix-caching
```

### Batch offline inference

```python
from vllm import LLM, SamplingParams

llm = LLM(
    model="meta-llama/Llama-3-8B-Instruct",
    tensor_parallel_size=2,
    gpu_memory_utilization=0.9,
    max_model_len=4096
)

sampling = SamplingParams(
    temperature=0.7,
    top_p=0.95,
    max_tokens=512,
    stop=["</s>", "\n\n"]
)

prompts = [line.strip() for line in open("prompts.txt")]
outputs = llm.generate(prompts, sampling)

results = []
for output in outputs:
    results.append({
        "prompt": output.prompt,
        "generated": output.outputs[0].text,
        "tokens": len(output.outputs[0].token_ids)
    })

import json
with open("results.jsonl", "w") as f:
    for result in results:
        f.write(json.dumps(result) + "\n")
```

### Quantized model serving

```bash
# AWQ for 70B models — minimal accuracy loss
vllm serve TheBloke/Llama-2-70B-AWQ \
  --quantization awq \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.95
# 70B model fits in ~40GB VRAM
```

## Troubleshooting

| Problem | Fix |
|---------|-----|
| OOM during loading | `--gpu-memory-utilization 0.7` or use `--quantization awq` |
| Slow TTFT (>1s) | `--enable-prefix-caching`; for long prompts: `--enable-chunked-prefill` |
| Model not found | `--trust-remote-code` for custom models |
| Low throughput (<50 req/sec) | Increase `--max-num-seqs 512`; check `nvidia-smi` GPU util >80% |
| Inference slower than expected | Use power-of-2 GPU count for tensor parallelism; try `--speculative-model DRAFT_MODEL` |

## Hardware requirements

| Model size | GPU needed |
|------------|------------|
| 7B-13B | 1x A10 (24GB) or A100 (40GB) |
| 30B-40B | 2x A100 (40GB) with tensor parallelism |
| 70B+ | 4x A100 (40GB) or 2x A100 (80GB), use AWQ/GPTQ |

Supported: NVIDIA (primary), AMD ROCm, Intel GPUs, TPUs.

## Reference files

- `references/server-deployment.md` — Docker, Kubernetes, load balancing
- `references/optimization.md` — PagedAttention tuning, continuous batching, benchmarks
- `references/quantization.md` — AWQ/GPTQ/FP8 setup, model preparation, accuracy comparisons
- `references/troubleshooting.md` — detailed error messages, debugging steps

## Resources

- Docs: https://docs.vllm.ai
- GitHub: https://github.com/vllm-project/vllm
- Community: https://discuss.vllm.ai