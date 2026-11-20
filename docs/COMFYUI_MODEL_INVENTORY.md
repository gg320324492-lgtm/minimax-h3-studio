# ComfyUI 模型清单 —— 2026-11-20 审计

> 目的：给「删哪些模型」这个决策提供依据。结论先行——
> **99 GB 的模型里没有可直接删除的项**，唯一可清的是两份内容完全相同的拷贝（已删）。
> 下文给出逐模型依据与复核方法。

## 0. 结论

| 结论 | 说明 |
|---|---|
| 模型总量 | `third_party/ComfyUI/models/` = **99 GB**（>50MB 的 23 个 + <50MB 的 16 个共 82 MB） |
| 明确在用 | **23 个全部有引用来源**，没有一个是孤儿 |
| 可删候选 | **0 个**。唯一的重复件已在本轮清掉（见 §4） |
| 待你决策 | 只有 **FlashVSR-v1.1 整组 6.5 GB** 属"已就绪待批接入"——接不接由你定，见 §5 |

## 1. 为什么不能只搜文件名

第一版审计只扫 `out/workflows/*.json`，得出"37 GB 未被引用"的结论——**这是误报**。
ComfyUI 的加载节点按「目录 + 下拉选项」取模型：

| 模型目录 | 加载节点 |
|---|---|
| `diffusion_models/`、`unet/` | UNetLoader / UNetLoaderGGUF |
| `vae/` | VAELoader |
| `loras/` | LoraLoader |
| `text_encoders/` | CLIPLoader |
| `checkpoints/` | CheckpointLoader |
| `model_patches/` | ModelPatchLoader |
| `controlnet/` | ControlNetLoader |

工作流 JSON 里存的是**下拉框的显示名**或节点配置，不是文件名，所以
`seedvr2_ema_3b.safetensors`（12.6 GB）这种靠节点选取的文件，在工作流里搜不到名字，
但它实际被 `SeedVR2ModelLoader` 使用、并在 P58 的实测链路里跑过。

把扫描范围扩到「工作流 + 归档工作流 + 脚本 + 成片脚本 + 实验脚本 + 文档」之后，
23 个大模型**全部命中引用来源**。

## 2. 目录构成

| 子目录 | 体积 | 说明 |
|---|---|---|
| `diffusion_models/` | 52 GB | H3 主模型 r2v/fl2v、SeedVR2-3B、RT-DETR |
| `text_encoders/` | 15 GB | Qwen3-VL 32B（视觉理解，H3 提示词改写用） |
| `loras/` | 9.2 GB | H3 turbo 步数 LoRA、Pika Flex 变体 |
| `model_patches/` | 7.9 GB | ControlNet Union 2.0 |
| `FlashVSR-v1.1/` | 6.5 GB | FlashVSR 整组（待批接入） |
| `vae/` | 5.5 GB | H3 视频/音频 VAE |
| `checkpoints/` | 1.8 GB | SDPose 全身姿态 |
| `seedvr2/` | 958 MB | SeedVR2 的 VAE 与条件嵌入 |
| `geometry_estimation/` | 517 MB | Depth Anything v3 |
| `tts/` | 316 MB | Kokoro-82M（HF 缓存形态） |
| `upscale_models/` | 200 MB | Real-ESRGAN x2plus / x4plus |
| 其余 13 个目录 | 0 | ComfyUI 标准空目录 |

整个 `third_party/ComfyUI/` = 106 GB（models 99 GB + venv 6.8 GB + 代码 0.15 GB）。

## 3. 逐模型清单

| 模型 | 体积 | 目录 | 引用来源 |
|---|---|---|---|
| `minimax_h3_ref2va_pruned_int8_convrot.safetensors` | 19.5 GB | `diffusion_models/` | 实验脚本、工作流、归档工作流、成片脚本 |
| `minimax_h3_fl2va_pruned_int8_convrot.safetensors` | 19.5 GB | `diffusion_models/` | 实验脚本、工作流、成片脚本、文档 |
| `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | 14.6 GB | `text_encoders/` | 实验脚本、工作流、归档工作流、成片脚本 |
| `seedvr2_ema_3b.safetensors` | 12.6 GB | `diffusion_models/` | 实验脚本、文档 |
| `minimax_h3_fun_controlnet_union_2.0_pruned_bf16.safetensors` | 7.8 GB | `model_patches/` | 实验脚本、工作流、文档 |
| `diffusion_pytorch_model_streaming_dmd.safetensors` | 5.3 GB | `FlashVSR-v1.1/` | 实验脚本 |
| `minimax_h3_video_vae_fp16.safetensors` | 4.9 GB | `vae/` | 实验脚本、工作流、归档工作流、成片脚本、文档 |
| `minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` | 1.8 GB | `loras/` | 实验脚本、工作流、归档工作流 |
| `minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` | 1.8 GB | `loras/` | 实验脚本、工作流、成片脚本 |
| `minimax_h3_fl2v_turbo_8step_v1.0_768p_comfyui_bf16.safetensors` | 1.8 GB | `loras/` | 成片脚本 |
| `pika_h3_flex_ref2va_v1_bf16.safetensors` | 1.8 GB | `loras/` | 实验脚本、工作流、文档 |
| `pika_h3_flex_fl2va_v1_bf16.safetensors` | 1.8 GB | `loras/` | 实验脚本、工作流、文档 |
| `sdpose_wholebody_fp16.safetensors` | 1.8 GB | `checkpoints/` | 实验脚本、工作流、文档 |
| `ema_vae.pth` | 0.9 GB | `seedvr2/` | 实验脚本、文档 |
| `minimax_h3_audio_vae_fp32.safetensors` | 0.6 GB | `vae/` | 工作流、归档工作流、成片脚本 |
| `LQ_proj_in.ckpt` | 0.5 GB | `FlashVSR-v1.1/` | 实验脚本 |
| `depth_anything_3_base.safetensors` | 0.5 GB | `geometry_estimation/` | 实验脚本、文档 |
| `Wan2.1_VAE.pth` | 0.5 GB | `FlashVSR-v1.1/` | 实验脚本 |
| `kokoro-v1_0.pth` | 0.3 GB | `tts/models--hexgrad--Kokoro-82M/snapshots/…/` | 节点按目录加载（KPipeline 按 repo_id 取） |
| `TCDecoder.ckpt` | 0.2 GB | `FlashVSR-v1.1/` | 实验脚本 |
| `rt_detr_v4-x-hgnet_fp16.safetensors` | 0.1 GB | `diffusion_models/` | 实验脚本、工作流、文档 |
| `RealESRGAN_x2plus.pth` | 0.1 GB | `upscale_models/` | 实验脚本、脚本 |
| `RealESRGAN_x4plus.pth` | 0.1 GB | `upscale_models/` | 脚本 |

> **合计 98.9 GB**（>50MB 的模型 23 个；另有 16 个 <50MB 的小模型，合计 82 MB）

## 4. 本轮已清的重复件（md5 完全相同）

| 已删 | 保留 | 体积 |
|---|---|---|
| `models/vae/ema_vae.pth` | `models/seedvr2/ema_vae.pth` | 0.9 GB |
| `models/tts/kokoro-v1_0.pth` | `models/tts/models--hexgrad--Kokoro-82M/snapshots/…/kokoro-v1_0.pth` | 0.3 GB |

两对文件的 md5 完全一致（`94f916c…` / `ac45d7db…`），各留一份即可。
删后已实测 Kokoro 仍可正常合成中文语音（3.83 秒）。

## 5. 唯一待你决策项：FlashVSR-v1.1 整组 6.5 GB

| 文件 | 体积 |
|---|---|
| `diffusion_pytorch_model_streaming_dmd.safetensors` | 5.3 GB |
| `LQ_proj_in.ckpt` | 0.5 GB |
| `Wan2.1_VAE.pth` | 0.5 GB |
| `TCDecoder.ckpt` | 0.2 GB |

状态：**接入件已就绪、待批**（见 `docs/OPTIMAL_PIPELINE_REPORT.md`）。
目前只有实验脚本引用，尚未进入任何交付工作流。
接 → 保留；不接 → 可整组删除，回收 6.5 GB。

## 6. 怎么复核这份清单

```bash
# 重跑审计（会重新生成 out/工具scripts/_model_table.md）
python -I out/工具scripts/gen_model_inventory.py

# 查某个模型被谁引用
grep -rn "minimax_h3_ref2va" out/workflows/ scripts/ productions/ experiments/ docs/
```

审计脚本：`out/工具scripts/gen_model_inventory.py`。
**扫描范围必须包含脚本与文档**，只扫工作流会得出"大把未引用"的假结论。
