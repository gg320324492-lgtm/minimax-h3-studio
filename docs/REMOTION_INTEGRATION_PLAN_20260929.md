# Remotion × MiniMax-H3 融合方案：多类型视频本地生成工作室

> 调研日期：2026-09-29 ｜ 状态：设计稿（待评审）
> 调研范围：Remotion 生态现状（v4.0.529）、开源 "AI+Remotion" 项目格局、本机管线盘点、AI 片段生成与组装模式

---

## 0. 结论（TL;DR）

**Remotion 与 MiniMax-H3 管线是高度互补的两层，融合成本可控、收益明显：**

| | MiniMax-H3 管线（现有） | Remotion 层（新增） |
|---|---|---|
| 职责 | AI 视频片段生成（画面+原生音频）、TTS、混音、超分 | 程序化合成：装配、转场、字幕、花字、片头片尾、封面、数据图表 |
| 引擎 | ComfyUI @ RTX 5090 | headless Chrome + 自带 Rust compositor + 自带 FFmpeg |
| 输入 | prompt / 参考图 / 首末帧 | **timeline JSON（zod schema 校验）+ 已生成的片段资产** |
| 输出 | 24fps 竖屏/横屏片段 MP4 | 成品 MP4（直接过现有 QA 门禁） |

三个运行模式，互相独立、可单独使用：

- **模式 A（结合）**：H3 管线产出片段 → `timeline_v2.json` → Remotion 渲染成品。替换现有 PIL 烧字幕 + ffmpeg concat + PIL 封面，获得转场/花字/数据叠加能力。
- **模式 B（独立）**：纯程序化模板视频（数据报告、日报、榜单、营销模板）——不占 GPU、不需要 H3，分钟级出片。
- **模式 C（模板工厂）**：Claude Code + 官方 Remotion Agent Skills 生成新模板组件，人工 review 后入库，转成模式 A/B 的确定性资产。

**许可证无障碍**：Remotion 按人数计（非收入），个人与 ≤3 人公司免费，本地渲染商业视频也免费。**关键前提已满足**：本机 Node v24.16.0 / npm 11 / pnpm 9 均就绪。

**建议实施节奏**：Phase 0 环境验证与渲染基准（半天）→ Phase 1 EP01 包装层迁移（1–2 天）→ Phase 2 全模板迁移 + timeline v2（2–3 天）→ Phase 3 新视频类型 + 词级卡拉OK字幕 + 模板工厂（2–3 天）。详见 §10。

---

## 1. 现状盘点：本机管线是什么

### 1.1 生成模型：MiniMax-H3（全模态视频+音频）

`video_minimax_h3_r2v.json` / `video_minimax_h3_t2v.json` 背后是 **MiniMax 官方开源的 H3 全模态生成模型**（ComfyUI 原生支持，权重 `Comfy-Org/MiniMax-H3`），一条前向同时生成视频画面与原生立体声音频：

| 变体 | 节点 | 能力 |
|---|---|---|
| `ref2va`（20.97GB int8） | `MiniMaxH3ReferenceToVideo` | 最多 9 图 / 3 视频 / 3 音频参考，prompt 中 `<Picture 1>` 寻址，锁定角色一致性 |
| `fl2va`（20.97GB int8） | `MiniMaxH3ImageToVideo` | 文生视频 / 首帧图生视频 / 首+末帧插值控制 |

配套：Qwen3-VL 32B 文本编码器（nvfp4_awq）、双 VAE（视频 fp16 + 音频 fp32）、社区 Turbo LoRA（r2v 4-step / fl2v 8-step，`lightx2v/Minimax-h3-Turbo` 等，另有 `MiniMaxAI/MiniMax-H3-Turbo-Lora`）。输出 24fps、4–15s、768p 短边起（最高 2K）、帧长必须满足 **17k+5**（22/56/124/141/192/226…）、原生 **32kHz 立体声**与画面联合生成；`<d>` 对话 token 的中文台词生成稳定（11 语言）。EP01 用 768×1344 竖屏，8-step Turbo + `res_multistep/simple` + cfg=1。

### 1.2 管线：timeline.json 驱动的六段链

四个项目（EP01 竖屏短剧 / 聊斋复古动画 / 辟谣 PSA / 第三盏灯国风 2K）共享同一阶段链：

```
00_project(剧本/manifest) → ComfyUI H3 片段 → 选片(select_takes) → 拼接 picture lock(concat demuxer)
  → Real-ESRGAN 超分 1080p(sr_pipeline_v2) → 混音(mix_audio_v4: adelay/amix/sidechain/loudnorm −14LUFS)
  → PIL 逐帧烧字幕(burn_subtitles_v2) → 封面+交付(finalize) → QA 门禁(qa_final, 14 项)
```

**`00_project/timeline.json` 是全管线单一数据源**，字段：`project / total_duration / shot_boundaries / audio_events / sfx_events / subtitle_events / bgm`。事件带绝对秒级时间、文件路径、类型（dialogue/inner/sfx）、字幕样式名（normal/inner/opening/special/inner_special/ending）。下游混音、字幕、QA 都是它的纯函数——**这就是接 Remotion 的天然接缝**。

### 1.3 痛点（Remotion 要解决的）

1. **字幕**：PIL 逐帧画 + 全片重编码，慢且样式改动 = 全量重跑；无逐词动画、无花字动效。
2. **包装元素缺失**：转场只有硬切；片头卡/结束卡/进度条/数据图表/角标全靠临时拼。
3. **迭代回路长**：改一个样式 → 跑 ffmpeg → 全片重编 → 肉眼看结果，无实时预览。
4. **封面**：PIL 拼贴，无法复用影片视觉资产。
5. **类型扩展难**：新增"数据报告/榜单/日报"类视频时，ffmpeg 链路无法表达图表动画。

---

## 2. Remotion 核心调研结论（2026-09 现状）

### 2.1 版本与架构

- 当前稳定 **4.0.529**（2026-09-25），全包版本号锁定一致；5.0 已有迁移指南但未发布（发布日未宣布）。
- 渲染管线：webpack bundle → **chrome-headless-shell**（自动下载到 `node_modules/.remotion/`，非 Puppeteer）N 个并发 tab 逐帧截图（默认 JPEG）→ **Rust compositor** 调**自带 FFmpeg** 编码混流。**不依赖系统 ffmpeg**——天然绕开本机 PATH 上 Octave 的 ffmpeg 4.2.11 陷阱。
- **NVENC 硬编码**：4.0.484 起 Windows 自带 FFmpeg 支持 `h264_nvenc`/`hevc_nvenc`（`hardwareAcceleration: "if-possible"`，驱动 525+ 即可）。注意硬编时 `crf` 无效，改用 `videoBitrate`（官方建议 1080p 约 8M 起，竖屏高码率建议 12–16M）。
- 并发 = 并行浏览器 tab，默认 CPU 线程数一半，`npx remotion benchmark` 实测选优；渲染基本是 CPU/解码瓶颈，GPU 只参与编码。
- Studio（`npx remotion studio`）已进化为可视化编辑器：画布点选拖拽、CSS/props 关键帧、Inspector——**替代"改代码→重跑→肉眼看"的迭代回路**。

### 2.2 对本方案最要紧的 API

- **数据驱动**：zod schema 挂在 `<Composition schema={...}>` 上，`calculateMetadata` 由 props 动态算时长/尺寸；CLI `--props=x.json` 或 Node API `renderMedia({inputProps})`。**一次 bundle 无限次渲染**（逐次 bundle 是官方点名的反模式）。
- **AI 片段接入**：`<OffthreadVideo>`（渲染时服务端精确抽帧）支持 `trimBefore` / `durationInFrames` 帧级裁剪、`volume`（可随帧变化）、`muted`、`playbackRate`；本地文件走 `staticFile()`（`public/` 目录）。注意 `trimAfter` 已废弃 → 用 `durationInFrames`；不支持倒放与 loop（有 `<LoopableOffthreadVideo>` 变通）。
- **新 `<Video>`（@remotion/media）**：WebCodecs/Mediabunny 解码更快，但 2026-09 有多个 Windows 卡住 issue（#11018/#11020 已修，#11393 客户端渲染路径仍 open）——**保守起见本地渲染先用 `OffthreadVideo`**。
- **字幕**：`@remotion/captions`（MIT：SRT/VTT 解析、`Page`/`Caption` 类型）+ `@remotion/install-whisper-cpp`（本地 whisper.cpp，token 级时间戳，跨平台含 Windows）。官方 `template-tiktok` 是逐词卡拉OK字幕参考实现。
- **封面/静帧**：`renderStill()` 单帧出 PNG/JPG——封面模板与影片共用视觉资产。
- **转场**：`@remotion/transitions`（fade/slide/wipe/flip/clock-wipe/blurSlide 等）+ `<TransitionSeries>`。
- **效果**：`@remotion/effects`（lut() 调色、zoom-blur、color-key、pixelate）、`@remotion/gsap`、`@remotion/motion-blur`。

### 2.3 许可证（精确）

- **免费**：个人、非营利、评估期、**≤3 人营利组织**——含商业成片。按**人数**而非收入判定。本工作室（单人）完全免费。
- 4 人起需 Company License：Creators $25/月/席 或 Automators $0.01/渲染（$100/月起）。
- **5.0 预告**（未生效）：外包人员计入人数；渲染 API 必须传 `licenseKey`（免费用户传 `"free-license"` 字符串即可）。
- 核心（remotion/renderer/bundler/player/transitions/media）为 Remotion License；**captions、media-utils、shapes、whisper-webgpu、video-matting、gsap 为 MIT**。

### 2.4 Windows 注意事项

- 官方支持 win64；Node ≥16（本机 v24 ✓）。路径短（`E:\Minimax-H3\studio` ✓，避开 OneDrive 同步目录——社区高频翻车点）；深路径可能撞 `ENAMETOOLONG`。
- compositor 二进制未做微软签名 → 首次运行可能弹 SmartScreen（一次性放行）。
- 首次渲染前 `npx remotion browser ensure` 预下载 chrome-headless-shell。
- 中文字体：headless Chrome 用系统字体（微软雅黑/黑体可用），稳妥做法是把字体文件放 `public/fonts/` 用 `@font-face` 自托管（`.ttc` 建议转 ttf/woff2，`simhei.ttf` 可直接用），配 `delayRender` 等待字体就绪。

### 2.5 备选方案对比（为什么是 Remotion）

| 方案 | 状态（2026-09） | 结论 |
|---|---|---|
| **Remotion 4.x** | 日更级活跃，61k★ | ✅ 唯一同时满足：schema 驱动、并行渲染、Windows 本地、自带 ffmpeg+NVENC、消费成品片段、字幕生态、Agent 工具链 |
| Editly | 5.5k★，实质停更（2025-05） | 表达力差距大，ffmpeg 版本脆弱 |
| MoviePy 2.x | 活跃（14.9k★） | 适合 Python 胶水/校验，无并行帧模型、无预览、无模板体系 |
| FFCreator | 停更（2024-12） | 架构相似但生态小 |
| Clapper | 半停滞（2025-08） | 编辑器 UI，非嵌入引擎 |
| HyperFrames（54k★，Apache-2.0） | 活跃（HTML/GSAP→视频） | Remotion 的替代 runtime，agent 生态强；但缺 schema 校验/Studio/许可证成熟度，作为观察项 |

---

## 3. 开源 "AI + Remotion" 生态：五种主流架构与借鉴点

| 项目 | Stars/许可 | 架构 | 对本项目的借鉴 |
|---|---|---|---|
| **short-video-maker** (gyoridavid) | 1.4k / MIT | Kokoro.js TTS → whisper.cpp 词级时间 → Remotion 字幕 → 拼装；MCP + REST | ⭐ **直接对齐我们的栈**：Kokoro+Whisper+Remotion 循环的现成参考 |
| **OpenMontage** | 61.8k / **AGPL-3.0** | Agent 即编排器：YAML 导演技能 + Python 工具 + ComfyUI(Wan) 出片 + Remotion 合成；ffprobe 自检+人工门 | 借鉴其**管线清单/skill 文件组织**与"渲染后自动 QA"；**AGPL——只学架构，不抄代码** |
| **video-podcast-maker** | 1.6k / MIT | 剧本 → TTS 产出 wav+SRT+`timing.json` → React 4K 渲染字幕 → ffmpeg 混 BGM → 多平台发布 | 字幕/口播同步的 timing.json 模式；B 站/抖音发布环节 |
| **video-shotcraft** | 9.9k / Apache-2.0 | 157 张"镜头配方卡" → agent 选卡 → 参数化 Remotion 组件 | ⭐ 镜头配方卡 = 我们的 shot 模板库设计原型 |
| **Pixelle-Video** | 28.5k / Apache-2.0 | LLM 文案 + ComfyUI 视觉 + 多引擎 TTS 全本地（国内项目） | 国内最接近的"LLM+ComfyUI+TTS"参照系 |
| **OpenChatCut** | 2k / AGPL-3.0 | agent 经命令/MCP 提案编辑不可变时间线，Remotion 预览+导出 | 人机协同精修的 Phase 4 方向 |
| **MoneyPrinterTurbo** | 126.8k / MIT | MoviePy 路线（非 Remotion） | 只读其 prompt→脚本→TTS 实践；架构不采纳 |
| 官方 AI 工具链 | — | **Agent Skills**（`npx skills add remotion-dev/skills`，12 个 skill，官方 MCP 已弃用）；结构化输出 `{code,title,durationInFrames,fps}` + zod 校验重试；"codegen 在内、schema 在外" | ⭐ 模式 C 的官方实现路径 |

**五种架构模式**（业界收敛结果）：
1. Agent-as-orchestrator（技能文件+工具+门禁）——天花板高，不确定性高，token 消耗大；
2. 自由 codegen + JIT 编译 + 重试——适合"描述即动画"类产品；
3. **schema 约束数据 → 参数化模板**——批量生产最可靠最便宜，表达力上限=模板质量；
4. 字幕优先的 shorts 工厂——跑量模式；
5. Agent-NLE（命令式时间线提案）——人机精修，工程量最大。

**本方案采纳：以模式 3 为骨架（生产），模式 1/2 为模板工厂（扩产能），必要时演进模式 5（精修）。** 这与 Remotion 官方建议一致。第四路调研（AI 片段组装）独立得出了同一结论：业界最稳健的模式正是"**TTS 锚定时间线 JSON → Remotion 渲染**"（short-video-maker / claude-video-kit 均如此），本方案的 timeline v2 契约与该模式同构。

---

## 4. 总体架构设计

### 4.1 分层

```
┌─────────────────────────────────────────────────────────────────┐
│  编排层  Claude Code（+ Remotion Agent Skills、本项目 skills）      │
│          剧本→分镜→timeline_v2 生成 · 新模板 codegen · QA 审读      │
├──────────────────────────────┬──────────────────────────────────┤
│  AI 资产生成层（GPU，现有不动）   │  合成渲染层（CPU+NVENC，新增）        │
│  ComfyUI + MiniMax-H3         │  Remotion 4.0.529 (studio/)       │
│  r2v / fl2va + Turbo LoRA     │  模板组件库 + zod schema 注册表      │
│  Kokoro / Qwen3-TTS           │  OffthreadVideo 装配 · transitions │
│  Real-ESRGAN 超分(逐片段)       │  captions 字幕 · renderStill 封面   │
│  ffmpeg 混音(mix_audio:保留)    │  Studio 实时预览                    │
├──────────────────────────────┴──────────────────────────────────┤
│  数据层  timeline_v2.json（zod schema = 唯一契约，Python/TS 双端校验）│
├─────────────────────────────────────────────────────────────────┤
│  质量层  qa_final.py 门禁（复用，扩展 remotion 路径）+ loudness/规格   │
└─────────────────────────────────────────────────────────────────┘
```

职责划分原则：**GPU 重活与响度工程留在 Python 侧（已验证、QA 已锁），视觉表达与装配全部上 Remotion。**

### 4.2 数据流（模式 A：结合）

```
[现有] ComfyUI 片段 → select_takes → 04_video_selected/*.mp4
[改造] sr_pipeline_v2 逐片段超分 → 04_video_selected_sr/<SHOT>_1080.mp4      ← 改为逐片段（见 §7.3）
[现有] gen_tts/gen_audio_assets/mix_audio → 05_audio + premixed.m4a          ← 混音链不动
[新增] build_timeline.py v2 → 00_project/timeline_v2.json
       └─ jsonschema 校验（schema 由 studio 的 zod 导出，杜绝双端漂移）
[新增] stage_assets.py：硬链接资产 → studio/public/jobs/<job_id>/（同盘零拷贝）
[新增] node studio/bin/render.mjs --comp DramaVertical --props .../timeline_v2.json --out 07_edit/EP01_v3.mp4
[现有] finalize.py（mux 音频 -c:v copy、封面改走 renderStill）→ 09_final
[现有] qa_final.py（14 项门禁全部适用）
```

### 4.3 目录结构

```
E:\Minimax-H3\
├── studio\                          # Remotion workspace（Node，pnpm）
│   ├── package.json                 # remotion 等全家族 pinned 4.0.529
│   ├── remotion.config.ts           # NVENC/并发/字体配置
│   ├── bin\
│   │   └── render.mjs               # Node API 桥：--comp --props --out（含 bundle 缓存）
│   ├── src\
│   │   ├── Root.tsx                 # <Composition> 注册表（模板名→schema→组件）
│   │   ├── schemas\
│   │   │   ├── timeline-v2.ts       # zod 主 schema（唯一契约）
│   │   │   ├── report-data.ts       # 模式 B 数据类模板 schema
│   │   │   └── timeline-v2.schema.json  # zod→JSON Schema 导出物，供 Python 校验
│   │   ├── templates\
│   │   │   ├── common\              # CaptionLine/TitleCard/EndCard/LowerThird/进度条/封面框
│   │   │   ├── drama-vertical\      # EP01 类竖屏短剧（1080x1920@24）
│   │   │   ├── psa-wide\            # 辟谣/公益横屏（1920x1080@24）
│   │   │   ├── story-animation\     # 聊斋/国风叙事（1920x1080 / 2560x1440）
│   │   │   └── report\              # 数据报告/榜单/日报（模式 B，无 AI 片段）
│   │   └── styles\tokens.ts         # 自 burn_subtitles_v2.STYLES 移植的设计令牌
│   └── public\
│       ├── fonts\                   # 自托管中文字体（ttf/woff2）
│       └── jobs\<job_id>\           # 每次渲染的硬链接资产（渲染后可清）
├── ceo_mindread_ep01\               # 现有项目不动；build_timeline 升级 v2
├── scripts\
│   ├── stage_assets.py              # 资产硬链接 + job 清单
│   └── render_with_remotion.py      # Python→node 桥（subprocess），渲染后自动 qa
└── （其余现有结构不变）
```

---

## 5. Timeline Schema v2（核心契约）

原则：**v1 字段全兼容**（audio_events/sfx_events/subtitle_events/bgm 语义不变），v2 增加渲染所需信息。zod 是唯一权威定义，JSON Schema 导出物供 Python 侧 `jsonschema` 校验。

```ts
// studio/src/schemas/timeline-v2.ts（示意）
export const Transition = z.object({
  type: z.enum(['none','fade','slide','wipe','clockWipe','blurSlide']),
  durationInFrames: z.number().int().min(0).default(0),
});

export const Shot = z.object({
  id: z.string(),                        // "S01"
  file: z.string(),                      // jobs/<id>/S01_1080.mp4（超分后）
  trimBefore: z.number().int().default(0),       // 源片段起始帧
  durationInFrames: z.number().int(),            // 呈现帧数（= round(dur*24)）
  transitionIn: Transition.default({type:'fade', durationInFrames:12}),
  nativeAudio: z.object({                // H3 片段自带音频（默认弃用，可作环境声）
    use: z.boolean().default(false), volume: z.number().default(0.3)
  }).default({}),
});

export const SubtitleStyle = z.enum(['normal','inner','opening','special','inner_special','ending']);

export const SubtitleEvent = z.object({
  id: z.string(), text: z.string(),
  style: SubtitleStyle,
  start: z.number(), end: z.number(),          // 秒（v1 语义）
  words: z.array(z.object({ t: z.number(), d: z.number() })).optional(), // 词级(Phase 3)
});

export const TimelineV2 = z.object({
  version: z.literal(2),
  project: z.string(),
  template: z.enum(['drama-vertical','psa-wide','story-animation']),
  format: z.object({ width: z.number(), height: z.number(), fps: z.literal(24) }),
  totalDuration: z.number(),
  shots: z.array(Shot),
  audioBus: z.object({ premixed: z.string() }),   // mix_audio 产出的成品混音轨（单 <Audio>）
  subtitleEvents: z.array(SubtitleEvent),
  overlays: z.array(z.object({                    // 花字/角标/图片叠加(可选)
    kind: z.enum(['text','image','progress','lower-third']),
    start: z.number(), end: z.number(), payload: z.record(z.any()),
  })).default([]),
  cover: z.object({ template: z.string(), payload: z.record(z.any()) }).optional(),
});
```

要点：
- **混音产物作为单条 `audioBus.premixed` 进渲染**：Remotion 侧一个 `<Audio>` 对齐时间轴，避开 Remotion 无 loudnorm/sidechain 的短板；`nativeAudio` 留作后续在 Remotion 音频图里做环境声混合的口子。
- **帧数换算统一**：`durationInFrames = round(seconds * 24)`，总帧数 `ceil(totalDuration*24)`；边界漂移 ≤1 帧与现有 ffmpeg 链路等价。
- **样式令牌**：`styles.tokens.ts` 移植 `STYLES` 字典（字号/描边/颜色/y 位置），`qa_final.py` 的字幕宽度检查改读渲染侧导出的同源 JSON，双端仍一致。

---

## 6. 多类型视频模板矩阵

| 模板 | 分辨率 | 输入 | 来源项目 | 状态 |
|---|---|---|---|---|
| `drama-vertical` 竖屏短剧 | 1080×1920@24 | timeline_v2（H3 片段+TTS+心声样式） | EP01 | Phase 1 首发 |
| `psa-wide` 公益/辟谣 | 1920×1080@24 | timeline_v2（旁白+证据叠加+横幅） | piyao_2026 | Phase 2 |
| `story-animation` 叙事动画 | 1920×1080 / 2560×1440 | timeline_v2（旁白+章节卡+LUT/颗粒） | liaozhai / third_lantern | Phase 2 |
| `report` 数据报告/榜单 | 1080×1920 或 1920×1080 | report-data.json（纯数据，无 GPU） | 新类型 | Phase 3 |
| `daily-brief` 日报/资讯 | 1080×1920 | report-data.json | 新类型 | Phase 3 |
| `trailer` 预告混剪 | 任一 | timeline_v2 子集 + kinetic 标题 | 新类型 | Phase 3+ |

- **模式 B（独立）**：`report` / `daily-brief` 只吃 JSON 数据——LLM 填 schema 或脚本直出，Remotion 渲染，**不占用 GPU、与 H3 完全无关**，满足"可互相独立"。
- **模式 C（模板工厂）**：新模板由 Claude Code 生成（装 `remotion-best-practices` / `remotion-create` / `remotion-captions` / `remotion-render` 等 skill），Studio 预览调优，人工 review 后入库——之后它就是确定性资产，生产不再依赖 LLM。

---

## 7. 关键技术决策

### 7.1 字幕：从 PIL 逐帧烧录 → Remotion 组件

- Phase 1 平移：`subtitle_events`（行级）+ `tokens.ts` 样式，视觉对齐现有版本（QA 宽度检查沿用）。
- Phase 3 升级：TTS 音频过 whisper.cpp（`@remotion/install-whisper-cpp`，或 Python 侧 faster-whisper 出词级 JSON 进 `subtitleEvents[].words`）→ 逐词卡拉OK/弹跳样式（参考官方 `template-tiktok`）。心声样式可加打字机+低透明度动画，台词样式加逐词高亮。

### 7.2 音频：混音链完全保留在 Python 侧

`mix_audio_v4.py` 的 adelay→amix→sidechaincompress 鸭化→loudnorm(−14 LUFS 闭环)→alimiter 链是 QA 验证过的资产，且 Remotion 原生无响度归一/侧链能力 → **保留**，产物作为 `audioBus.premixed` 单轨进渲染。渲染若走 NVENC+视频流，finalize 用 `-c:v copy` mux 音频（与现状一致）。

### 7.3 超分：改"整片超分"为"逐片段超分"

现状：720p picture lock → 整片 Real-ESRGAN → 1080p。新链路：`04_video_selected` 逐片段 x2（768×1344→1536×2688→Lanczos 1080×1920）→ Remotion 以原生 1080p 装配。收益：转场/字幕在原生分辨率上合成（不再对已压缩整片二次编码），顺带消灭 720p 中间环节的画质损失。逐片段的模型热身开销（秒级）相对生成分钟级可忽略。

### 7.4 编码：先 x264 crf18 对齐 QA，NVENC 作提速选项

- 默认 `codec: h264, crf 18`（与 qa_final 现行规格逐字节对齐，`yuv420p` 为 Remotion h264 默认）。
- 提速选项：`hardwareAcceleration: 'if-possible'`（5090 NVENC）+ `videoBitrate: 14M~16M`，Phase 0 实测画质/速度后决定是否设为默认。

### 7.5 版本与迁移策略

- `package.json` **精确 pin 4.0.529**（全 @remotion/* 同版本）。5.0 发布后单独立项迁移（licenseKey 传 `"free-license"`、`<Video>` 新组件评估、media-parser→Mediabunny）。
- Python↔Node 契约只通过 `timeline-v2.schema.json` 文件耦合，任一侧升级不隐性漂移。

### 7.6 渲染桥（bin/render.mjs）

```js
// 伪码：bundle 缓存 + inputProps + 输出规格
const bundleLocation = await bundle({ entryPoint: './src/index.ts' });   // 进程内复用
const composition  = await selectComposition({ serveUrl, id, inputProps });
await renderMedia({ composition, serveUrl, codec: 'h264', crf: 18,
  inputProps, outputLocation: out, hardwareAcceleration: 'if-possible' });
```

Phase 1 用一次性进程（bundle ~10–30s，对 60s 成片可接受）；Phase 3 若批量出片，升级为常驻渲染服务（bundle 常驻 + 任务队列）。Python 侧 `render_with_remotion.py` 负责 staging→渲染→QA 三步串接与失败回滚（失败自动回退现有 v2 管线出片，保证交付永不中断）。

### 7.7 风险清单

| 风险 | 等级 | 缓解 |
|---|---|---|
| Remotion 渲染 60s×12 片段时间线性能未知（官方无基准） | 中 | Phase 0 首项任务：`remotion benchmark` 并发扫描 + NVENC/x264 A/B，不达标则降并发/换 OffthreadVideo 参数 |
| **MiniMax H3 Community License 有地域条款**（USA/EU/UK/KR 商用分发需申请；国内分发暂不受限） | 中 | 纯自用/国内分发不受影响；出海分发前补申请（huggingface.co/MiniMaxAI/MiniMax-H3 模型卡） |
| `@remotion/media <Video>` Windows 卡住（#11393 客户端路径 open） | 低 | 本地渲染统一 `OffthreadVideo`；5.0 后再评估 |
| compositor 未签名 → SmartScreen | 低 | 首次人工放行；写入环境文档 |
| 帧边界漂移（秒→24fps 取整） | 低 | 统一 round 规则进 schema 描述；QA 时长容差沿用 ±0.5s |
| 中文字体在 headless Chrome 的渲染差异 | 低 | 字体自托管 public/fonts + delayRender；QA 字幕宽度检查兜底 |
| 5.0 迁移（licenseKey/外包计数） | 低 | pin 4.0.529；单人免费不受影响；迁移独立排期 |
| OpenMontage 等 AGPL 代码污染 | 中 | 只读架构不复制代码；引入外部代码仅限 MIT/Apache |
| 学习成本（React/TS 栈 vs 现有 Python 栈） | 中 | 模板收敛为"数据进、片出"的使用方式；模板本身由 Claude Code+skills 维护 |

---

## 8. 生成层（H3 侧）配套演进

### 8.1 H3 模型背景（调研确认）

- 2026 年 8 月初开源，**33B dense 单流 "H3-Omni-Transformer"**（约 13B 在可预计算缓存的 AdaLN 分支）；H3-Encoder 复用 Qwen3-VL-32B 权重。我们手里两个工作流就是 **ComfyUI Day-0 官方模板**，对应两个开放 checkpoint：`H3-Base-FL2VA`（0/1/2 关键帧→视频，即 t2v/i2v/首末帧）与 `H3-Base-Ref2VA`（9 图+3 视频+3 音频全模态参考）。月下载 ~360 万，生态健康（city96 GGUF 量化、社区 Turbo LoRA、Dual-Clock Euler 采样器修复音频过曝）。
- **未开源**：H3-Context-IR（prompt 结构化）与 H3-Regenerate-2K（2K 二次精修）——API 专属；本地 2K 靠生成原生分辨率 + 超分链（现状即如此）。
- 许可证：Community License，**USA/EU/UK/KR 商用分发需提交申请表**；自用与国内分发不受限（已列入 §7.7 风险表）。

### 8.2 与 Remotion 层的配合

- **生成长度与呈现长度解耦**：H3 帧长 17k+5 的约束，被 timeline v2 的 `Shot.trimBefore/durationInFrames` 裁剪彻底解耦——生成略长、选片后裁到对白/节奏点上，不再被生成网格绑架。
- **片段原生音频**（32kHz 立体声，画面联合生成）：默认弃用（TTS 后配时间更可控），但保留 `nativeAudio` 口子作环境声/低成本 SFX；社区 Dual-Clock Euler 采样器可修音频伪影，值得列入 ComfyUI 侧试验项。
- **原生对白实验（远期）**：`<d>` token 中文对白生成稳定 → 对口型要求高的镜头可尝试"原生对白 + 字幕对齐转录"替代 TTS 后配，牺牲时间精度换取口型同步；timeline v2 裁剪机制已为此铺路。
- **参考图工作流升级**：用 Qwen-Image-Edit 生成多角度角色参考表（比当前 21 帧首帧法更规范）→ Ref2VA 每镜头引用；这是社区验证的 Ref2V 标准姿势。

### 8.3 TTS 演进（中文）

| 引擎 | 定位 | 备注 |
|---|---|---|
| **Kokoro-82M v1.1-zh**（现用） | 草稿与预设角色 | 8 个 zh 音色，CPU 实时级；无词级时间戳 |
| **IndexTTS-2**（B站） | 最终旁白/角色 | **精确时长控制**（"正好说 3.2s"）——镜头适配利器；零样本克隆+情感解耦；安装较挑剔 |
| VoxCPM | 快速上手备选 | `pip install voxcpm`，~7s 合成 |
| CosyVoice 2 | 流式/指令情感 | 紧随 IndexTTS-2 |

- **行业空白确认**：所有本地中文 TTS 都不输出词级时间戳；通行做法是**用自己的 TTS 产物过 whisper.cpp/whisperX 反推**（我们生成的旁白是干净音频，转录极其可靠）。中文逐字对齐建议 whisperX + 中文 wav2vec2。→ 直接支撑 Phase 3 卡拉OK字幕。
- 可选:需要精确卡点时优先 IndexTTS-2（时长可控）而非先 TTS 再裁。

### 8.4 备用/并行生成栈（不替代 H3，按需引入）

- **Wan 2.2 A14B MoE**（开源权重最新旗舰）：生态最深——VACE（姿态/深度控制）、Phantom（主体一致性）、MultiTalk（多说话人口型）、WanAnimate、musubi-tuner 双专家角色 LoRA、原生 FLF2V 首末帧链。需要口型同步、姿态控制或特定社区 LoRA 时引入。
- **HunyuanVideo 1.5（8.3B）**：快速草稿/占位镜头。
- 首末帧链接（镜头 N 末帧 = 镜头 N+1 首帧）社区标准做法，H3 FL2VA 原生支持；已知坑：长链 ~100 帧处回弹（Wan wrapper issue #1342）。

### 8.5 行业空白（本方案的自研价值点）

调研确认以下环节**没有现成开源方案**，是本项目需要自持的资产：
1. 端到端"AI 导演"（分镜规划+一致性+装配一体）不存在——所有可用系统都是单镜头生成 + 外部拼接；
2. 本地中文 TTS 词级时间戳不存在——需自建转录对齐环节（Phase 3）；
3. **Python↔Remotion 桥不存在标准件**——timeline v2 JSON 契约是本项目核心自研资产，值得文档化与测试覆盖。

---

## 9. 模式 B 示例：纯程序化数据视频（与 H3 完全独立）

```jsonc
// report-data.json（示意）
{
  "template": "report",
  "format": { "width": 1080, "height": 1920, "fps": 30 },
  "title": "2026 Q3 短剧市场速览",
  "stats": [
    { "label": "全网播放", "value": "48.2亿", "delta": "+12%" },
    { "label": "上新部数", "value": "1,204", "delta": "+7%" }
  ],
  "chart": { "type": "bar", "series": [ ... ] },
  "narration": { "audio": "public/jobs/x/narr.m4a", "captions": "public/jobs/x/narr.json" }
}
```

产出路径：Claude Code 填数据（或接入行情/表格）→ `render.mjs --comp Report` → 成片。分钟级、零 GPU、可无限换皮。

---

## 10. 分阶段实施计划

### Phase 0 —— 环境验证与基准（0.5 天）
1. `pnpm init` 建 `studio/`，pin `remotion@4.0.529` 全家族；`npx remotion browser ensure`。
2. 用 EP01 真实资产搭 60s/12 片段 dummy 时间线，跑 `remotion benchmark`（并发 4/8/12）与 NVENC vs x264 A/B；记录 ffprobe 确认 24fps/yuv420p/规格过 QA 检查项。
3. 中文字体（msyh 转 ttf/woff2 或 simhei.ttf）自托管渲染验证。
4. **产出：BENCHMARK_20260929.md（渲染耗时/编码参数/最终并发配置）。**

### Phase 1 —— EP01 包装层迁移（1–2 天）
1. `schemas/timeline-v2.ts` + JSON Schema 导出；`build_timeline.py` 升级写 v2（v1 字段兼容）。
2. `drama-vertical` 模板 MVP：OffthreadVideo 装配 + 行级字幕（tokens 移植）+ 开场/结束卡；无转场（先对齐现状）。
3. `stage_assets.py`（硬链接）+ `bin/render.mjs` + `render_with_remotion.py`（失败回退旧链）。
4. **验收：EP01_v3 全程新链出片，qa_final 14/14 PASS；与 v2 成片并排 A/B。**

### Phase 2 —— 全模板 + 转场 + 封面（2–3 天）
1. transitions（淡入淡出/闪白节奏点对齐 sfx_events）；`psa-wide`、`story-animation` 模板迁移。
2. 逐片段超分脚本改造；封面 `renderStill`（`08_cover` 模板化）。
3. overlays 体系（花字/角标/进度条）。

### Phase 3 —— 新类型 + 词级字幕 + 模板工厂（2–3 天）
1. `report` / `daily-brief` 纯程序化模板（模式 B 打通）。
2. 词级时间戳（whisper.cpp token 级；中文逐字对齐用 whisperX + 中文 wav2vec2）→ 卡拉OK字幕；心声打字机动效。
3. 安装 Remotion Agent Skills；沉淀本项目 skills（镜头配方卡：H3 prompt 模板 ↔ Remotion 组件一一对应）；新模板 codegen 工作流 + review 门禁。

### Phase 4（可选）—— 常驻渲染服务 / Player 预览 UI / 批量队列
- 批量产能需要时：bundle 常驻 + 任务队列 + `@remotion/player` 网页预览（或 Electron 模板做桌面壳）。

---

## 11. 附录：调研来源（关键）

- Remotion 官方：remotion.dev/docs/{ssr-node, parametrized-rendering, schema, offthreadvideo, media/video, captions, install-whisper-cpp, hardware-acceleration, gpu, chrome-headless-shell, ai/skills, ai/mcp, ai/generate, 5-0-migration}；LICENSE.md；releases（4.0.529）
- 许可：remotion.pro/license（≤3 人免费、按人头、$25/月/席、$0.01/渲染）；PR #3750（5.0 条款）
- Windows 证据：issues #10698（NVENC 自带 ffmpeg）、#11018/#11020/#11393（<Video> Windows stall）、#11784（签名）
- 生态项目：github.com/{gyoridavid/short-video-maker, calesthio/OpenMontage, Agents365-ai/video-podcast-maker, Vincentwei1021/video-shotcraft, ATH-MaaS/Pixelle-Video, 0xsline/OpenChatCut, harry0703/MoneyPrinterTurbo, remotion-dev/template-tiktok, remotion-dev/skills, heygen-com/hyperframes}
- H3 模型：huggingface.co/MiniMaxAI/MiniMax-H3（模型卡+Community License）；blog.comfy.org（H3 Day-0 support）；github.com/kijai/ComfyUI-WanVideoWrapper（备用栈生态）
- TTS：github.com/{RVC-Boss/GPT-SoVITS, index-tts（IndexTTS-2）, FunAudioLLM/CosyVoice2-0.5B, modelbest/VoxCPM, hexgrad/Kokoro-82M-v1.1-zh}；github.com/m-bain/whisperX
- 本机盘点：`ceo_mindread_ep01/00_project/{environment_report.md, timeline.json, dialogue.json}`、`scripts/{build_timeline, mix_audio_v4, burn_subtitles_v2, qa_final}.py`、`video_minimax_h3_{r2v,t2v}.json`
