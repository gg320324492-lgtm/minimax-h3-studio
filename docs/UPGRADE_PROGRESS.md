# 升级进度总账（Upgrade Progress）

> 总规划：[UPGRADE_MASTER_PLAN.md](UPGRADE_MASTER_PLAN.md)
> 本文档是本轮升级的唯一进度源，每完成一步打勾并记录数据/结论。
> 状态：⬜ 未开始 ｜ 🔄 进行中 ｜ ✅ 完成 ｜ ⏸️ 阻塞/搁置

---

## P0 — 全库审计与生产边界收敛　状态：✅ 完成

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 0.1 | 全库技术审计（只读，证据化） | ✅ | 12 条风险(R1-R12)+ 生产入口分类 + 28 脚本分类 + 硬编码计数(202/103/40) + 63 行可抽取共性；报告 docs/ARCHITECTURE_AUDIT_20260930.md |
| 0.2 | `pipeline_manifest.yaml` | ✅ | 系统模块/链A链B/上游手工/模板/工具/experiments 四分类+forbidden 清单/local_only 校验命令；experiments 28 脚本逐个定性 |
| 0.3 | 消灭「猜最新文件」+ 有界轮询 | ✅ | **R3 修复**：comfy_utils.fallback_newest 默认 True→False（生产严格，history 缺失即 None）；新增 wait_for_prompt(3600s deadline+异常守卫+进度日志)；4 个生产脚本(gen_office/gen_references/gen_reference_sheets/gen_keyframes_v3)的无限 while-True 全部替换；模块加载验证通过 |
| 0.4 | `config/` 配置集中化 | ✅ | config/paths.py（YAML+env 覆盖，4 级优先级）+ local.example.yaml；env 覆盖实测生效。**顺带修 R4**：ffmpeg_env 裸命令名不再把 CWD 注入 PATH（实测 CWD leaked=False，改为明确告警提示 Octave 陷阱） |
| 0.5 | 审计报告 + 旧流程可启动 | ✅ | 报告落盘；链A build_timeline + qa_final **16/16 PASS**；四脚本 import 正常 |
| 0.x | **R1 安全修复（审计外紧急）** | ✅ | 公开仓库泄露风险：实测发现「敏感文件已 gitignore」为假（规则段被历史重写覆盖），`git add -A` 会回带 40 个敏感文件 → 重加规则并逐条 check-ignore 验证 12/12，已推送 |
| 0.y | **R5 fit 默认值修复** | ✅ | emit_props `fit: fill` → `fit: auto`（SR 直出 fill / 原始片 cover），消除二次拉伸；piyao 验证为 cover |

**P0 验收**：旧生产流程仍能启动；manifest 落地；审计报告发布。

---

## P1 — 自动选片 TakeRanker　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 1.1 | 统一 Take 数据结构（seed/prompt_hash/workflow_hash/metrics/critic/status） | ⬜ | |
| 1.2 | Cheap Metrics（blur/exposure/black/duplicate/freeze/flicker/flow/artifact/text-contamination/subject） | ⬜ | |
| 1.3 | VLM Critic provider abstraction（6 帧采样 → 结构化 JSON） | ⬜ | |
| 1.4 | 综合评分（默认权重：adherence20/consistency15/temporal15/motion10/artifact10/exposure5/sharpness5/text5 + composition15） | ⬜ | |
| 1.5 | 替换 `select_takes.py` 的 T01 默认，保留人工 override 最高优先 | ⬜ | |
| 1.6 | 排名报告（联系表/HTML）+ 写入 manifest | ⬜ | |

---

## P2 — H3 Atomic Shot + Prompt Compiler　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 2.1 | `ShotSpec` schema（purpose/subject/environment/camera/motion/lighting/duration/reference/negative） | ⬜ | |
| 2.2 | Prompt Compiler（ShotSpec→H3 prompt，记录 version/seed/workflow/LoRA/steps） | ⬜ | |
| 2.3 | Shot 级重试（单镜头重生成，不重跑整集） | ⬜ | |

---

## P3 — Showcase Scene Graph　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 3.1 | `schemas/showcase-v1.ts` + JSON Schema 导出 | ⬜ | |
| 3.2 | 20 种 scene 类型注册 | ⬜ | video/kpi-hero/browser-window/browser-stack/dashboard/stat-card/card-grid/calendar/bar-chart/line-chart/area-chart/bubble-chart/rank-chart/slope-chart/heatmap/data-table/quote/data-plane-3d/logo/outro |
| 3.3 | Camera Model（perspective/translate/rotate/scale/focus 曲线，与组件 motion 分离） | ⬜ | |
| 3.4 | Motion Profile（premium/energetic/cinematic/minimal） | ⬜ | |

---

## P4 — FinanceShowcaseWide 模板　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 4.1 | 模板骨架 1920×1080@60fps（premium 语言，不复用 energetic 特效） | ⬜ | |
| 4.2 | Scene A — KPI Hero（count-up/odometer/eyebrow/micro-settle/自定义数字字体） | ⬜ | |
| 4.3 | Scene B — 3D Dashboard Stack（BrowserWindow/PerspectiveCard/DepthStack/CameraRig） | ⬜ | |
| 4.4 | Scene C — Big Number + 3D Columns（camera tilt/纵深柱阵/staged build） | ⬜ | |
| 4.5 | Scene D — Calendar / Data Grid（SVG calendar/高亮/mask reveal/表格动效） | ⬜ | |
| 4.6 | 扩展：Quote/Rank/Dashboard Overview/Data Plane/Window Wall/Logo/CTA | ⬜ | |

---

## P5 — Motion Design Foundation　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 5.1 | Camera primitives：CameraRig/DepthStack/ParallaxLayer/FocusLayer | ⬜ | |
| 5.2 | Layout：SafeArea/Grid/Stack/WindowFrame/Card | ⬜ | |
| 5.3 | Typography：KpiNumber/Odometer/AnimatedText/MaskText/Label | ⬜ | |
| 5.4 | Motion：MaskReveal/SlideReveal/ScaleReveal/DepthPush/CameraPush/CameraOrbit/SharedAxis/StaggerGroup | ⬜ | |
| 5.5 | Visual：SpecularSweep/SoftGlow/Vignette/NoiseTexture/GridBackground | ⬜ | |
| 5.6 | `motionTokens.ts` 集中 spring 预设（micro/standard/hero/slowCinematic/camera/overshoot/settle） | ⬜ | |

---

## P6 — Design System　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 6.1 | Palette tokens（background/surface/ink/accent/positive/negative/grid/border）+ premium-dark/light 主题 | ⬜ | 黑+米白+金/橙 |
| 6.2 | Typography roles（displayXL…annotation + numericDisplay/numericTable，全 tabular-nums） | ⬜ | |
| 6.3 | Spacing 尺度（4…96） | ⬜ | |
| 6.4 | Depth 层级（z0…zHero） | ⬜ | |

---

## P7 — 图表引擎　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 7.1 | 自研 SVG 图表：Bar/Line/Area/Slope/Bubble/Heatmap/RankTable/Sparkline/VolumeBars | ⬜ | |
| 7.2 | 统一 chart 生命周期（intro/settle/highlight/focus/exit） | ⬜ | |
| 7.3 | annotation/label 避让/数字格式/theme/stagger/emphasis | ⬜ | |

---

## P8 — Format 数据驱动　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 8.1 | `calculateMetadata` 返回 width/height/fps/durationInFrames | ⬜ | |
| 8.2 | 验证 1920×1080@60 / 1080×1920@60 / 3840×2160@60 | ⬜ | |

---

## P9 — Beat Grid + 高级音频同步　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 9.1 | BeatGrid（bar/beat/halfBeat/quarterBeat/accent/phrase） | ⬜ | |
| 9.2 | 动作绑定 grid（cut/camera settle/chart finish/number finish/card arrival/hit） | ⬜ | |
| 9.3 | Premium SFX profile（soft whoosh/UI click/tonal tick/muted impact/low air） | ⬜ | 替代每屏 whoosh+impact+flash |

---

## P10 — Visual QA　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 10.1 | `visual_qa.py` deterministic 规则（safe area/clipping/overflow/collision/font size/contrast/black/freeze/duplicate/blur/flicker/aspect/missing asset/broken font） | ⬜ | |
| 10.2 | VLM Critic（每 scene 抽 5 帧，多维评分 + problems + repair_suggestions） | ⬜ | |

---

## P11 — Auto Repair Loop　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 11.1 | Repair Planner（可改 padding/scale/font/chart width/color/timing/camera/stagger/duration） | ⬜ | |
| 11.2 | 锁定项保护（核心文案/品牌 logo/数值事实） | ⬜ | |
| 11.3 | MAX_REPAIR_ROUNDS=3 + scene 级重渲 | ⬜ | |

---

## P12 — Director Agent　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 12.1 | BriefParser→ReferenceAnalyzer→StyleBible | ⬜ | |
| 12.2 | ScenePlanner→Storyboard→showcase_v1.json | ⬜ | |
| 12.3 | Asset Router（每 scene 判 Remotion/H3/Image/Existing/Hybrid） | ⬜ | |

---

## P13 — Scene Cache / 增量构建　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 13.1 | `job_state.json`（scene 级 input/asset/render hash + qa_status + version） | ⬜ | |
| 13.2 | 改一个 scene 只重跑该 scene 的 preview/QA/final | ⬜ | |

---

## P14 — Render Worker / Fast Preview　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 14.1 | 长驻 bundle 的 render worker | ⬜ | |
| 14.2 | still/scene/draft/full 分级渲染（preview 540p30 快编码） | ⬜ | |

---

## P15 — SR 路由升级　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 15.1 | SR Router：程序化内容 native 直出免 SR；H3 走 sr_pipeline_v2 | ⬜ | |
| 15.2 | FlashVSR 仅纹理丰富镜头（hair/fabric/architecture/hero） | ⬜ | |

---

## P16 — 参考视频 Benchmark　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 16.1 | `reference_analyze.py` → `reference_analysis.json`（scene 边界/时长/色彩/布局/运动/相机/图表/字体/转场/密度/亮度/beat） | ⬜ | |
| 16.2 | 24–40s 四类 scene 视觉语言对齐 | ⬜ | 只复刻视觉语言，不复制品牌内容 |

---

## P17 — Showcase Demo　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 17.1 | 16:9 / 1920×1080 / 60fps / 45–60s 商业级 demo | ⬜ | 含 1–3 个 H3 cinematic shot |

---

## P18 — 最终 QA（四类）　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 18.1 | Technical / Layout / Motion / Visual 四层门禁 | ⬜ | |

---

## 变更记录

- 2026-09-30：升级总规划立项（docs/UPGRADE_MASTER_PLAN.md + UPGRADE_PROGRESS.md）。
- 2026-09-30：**P0 完成**。审计发现 12 条风险；当场修复 4 条高危：R1 公开仓库泄露（gitignore 失效，紧急推送）、R3 mtime 猜测+无限轮询、R4 CWD 注入 PATH、R5 fit 二次拉伸。产出 pipeline_manifest.yaml + config/ 配置层 + 审计报告。链 A 复测 16/16 PASS。**下一步 P1 TakeRanker**（select_takes T01 默认 → 自动评分选片）。
