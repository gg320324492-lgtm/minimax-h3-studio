# MiniMax-H3 本地视频工作室

**一句话**：从剧本文到成品片的本地全自动生产线——MiniMax-H3 全模态模型生成画面与声音，Remotion 程序化合成包装，ffmpeg/Python 负责超分、混音与质量门禁，全部跑在一台 RTX 5090 工作站上。

## 五层架构

```
┌────────────────────────────────────────────────────────────────────┐
│ 编排层   Claude Code（Remotion Agent Skills + minimax-video-templates）│
├─────────────────────────────┬──────────────────────────────────────┤
│ AI 生成层（GPU）              │ 合成渲染层（CPU+NVENC）                │
│  ComfyUI + MiniMax-H3        │  studio/  Remotion 4.0.529            │
│  r2v 角色一致 / fl2va 首末帧   │  TimelinePlayer × 三模板 + 数据报告    │
│  Turbo LoRA 8-step           │  卡拉OK字幕 · 转场 · 卡点量化 · 封面    │
│  Turbo 4-8 步, 17k+5 帧格     │  Studio 实时预览                      │
├─────────────────────────────┴──────────────────────────────────────┤
│ 数据层   timeline_v2.json（zod 契约 = Python↔TS 双端唯一真相）          │
├────────────────────────────────────────────────────────────────────┤
│ 后期层   Real-ESRGAN 逐片段超分 → ffmpeg 混音（loudnorm −14 LUFS）      │
├────────────────────────────────────────────────────────────────────┤
│ 质量层   qa_final.py (16 项) / qa_report.py (10 项) / check_contract   │
└────────────────────────────────────────────────────────────────────┘
```

## 仓库地图

| 目录/文件 | 内容 |
|---|---|
| `ceo_mindread_ep01/` `liaozhai_demo/` `piyao_2026/` `third_lantern/` | 四个生产项目（竖屏短剧/复古动画/辟谣 PSA/国风 2K） |
| `studio/` | Remotion 合成层（模板/契约/渲染桥/音频），见 [studio/README.md](studio/README.md) |
| `workflows/` | ComfyUI H3 工作流 JSON（r2v 角色一致 / fl2va 首末帧 / 归档备份） |
| `docs/` | 全部报告与方案文档（管线升级史 / Remotion 融合方案 / 动效调研） |
| `experiments/` | 一次性实验脚本与基准残留（SR 调参/管道变体/分析 dump），非生产依赖 |
| `ffmpeg_env.py` `sr_pipeline_v2.py` | ⚠️ 根级系统模块：ffmpeg 解析器 / Real-ESRGAN 超分引擎，**被多项目生产链引用，勿移动** |
| `tools/ffmpeg-7.1.1-full_build/` | 自带 ffmpeg/ffprobe（PATH 上有 Octave 的 4.2.11 陷阱，一律经 `ffmpeg_env.py` 解析） |
| `preview/` `upscale_frames*/` `work_frames/` `logs/` `tests/` | 工作 scratch（gitignore） |

## 项目模板规范（四个项目共用）

```
<project>/
├── 00_project/      剧本/分镜/manifest/timeline（入库 ✓）
├── 01_reference/    角色与场景参考图
├── 03_video_raw/    H3 生成的原始 take
├── 04_video_selected/  选片结果（+ _sr/ 超分产物）
├── 05_audio/        TTS/BGM/SFX（生成物，gitignore）
├── 07_edit/         中间装配产物（gitignore）
├── 08_cover/ 09_final/  封面与交付（gitignore）
├── scripts/         该项目的阶段脚本（入库 ✓）
└── logs/            gitignore
```

## 核心约定（铁律）

1. **ffmpeg 一律走 `ffmpeg_env.py` 解析**——PATH 上的 `ffmpeg` 是 Octave 附带的 4.2.11。
2. **H3 帧长必须 17k+5**（22/56/124/141/192/226…）；生成长度≠呈现长度，用 timeline v2 的 `trimBefore` 裁。
3. **timeline JSON 是唯一数据源**；zod schema 在 `studio/src/schemas/`，改 schema 必须 `pnpm exec tsx bin/export-schema.ts` 并提交导出物。
4. **Remotion 渲染定稿参数**：x264 crf18 + jpeg + `colorSpace:'bt709'` + 并发 16（缺 bt709 输出 yuvj420p 挂 QA）。
5. **音频母带走 WAV 中转**（`studio/scripts/master_audio.py`，−14 LUFS），直接 MP4 上 loudnorm 不收敛。
6. **转场只用帧内动画**（不改时间轴）；`TransitionSeries` 重叠式会破坏对白绝对秒对齐。
7. 提交前跑 `studio/scripts/check_contract.py`（schema 漂移 + props 校验）。

## 命令速查

```bash
# 短剧项目：生成 → 出片（含 QA）
E:/ComfyUI/venv/Scripts/python.exe ceo_mindread_ep01/scripts/build_timeline.py
E:/ComfyUI/venv/Scripts/python.exe ceo_mindread_ep01/scripts/render_with_remotion.py --job <id> --out 07_edit/<out>.mp4 --qa

# 纯数据视频（零 GPU，模式 B）
cd studio && node bin/render.mjs --comp ReportVertical --props <data.json> --out out/x.mp4
E:/ComfyUI/venv/Scripts/python.exe scripts/master_audio.py out/x.mp4 && E:/ComfyUI/venv/Scripts/python.exe scripts/qa_report.py --video out/x.mp4 --props <data.json>

# 迭代预览
cd studio && pnpm dev        # Remotion Studio 实时预览

# 契约/资产自检
E:/ComfyUI/venv/Scripts/python.exe studio/scripts/check_contract.py
```

## 文档索引

| 文档 | 内容 |
|---|---|
| [docs/REMOTION_INTEGRATION_PLAN_20260929.md](docs/REMOTION_INTEGRATION_PLAN_20260929.md) | Remotion 融合方案（四路深度调研） |
| [docs/REMOTION_INTEGRATION_PROGRESS.md](docs/REMOTION_INTEGRATION_PROGRESS.md) | **进度总账**（Phase 0–7 逐项记录） |
| [docs/REMOTION_MOTION_UPGRADE_20260930.md](docs/REMOTION_MOTION_UPGRADE_20260930.md) | 动效张力调研与实现记录 |
| [docs/UPGRADE_REPORT_20260919.md](docs/UPGRADE_REPORT_20260919.md) | 超分管线升级证据（SR 基准） |
| [docs/OPTIMAL_PIPELINE_REPORT.md](docs/OPTIMAL_PIPELINE_REPORT.md) / [docs/TEST_REPORT_20260910.md](docs/TEST_REPORT_20260910.md) | 早期管线选型与测试 |
| [studio/BENCHMARK_20260929.md](studio/BENCHMARK_20260929.md) | Remotion 渲染基准（并发/编码定稿依据） |

## 许可注意

- **MiniMax H3 Community License**：USA/EU/UK/KR 商用分发需向 MiniMax 提交申请；自用与国内分发不受限。
- **Remotion License**：个人/≤3 人公司免费；5.0 起渲染传 `licenseKey: "free-license"`。
- **音频**：Mixkit Free License / Kenney CC0（审计链见 `studio/public/audio/manifest.json`）。
