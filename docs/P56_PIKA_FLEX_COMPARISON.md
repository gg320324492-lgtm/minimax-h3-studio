# P56 — Pika H3 Flex vs the local MiniMax H3 baselines, measured

> Execution record for `docs/WORKORDER_P56_PIKA_FLEX_COMPARE.md`. Every number
> here was measured in this task: RTX 5090 (32 GB, one GPU, serial runs),
> ComfyUI v0.43.2, 2026-11-04. **The adopt/reject ruling is deliberately not
> made here** — this file exists to put decidable numbers in front of the
> user; the switch decision stays with the user and the command window.

## 0. Data conclusion (one paragraph, no ruling)

On identical prompts, seed, resolution (1344×768) and duration (5 s → 124
frames), Pika H3 Flex (6-step `lcm` + `ManualSigmas`, its own LoRA, no
second speed LoRA) is **3.8× faster on t2v** (284.5 s vs 1087.4 s for the
full 20-step baseline), **~20 % faster on fl2v** (322.9 s vs 403.5 s vs the
turbo_8step baseline), and **~31 % slower on r2v** (264.4 s vs 201.8 s vs the
turbo_4step baseline — the baseline there is already a 4-step distilled
run, so a 6-step Flex cannot win it on speed). All six renders met spec
(1344×768, 124 frames, h264 + stereo AAC), none froze, and VLM-verified
instruction-following hit counts are in §4. Whether the quality and the
licensing terms justify a switch is the user's call; three frames per video
are in `E:\Minimax-H3\out\p56\compare\` for eyeballing.

## 1. What ran

Six workflows, one per scene/side, built by `experiments/p56_build_workflows.py`
into `workflows/` (gitignored, like every workflow in this repo; the
originals were not touched):

| file | skeleton | speed path |
|---|---|---|
| `video_p56_r2v_A_turbo.json` | local r2v, turbo branch on | `ref2v_turbo_4step` LoRA, `res_multistep` + simple, 4 steps |
| `video_p56_r2v_B_flex.json` | local r2v + pika LoRA | `pika_h3_flex_ref2va` LoRA, `lcm` + `ManualSigmas` (7 sigmas), 6 steps |
| `video_p56_fl2v_A_turbo.json` | official fl2va template, retargeted | `fl2v_turbo_8step` LoRA, `res_multistep` + simple, 8 steps |
| `video_p56_fl2v_B_flex.json` | official fl2va template, as shipped | `pika_h3_flex_fl2va` LoRA, `lcm` + `ManualSigmas`, 6 steps |
| `video_p56_t2v_A_full.json` | local t2v, as found | no LoRA, full 20 steps |
| `video_p56_t2v_B_flex.json` | official pika t2v template, as shipped | `pika_h3_flex_fl2va` LoRA, `lcm` + `ManualSigmas`, 6 steps |

Control variables pinned across all six:

- seed `261662374822964` (the r2v workflow's own `RandomNoise` value, pinned
  at the API prompt level by `experiments/p56_runner.py`, so it survives
  subgraph flattening);
- resolution 1344×768 — 0.98 MP via `ResolutionSelector` where the skeleton
  has one, via 1344×768 reference pictures where the template derives size
  from `GetImageSize` (the local 512×512 inputs were cover-cropped to
  `p56_ref_first_1344x768.png` / `p56_ref_last_1344x768.png` in
  `E:\ComfyUI\input\`);
- duration 5 s → 124 frames (17k+5 grid, the templates' own expression);
- one prompt body (comic-book two-cut scene, with a whip-pan transition),
  with per-modality framing lines: r2v references `<Picture 2>/<Picture 1>`,
  fl2v declares the first/last-frame alignment, t2v drops references. It
  embeds the three decidable elements the work order asks for: the subtitle
  words **MEET / MAKER** (word-by-word overlay), the **numeral 7** (stamped
  countdown in CUT 2), and the **roar** (jaws-wide action);
- video VAE `minimax_h3_video_vae_fp16.safetensors` on every side (the
  official templates ship int8_convrot; they were retargeted so the VAE is
  not a second variable), same text encoder
  (`qwen3vl_32b_minimax_h3_nvfp4_awq`), same UNETs per scene.

The full prompt text and every node value is in the workflow files; each was
converted to an API prompt and spot-checked (`[audit] … ok` in the build log)
before submission.

## 2. Speed (measured end-to-end per render, same card, serial)

| scene | A (baseline) | B (Flex) | delta |
|---|---|---|---|
| r2v | 201.8 s (turbo, 4 steps) | 264.4 s (Flex, 6 steps) | **B +31 % slower** |
| fl2v | 403.5 s (turbo, 8 steps) | 322.9 s (Flex, 6 steps) | **B 20 % faster** |
| t2v | 1087.4 s (full, 20 steps) | 284.5 s (Flex, 6 steps) | **B 3.8× faster** |

The r2v direction is the expected one: the local baseline is already a
distilled 4-step run, so Flex's 6 steps cannot beat it on speed. The speed
case for Flex is t2v (and, mildly, fl2v).

## 3. Spec compliance (ffprobe, every side)

| scene | side | size | frames | fps | audio |
|---|---|---|---|---|---|
| r2v | A / B | 1344×768 | 124 | 24 | aac stereo 32 kHz |
| fl2v | A / B | 1344×768 | 124 | 24 | aac stereo 32 kHz |
| t2v | A / B | 1344×768 | 124 | 24 | aac stereo 32 kHz |

`freezedetect` (n=0.003, d=0.4): **no freeze segments in any of the six**.
Adjacent-frame diffs (sampled pairs, pixels differing >8, the `ab_field`
threshold): min 24–50 %, median 61–73 %, no near-frozen pair in any render —
consistent with the scripted whip pan and roar.

## 4. Instruction following (P45 instrument, `qwen2.5vl:7b` over local
ollama; closed yes/no questions on 5 sampled frames each; an element hits if
any frame answers yes; raw answers kept in `out/p56/measure_*.json`)

Five sampled frames per render (f000/f029/f062/f094/f123), four closed
questions each. `Y/n` = element hit, n of 5 frames answered yes.

| scene | side | MEET | MAKER | numeral 7 | roar (jaws wide) | elements hit |
|---|---|---|---|---|---|---|
| r2v | A (turbo) | Y/2 | Y/1 | **N** (5×NO) | Y/2 | **3/4** |
| r2v | B (Flex) | Y/2 | Y/1 | **N** (5×NO) | Y/2 | **3/4** |
| fl2v | A (turbo) | Y/1 | Y/1 | Y/1 | Y/1 | **4/4** |
| fl2v | B (Flex) | Y/1 | Y/1 | Y/1 | Y/1 | **4/4** |
| t2v | A (full 20) | Y/1 | Y/1 | Y/2 | Y/2 | **4/4** |
| t2v | B (Flex) | Y/2 | Y/1 | Y/2 | Y/2 | **4/4** |

A/B ties in every scene — Flex neither gained nor lost decidable elements.
The one miss (the numeral 7 in r2v) is identical on both sides and the raw
answers are clean, decisive NOs on all five frames each, while the same
question hits in fl2v/t2v — so the instrument is working; the r2v
reference-guided composition simply dropped that element on both sides.

## 5. Frame grabs for the user's own eyes (quality is not decidable here)

`E:\Minimax-H3\out\p56\compare\{scene}_{A|B}_f{000,062,123}.png` — first,
middle and last sampled frame of each render, 18 PNGs.

## 6. Licensing note (flagged by the work order, not reviewed here)

Pika H3 Flex is distributed under the MiniMax H3 community license per the
Comfy-Org repo page. **Before any commercial use, the license text needs a
proper review** — this task measured feasibility and speed only.

## 7. Execution notes

- **Precondition check**: the work order asks to confirm P55 by reading
  `docs/P55_COMFYUI_UPGRADE.md`. That file does not exist on disk or in
  git (only `WORKORDER_P55_COMFYUI_UPGRADE.md` and the evidence under
  `from_e_root/out/p55/`). The precondition was instead confirmed from
  evidence: `E:\ComfyUI` reports `comfyui_version 0.43.2`, and
  `from_e_root/out/p55/new_baseline_r2v_0432.mp4` matches the recorded
  md5 `d5e83c59…`. The missing P55 report itself is a gap its owner
  should close.
- **r2v baseline state**: the local r2v workflow ships with its turbo branch
  switched OFF (node 146 = false → bare UNET + full steps), while the work
  order defines the r2v baseline as turbo_4step. Side A was run with the
  branch ON, i.e. the work order's definition. Nothing was changed in the
  original file.
- **Flattened-subgraph bug found and fixed**: retargeting an official
  template's flattened nodes via `widgets_values_named` silently loses to
  the template's own widget bridges — expansion writes bridge bindings into
  node inputs under `resolved`, and `resolved` overrides named values in
  the prompt converter. `set_value` in `p56_build_workflows.py` now writes
  all three serialization surfaces; the build-time audit caught this before
  anything ran (one wasted submission, which failed ComfyUI validation
  before executing).
- **Disk event mid-task**: ollama + qwen2.5vl:7b were installed to support
  the P45 instrument. The first pull landed in `C:\Users\pc\.ollama`
  (~5.6 GB) before the no-C-drive rule arrived; the sibling session moved
  it to `E:\Minimax-H3\third_party\ollama\models` (OLLAMA_MODELS), the pull
  was redone to E:, and this task's temp-frame directory was moved to
  `out/p56/` as well. The ollama *program* itself (3.1 GB, winget) is still
  under `C:\Users\pc\AppData\Local\Programs\Ollama` — reported, left for
  the user to rule on.
- Videos live in `E:\Minimax-H3\out\p56\{scene}_{side}.mp4` (~28 MB total,
  kept — the work order's cleanup rule asks to drop large files at the end;
  28 MB is small enough to keep until the ruling).
- Per-run runner logs (seed pin, prompt ids, elapsed, outputs) are in the
  session transcript; the machine-readable measurement files are
  `E:\Minimax-H3\out\p56\measure_{scene}_{side}.json`.
