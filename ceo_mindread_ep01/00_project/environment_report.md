# Environment Audit Report - CEO Mindread EP01
**Audit Date**: 2026-08-28
**Phase**: PHASE 01 - Environment Audit

---

## Hardware
| Component | Spec |
|-----------|------|
| **GPU** | NVIDIA GeForce RTX 5090 |
| **VRAM** | 32 GB (Blackwell sm_120, compute capability 12.0) |
| **Driver** | 616.56 |
| **CUDA** | 12.8 |
| **System RAM** | 66 GB total / 40 GB free |
| **OS** | Windows 11 |

## Python / ComfyUI
| Component | Version |
|-----------|---------|
| **Python** | 3.12.10 (system + venv) |
| **PyTorch** | 2.11.0+cu128 |
| **ComfyUI** | v0.34.0 |
| **API** | http://127.0.0.1:8188 |
| **Launch Flags** | `--listen 0.0.0.0 --port 8188 --disable-smart-memory --bf16-vae` |
| **Installed Templates** | 0.11.48 |

## Models Inventory
| Type | Path | File |
|------|------|------|
| **Diffusion (T2V/I2V)** | `models/diffusion_models/` | minimax_h3_fl2va_pruned_int8_convrot.safetensors (20.97 GB) |
| **Diffusion (R2V)** ⭐ | `models/diffusion_models/` | minimax_h3_ref2va_pruned_int8_convrot.safetensors (20.97 GB) |
| **Text Encoder** | `models/text_encoders/` | qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors (15.69 GB) |
| **Video VAE** | `models/vae/` | minimax_h3_video_vae_fp16.safetensors (5.21 GB) |
| **Audio VAE** | `models/vae/` | minimax_h3_audio_vae_fp32.safetensors (0.61 GB) |
| **LoRA (FL2V 8-step turbo)** | `models/loras/` | minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors (1.96 GB) |
| **LoRA (R2V 4-step turbo)** | `models/loras/` | minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors |
| **Upscaler** | `models/upscale_models/` | RealESRGAN_x2plus.pth (64 MB) |

## Active Video Pipeline
- **Primary Video Model**: **MiniMax-H3 Ref2VA** (locked)
- **Character Consistency**: Built-in Reference-to-Video via `<Picture N>` tags
- **Generation Spec**: Up to 2K resolution, 24fps, native audio (joint decode)

## Image Generation
- **No local image checkpoint installed** (no SD 1.5/SDXL/Flux model files)
- **Decision**: Generate keyframe images using the same MiniMax-H3 R2V model (extract first frame from a 1-second generation, OR generate directly as I2V reference)

## Custom Nodes Status
| Category | Status |
|----------|--------|
| ComfyUI Built-in Nodes | ✅ 900+ available |
| MiniMax-H3 Native Nodes | ✅ 15 nodes built-in |
| PuLID | ❌ Not installed (not needed - using R2V) |
| IPAdapter / IPAdapter FaceID | ❌ Not installed (not needed) |
| InstantID | ❌ Not installed (not needed) |
| ReActor / Face Detailer | ❌ Not installed (not needed) |
| Wan Video Wrapper | ❌ Not installed (no Wan models) |
| Hunyuan Video Wrapper | ❌ Not installed (no Hunyuan models) |
| LTX Video Wrapper | ❌ Not installed (no LTX models) |

## Upscale Pipeline (LOCKED ✅)
- **Tool**: Real-ESRGAN_x2plus + fp16
- **Production Script**: `E:\Minimax-H3\pipe_fast.py`
- **Tile**: 512, overlap: 32
- **Time**: ~90s for 124 frames (768p → 1440p)
- **Output**: Will be Lanczos-scaled to 1080x1920 for final

## TTS / LipSync
- **TTS**: No local TTS engine installed (no ComfyUI-Fish-Speech / CosyVoice / GPT-SoVITS)
- **Plan**: Use external TTS service (Edge TTS / ElevenLabs API) - to be acquired
- **LipSync**: No local LipSync node (no SadTalker / MuseTalk / Wav2Lip)
- **Mitigation**: Avoid direct dialogue LipSync; use J-cut / L-cut / reaction shots; rely on subtitles + inner voice reverb

## Audio Tools
- **FFmpeg**: 4.2.11 ✅
- **FFprobe**: 4.2.11 ✅

## Production Strategy (LOCKED)
| Step | Approach |
|------|----------|
| **1. References** | MiniMax-H3 R2V generates character reference clips; extract best frames as PNG |
| **2. Keyframes** | Use R2V with first-frame as reference image; extract single best frame |
| **3. I2V Video** | R2V with reference image + new scene prompt (character maintained by R2V) |
| **4. Upscale** | Real-ESRGAN fp16 (tile 512) → Lanczos to 1080x1920 |
| **5. Audio** | External TTS + native audio baked into R2V output (joint decode) |
| **6. Subtitles** | Post-process with FFmpeg + ASS styling |

## Critical Constraints
1. **No separate TTS engine available locally** - must acquire or use external API
2. **No local LipSync** - dialogue-heavy scenes must use J-cut/L-cut/reaction shot strategy
3. **MiniMax-H3 is the ONLY video model** - no Wan/Hunyuan/LTX backup
4. **R2V generates video + audio jointly** - can leverage built-in audio for SFX/BGM elements

## Next Phase: PHASE 02 - Project Structure ✅ COMPLETE
Project tree at `E:\Minimax-H3\ceo_mindread_ep01\` created.