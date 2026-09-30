---
name: mlops-training
description: "LLM fine-tuning and post-training — axolotl (YAML configs), TRL (SFT/DPO/PPO/GRPO), unsloth (fast LoRA). Covers the full RLHF pipeline, preference alignment, and memory-efficient training."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [fine-tuning, post-training, rlhf, lora, qlora, dpo, grpo, sft, ppo, axolotl, trl, unsloth]
    related_skills: [mlops-inference, huggingface-hub]
---

# LLM Fine-Tuning & Post-Training

A unified skill for training and aligning large language models — from supervised fine-tuning to full RLHF preference alignment.

## Tool Map

| Tool | Best for | Approach | Key advantage |
|------|----------|----------|---------------|
| **unsloth** | Fast LoRA/QLoRA on consumer GPUs | Python API | 2-5x faster, 50% less VRAM |
| **axolotl** | Complex multi-GPU training | YAML configs | 100+ model support, DeepSpeed, multimodal |
| **TRL** | Post-training / RLHF pipeline | Python API | SFT/DPO/PPO/GRPO, full alignment suite |

## Quick Decision Guide

```
Want the fastest LoRA training on limited VRAM?     → unsloth
Need YAML-based training with many model support?   → axolotl
Doing RLHF or preference alignment (DPO/PPO/GRPO)? → TRL (trl-fine-tuning)
Need multimodal fine-tuning?                        → axolotl
Running on multiple GPUs with DeepSpeed?            → axolotl
Quick single-GPU instruction tuning?                → unsloth
```

---

## unsloth — Fast LoRA / QLoRA

> **Skill:** `unsloth`
> **Speed:** 2-5x faster than naive LoRA, 50% less VRAM
> **Models:** Llama, Mistral, Gemma, Qwen, and more

Best for single-GPU instruction tuning when speed and memory efficiency are paramount.

**Installation:**
```bash
pip install unsloth unsloth[ampere]  # Ampere+ GPUs (A100, RTX 3090+)
# Or for older GPUs:
pip install unsloth unsloth[turing]  # Turing (RTX 2000 series)
```

**Basic LoRA training:**
```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/Llama-3.2-3B-Instruct",
    max_seq_length=2048,
    load_in_4bit=True,  # QLoRA — 4-bit quantization
)

# Add LoRA adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=16,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    lora_alpha=16,
    bias="none",
)

# Train
from trl import SFTTrainer
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    args=...,
    processing_class=tokenizer,
)
trainer.train()
```

**Why unsloth:** If training takes 10 hours on naive LoRA, unsloth finishes in 2-5 hours on the same hardware.

---

## axolotl — YAML-Based Multi-GPU Training

> **Skill:** `axolotl`
> **Approach:** YAML configuration files
> **Key advantage:** 100+ models, DeepSpeed, FSDP, multimodal, all training methods

Best for complex training setups requiring multi-GPU coordination, DeepSpeed, or multimodal models.

**Installation:**
```bash
pip install axolotl
```

**YAML config example (LoRA):**
```yaml
base_model: meta-llama/Llama-3.2-3B-Instruct
model_type: LlamaForCausalLM

load_in_4bit: true
quantization:bnb

training_steps: 1000
batch_size: 2
gradient_accumulation_steps: 4
optim: adamw_torch

loRA:
  r: 16
  lora_alpha: 16
  target_modules: q_proj k_proj v_proj o_proj
```

**Run training:**
```bash
axolotl train config.yml
```

**Key features:**
- **DeepSpeed FSDP** — multi-GPU training with model parallelism
- **Multimodal** — vision-language models (LLaVA, etc.)
- **All methods** — LoRA, QLoRA, DPO, GRPO, KTO, ORPO
- **100+ model configs** — pre-built YAML templates for popular models

---

## TRL — Post-Training & RLHF

> **Skill:** `fine-tuning-with-trl`
> **Approach:** Python API
> **Key advantage:** Complete RLHF pipeline (SFT → Reward Model → PPO), DPO/GRPO preference alignment

Best for full RLHF pipelines and preference-based alignment methods.

**Installation:**
```bash
pip install trl transformers datasets peft accelerate
```

### The Full RLHF Pipeline

```
SFT (Supervised Fine-Tuning)
    ↓
Reward Model Training
    ↓
PPO / GRPO Reinforcement Learning
    ↓
Aligned Model
```

**Step 1 — SFT (instruction tuning):**
```python
from trl import SFTTrainer, SFTConfig

trainer = SFTTrainer(
    model="Qwen/Qwen2.5-0.5B",
    train_dataset=dataset,  # prompt-completion pairs
)
trainer.train()
```

**Step 2 — Reward Model:**
```python
from trl import RewardTrainer, RewardConfig

model = AutoModelForSequenceClassification.from_pretrained(
    "Qwen2.5-0.5B-SFT", num_labels=1
)
trainer = RewardTrainer(
    model=model,
    train_dataset=preference_dataset,  # chosen/rejected pairs
)
trainer.train()
```

**Step 3 — PPO or GRPO:**
```bash
# PPO
trl ppo --model_name_or_path Qwen2.5-0.5B-SFT --reward_model_path Qwen2.5-0.5B-Reward

# GRPO (more memory-efficient)
trl grpo --model_name_or_path Qwen/Qwen2-0.5B-Instruct --dataset_name trl-lib/tldr
```

### Quick Preference Alignment (DPO)

When you have preference data but don't want the full RLHF pipeline:

```python
from trl import DPOTrainer, DPOConfig

config = DPOConfig(output_dir="model-dpo", beta=0.1)
trainer = DPOTrainer(
    model=model,
    train_dataset=preference_dataset,  # {prompt, chosen, rejected}
)
trainer.train()
```

---

## Training Method Selection

| Method | When to use | What you need |
|--------|-------------|---------------|
| **SFT** | Basic instruction following | Prompt-completion pairs |
| **DPO** | Preference alignment (simpler than RLHF) | Chosen/rejected pairs |
| **GRPO** | Online RL with memory constraints | Reward function or model |
| **PPO** | Full RLHF with maximum control | Trained reward model |
| **Reward Model** | Scoring generations for RLHF | Preference dataset |
| **KTO/ORPO** | Alternative preference methods | Preference dataset |

---

## Hardware Requirements

| Method | Minimum VRAM | Recommended |
|--------|-------------|-------------|
| unsloth LoRA (7B) | 8GB (QLoRA) | 16GB |
| axolotl LoRA (7B) | 12GB | 24GB |
| TRL SFT (7B) | 16GB | 24GB |
| TRL DPO (7B) | 24GB | 40GB |
| TRL GRPO (7B) | 24GB | 40GB |
| axolotl multi-GPU | 4x A100 | 8x A100 |

**Memory optimization across all tools:**
- Use QLoRA (4-bit) when VRAM is limited
- Enable gradient checkpointing
- Reduce batch size, increase gradient accumulation
- Use BF16 precision on A100/H100

---

## Related Skills

| Skill | Role |
|-------|------|
| `mlops-inference` | Serving trained models (llama.cpp, vLLM) |
| `huggingface-hub` | Downloading models and datasets |