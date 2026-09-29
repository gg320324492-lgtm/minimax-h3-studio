---
name: minimax-video-templates
description: 本地 AI 视频工作室的 Remotion 模板工厂——三种时间线模板 + report 数据模板的契约规则、渲染命令、新模板 codegen 工作流与 review 门禁
metadata:
  type: project
---

# MiniMax-H3 视频工作室 · Remotion 模板工厂

把"新视频需求"变成"确定性成片"的完整路径。架构与基准数据见
`docs/REMOTION_INTEGRATION_PLAN_20260929.md` / `studio/BENCHMARK_20260929.md`，进度见 `docs/REMOTION_INTEGRATION_PROGRESS.md`。

## 模板配方卡（需求 → 模板 → 命令）

| 需求类型 | Composition | 输入契约 | 渲染命令 |
|---|---|---|---|
| 竖屏短剧（AI 片段） | `DramaVertical` 1080×1920 | `timeline_v2.json`（zod: timeline-v2） | `render_with_remotion.py --job <id> --out <path> --qa` |
| 横屏公益/辟谣 | `PsaWide` 1920×1080 | 同上，template=psa-wide | `emit_props.py` → `render.mjs --comp PsaWide` |
| 横屏叙事动画（2K） | `StoryAnimation` 2560×1440 | 同上 + titlecard/endcard 段 | 同上，comp=StoryAnimation |
| 封面/竖版海报 | `CoverCard`（still） | cover props JSON | `npx remotion still CoverCard --props=x.json --output=cover.png` |
| 数据报告/榜单（无 GPU） | `ReportVertical` 1080×1920 | report-data schema（stats/chart/takeaways/outro，自动时间轴） | `render.mjs --comp ReportVertical --props=x.json` |

## 铁律（违反 = 渲染失败或 QA 挂）

1. **改 schema 必须双端同步**：`studio/src/schemas/*.ts` 改完跑 `pnpm exec tsx bin/export-schema.ts`，
   Python 侧 stage_assets.py 用导出的 JSON Schema 校验。
2. **转场只允许帧内动画**（ShotFrame fade/flash）——`TransitionSeries` 重叠式会挪动绝对秒，毁掉对白对齐。
3. **混音留在 Python**（mix_audio → audioBus.premixed 单轨）；Remotion 无 loudnorm/sidechain。
4. **编码定稿**：x264 crf18 + jpeg + `colorSpace:'bt709'`（缺 bt709 输出 yuvj420p 挂 QA）+ 并发 16。
   Node API 不读 remotion.config.ts，参数必须显式传（render.mjs 已内置）。
5. **样式令牌双端同源**：模板 styles.ts 从各项目 `burn_subtitles*.py` 的 STYLES 移植，改动要两侧同步。
6. **pnpm install 后必须 `npx remotion browser ensure`**（浏览器缓存在 node_modules/.remotion 会被清）。
7. **Python 侧 ffmpeg 一律走 `ffmpeg_env.py`**；Remotion 用自带 compositor/ffmpeg，两边别混。

## 生成层（ComfyUI H3）对接速查

- 片段生成：`video_minimax_h3_r2v.json`（角色一致）/ `_t2v.json`（首末帧）；帧长 17k+5；Turbo LoRA 8-step。
- 生成长度 ≠ 呈现长度：`Shot.trimBefore` + `durationInFrames` 裁剪解耦，选片后对齐节奏点。
- 逐片段超分：`ceo_mindread_ep01/scripts/sr_takes.py`（x2plus fp16 tile768/64 → 1080×1920）。
- 词级卡拉OK：`studio/scripts/word_timestamps.py --in-place`（faster-whisper small；ASR 词面只当对齐标尺，
  文字用已知原文；台词=卡拉OK、心声=打字机、钩子/结束卡被相似度守卫拒绝=静态）。

## 新模板 codegen 工作流（模式 C）与 review 门禁

1. 需求 → 先判断能否用现有模板 + 新样式/新 props 字段解决；只有新"视觉形态"才新建模板目录。
2. 生成代码时：复用 `common/`（TimelinePlayer/captions/overlays/transitions/styleSet），禁止绕过契约直接发明字段。
3. **入库门禁（全部通过才能进 Root.tsx 注册）**：
   - [ ] `pnpm exec tsc --noEmit` 零错误
   - [ ] zod schema 定义完整并导出 JSON Schema
   - [ ] 真实 props 渲染通过（`render.mjs` 或 `remotion still`），产物 ffprobe 规格正确（H.264 yuv420p tv）
   - [ ] 人工目检抽帧（≥3 个代表帧）
   - [ ] 有 QA 可校验的输出规格（时长/分辨率/字幕宽度）时接入 qa 脚本
   - [ ] 涉及样式：与 Python 侧样式字典核对一致
4. 外部参考代码只允许 MIT/Apache（AGPL 项目只学架构不抄代码——OpenMontage 等）。
