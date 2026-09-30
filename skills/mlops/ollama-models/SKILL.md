---
name: ollama-models
description: "Discovering and choosing models on ollama.com — catalog navigation via URL patterns, capability tags (image/vision/tools/thinking/cloud), cloud vs local model semantics, and the current image-generation catalog. Use when asked 'what is the best X model on Ollama' or for any ollama.com model research."
tags: [ollama, model-discovery, image-generation, catalog]
---

# Ollama Model Catalog & Discovery

How to find and pick models on ollama.com without guessing. The catalog changes monthly — verify against the live site, use the URL patterns below, and never quote model specs from memory when a model page is one fetch away.

## Catalog navigation (URL patterns work; avoid click-walking)

- Category listing: `https://ollama.com/search?c=<category>` — categories include `tools`, `vision`, `image`, `embedding`, `thinking`
- Category + text query: `https://ollama.com/search?c=<category>&q=<query>`
- Model detail: `https://ollama.com/<namespace>/<model>` — README has features, usage, quant table
- Tags/variants: `https://ollama.com/<namespace>/<model>/tags` — the authoritative list of sizes and quants (fp4/fp8/bf16, parameter sizes)
- Blog announcements: `https://ollama.com/blog/<topic>` (e.g. `/blog/image-generation`)

On-page filter quirks (observed Sept 2026):
- The "Cloud" checkbox on the search page did not visibly filter results during a live audit — URL params and the `/tags` pages were more reliable.
- Text-search fallback that works: type into the search box, press Enter.
- Sort options: Popular (default) / Newest.

## Cloud vs local — get the semantics right before answering

- Ollama's **cloud** tag covers text LLMs only (gpt-oss, glm, minimax, deepseek, kimi...). Cloud models are called via `https://ollama.com/v1/chat/completions` with Bearer auth — see the `ollama-cloud-scripts` skill for the API pattern (bare model names, no `:cloud` suffix on the hosted API).
- **Image generation models are local-run**, not cloud. When a user asks for "cloud hosted image models on Ollama", the honest answer is that the image models run locally — clarify rather than inventing a cloud image model.
- Community mirrors of popular models exist (e.g. `jmorgan/z-image-turbo` duplicating `x/z-image-turbo`). Prefer the first-party `x/` namespace or high-pull originals; skip low-pull mirrors.

## Image generation catalog (audited Sept 2026 — re-verify before quoting)

Ollama added experimental image generation (blog: Jan 2026). Catalog is tiny — verify current state at `https://ollama.com/search?c=image`:

| Model | Params | Strength | License |
|---|---|---|---|
| `x/z-image-turbo` | 6B | Best overall quality, photorealism, EN+CN text rendering | Apache 2.0 (fp8 13GB default, bf16 33GB) |
| `x/flux2-klein` | 4B / 9B | Clean legible typography — signage, UI mockups | 4B Apache 2.0; 9B non-commercial |

Decision rule: best quality → `x/z-image-turbo` (fp8); text-in-image/UI mockups → `x/flux2-klein:9b`; fastest → `x/flux2-klein:4b`.

Platform caveat: the launch READMEs said macOS-only with Windows/Linux "coming soon". **Do not harden this** — check the model page or blog before telling a user image gen won't run on their OS. On Linux, the workaround is ComfyUI/Forge running Z-Image or FLUX weights directly (see `comfyui` skill).

Usage: `ollama run x/z-image-turbo "prompt"`. Controls: `/set width|height`, negative prompts, seed for reproducibility; step counts auto-default per model. Images save to cwd.

## Workflow

1. Identify the capability class the user wants (chat / vision / tools / image / embedding).
2. Fetch the category URL, not a guessed model name.
3. Open `/tags` for any shortlisted model to confirm sizes, quants, and update recency.
4. Check pull counts to distinguish first-party from mirrors.
5. Cross-check the launch blog for platform/support caveats before quoting them.

## Related skills

| Skill | Role |
|---|---|
| `ollama-cloud-scripts` | Calling Ollama cloud models from scripts (/v1/chat/completions, Bearer auth) |
| `comfyui` | Local image/video generation pipeline when Ollama image gen doesn't cover the need |
| `hindsight-integration` | Local Ollama daemon operation for Hindsight |