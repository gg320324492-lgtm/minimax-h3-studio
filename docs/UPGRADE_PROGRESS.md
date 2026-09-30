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

## P1 — 自动选片 TakeRanker　状态：✅ 完成

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 1.1 | 统一 Take 数据结构 | ✅ | TakeMetrics dataclass：probe(尺寸/帧数/fps) + 9 项 0..1 指标 + hard_fail + redundant_with + notes；_sig 内部像素签名 |
| 1.2 | Cheap Metrics | ✅ | sharpness(Laplacian方差)/exposure(中灰)/not_black/motion(运动量甜区)/stability(亮度闪烁)/flow_jitter(Farneback流方差)/not_duplicate/artifact(饱和过曝+块效应)/subject_consistency(直方图漂移)。**12 帧均匀采样+256px 降采样**，226 帧与 56 帧同成本；单项失败降级不中断 |
| 1.3 | VLM Critic provider abstraction | ⬜ | 本轮未做（客观指标已能淘汰坏的；「都好里挑更好」需 VLM，留 P1.2 增量）。**关键发现**：客观指标对「都很好」的 take 无区分力——S06 两个 take 全部指标完全相同 |
| 1.4 | 综合评分 | ✅ | 9 项加权（0.05~0.10），权重集中在 motion/artifact/consistency；VLM 三维度(20/15/15) 留给 critic 阶段合并 |
| 1.5 | 替换 select_takes 的 T01 默认 | ✅ | 无 override→ 调 TakeRanker（`_auto_rank()`）；override 仍最高优先（实测 human override 生效）；**缺 take 改 fail-closed**（exit 1 + 不写 manifest，旧代码静默 continue 会让整集变短） |
| 1.6 | 排名报告 + manifest | ✅ | `take_ranking.json` + `take_report.md`（逐 take 指标表）+ `contact_sheet.html`（每 take 4 帧缩略图，黄框=选中，红=硬失败，灰=冗余）；manifest 写回 source_take/duration/frames/ranking_score |
| 1.7 | 真实数据验证 | ✅ | **S05A 自动改选** T01(0.725)→v1(0.881)：T01 的 stability=0.01 严重闪烁是真缺陷；**S06_T02 判定冗余**——像素差 0.0，同 seed 重复生成，25 分钟 GPU 完全浪费；S05A top-2 差 0.002 → 正确标记 needs_human_review |
| 1.8 | 回归修复 | ✅ | auto 路径下 `take` 变量为 None 导致 source_take 写空 → qa_final 崩溃；改用 `src.stem` 后 16/16 PASS |

---

## P2 — H3 Atomic Shot + Prompt Compiler　状态：✅ 完成（ShotSpec 字段待人工补全）

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 2.1 | `ShotSpec` schema | ✅ | pipeline/shotspec.py：id/purpose/duration_target_s/generation_frames/seed_base/takes/subject/action/environment/camera/lighting/style/references/negative/extra。校验含 **17k+5 帧格**（22/56/124/141/226 通过，100/55/60/130 拒绝）与 **原子性**（剪辑语义检测） |
| 2.2 | Prompt Compiler | ✅ | pipeline/prompt_compiler.py：ShotSpec→H3 prompt，**确定性**（同 spec 逐字节相同）+ sha256 指纹；结构化模板零 prompt 字面量；否定去重（"no text artifacts" → "Avoid: text artifacts"）；读写 gitignored JSON |
| 2.3 | 原子性检测（真实数据） | ✅ | **修正了一个共同误判**：EP01 全部 11 个 prompt 实际都是原子的。S06 的 "Two-shot medium close-up" 是电影术语的**双人同框镜头**（two-h shot），不是两次剪辑；S01/S02/S05B 的 "then" 是单镜头内的连续表演。初版正则把这些误判为非原子，收紧为只匹配剪辑语义（cut to / 镜头切 / two-shot: 冒号形式）后**误报归零、真非原子仍全抓** |
| 2.4 | ShotSpec 骨架 | ✅ | migrate_shotspecs.py → `00_project/shot_specs.json`（11 specs，含结构化字段空位 + prompt_source 指针）；**待人工补全** subject/action/camera 后即可编译 |
| 2.5 | P2 前置契约（复验要求） | ✅ | 9 项测试锁住：编译器零 prompt 字面量、生成脚本无 prompt、数据文件不入库、pipeline/ 已入库、原子性正反例、17k+5 正反例、确定性、否定去重、端到端形状 |

**P2 遗留（需人工）**：`00_project/shot_specs.json` 的结构化字段（subject/action/environment/camera/lighting/style）为空位——拆分与镜头语言是创作决策，不从文本猜测。补全后跑 `prompt_compiler.py` 即可产出编译好的 prompt JSON 供 `gen_keyframes_v3.py` 使用。

**P2 未做**：shot 级重试（单镜头重生成不重跑整集）——依赖 ShotSpec 填完后的 shot 状态记录，随 P13 Scene Cache 一起做更合理。

---

## P3 — Showcase Scene Graph　状态：✅ 完成

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 3.1 | showcase-v1 契约（JSON Schema + zod 镜像） | ✅ | pipeline/schemas/showcase-v1.schema.json（draft-07）+ studio/src/schemas/showcase-v1.ts。20 种 scene 类型、Camera（perspective/translateXYZ/rotateXYZ/scale/focus 各自独立轨道）、Motion（premium/energetic/cinematic/minimal）、Transition、StyleBible、format 元数据驱动 |
| 3.2 | Python 加载/校验/时序推导 | ✅ | pipeline/scene_graph.py：7 类错误全部抓出（重复 id/未知类型/零时长/坏 camera 轨道/非法 fps/未知 motion profile/空 scenes）；`resolve()` 推导 startFrame；`generative_scenes()` 按类型路由 H3 vs 程序化 |
| 3.3 | Camera 与组件 motion 分离 | ✅ | camera 独立 schema，组件动效走 motion.preset —— P3 设计规则已编码进契约 |
| 3.4 | 双端不漂移 | ✅ | tests/test_showcase_schema_parity.py：scene 类型/camera 通道/generative 路由三处 Python↔TS↔JSON Schema 对照（7 项） |
| 3.5 | 卡点量化（两轮复验修复） | ✅ | **复验两次各抓出一个我漏报的问题**。第一轮：误差单调累积（每场 +0.43 帧，10 场 3.86 帧/64ms）。第二轮：`floor` 修掉重叠后，`round` 起点配 `floor` 时长在 frac≥0.5 时必然差 1 帧 —— **重叠变成了同量级的空隙**，而 `startFrame >= prev.endFrame` 断言天然看不见空隙。**根因不是选 round 还是 floor**：`round(a)+round(b) ≠ round(a+b)`，任何「起点一种舍入+时长另一种」的组合都会留 1 帧缺陷。**最终解法是结构性的**：在拍空间算出每场的起止边界，时长 = end − start，于是 start[i+1] == end[i] 由构造保证，重叠与空隙**同时不可表达**；漂移仍 ≤0.5 帧且不累积。配套：`on_beat()` 容差改半帧（原半拍宽松 29 倍）；`beat_aligned_durations` 改测 resolve() 实际输出；resolve 输出新增 `adjusted` 标记，CLI 用 `*` 显式暴露「声明 801f → 实际 800f」的量化差异。**流程教训（本项目第三次同类问题）**：mtime→严格模式、round→floor 都是在二元选项里换边；正确解法在选项之外——「让错误在结构上不可表达」，而不是选对参数 |
| 3.6 | 样例图谱 | ✅ | pipeline/examples/showcase_demo.json：对齐参考片 24-40s 的四类代表 scene（kpi-hero / browser-stack / dashboard / calendar），1920x1080@60、13.35s、**纯程序化零 H3** |

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
- 2026-09-30：**P1 复验裁定（独立取证）**。R-01/R-02/R-03 三工单全过；从仓库外 `/tmp` 跑测试 20 passed 证明可移植性（非仅 grep）。**阈值安全性用真实数据裁定**：9 对真实 take 的像素距离分布 = `{0.000} ∪ [34.5, 67.2]`，中间为空 —— 0.5 精确落在真重复上，距最近的真实不同 take 有 34.5 倍余量。
  - **新事实**：`03_video_raw_v2_archive/S01/S01_T02.mp4` 距 S01_T01 为 67.175，是**真正不同的生成而非重复** —— 是被 T01 硬默认埋掉的**有效素材**，不是浪费的 GPU。P1 价值的第二次独立确认。
  - **已知边界一（样本量薄）**：真实数据仅 9 对，其中真重复仅 1 例（n=1）。后续每积累多 take 镜头应重测该分布。
  - **已知边界二（语义已收窄）**：0.5 只抓「逐像素完全相同」，不再抓「近重复」。若将来出现「同 seed + 非确定性采样器」的重跑（距离小但非零）会漏检。已写入 `rank_takes.py` 阈值注释。
- 2026-09-30：**P1 完成**。TakeRanker 上线：9 项客观指标 + 像素级冗余检测 + 人工 override 最高优先 + fail-closed。EP01 实测：S05A 自动改选(闪烁缺陷 take 被淘汰)、S06_T02 判定同 seed 冗余(像素差 0.0)。select_takes 全 12 镜头走自动排名，QA 16/16 PASS。**边界认知：客观指标只能淘汰坏的，无法在「都好」里挑出更好的——S06 两 take 全指标相同，VLM critic 留作增量。**
