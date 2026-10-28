# OSCAR: Local AI Plan (text/sketch -> 3D -> print, and an offline assistant model)

Status: plan written 2026-10-27. Nothing here is wired into OSCAR yet. Items marked **VERIFY** are
claims from web search or memory that have not been checked on this machine.

## Goal

1. **Make a 3D object by voice or sketch** ("Oscar, make a toy duck"), show it on the projector, then
   hand it to the Bambu A1 to print. Inspired by the hackathon project `elijahzhao24/produhacks-2026`
   (LeGenesis: sketch + prompt -> concept image -> image-to-3D -> GLB, with a `context_token` edit loop).
   That project uses paid APIs (Meshy, OpenAI). OSCAR replaces each paid step with an open model.
2. **Run the assistant brain locally** so there is no API subscription. Today `assistant/agent.py`
   calls Claude (`claude-opus-5-5`) through the Anthropic SDK. The replacement is an open-weight model
   served on the PC. Reasoning quality matters little here: the model only picks tools and phrases a
   one-sentence reply.

Everything heavy runs on the PC (RTX 5070 Ti, 16 GB VRAM, 30 GB RAM). The Pi stays the hub.

## Pipeline

```
voice/typed ──▶ assistant (local LLM, tool call: make_model)
                   │
   sketch? ──▶ concept image (open image model)         single isolated object, plain background
                   │
                   ▼
              image -> 3D (open model)  ──▶ GLB ──▶ show on projector (three.js viewer page)
                                                  └▶ trimesh -> STL/3MF ──▶ Bambu Studio/printer (BAMBU_PLAN.md)
```

Edit loop (from LeGenesis): keep the previous concept image + mesh path in a small server-side
context object; an edit regenerates from the edited image so the result stays similar. This is an
edited image re-run through image-to-3D, not true mesh editing.

## Image -> 3D: choices (16 GB VRAM)

| Model | Origin | VRAM (reported) | Fit | Notes |
|---|---|---|---|---|
| **Hunyuan3D 2.1, shape only** | Tencent | ~10 GB shape, ~21 GB texture, ~29 GB both | Shape fits | **First spike.** Source headers say Tencent Hunyuan **Non-Commercial** licence (the community licence also excludes EU/UK/South Korea); fine for a personal project, not for selling prints. A print only needs shape. Repo documents a `--low_vram_mode` flag in its Gradio app (**VERIFY** what it does). |
| TRELLIS.2 | Microsoft, MIT | stated 24 GB minimum | Does not fit without offloading | Second test with CPU offload (30 GB RAM available). One blog reports a 16 GB 4070 working with offloading (**VERIFY**). Failure mode without offload is a CUDA OOM error, not damage. |
| Hunyuan3D 2.0 | Tencent | ~6 GB shape, ~16 GB with texture | Fits | Older fallback. |
| TRELLIS v1 | Microsoft | ~16 GB | Borderline | |
| TripoSR / SF3D | Stability + Tripo | small (recalled, **VERIFY**) | Fits | Fast but rougher geometry; good for previews. |
| Step1X-3D | StepFun | unknown | unknown | Appeared in a search; no source covered it. |

Sources for the numbers are vendor and SEO blogs that disagree with each other, so the spike's
measured VRAM and seconds replace them.

## Sketch/text -> concept image

Open options: FLUX with a sketch/scribble ControlNet, or Qwen-Image-Edit (Alibaba, Apache 2.0; the
full model is ~60 GB so it needs an fp8/GGUF build to fit, **VERIFY**). Qwen-Image-2.0 is API-only,
so it does not count as local. Constraints to prompt for (from LeGenesis): single isolated object,
plain white background, clean silhouette, 3/4 front view. Second step after the 3D spike works.

## Local assistant model (no subscription)

Requirements: reliable **tool calling** with our schemas (habit, page, PC tools, plus `make_model`),
fast first token, fits beside Whisper in 16 GB.

| Candidate | Origin | Size at 4-bit (reported) | Notes |
|---|---|---|---|
| **Qwen3 8B-class (instruct)** | Alibaba, Apache 2.0 | ~5-6 GB | Default pick: small, good tool calling for its size. |
| Qwen3 MoE (~30B total, 3B active) | Alibaba, Apache 2.0 | needs CPU offload on 16 GB | Better answers, slower start. Test second. |
| gpt-oss-20b | OpenAI, Apache 2.0 | ~16 GB | Non-Chinese fallback; leaves no room for Whisper. |
| GLM, DeepSeek (full) | Zhipu, DeepSeek | far too large | DeepSeek R1 distills fit but are weak at tools. |

No source benchmarked tool-calling accuracy for small models, so **the test is ours**: run a fixed
set of utterances ("mark gym done", "show the schedule", "make a toy duck") against each candidate and
count correct tool + arguments.

Serving: Ollama is already installed (`/usr/local/bin/ollama`). It exposes an OpenAI-compatible
`/v1/chat/completions` endpoint with tool calls. Code change: `assistant/agent.py` is written
against the Anthropic SDK (content blocks, `tool_use` / `tool_result`, `output_config`). Add a thin
backend interface so `Assistant.ask` can run on either, rather than rewriting the loop. Keep Claude
as an optional backend; default to local. Whisper (already open, `faster-whisper`) is unchanged.

## Build order

1. **Hunyuan3D shape-only spike** (environment, code and ~7.5 GB of weights are set up in `~/ai/`; **the run itself has not happened yet**) in its own environment (`~/ai/`, outside the repo; Python 3.11,
   PyTorch cu128, because the 5070 Ti is Blackwell and PyTorch 2.5/cu124 has no kernels for it,
   **VERIFY**). Record VRAM peak and seconds on this card. Output: a GLB from a test image.
2. **Local assistant backend**: backend interface, Ollama/Qwen3 adapter, tool-call test set.
3. **`make_model` tool**: takes a prompt (and optional sketch), runs the pipeline as a background job
   (generation takes tens of seconds to minutes), returns a job id; the reply says it started, and the
   result is shown on the wall when done.
4. **Concept image step** (FLUX/ControlNet or Qwen-Image-Edit).
5. **Viewer page** on the display app (three.js) so the GLB can be shown through `/stage`.
6. **Print handoff**: GLB -> STL/3MF via `trimesh`, scale/orient checks, upload via the Bambu link.
7. Edit loop with the context object.

## Open questions

- Does Hunyuan3D shape output come out watertight and printable, or does it need repair?
- Is texture needed for the wall view, or is a shaded grey mesh enough? (Texture needs ~21 GB, so it
  would not fit without offloading.)
- Does the PC run one model at a time? (Qwen3 + Whisper + an image model will not all fit in 16 GB
  at once, so a loader that unloads between jobs may be needed.)
