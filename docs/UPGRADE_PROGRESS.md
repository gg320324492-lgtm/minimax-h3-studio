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


**以下为 P3 立项时的原始清单，已被上表取代，不计入任务**（编号与上表重复、状态全为 ⬜，任何按任务行统计的读法都会把它算成未完成）。保留原文以供对照，故行号加删除线、状态改为 `—`。

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| ~~3.1~~ | `schemas/showcase-v1.ts` + JSON Schema 导出 | — | |
| ~~3.2~~ | 20 种 scene 类型注册 | — | video/kpi-hero/browser-window/browser-stack/dashboard/stat-card/card-grid/calendar/bar-chart/line-chart/area-chart/bubble-chart/rank-chart/slope-chart/heatmap/data-table/quote/data-plane-3d/logo/outro |
| ~~3.3~~ | Camera Model（perspective/translate/rotate/scale/focus 曲线，与组件 motion 分离） | — | |
| ~~3.4~~ | Motion Profile（premium/energetic/cinematic/minimal） | — | |

---

## P4 — FinanceShowcaseWide 模板　状态：✅ 完成（四类代表 scene 已渲染验证）

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 4.1 | 设计系统 tokens | ✅ | `design/tokens.ts`：PALETTE（premium-dark/light，黑+米白+金，语义色仅用于正负）、TYPE（displayXL→annotation 9 个角色 + tabular 数字）、SPACE/RADIUS/DEPTH/SHADOW/MOTION。**所有数值按设计高 1080 定义、随 format 缩放**——同一图谱 1080p 与 4K 出同一张图 |
| 4.2 | CameraRig（2.5D 摄像机） | ✅ | `common/CameraRig.tsx`：perspective + translateXYZ/rotateXYZ/scale/focus 各自独立轨道，接受常量或 [from,to]；**相机运动与组件动效分离**（premium 相机 2.6s 缓出，组件各自 pop）；自带 cubic-bezier 求解器避免为一条曲线引依赖 |
| 4.3 | Scene A — KPI Hero（参考片 24s） | ✅ | 超大 tabular 数字 + eyebrow 遮罩上移 + 4 次方缓出 count-up + delta 胶囊 + 金色下划线生长；**刻意不用 shake/白闪/RGB split** |
| 4.4 | Scene B — Browser Stack（26-30s） | ✅ | 三个浏览器窗口分处不同 translateZ 平面 + 反向 rotateY，错峰入场；含 MiniBars / Sparkline（strokeDashoffset 描线） |
| 4.5 | Scene C — Big Number + Columns（32s） | ✅ | 巨数压柱阵之上；柱高由 seed 确定性生成（同图谱必出同画面）；金色高柱带辉光 |
| 4.6 | Scene D — Calendar / Data Grid（34-38s） | ✅ | 30 格月历，值由 seed 确定，高亮格最后到达并带辉光；逐格 stagger |
| 4.7 | P8 元数据驱动（提前兑现） | ✅ | `showcaseMeta` 从图谱读 width/height/fps/durationInFrames；实测 1920×1080@60、801 帧。**踩到并修掉一个隐蔽坑：Remotion 4.0.529 的 calculateMetadata 收到的是参数对象 `{props, defaultProps,...}` 而非 props 本身**，直接当 props 解析会永远走回退分支 |
| 4.8 | **style_bible 接线**（复验要求，P5 前置） | ✅ | 复验发现图谱声明的 palette/typography/motionLanguage/cameraLanguage **全部被忽略**——四个 scene 静态 import TS tokens，声明式图谱只能驱动「有哪些 scene、多长、画什么内容」，不能驱动「长什么样」。字段名还三方漂移（schema/Python=`style_bible`，TS=`styleBible`），zod 默认 strip 使其静默失效。**修法**：新增 `design/styleBible.tsx`（resolveStyleBible 按默认键过滤合并 + React Context + `useDesign()` 别名钩子），场景一律走 context；字段名统一为 `style_bible`。**验证**：只改图谱 accent 色与 KPI 字号，渲染结果真实改变（截图对比金色→青色、232→190px）。4 条测试锁住（字段名一致/scene 不得直接 import tokens/主模板必须传图谱值/合并必须按已知键做类型校验） |
| 4.9 | 视觉缺陷修复 | ⚠️ **一次假账，两次更正** | Browser Stack 右边缘裁切 + Data Columns 标题叠压。**第一次"已修"是假的**：修复当时确实应用并目检通过，但 P5 迁移风格时执行了 `git checkout .../scenes/`，把未提交的布局改动一并回滚，之后未复验就写下了"已修"（commit 532b584 与本表 4.9 同时声称「间距 330→250、窗宽 560→520」）。复验官以「代码里搜不到 250/520」+自行重渲双重取证推翻。**现已真正修复并重渲抽帧确认**：间距 250、窗宽 520、translateZ 110；Data Columns 柱宽 44、场高 480、标题 `translateY(-330*s)` 上移 |

**流程教训（本项目第二次「记为已修但无产物」）**：第一次是 P0 的 `check_contract` 假通过，本次是布局修复被自己的 `git checkout` 回滚后未复验即记账。**测试网接不住这类缺陷**——布局问题本就不在单元测试能力范围内，靠抽帧目检。**今后记账规则：任何"已修"必须附可复现证据（具体代码值 + 抽帧截图路径），且清理工作树的操作后必须重验受影响项。**

**第三次同类问题（同一轮内）的根因，比前两次更基础**：前两次是"改了没复验"和"被 git checkout 回滚"，这次是**改错了文件对象**——改了 gitignore 的暂存副本而不是入库的源文件，于是改动在产物里根本不存在。凡涉及"图谱/配置/数据"的调整，必须先确认目标文件是否入库（`git check-ignore`），改在 source-of-truth 上。

**P4 遗留（属 P5 motion foundation 的工作）**：场景切换目前是硬切（transitionIn/out 字段已在契约里但未实现）；KPI 的 eyebrow/主体是整块淡入而非分层；无音频绑定；**parity 测试仍只锁类型名不锁字段级（P8 前必须补）**；`SHOWCASE_DEFAULTS` 与 demo 图谱是两份内容不同的源——前者仅作 Studio 占位样例，已在代码注释标明。

**P4 修复记录**：复验指出三处——① style_bible 未接线（架构级，已修，见 4.8）② Browser Stack 整簇偏右、Errors 窗口被右边缘裁切（横向间距 330→250、窗宽 560→520，已修）③ Data Columns 标题压柱阵且仅占画面 25%（重标定尺度 + 标题上移；根因之一是模板字符串里 `-330 * s` 未插值 `$`，CSS 收到非法值后整条 transform 被丢弃——这类"静默失效"值得警惕）。


**以下为 P4 立项时的原始清单，已被上表取代，不计入任务**（编号与上表重复、状态全为 ⬜，任何按任务行统计的读法都会把它算成未完成）。保留原文以供对照，故行号加删除线、状态改为 `—`。

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| ~~4.1~~ | 模板骨架 1920×1080@60fps（premium 语言，不复用 energetic 特效） | — | |
| ~~4.2~~ | Scene A — KPI Hero（count-up/odometer/eyebrow/micro-settle/自定义数字字体） | — | |
| ~~4.3~~ | Scene B — 3D Dashboard Stack（BrowserWindow/PerspectiveCard/DepthStack/CameraRig） | — | |
| ~~4.4~~ | Scene C — Big Number + 3D Columns（camera tilt/纵深柱阵/staged build） | — | |
| ~~4.5~~ | Scene D — Calendar / Data Grid（SVG calendar/高亮/mask reveal/表格动效） | — | |
| ~~4.6~~ | 扩展：Quote/Rank/Dashboard Overview/Data Plane/Window Wall/Logo/CTA | — | |

---

## P5 — Motion Design Foundation　状态：✅ 完成（动效收敛 + 转场实现）

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 5.1 | 集中 motionTokens（按语义命名） | ✅ | `design/tokens.ts`：SPRINGS 六个意图命名（settle/pop/land/reveal/hero/linear）+ durations + **四个 profile**（premium/energetic/cinematic/minimal，各自 stagger/spring/ease）。**不再按物理参数命名**——场景问「settle」而不是「damping:200」 |
| 5.2 | Motion primitives | ✅ | `common/primitives.tsx`：Reveal（标准入场）/ Stagger（错峰）/ MaskReveal（遮罩上移）/ SpecularSweep（光扫）/ VignettePulse（暗角脉冲） |
| 5.3 | 转场实现（兑现契约字段） | ✅ | `SceneEnter`：fade / mask-wipe / depth-push / dissolve，**全部帧内**——不消耗相邻场景的时间，因为那会把下游字幕/音频/节拍整体移位（ffmpeg 时代的铁律）。`transitionIn` 字段终于有人读了 |
| 5.4 | 场景动效收敛 | ✅ | 三个场景的 7 处手写 spring 全部换成语义 token；**修掉一个遮蔽 bug**：prop 名叫 `spring` 会盖掉 remotion 的 `spring()` 函数，导致 `spring({...})` 变成调用字符串（TS 报 "not callable" 才暴露），已改名 `springName` |
| 5.5 | 测试 | ✅ | 5 条：无手写 spring 物理 / token 按意图命名 / 转场必须帧内 / primitives 不得遮蔽 spring / 每个 scene 必须用 style bible + motion |

**P5 遗留**：charts 组件集（P7）、Design System 正式化（P6）、scene 转场只实现了 in 未实现 out、reveal 原语尚未接入四个场景（已可用未全用）。


**以下为 P5 立项时的原始清单，已被上表取代，不计入任务**（编号与上表重复、状态全为 ⬜，任何按任务行统计的读法都会把它算成未完成）。保留原文以供对照，故行号加删除线、状态改为 `—`。

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| ~~5.1~~ | Camera primitives：CameraRig/DepthStack/ParallaxLayer/FocusLayer | — | |
| ~~5.2~~ | Layout：SafeArea/Grid/Stack/WindowFrame/Card | — | |
| ~~5.3~~ | Typography：KpiNumber/Odometer/AnimatedText/MaskText/Label | — | |
| ~~5.4~~ | Motion：MaskReveal/SlideReveal/ScaleReveal/DepthPush/CameraPush/CameraOrbit/SharedAxis/StaggerGroup | — | |
| ~~5.5~~ | Visual：SpecularSweep/SoftGlow/Vignette/NoiseTexture/GridBackground | — | |
| ~~5.6~~ | `motionTokens.ts` 集中 spring 预设（micro/standard/hero/slowCinematic/camera/overshoot/settle） | — | |

---

## P6 — Design System　状态：🔄 进行中

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 6.1 | **双图谱治理**（复验提出） | ✅ | 新增 `studio/scripts/stage_showcase.py`：图谱 → `public/jobs/<job>/` 的**唯一**合法通道，附 `.staged-from.json` 指纹边车（对语义内容哈希，忽略键序/缩进）。**规则确立：CLI 渲染一律 `--props` 指向入库源图谱；暂存副本只为 Remotion Studio 存在（需 HTTP 提供 props）**。漂移可检测（源改了/副本被手改都会报 DRIFT） |
| 6.2 | per-window 构图参数上图谱 | ✅ | 图谱 `layout` 新增 `spreadX/spreadZ/perWindowRotateY/windowWidth/windowHeight/equalOnScreen`，组件读它们（保留默认值兼容旧图谱）。**产物可核验**：`git diff pipeline/` 有真实 diff，渲染用**入库源图谱**。参数确实生效（窗口簇收紧、扇形可见）。**归因更正：原记录的「光学重心偏右 = 近端窗口被透视放大」不是主因** —— 见 6.2b，真正的缺陷有三个，见下 |
| 6.2b | Browser Stack 真正居中 | ✅ **已修，量到像素** | 上一条的归因是错的。量渲染帧后发现三个缺陷：<br>**① `translate(-50%,-50%)` 是空操作** —— 包裹层唯一子元素是 `position:absolute`，自身塌成 0×0，百分比解析为 0，每个窗口以**左上角**挂在画面中心向右下生长，整簇落在右下象限。源码里那句「without this the windows hang off the right edge」描述的正是此现象，**修复写了但从未生效**，源码读不出来。<br>**② 改为屏幕空间排版、逐帧反解 CSS**（`cssXForScreenX` 按**绝对**深度解 x —— 相机自己的 translateZ 会改变每个窗口的深度；`screenScaleFor` 按物体自身平面解 scale）。居中从此是布局的结构性质，不是调出来的数。<br>**③ `screenScaleFor` 返回了放大系数而不是它的逆** `P/(P−z)` 而非 `(P−z)/P` —— 正是它自己注释里警告的错。一行分数、两种写法只差方向，源码读不出来。**靠隔离实验定位**（旋转与相机归零后仍 +33px，推翻了"旋转导致"的假设）。<br>**实测**（`studio/scripts/measure_frame.py`，新工具；表面色剪影 bbox，渲染自入库源图谱）：静止位姿 **+1.5px**；隔离态（无旋转无相机）**−0.5px** 且宽度精确 = 190×2+520 = 900；相机推进中 +15.0→+10.0→+1.5px **收敛**；从交付 mp4 抽帧 **+3.0px**。推进中的偏移是相机在动，不是漂移。<br>**取舍已显式化**：精确居中要求把每个窗口反缩放到图谱要求的**屏幕**尺寸，于是近端不再画得更大，景深变弱。另一读法（真透视尺寸、近端明显更大）也渲了也量了：**+30.0px**，观感更像景深。两者**互斥**（透视下「中心对称」与「剪影对称」不可兼得），故 `layout.equalOnScreen` 在图谱里显式二选一，默认精确居中。<br>**防线**：`projection.check.ts`（tsx 可执行）断言 `cssXForScreenX` 是 `projectX` 的逆（75 组）且 `screenScaleFor` **抵消**投影（14 组）。**变异测试通过**：把分数改回 `P/(P−z)` 后 6 条转红。已接进 `pytest tests/`（无 node 则 skip），**60 passed** |
| 6.3 | 四场构图目检 | ✅ | 按复验口径逐场抽帧目检。s01 KPI Hero：设计上的左对齐（`align:left`/`padX:120`），非缺陷；s02 Browser Stack：见 6.2b；s04 Calendar：静止位姿 −0.5px。<br>**s03 DataColumns 发现真缺陷并已修**：说明文字「accounts opened」**必然**落在柱场内 —— 柱场占 y 323–843，标题块（数字 222px + 说明 53px）落 y 99–398 —— 好不好看取决于 columnSeed 抽到高柱还是矮柱，**是只能靠运气对的布局**。改为常规流纵向排布（标题在上、柱场在下），**重叠变得无法表示**。代价是柱子不再从数字背后穿过。<br>**未修、留待判断**：s03 相机 `rotateX:[12,2]` 把竖柱剪切成斜的。数据图的竖柱本应竖直，但轻微倾斜也可读作景深 —— 属艺术判断，未擅自改图谱 |
| 6.4 | Camera 状态单一实现 | ✅ | 相机状态原本只有 `CameraRig` 内部知道；要参与布局就得在场景里复制一份推进/缓动逻辑，两份会各自漂移。改为共享的纯函数 `cameraStateAt` / `useCameraState`，投影数学独立成零依赖的 `common/projection.ts`（这样测试能 import 真代码而不是副本）。有测试锁住「场景不得自建 perspective 变换」 |
| 6.0 | Browser Stack 居中尝试 | ❌ **无效（改错对象）** | 复验指出整簇偏右源自图谱 camera 取向，修法应在图谱。**实际做的是改渲染用的暂存副本 `studio/public/jobs/showcase_demo.json`（该目录被 gitignore），而源图谱 `pipeline/examples/showcase_demo.json` 从未改动** —— 因此从提交产物看等于没做，`0d59c11` 仅含 docs 一个文件。**自述的「重渲确认生效」不成立**。复验官独立实测证明声明式控制链本身成立：只改图谱 `rotateY −9→−40` 会改变 1.25% 像素、变化区域精确落在三个窗口上；但相机这条路本就不是居中正解（横向铺开由组件内每窗口自己的 rotateY(−7/0/+7) 与 translateX(250·s) 主导）。**归入 6.x：把 per-window 参数提升到图谱层** |

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 6.5 | Palette tokens + premium-dark/light 双主题 | ✅ | **发现并修掉一个半接线缺陷**：`scene.theme` 字段和 `Backdrop` 里的 `premium-light` 判断早就存在，但四个场景一直从 StyleBible 读 premium-dark —— 图谱作者设 `theme: premium-light` 会得到**亮背景配黑窗口**。半接线比没接线更糟，因为字段看起来是能用的。<br>修法：新增 `design/themes.ts`（**主题 = palette + shadow + depthCue 三件套**。阴影必须随主题走 —— 近黑底上的阴影在纸上等于没有，纸上的阴影在近黑底上是一块淤青）；`StyleBibleProvider` **移进场景循环**（原来包着整片影片，所以 theme 只能在 Backdrop 生效；解析必须发生在 theme 被声明的地方）；`Backdrop` 去掉按主题名的分支（解析后的调色板已经带着本场景的底色，同一个表达式在两种表面上都对，按名字分支正是两种语言漂移的来源）。<br>**实测**（像素采样）：light 背景 (253,252,251)→(244,241,234) = 精确的 #FFFFFF→#F4F1EA；窗口面 (240,240,239)；dark 侧 (15,15,18)/(16,16,19) 未受影响。四场亮色全部目检通过。<br>**但主题第一次渲出来是坏的**，见变更记录 —— 根因不在主题系统 |
| 6.6 | Typography roles | ✅ | 补齐 `numericDisplay`（展示级数字，232/700，tabular）/ `numericTable`（表格级数字，52/700，tabular）。理由：标题数字和表格数字是**同一个数字的不同排版** —— 前者要紧字距重字重，后者要等宽不换行；此前 KpiHero 拿 `kpiXL`（展示角色）去放一个会动的数字，只好手工补 `tabular-nums` 才不抖。KpiHero 已改用 `numericDisplay` 并删掉手工 tabular 设置。**图谱级覆盖已验证有效**（见变更记录，0.92% 像素变化，变化区域精确落在数字上） |
| 6.7 | Spacing 尺度 | ✅ | **完成方向与旧记录相反**（复验，不是加工任务）。`SPACE` = 8×斐波那契（1:2:3:5:8:13:21），尺度原样保留；旧行写的「与总任务书要求的 4…96 步长不一致」**两个半部都不成立**（证据见下）。<br>**① 总任务书从未有过数字**：`UPGRADE_MASTER_PLAN.md:131` 的 P6 行自始只写 「`design/` tokens：palette/typography/spacing/depth」；`git log -S '4…96' -- docs/UPGRADE_MASTER_PLAN.md` 零命中，且该文件全历史只有一个内容 blob。**曾被引用的「6.7」这个子项号也不是总任务书的**（它从不编子项号）。<br>**② 这句话第一次出现就是账本自己**：`71da3cd`（2026-09-30）写的是参数 **6.3**，原文「Spacing 尺度（4…96）」**判定格空白**；`b27cbf2` 把 6.3 改名为 6.7，**并填上了「与总任务书要求的」这个归属——指向一个从未包含这些字的文件**；`014ebe7` 首次称它「规定的」，另四个提交转述。**五个提交、三个文件、零出处。**会话历史内可能的出处已排除：六个会话里五个旧的零命中，只有 `de13ac51` 有且最早时间戳比 `71da3cd` 晚 **3 分 33 秒**（提出这条规则的会话不在存活的六个里）。<br>**③ 账本的算术两次都错**：七个值 **已全部是 4 的倍数**（÷4 = 2/4/6/10/16/26/42），「4 的倍数」现状已满足；未满足的是「4…96 的区间」，而「区间」从来不是总任务书的表述。**旧行里「总任务书要求的」这个承重词已删掉——它正是让一句无出处的转述读起来像规则的那几个字。**<br>已交付（复验通过）：**①** 记录文档 `docs/SPACING_SCALE_VERDICT.md`（含检索与提交链证据）；**②** 新增 `tests/test_space_scale.py`（两条）——断言**比例序列**等于 1:2:3:5:8:13:21（不是钉死数字）、且死刻度集合锁定为 `xs`/`xxl`/`hero` 并要求分别在 `tokens.ts` 被点名；官方自报两条变异（指少 `hero:168→170`、插入 `xxxl:180`），**指挥窗口独立复现，均红在正确断言上**（`:117` 比例断言 / `:156` 死刻度断言），还原后 sha256 回到 `68b08661…`、git 干净。<br>**本项目守卫记录**：守卫在干净树上**本来会红**——工单要求断言「七个刻度零死」，但工单自己的爆炸半径表就测出三个零消费。执行 agent **主动上报了这个偏离并未擅自照做**，改成冻结死刻度集合（「死刻度只可能变少，新增必须是显式决策」）——**这个判断是对的，指挥采纳**。<br>全量测试 325→**327 passed, 2 skipped**（+2 = 新增守卫）。刻度值未动（`tokens.ts` 23 行纯注释、0 行删除，SPACE 定义行字节不变）。 |
| 6.8 | Depth 层级 | ✅ | **订正旧记录并修掉一处真缺陷**。旧行说「`DEPTH` 四场无一使用」——这句对但不完整：**`DEPTH` 并非死 token，它已接线**（`styleBible.tsx:73` `mergeSection({...DEPTH}, b.depth)` + `:173` 导出 `DEPTH: s.depth`），**零的是场景读取方，不是通路**。「接线了但没人用」与「没接线」是两个不同量级的缺陷。<br>**真缺陷（先测后修，实测证实）**：`DEPTH_CUE` 当时只有 **3 层**，而 `BrowserStack.tsx` 用 `DEPTH_CUE[Math.min(i, DEPTH_CUE.length - 1)]` 取值 → **第 4 个窗口及以后全部塌成第 3 层阴影**，4 层以上的窗口堆叠**视觉上完全没有深度差**。实测（渲染真实场景、读 React 实际发出的 box-shadow 字符串，六窗口 @frame240）证实修复前 `w3/w4/w5 == w2` 完全相同。<br>**为什么此前没被发现**：已交付图谱里**全部 browser-stack 场景都恰好 3 窗口**（指挥窗口独立复现：3 个场景，窗口数分布 `{3:3}`），而 `content` 在两侧 schema 都是无类型袋子 —— **一个 4 窗口的图谱一直合法、且一直画错**。**执行 agent 自报「46 个 browser-stack 场景」，指挥窗口复现不出（实为 3 个），数字有误；但它据此得出的结论「无已交付帧受影响」经复验成立，故结论不受影响。**<br>**扩展规则是拟合出来的，不是选出来的**：从已交付的三层反推 `y` 步长 16(dark)/12(light)、`blur = k·y` 最小二乘（k=2.849/2.671）、alpha 按最后一段实测比值（1.240/1.357）外推 → **五层是真实天花板**（dark alpha 在第 5 层到 0.95，第 6 层需 1.18 —— 那不是一个颜色）。**循环（wrap）被单独否决**：它会把第 5 个窗口画成第 0 层，即**最远**平面、塌在一个更近的窗口后面 —— 那是可见的深度谎言。故 `depthCueAt` 为纯 clamp。<br>**判定：图谱不应驱动 `DEPTH`**（只给设计未实施，schema 未动）。深度是场景几何，与图谱**已经**设置的 `layout.spreadZ` 同类，而 `locked_fields.py` 刻意不锁 `spreadZ`；`DEPTH` 与 `spreadZ` 冗余，**不是缺失的 schema 字段**。反向决定所需设计已写进 commit message。<br>**已交付（复验通过）**：**①** `depthCue` 3→5 层（两主题）；**②** 新增 `depthCueAt()` 纯 clamp；**③** `depthCue.check.ts`（409 行夹具）+ `tests/test_depth_cue_layers.py`（7 条）。夹具**渲染真实场景读真实 CSS 字符串**、刻意不重写一遍 clamp —— 它要找的正是「clamp 写得和场景不一样」这一类 bug；并说明为何不走 `visual_qa.py` 像素路径：**阴影塌陷是 CSS 声明层面的事实，从压平后的帧里不可恢复**。<br>**指挥窗口独立注入的变异**：把 clamp 改成 `cue[i % cue.length]`（循环）→ 2 条守卫红，其中行为那条打印出 `window 5: 0 14px 40px rgba(0,0,0,0.40)`，**即最远层塌到最近层后面**——红得正是它该抓的东西。还原后 git 干净，全量 **334 passed, 2 skipped**（+7）。<br>**执行 agent 纠正了指挥窗口的错误**：工单称四个文件都是 CRLF —— 实测 `tokens.ts`/`themes.ts` 是 **LF**，仅 `styleBible.tsx`/`BrowserStack.tsx` 是 CRLF；它按各自实际行尾保存。该 agent 另主动上报五条自身失误（夹具后缀污染套件、heredoc 注入 0x08 字节、alpha 外推算错并更正、中途删除快照后靠 sha256 恢复等），均如实记录。 |

---

## P7 — 图表引擎　状态：✅ 完成

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 7.1 | 自研 SVG 图表：Bar/Line/Area/Slope/Bubble/Heatmap/RankTable/Sparkline/VolumeBars | ✅ | 9 种全部实现并**逐场渲出目检**（`pipeline/examples/charts_demo.json`，P7.1 当时 9 场 1350 帧；**P7.2 为测封顶追加第 10 场 `c10_bar_long` 600 帧 → 现为 10 场 1950 帧**）。<br>**先发现一件事**：`bar-chart / line-chart / area-chart / bubble-chart / rank-chart / slope-chart / heatmap` **七个场景类型从 P3 起就在 schema 里声明了，却没有任何渲染器** —— 图谱要一张柱状图，得到的是一屏 "not implemented in P4"。**schema 承诺了没人兑现的能力，正是本项目反复踩的那一类。** 引擎做完这七种才变成真的；另补声明 `volume-chart` / `sparkline-chart`（引擎支持但 schema 没有，同样是不对称）。<br>**结构**：`charts/options.ts`（声明面，先写）→ `charts/scale.ts`（纯数学，零依赖）→ `charts/ChartFrame.tsx`（轴/网格/刻度/数值标签，**拥有定义域**）→ `charts/types.tsx`（九个标记）→ `charts/Chart.tsx`（适配器）。标记一律从 frame 拿已解析的比例尺，**不许自己算定义域** —— 否则标记可能和它所在的轴不是同一个尺度，而那种图是可读且错误的。 |
| 7.1b | 选项面与 A/B 证据 | ✅ | 按纪律先注册再实现。`FIELD_READERS` 18 个选项全部注明读它的文件；**检查会读那个文件的源码确认它真的提到这个名字**（只查注册表自己的账本分不清能用和哑的）。<br>**A/B 矩阵 23 个选项全部实测为「活」**（`studio/scripts/chart_ab_matrix.py`，退出码 0，报告 `out/chart_ab.md`；**P7.2 后为 24/24**，新增运动项 `enterFrames` / `staggerFrames` 与 `deemphasis`）。**过程中抓到一个源码级检查抓不到的真 bug**：`showArea` 登记为"被 types.tsx 读过"、也真的出现在 types.tsx —— 但在 **Area 组件**上，于是每一张 line 图的 `showArea` 都是哑的。根因更深一层：`option()` 拿 `TYPE_OPTIONS` 做**运行时闸门**，所以一张过时的表就能让一个能用的选项变哑，而守卫看不见（名字在文件里）。**修法：闸门去掉，表降级为声明，准确性另测。** 修后 volume 的 `emphasisIndex` 从 0px 变 50,730px（2.45%，区域正好一根柱）。<br>**顺带删掉 `inline`**：声明了、没有任何标记读它。与其糊一层，不如删。<br>**新增两条机械化的纪律**：每个声明的选项都必须在 A/B 矩阵里有实测行；`option()` 不得再按表过滤。 |
| 7.2 | 统一 chart 生命周期（intro/settle/highlight/focus/exit） | ✅ | 九个标记原来各有一套入场（弹簧长 / dash offset 画 / 从左伸 / 缩放格子）→ 纯函数 `lifecycleAt(frame, duration, count, opts)`，五阶段按**场景时长的比例**而非固定帧数（90 帧和 600 帧都读得对），入场长度**封顶**为 `min(场景的 34%, 标记实际所需)`；`emphasis` 是阶段属性而非第二套动画（intro 升 → settle 到 → highlight/focus 保持）。`types.tsx` 迁移后**零 Remotion import**，时钟只剩一个来源，`useCurrentFrame`/`useVideoConfig`/`spring`/`interpolate` 的最后一个读者随之删除。<br>同轮**用测量抓到一个自 P7.1 就存在的柱状图入场缺陷**（`top` 是常数、height 增长 → 柱子从顶端垂下，只在满高时恰好落回基线；四次稳定帧渲染全都没暴露）→ 柱形几何抽成纯函数 `barBox(valueY, baselineY, progress)` 放进 `scale.ts`，`VolumeBars` 一并修。<br>详见变更记录 2026-09-30 P7.2 条。**复验补注（10-01）**：`lifecycle.check.ts` 实测 29 个 `check(` 调用点 / 54 条断言（原记「60+ 项」为假账）；且**未接进 pytest**，守卫目前纯靠自觉 —— 详见变更记录同日复验条。 |
| 7.3 | annotation/label 避让/数字格式/theme/stagger/emphasis | ✅ **复验通过（10-01）** | 两条实测缺陷修后复测归位（柱标签 −160/+322px → 五个全部 −9/−10px；slope 线顶与刻度从差 57px → **21px = 数据差 1 单位**）。110 passed、tsc 0、三 check 0、**A/B 26/26**、成片重渲契约保持。`lifecycle.check.ts` 已接进 pytest。详见变更记录 2026-10-01 P7.3 完成条<br>**复验补注（10-01，遗留一项不阻塞本阶段）**：三条新守卫**实测全部能红**（`declutterByY` 排序退回类别顺序 → scale.check 3 条转红报 `[300,400,426]`；`enterFrames` 注册表指回 types.tsx → exit 1 报 CODE never mentions；`WEIGHTS.focus` 0.36→0.40 → pytest 转红）。**但仍有一个未被任何守卫覆盖的空隙**：`declutterByY` 的**调用点**若被改回 `declutter`（函数本身不动），**110 条测试全绿、三份 check 全过** —— 守卫只证明纯函数对，不证明九个标记真的调它。与 `showArea`（表在、名字在文件里、不在那个组件上）同型。**留给 P8 的 A/B 矩阵 CI 化时一并处理**，不阻塞本阶段 |

---

## P8 — Format 数据驱动　状态：✅ 完成

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 8.1 | `calculateMetadata` 返回 width/height/fps/durationInFrames | ✅ | **代码 P6 起就已存在，但「返回 format」不等于「按 format 渲」** —— 审计才把这两件事分开。`showcaseMeta`（`FinanceShowcaseWide.tsx`）四项全返回、`Root.tsx:63` 已接上，`render.mjs` 走 `selectComposition` 所以 format 确实来自图谱。**但布局是高度驱动的**：`scaleFrom(height) = height/1080`，**全库没有任何东西读帧宽**。于是竖版一渲就横向溢出（见 8.2）。<br>**修法**：`scaleFrom` **删除**（不留别名 —— 「一个只认高度的缩放器存在」本身就是病因），换成 `scaleFor(width, height) = min(w/1920, h/1080)`（contain），补上缺失的 `DESIGN_WIDTH`。**11 处生产调用点**全改（含 `styleBible.useScale()` 与 `primitives.tsx` 三处内联的 `comp.height/1080`）。<br>**附带**：判据抽成纯模块 `schemas/showcaseMeta.ts`（只依赖 zod，因此可测），组件里只剩两行包装 —— 原判据在 React 组件内部，**「图谱写坏会怎样」这个问题在不渲一帧的前提下无法提出**。<br>16:9 不变性**实测**：`orig` vs `scaleonly` @f343 = **0 px 逐位相同**（`min(1,1)=1`）。 |
| 8.2 | 验证 1920×1080@60 / 1080×1920@60 / 3840×2160@60 | ✅ **但验证本身抓出三个缺陷** | **实测数据（复验重测，判据 = 内容像素 `max channel > 30`；背景渐变 ≤18、内容 ≥49，两侧留足余量）**：<br>**① 竖版横向溢出（已修）**。`scaleFrom(1920)=1.7778` 而帧只有 1080 宽。修前三帧**全部 `x 0-1079` 双向裁切**；修后 **v515 x 255-824（边距 L255 R255）、v343 x 231-857、v259 x 255-844，全部干净**。<br>**② 静默回退（已修）**。`safeParse` 失败时旧代码返回 `1920×1080@60 / 1 帧` —— 图谱写坏时渲染器**不报错**，交出一段别的东西。`broken.json`（`width: "1920"`）现在抛：`showcase-v1: this graph does not match the schema, so its render format cannot be trusted.` + `format.width: Invalid input: expected number, received string`。**旧代码在帧 515 报的是 `Cannot use frame 515: Duration of composition is 1` —— 在怪帧号，而不是在怪图谱。**<br>**③ `Math.max` 方向错误，token 在所有已交付场景里都是死的（已修）**。HEAD 的 `rampOf` 结尾是 `Math.max(1, seconds*fps/sceneFrames)`：`229 帧 ÷ (2.6s×60fps=156) = 0.68`，而 **`Math.max(1, 0.68) = 1`** —— clamp 只往上抬，于是**任何长于标称时长的场景，ramp 都被抬成 1.0，相机动机跑满整场**，`premiumCameraSeconds: 2.6` 被乘出来然后丢掉。藏在其下的 fps 依赖是真的，但只在**短于**标称时长的场景上显形，所以之前没被发现。改为 `cameraMoveFrames = seconds*fps`（绝对帧数，**不取整**：energetic 0.55s 在 30fps 是 16.5 帧，`Math.round` 会变 17，等于把刚要修掉的 fps 依赖装回去）→ premium 在 229 帧场景第 **156** 帧到位、后 72 帧静止，与 token 声明和 `CameraRig` 两处注释一致。<br>**施工方主动更正了自己上一轮的判断**（原文称「60fps 只差不到一帧」，是把 `Math.max` 的方向写反了）—— 这条更正比原结论有价值，已留在变更记录。 <br>**⑤ chart 场景三档复验（10-01，本阶段收尾）—— 抓到并修掉一个 P7.1 遗留缺陷**。P7.3 的整条证据链（柱标签、slope 轴、A/B 26/26、成片 1950 帧）**全部建立在 1920×1080 单档上**，而缩放器是共享的。用 `--baseline` 从 `charts_demo.json` 派生探针（只改 `format`，字节校验 + self-test），三档 × 四帧共 12 张全部渲出、无裁切。<br>**缺陷**：`ChartFrame.tsx` 的 plot 盒取自 `H = comp.height - padY` —— **原始帧高**，而标记/字体/padding 全乘 `s`。这行来自 **`11b9274`（P7.1）**，不是 P8 引入的；**P8 让它第一次能被渲出来**。`comp.width - padX` 恰好正确是因为三档都满足 `comp.width = DESIGN_WIDTH × s`，**高度只在首个非 16:9 格式上分家**（竖版 s=0.5625：设计高 607.5、帧高 1920）。实测竖版五根柱 **1223/1012/1331/943/1557px**，设计值 **319/285/345/260/406** —— **被拉伸 3.4 倍**，基线落在 y=1824 而非 532。**修法是结构性的**：plot 盒 = **设计盒 × s**，不再是「帧减 padding」。**16:9 与 4K 共 8 张渲染 `0 px` 逐位相同**（构造上即 no-op，已用像素证明），竖版柱高回到 **318/263/353/252/406**、slope 顶部墨迹 hd 87 / 竖版 48（预期 49）/ 4K 174（预期 174）。<br>**顺带把竖版图表居中**：`offsetY = max(0, (comp.height - DESIGN_HEIGHT × s) / 2)`，修前竖版图表贴顶（上方留白 33、下方 **1385px**），修后上下 **690/729、703/710、762/714、689/714** —— 与场景的「上下各约 700px」一致。**同样是 16:9/4K 的 0 px no-op**（`comp.height` 在这两档恰等于 `DESIGN_HEIGHT × s`）。<br>**柱标签主张三档复测**：hd **−10/−9/−10/−10/−9px**，与 P7.3 声称逐项吻合；4K/竖版大体随 `s` 缩放，个别柱偏差来自**标签与柱顶只隔 1–2px、该间隙在缩放后不成立**（P7.3 记录过的同类污染读数），**不是新缺陷**。 |

---

## P9 — Beat Grid + 高级音频同步　状态：✅ 完成

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 9.1 | BeatGrid（bar/beat/halfBeat/quarterBeat/accent/phrase） | ✅ **但先抓到 tempo 是错的** | **代码 P3 起就有 beat 数学**（`scene_graph.py` + `showcase-v1.ts` 两端，被 6 条漂移/一致性测试守着），**缺的是网格层级与 accent**。<br>**审计第一件事：一个入库文件，`bgm_beats.json`，自述「for the renderer」，`studio/src` 读取者 = 0** —— 与 P3 七个场景类型「声明了却无渲染器」同形。**量出来的更要紧**：文件自报 **129.2 bpm**，图谱写 **126**，**208 拍后相差 2.45 秒**。<br>**最小二乘拟合给出 129.00 bpm**（interval 0.465122s、RMS **7.9ms**、max **18.0ms**）—— **选对 tempo 把误差从 2452ms 压到 ≤18ms，136 倍**，且**网格不必携带逐拍时刻**。<br>**裁定用拟合值**：两个图谱的 `bpm` → **128.998**（不是 129，斜率标准误 ±0.0025，三位小数有依据；129 会掩盖这值是拟合来的）。**修法不是改数字而是不许它静默错**：由 `bgm_beats.json` 拟合，图谱 `bpm` 必须与它相符（容差 0.5），不相符即红。**先立守卫、再改数据** —— 否则下次换 BGM 又漏一次（README:35 早已警告过此事，正因为没有守卫）。<br>**accent 必须来自分析，`i%4` 无任何支持**：12 个最响拍的 `i%4` 占满四个余数、间隔中位数 5、`bass>0.3` 选出 34/208 且间隔中位数 **2**（成对相邻，不是每 4 拍）。**置换检验 200 次，mod 2/3/4/8/16 全部低于打乱零假设 95 分位 —— 没有任何 index modulus 能预测 bass**。所以 `beatGrid.ts` 里**连 `%` 都没有**（源码级守卫剥注释后扫 `% 2`/`% 4`）。<br>**四级基准是 1/4 拍而非小节，不是风格选择**：60fps 下理想一拍 27.907 帧，独立取整会与 `4×round(6.977)` 恰好相同 —— **在图谱自己的 tempo 上，这个错误根本测不出来**；换 131.4 bpm 就分叉（beat 取整 27、四个 quarter 得 28，每条小节线差一帧）。check 里扫 9 tempo × 4 fps 报告分歧格数。<br>**新增** `beat/beatGrid.ts`（322 行，零 react/remotion）+ `beatGrid.check.ts`，导出 `fitBpm` / `grid` / `bpmDisagreement` / `tempoAgreement`；双端漂移守卫 `test_beat_grid_parity.py`（7 passed，Python 按规格常量重算、TS 跑真模块，四级边界**逐项相等**非近似；accent 比的是同一个 **SET**，针对并列值排序稳定性） |
| 9.2 | 动作绑定 grid（cut/camera settle/chart finish/number finish/card arrival/hit） | ✅ **只做有查询面的两个，其余四个记录为无面** | 六事件盘点（**先量「哪个有面」再谈绑定**）：`camera settle` 与 `chart finish` 是**可查询纯函数**；`cut` 有输入无查询面（`transitionIn` 由 `SceneEnter` 内部消费）；`card arrival` 有输入无查询面（`Reveal`/`Stagger` 局部算 spring）；`number finish` **连输入面都没有**（`countUp(..., seconds=1.6)` 既是默认参数**调用点 `:56` 也是字面量**）；`hit` **全模板不存在**（`onAccent` 是调色板色，与节拍无关）。<br>**新增** `beat/bindings.ts` + `bindings.check.ts`（18 处 `check(`，零 react/remotion），六事件各返回 `{available, frame, source}`，**四个不可用的 `source` 必须写明为什么没有面**（守卫断言长度 ≥20 字符，防 `'n/a'`/`'todo'` 混过）。**未接线到任何组件。**<br>**两条断言被自己的 check 纠正，且纠正都对**：① 「camera settle 必须落在场内」**错** —— 相机装不进 114 帧的 s03（60fps 下 2.6s = 156 帧），而 `cameraMoveFrames` 文档本就写明「move 允许越过场景」；② 「chart finish 随时长翻倍」**错** —— `lifecycleAt` 把入场封顶在 marks 的实际需要（单 mark 48 帧），只有 34% 上限起作用时（dur < ~141）才随时长增长。实测 **三档 fps 恒为 93**，随场景时长 90/150/300/600 → **58/93/138/228**（单调但次线性）。<br>**`beat_snap` 的结构性损耗，已量化并门控有界**：`resolveScenes` 逐场独立取整，**片亏损是各场亏损之和**（实测 6+5+3+6 = **20** = film delta −20），所以按片长门控实际在门控**场次数**。精确界是 **`bf/2 + 1`** 而非 `bf/2`（解算时长是 `round((k+b)·bf) − round(k·bf)`，**两个边界各自取整**），20 格全绿。**且符号不固定** —— 独立扫出 **6/20 格让片变长**（最大 **+68 帧** @174/120），**「beat_snap 丢帧」本身不是普遍成立**。126 的「几乎免费」是**运气不是设计**（130.435 bpm 下同一场反丢 8.2 帧）。<br>**`beat_snap` 在交付渲染路径从未被调用**（`FinanceShowcaseWide.tsx:97` 传 `false`），故以上对成片零影响；已加 `snapCost` 报告 + 源码级守卫钉住 `resolveScenes(doc, false)`，**让差异可见而不是让沉默替它说话** |
| 9.3 | Premium SFX profile（soft whoosh/UI click/tonal tick/muted impact/low air） | ✅ **只立规格，不接线** | **先量现状再定映射**：资产 **15 个 m4a / 6 个 `sfx_*`**，SFX 使用点**只有 `ReportVertical.tsx` 的 4 行**（`:375` whoosh、`:376` impact、`:378` ding、`:381` riser）；`TimelinePlayer.tsx:147` 是 `audioBus.premixed`（BGM 总线，**不是 SFX**）。FinanceShowcaseWide 侧**零 SFX**。<br>shipped report props 实算（9 屏 / 29.9s）：**whoosh+impact 同屏 = 8/8 屏**，18 个 sfx 事件 = **2.25 次/屏**，mix `{whoosh:8, impact:8, ding:1, riser:1}` —— **只有 ding（首个 takeaway）与 riser（outro）有条件，其余全是无差别**。**这就是 9.3 要压掉的毛病，已量化成基线。**<br>**新增** `beat/sfxProfile.ts` + `sfxProfile.check.ts`（12 处 `check(`），`EVENT_SFX` 六事件键集合恰等于 `BindingEvent`；**一个事件不得同时持 whoosh 与 impact**；映射文件名用 `fs` 对目录校验存在（**15 / 6 两个数都钉住**，防拼错）；**覆盖率由表推导而非常量** —— 实测 **3/6**，三个洞恰是既无帧也无输入的三个事件（`card-arrival`/`number-finish`/`hit`）。<br>`cut` 的映射是**有条件**的：它有输入（`transitionIn` 含 `out`）但无可查询帧，而「八次 whoosh 连响」正是要压掉的东西 —— **在绑定先接上帧、再接上声音之前，保留 transition 音**。**未接线到任何组件。** |

---

## P10 — Visual QA　状态：✅ 完成

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 10.1 | `visual_qa.py` deterministic 规则（safe area/clipping/overflow/collision/font size/contrast/black/freeze/duplicate/blur/flicker/aspect/missing asset/broken font） | ✅ **14 条里做成 10 条，4 条是仪器不存在** | **先审计 12 步，不写代码。** 起点：`qa_report.py` 91 行**全是容器级检查**（分辨率/codec/fps/LUFS），**像素级规则一条都没有**。<br>**已量到的结论（全部进守卫，不只是描述）**：<br>· **safe area**：showcase 四场最小边距 106px、charts 最紧 58px（上）。**判据取「边距 == 0」精确式，放弃正阈值** —— 193 帧实测四边分布**连续无空隙**（最小正值 左 16 / 右 24 / 上 **7** / 下 25），7px 阈值在 1080 帧上等于 0.65%，任何合理留白都会被判红。**余量 = 0 到各边最小正值之间的全部空间。**<br>· **clipping 不能用背景模型**（本轮最关键的设计结论）：`padX=0` 与 `padX=-200` 的背景模型残差都是 **208**（正常帧 **3**）—— **一个「检测内容触边」的检测器，靠帧边缘建模背景就无法测量触边帧**。改走**固定调色板色**路径（两主题各一常量，contrast 规则本就如此）。<br>· **overflow / collision 不是纯像素规则** —— **三种检测器各失败一次**：行带+列游程测的是**字形**（5 个 3 字符标签报 54 个游程）且**标签重叠时融成一个游程，于是「重叠 0px」恰恰因为重叠才出现**；柱体检测把坐标轴并成 1668px 的「柱」；连通域把柱+网格并成 **1668×745** 一块吞掉整个标签列。**需要 mark 布局输入，不是更多努力。**<br>· **font size**：声明 `20 × s`，实测文本带高 36 / 19 / 69px，比值 1.00 / 0.528 / 1.92 ≈ s —— **缩放无 bug，问题在绝对值**：竖版 **11.25px < 12px** 可读线。<br>· **contrast 已经红了，不需构造**：24 配对中 **8 对 < 4.5:1**（复验独立重算逐位吻合 2.82/2.89/2.16/3.23/3.71/2.19/3.64/4.18）。**`inkFaint` 就是图表数值标签的默认色**（`types.tsx` 的 `emphasised ? ink : inkFaint`）—— **亮主题下 2.16:1**，那是图表要传达的数字本身。**亮主题 accent 3.23:1**，而 `KpiHero` 的 eyebrow 用 `accent` 且是 **20px/weight 500**（WCAG 大字要 ≥24px 或 ≥18.66px 且 bold≥700）→ **实打实不达标**。<br>· **black frame 现有图谱造不出** —— 最空一帧（`enterFrames=400` 的 frame 1）内容 0.64%，**图表家具（轴/刻度/标题）永远在画**。唯一转红入口是 missing asset 类输入（`take_ranker` 的 `not_black` 早有先例）。<br>· **freeze 判据可取精确 0** —— 渲染噪声地板**实测为 0 像素**（同 props 连渲两次 `array_equal=True`，本次四对重渲与审计集**逐位相同 0.0000%**；PNG 无损，P0 那个 0.04% 是 mp4 地板、不适用）。<br>**新增 `studio/scripts/visual_qa.py`（751 行，numpy + PIL，零 cv2/remotion/react）**，**四值判定** `PASS` / `FAIL` / `UNVERIFIABLE` / `UNAVAILABLE` —— **「仪器测不了」与「测出问题」是两件事**，报告里必须分得开。四条无检测器的规则返回 `UNAVAILABLE` + 理由、**不给数字**。背景模型不可信时**拒绝出数**而非给坏数字（`bbox(None)` 曾抛 `ValueError: Calling nonzero on 0d arrays`，已修并加守卫）。<br>**`qa_report.py` 两处已证实漏洞已封**（审计用真 ffmpeg 造文件跑真工具）：<br>① **8a 绝对 0.6s 容差**：4.59s vs 4.0s = **14.75% 漂移**穿过。改为**相对容差** `max(0.05, expect × 0.02)`。**长片上反而放松了正确量**（121.2s vs 120s 旧 FAIL → 新 PASS），证明是真相对化而非换名的阈值。真实 demo 成片 29.9167s vs 29.9s = **0.056%**，**2% 留 35 倍余量**。边界加 `+1e-9`（`1.2000000000000002 > 1.2` 曾让容差内的片子被判红）。<br>② **8b props 无 `totalDuration` → 整条 PASS**：`expect = props.get('totalDuration') or 0` 后 `expect == 0 or ...` 使检查跳过，**而 `report_demo/props.json` 正是这个形状 —— 这条检查在唯一一份已交付 props 上从来没运行过**。现为 **`UNVERIFIABLE` 且非零退出**。<br>**变异测试 11/11 全杀**，且诚实区分了自己的坏测量：11 个里前 6 个是**坏测量而非真存活**（两个改了 docstring、一个方向性无效 —— `FREEZE_DIFF` 只选像素而判据是 `changed == 0`、一个提高门槛让更多帧红、一个以 `NameError` 而非行为死掉）。**「变异没杀掉」与「变异不是有效变异」是两件事。** |
| 10.2 | VLM Critic（每 scene 抽 5 帧，多维评分 + problems + repair_suggestions） | ⬜ **先查清承诺与现状后裁定依赖 P1.3，本轮不做** | **审计结论：本仓库没有任何 VLM 设施，且这与 `P1.3` 是同一底座。**<br>· `take_ranker.py:3-4` 的 docstring 承诺「The VLM critic (take_critic.py) runs only on the survivors」—— **`take_critic.py` 不存在**，全仓库 `git grep take_critic` **只有那一句注释本身**，无任何消费者。<br>· `take_ranker.py:278` 的 VLM 三维度权重 `prompt_adherence 0.20 / composition 0.15 / consistency 0.15` **只活在注释里**，`prompt_adherence` 标识符全仓库**仅 1 次命中**（就是那行注释）。**没有被读，是注释。** 而 `P1.4`（✅）的结论写着「VLM 三维度(20/15/15) 留给 critic 阶段合并」—— **权重表已把 VLM 部分标为待合并**。<br>· **无 provider 抽象、无 key 处理、无 endpoint、无推理客户端。** 唯一网络代码是 `experiments/download_models.py`（从 HuggingFace 下 H3 本地权重到 `E:\ComfyUI\models`，硬编码代理与本地路径，**不在 `studio/` 下，且 `requirements-dev.txt` 里只有 pytest —— 连 `requests` 都不是声明依赖**）。`qwen3vl_32b` 是 H3 的文本编码器检查点名，不是 VLM 服务。<br>**裁定：标为依赖 `P1.3`，不合并。** 推理层完全相同（provider 抽象 + 一次调用 + 一次评分），**必须只建一次**；消费者不同（`P1.3` 输视频文件、`10.2` 要帧 + 图谱上下文 + `problems` + `repair_suggestions`）。**合并会让「scene 级五帧抽帧 + repair 建议」这个明显更大的范围被 provider 抽象那一行盖住。**<br>**本轮未做**，原因已量而非推测：**从零建**（无底座），且缺少可离线验证的判据 —— 与 10.1 那种「量得出来就写」的性质不同。 |

---

<br>**惰性字段全量复核完成（10-02，含运行时验证）**：全量枚举后**真正惰性的是 6 个，不是交接文档记的 18 个** —— `scene.notes`、`scene.audioEvents`、`scene.transitionOut`、`camera.focus`、`motion.ease`、`content.chart.baseline`。**六个全部经 grep 零命中验证**（`focus`/`ease` 的命中数不为零，但全是同名诱饵：前者是生命周期阶段名 `focus`，后者是内置 `MOTION.profiles` 表的键，没有一处读图谱的值）。**这六个 schema 全部静默接受**——zod 无 `.passthrough()`，作者设了不报错，只是被忽略。<br>**最值得处理的一条不是这六个**：`FinanceShowcaseWide.tsx:99` 读顶层 `doc.audio` 并在 `:135` 渲染 `<Audio>`，**但 `ShowcaseSchema` 根本没声明 `audio`**。运行时实测：`safeParse` 返回 `success: true`，解析后键为 `version,project,format,bpm,scenes`，**`audio survived?: false`** —— zod 剥掉未知键，所以那个 `<Audio>` 分支**永久不可达**，任何今天写的带 `"audio": {"src": ...}` 的图谱都会**渲染静音且校验通过**。当前两份交付图谱都没有顶层 `audio`，所以**尚未造成实际损失**。<br>**六个里唯一被交付图谱主动设置的是 `motion.ease`**（`showcase_demo.json` 设 2 次、`studio/public/jobs/showcase_demo.json` 设 3 次）——作者有充分理由相信那些场景的缓动由它决定，而 `common/primitives.tsx:183` 把 bezier 硬编码成 `cubicBezierEase(0.16, 1, 0.3, 1)`，全仓无一处读 `motion.ease`。<br>**「18」的差异解释**：那个数字统计的是更大的面 —— 跨两个 schema（Python JSON Schema + TypeScript）、含 `style_bible` 子区（其中 `chartLanguage`/`audioLanguage` 解析 nowhere）、以及 Python 管线自己那层未接线的 chart-spec 字段（`chart.width`/`chart.height`/`color`/`timing`，这些字段今天在两份 schema 里都不存在）。**两个数字都不错，是问的不是同一批东西** —— 要合成一个数字，得先裁定 `style_bible` 的两个语言区与管线字段是否在审计范围内。


---

## 五之附二：三个「会骗人的字段」已修复（10-02，三笔独立复验通过）

惰性字段审计的结论不是「有 6 个死字段」，而是**其中三个不是死的，是在说谎**。三者都已修复，各带可失败的守卫。

**一、顶层 `audio` 永久不可达（`62f3249`）**：`FinanceShowcaseWide.tsx` 曾读 `doc.audio` 并渲染 `<Audio>`，而 `ShowcaseSchema` **从未声明该字段**、且无 `.passthrough()`。运行时实测：`safeParse` 返回 `success: true`、解析后键为 `version,project,format,bpm,scenes`、**`audio survived?: false`** —— zod 剥掉未知键，故该分支永久不可达，今天写带 `"audio"` 的图谱会**渲染静音且校验通过**。**已删除分支而非接线**，依据三条：① 没有任何生产者会生成它；② `pipeline/schemas/showcase-v1.schema.json` 是 `additionalProperties: false` 且只声明 6 键，**只在 zod 里接线会直接破坏 parity**；③ `beat/sfxProfile.check.ts` 断言「没有映射声音是 bgm」而 beat grid 是**从 `bgm_beats.json` 推导**的——对本模板 BGM 是节拍参考而非音床，接线会给每部片子铺一层音乐。`visual_qa.py` 的 `missing_asset` 同步收窄（它原本检查三个渲染器收不到的字段）。

**二、`motion.ease` 图谱在设、渲染器从不读（`e74e285`）**：交付图谱两处设 `"ease": "expo-out"`，而全仓**没有任何 `expo-out` 解析器**——调用点要的是四个数字（`cubicBezierEase(0.16, 1, 0.3, 1)`），图谱给的是一个**名字**。**接线需要发明一张 name→curve 表**，那是设计决定不是修 bug；改类型的折中更糟，会把今天所有图谱判为非法。**已清理**（删图谱取值 + 删 schema 声明，两份镜像同步）。附带发现 `design/tokens.ts` 的 `MOTION.profiles[].ease` **同样无人读**——`profileOf()` 只取 `.stagger` 与 `.spring`，两个惰性字段共用一个名字。

**三、`baseline` 生效在一层之上（`74852de`）**：前两个是「没人读」，这个是**能读但层错了**——生效的是 `content.baseline`，而作者写在看起来更自然的 `content.chart.baseline`（与 `values`/`labels` 并排）**静默失效**；交付图谱 volume-chart **两处都设 40**，故成片从来看不出来。像素级实测（同值、帧 59）：`chart.baseline=40` → 柱顶 **402.7**；不设 → **770.5**；旧层 `content.baseline=40` → **770.5**，**与不设完全相同**。**已改为从 `spec.baseline` 读**并删掉图谱里的惰性副本。依据不是口味：`options.ts:14` 早已写明「Options live on the SCENE's `content.chart`, never scattered through a component's props」——**规则就写在离读取点 40 行处**，而代码违反了它。且移动后 `baseline` **仍是锁定的 fact**（`locked_fields` 按叶子键匹配而非按路径），**零锁定覆盖损失**；若会损失，保留别扭的层才是对的。

**两笔未被授权修、但已记录的问题**：
- **两份 schema 镜像严格性不一致**：zod 的 `MotionSchema` 无 `.strict()`（**静默剥离**未知键），JSON Schema 的 `Motion` 有 `additionalProperties: false`（**拒绝**）。运行时验证：重新加 `motion.ease`，zod 给 `success: true` 且键消失，JSON Schema 会拒绝——**同一份图谱两种相反裁决**。修它要先定「哪边权威」，是设计决定。
- **`pipeline/scene_graph.py:25` 声明 `SCHEMA_PATH` 却从不校验**，Python 的 `_validate` 是手写的、不认识 `ease` 已消失 —— JSON Schema 目前只是由测试维持同步的镜像。

**三次任务共同的形态**：都不是「代码没写」，而是**代码在说谎**。三个都由**测量**钉住，不是读代码猜出来的。

**惰性字段的其余四条：只记账，不动代码。** `scene.notes`、`scene.audioEvents`、`scene.transitionOut`、`camera.focus` —— 实测**两份交付图谱一个都没设**（逐场逐层查过），所以它们不骗任何人，只是 schema 表面上的空承诺。与上面那三个「会骗人的字段」不是一类：那三个图谱**在设**、渲染器**不认**，作者会误以为有效；这四个图谱不碰，谁也不会依赖。删它们是 schema 瘦身，价值低于改动本身的风险；接线则要先有真实需求。**留给将来第一次有人要设其中之一时再定**——那时它是接线还是删除，取决于要解决什么问题，而现在两个都无从判断。
<br>**两份 schema 镜像已对齐（`55a1d90`）** —— 且修复过程中发现比原判断更重的问题。① **JSON Schema 此前根本无法编译**：`definitions/Track` 被 8 处 `$ref` 引用却从未定义，Ajv 报 `can't resolve reference #/definitions/Track`。**因为从来没有人真正运行过这个文件**（parity 测试只用正则比对），所以它那 6 处 `additionalProperties: false` **从未被任何真实图谱检验过**。现在 Ajv 与 `jsonschema` 均通过编译。② 严格性不一致已消除：zod 的 6 个对象全部 `.strict()`，与 JSON Schema 的 6 处 `additionalProperties: false` 一一对应。**运行时实测五种情形**：`clean` 通过、顶层 `audio` **拒绝**、`motion.ease` **拒绝**、场景里打错字 **拒绝**、`_note` **通过且保留**。<br>**主动接受的代价**：未知键从「静默忽略」变成**硬错误** —— 对着略旧草稿写的图谱会加载失败，而不是带着一个被忽略的字段跑起来。**故意付的**：另一个选项是双向都看不见的失败。错误不是裸 `ZodError`，`describeIssues` 会指出路径。<br>**`_note` 在两份镜像里都被显式声明**，不是删掉、也不是开一个洞放它过去 —— 它是本项目的元信息键惯例（`prompt_compiler.py`、`migrate_shotspecs.py` 已在产出它）。而 `layout` / `content` / `audioEvents` / `StyleBible` 这些自由容器**保持开放**：严格化覆盖的是图谱自身的词汇表，不是组件解释的载荷。<br>**两条既有守卫曾把缺陷钉成了契约**：`test_zod_strips_an_undeclared_top_level_audio_at_runtime` 与 `test_a_graph_setting_ease_still_validates_but_the_key_is_gone` 断言的正是「静默剥离」这个行为 —— **留着它们就等于把缺陷写进规格**，现已改为断言拒绝。<br>**一条工具选择的教训**：指挥窗口曾用 Python `jsonschema` 质疑「无法编译」的说法，得出「能编译」的相反结论 —— **因为 `jsonschema` 不解析 `$ref` 而 Ajv 解析**。用错工具就得出错结论。
<br>**镜像漂移已修，且指挥窗口的枚举漏了一处（`a55d03d`、`0dafc5c`）**。① **生产者曾是最宽松的那一方**：`scene_graph.py:25` 声明 `SCHEMA_PATH` 却从不使用，真正的校验是手写的 `_validate`，**从不检查未知键** —— 实测同一份加了两个未知键的图谱，Python **接受**、JSON Schema **拒绝**。而管线是图谱的**生产者**，**这正是三个「会骗人的字段」能长期存在的机制**。现已改为按 schema 校验，且 schema 文件读不到时**响亮失败**（静默跳过的校验器就是它要修的那个缺陷本身）。保留的只有 schema 覆盖不到的两条，其中「重复 scene id」有实据：`FinanceShowcaseWide.tsx:156` 用 `doc.scenes.find(x => x.id === r.id)` 解析，**两个同 id 场景会渲染第一个的内容**。<br>② **两份镜像对 `camera.perspective = 0` 裁决相反**（zod `.positive()` 拒绝 / JSON Schema `minimum: 0` 接受）。修复前的旧 Python 也拒绝 0 —— **JSON Schema 一直是异类**，只因从无人运行它（8 处悬空 `$ref`，上一笔才修）。**已按 zod 改为 `exclusiveMinimum: 0`**。<br>③ **指挥窗口手工枚举「四处数值边界、只有一处漂移」是错的 —— 执行 agent 用 `z.toJSONSchema()` 让 zod 机械地陈述自己的契约再与镜像对拍，又找到一处更严重的**：`format.width` / `format.height` 在镜像里是 `minimum: 16`、zod 是 `.positive()`（下限 1），**任何宽度 1～15 的图谱能过生产者却被渲染器拒绝** —— 正是那三笔修复要消除的「宽松生产者」的镜像版。已改为 `minimum: 1`。**教训：手工目测两份文件的边界不是测量方法。** 它还验明两处**不是**漂移：`Scene.type` 同样 22 个值只是顺序不同、`Track` 的 `oneOf` 与 tuple 写法等价。<br>④ **parity 测试为什么没抓住这些**：它把两个文件当**文本**解析。`test_camera_channels_match_across_sides` 在 `perspective` 分歧期间**一直是绿的**，因为 `"perspective"` 确实是两边的键 —— **文本比对不是较弱的语义比对，它回答的是另一个问题**，并且恰好在**边界**漂移时读绿。新守卫用 **78 个取值探针跑三个校验器**（zod / Ajv / 管线），其中两条直接从 schema 读出数值边界与枚举成员，**加了一个没有探针触及的边界就会红** —— 让扫描保持是扫描。


## P11 — Auto Repair Loop　状态：⬜（1/3：**11.2 完全闭环**；11.1 **前置仪器已建成、修复器未写**；11.3 未开始）。**

**11.1 的前置条件已建成，但修复器本身还没有。**新增 `studio/scripts/chart_geometry.py`：**从图表选项的几何算标签间隔，不靠像素**——这正是 P10 审计结论「Needs the mark layout from the chart options, not pixels」指的方向。对着渲染真值校准（**5 根柱 334px vs 333.6px，16 根柱 104.5px vs 104.2px，误差 0.2%**）；宽度用真实字体逐字符量（标签字体里 `i` 是 5.3px、`W` 是 20.4px，同长度差 4 倍，数字数会误判）。九个变异八个杀。

**仪器不下判定**：只报比值，阈值由调用方定，因为账本没给阈值。`visual_qa.py` 的 `collision` 规则**已接入但仍报 `UNAVAILABLE`**，理由写明「仪器已建成、缺的是判据」，并有 7 条守卫使「顺手填上阈值」变得代价昂贵。

**但 11.1 仍未实施，原因已重测（不是引用交接文档）**：已交付图表比值实测 **0.278**（最宽标签 `Retention` 92.6px / 间隔 333.6px），**没有一个标签碰到碰撞**，修复循环无伤可修。而它能用的唯一手段（缩短 labels）又恰好是 11.2 刚禁止的。新计划：11.1 做成「等真出现长标签图表时才起作用」的仪器，而不是一个修不存在问题的功能。

**11.3** 依赖 11.1，且 `MAX_REPAIR_ROUNDS=3` 本身是任意上限而非安全阈值（交接文档实测：每轮缩短 3 字符从 17 字符起需 4 轮，`rounds=3` 停在 11 字符仍在碰撞区；更根本的是刻度字号硬编码，**每轮步长无依据可定**）——正确做法是让轮次由「重新测量仍在碰撞」决定，不由计数器决定。

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 11.1 | Repair Planner（可改 padding/scale/font/chart width/color/timing/camera/stagger/duration） | ⬜ |**仪器已建成（`c6d7a5a`），修复器未写 —— 且这不是搁置，是实测结论。** 新增 `studio/scripts/chart_geometry.py`：从图表选项的几何算 x 标签间距，**不靠像素**（P10 审计结论「Needs the mark layout from the chart options, not pixels」）。对着渲染真值校准：**5 根柱 334px vs 333.6px、16 根柱 104.5px vs 104.2px，误差 0.2%**；宽度用真实字体（Microsoft YaHei）**逐字符量**而非数字数（该字体 `i` 是 5.3px、`W` 是 20.4px，同长度可差 4 倍）。九个变异八个杀。<br>**仪器不下判定** —— 只报比值，阈值由调用方定。`visual_qa.py` 的 `collision` 规则**已接入但仍报 `UNAVAILABLE`**，理由写明「仪器已建成、缺的是判据」，并有 7 条守卫让「顺手填上阈值」变得昂贵。<br>**解锁条件（实测，非推测）**：已交付图表比值 **0.278**（最宽标签 `Retention` 92.6px / 间距 333.6px），**没有一个标签接近碰撞**，修复循环无伤可修；而唯一能清碰撞的手段（缩短 labels）正是 11.2 禁掉的。→ **真正出现一个接近碰撞的图表时本项才需要动手**；若发现这样的图表，**应停下上报**——那会推翻本行的结论。**新计划**：11.1 做成「等真出现长标签图表时才起作用」的仪器，而不是一个修不存在问题的功能。<br>**惰性杠杆逐条复核（10-02 指挥窗口，非引述，附可证伪的 grep）**：`spec.width` / `spec.height` / `chart.width` / `chart.height` 在渲染源码里 **0 命中**；schema 里 `color` 字段 **0 命中**（唯一命中是注释里的单词 "colour"）；schema 里 `timing` 字段 **0 命中**。**十张图表场景只携带 `camera` / `durationInFrames` / `motion` 三个场景级字段**，`layout` 只存在于 showcase 的 kpi-hero / browser-stack / calendar → **11.1 在图表上真正够得着的只有时间轴三项**。**刻度字号硬编码 `20 * s`**（`ChartFrame.tsx:319` 与 `:378`）→ 这是 11.3「每轮步长无依据可定」的根因，字号不可由图谱影响，修复循环调不动它。 |
| 11.2 | 锁定项保护（核心文案/品牌 logo/数值事实） | ✅ | **新增 `studio/scripts/locked_fields.py`（14 条锁定规则）。**实测 **3 种 kind：fact 9 / copy 4 / identity 1**。**品牌那一类不走字段规则**：`logo` 在 `showcase-v1.ts:36` 是**场景类型**而非 content 字段，所以锁的是类型本身（`LOCKED_SCENE_TYPES = {'logo'}`），`by_kind['brand']` 实测为 **空列表** —— 计数器第三类为零斯箍这一点是实测结论，不是遗漏。为什么是显式路径而不是类型：`content` 在 `showcase-v1.ts:100` 是 `z.record(z.string(), z.unknown())`，**每个场的每个字段都是 `unknown`，包括那些不得动的** → 没有类型边界可靠，锁必须显式写下来，代价就是可能不完整——所以 `LOCK_RULES` 导出且在测试里数掉，`coverage_report()` 直接打印交付图谱真正命中的部分。<br>**实测覆盖：14 条规则、`unexercised: []`——零盲区。**<br>**不锁的是审计结论而不是口味：**`durationInFrames`/`camera`/`motion`/`layout`/`style_bible`/`format`/`transitionIn/Out` 正是 11.1 点名的杠杆，锁了它们修复循环就什么都做不了。边界是「**a claim** vs **the staging of the claim**」——可以改数字怎么呈现，不能改它说什么。<br>**变异测试，4 个全杀**：删 `labels` 规则 → 2 条红；列长差返回 `[]` → `test_a_repair_may_not_shorten_labels` 红；删第二个 `emit()` → `test_a_locked_field_added_where_none_existed_is_caught` 红。<br>**第三个变异暴露了一个真实缺陷，不是测量有效性的问题：**`diff_locked` 初稿只有单向 `emit(before, after)`，**修复过程里向一个原本没有锁定键的场景新增锁定字段（凭空写 caption、补值）就根本看不到**——每个其他测试全绿。补上第二次 `emit()` 后，新测试立即转红且 before/after 符号反了，需要在 `not primary` 时交换两边。<br>**14 条测试两个方向都断言**：违规动作被拒（改值/删标签/删整个字段/改标题），**11.1 的合法杠杆不被拦**——只会说「不」的守卫会通过这个文件里每一条测试，故 `test_the_levers_11_1_names_are_not_locked` 专为它存在。<br>**接线守卫已补齐（`9438563`）：`tests/test_locked_fields_wiring.py` 26 条 + `studio/scripts/locked_fields_mutation.py`。**修复规则本身此前零消费方——它是一道还没被任何东西跨过的栏杆。现在实测：**11.1 那 7 个合法杠杆全部放行**（durationInFrames / camera.translateZ / motion / style_bible / layout.padX / transitionIn / format，各 0 违规），**4 种攻击全部拦截且 kind 正确**（改 values→fact、删一个 label→identity、删整个 labels→identity、改 headline→copy），**双向不变量成立**（`diff_locked(a,b)` 与 `diff_locked(b,a)` 条数相同，含「只增不减」的 forward-only 修复形态）。<br>**变异 11 条，5 杀 6 存活 —— 六条全是「自我削弱」类，不是防御失效类。** 共同形状：函数里还有一条真断言，所以重言式检测不报。**这六条写进了代码，不只写进提交信息**，并由 `test_the_gap_is_still_open_and_labelled` 断言清单非空——**一份注释里的已知缺口会在被修掉的那一刻开始说谎**，而它只能保证缺口被修掉时会红（证明「仍然存活」需要跑元测试，本阶段明确不做）。<br>**扫描范围收窄的后果**：`SOURCE_ROOTS = ('studio','pipeline','docs')` 是**白名单**，**将来新增顶层源码目录必须同步这里**，否则「零消费方」会变成一句漂亮的谎。 |
| 11.3 | MAX_REPAIR_ROUNDS=3 + scene 级重渲 | ⬜ | |

---

## P12 — Director Agent　状态：⚠️ **勘察完成，实测结论「现在值得建 0 段」**

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 12.1 | BriefParser→ReferenceAnalyzer→StyleBible | ⬜ | **不建。** 解析侧已存在（`styleBible.tsx`），**生成侧零实现**；且生成侧若照 7 键 schema 走，默认就产出哑声明（见下） |
| 12.2 | ScenePlanner→Storyboard→showcase_v1.json | ⬜ | **不建。** Storyboard 零实现（0 命中）；下游 `scene_graph.py` 已存在（`a55d03d` 起读 JSON Schema），**上游却无产出者** —— 应等生成侧先有契约 |
| 12.3 | Asset Router（每 scene 判 Remotion/H3/Image/Existing/Hybrid） | ⬜ | **死头。** `visual_qa.py` 的 `missing_asset` 规则**实测已按 P11 收敛为 4 条硬编码 SFX 路径**（指挥窗口工单里写的「仍在读 3 个不可达字段」是过期的，执行 agent 纠正）；无资产判定需求可接 |

**勘察记录**：`docs/DIRECTOR_SCOPE_VERDICT.md`（518 行，含全部 grep 与逐键表）。**守卫已交付**：`tests/test_style_bible_no_dumb_declarations.py`（12 条）+ `tests/style_bible_consumption.py`。

**StyleBible 七键逐键三态**（判据是四段链：声明 → resolver 合并 → `useDesign()` 导出 → 场景解构，**四段全通才算可达**；**无一键是「直接读」**）：

| 键 | 结论 | 消费方 |
|---|---|---|
| `palette` | 间接读 | 12 处（`Chart.tsx:161` / `FinanceShowcaseWide.tsx:121` / `KpiHero.tsx:28` 等） |
| `typography` | 间接读 | 5 处 |
| `spacing` | 间接读 | 5 处，经 `styleBible.tsx:71` → `useDesign().SPACE`（**非词频可判**） |
| `motionLanguage` | 间接读 | 6 处 → `MOTION` |
| `cameraLanguage` | 间接读 | **仅 1 处**（`CameraRig.tsx:149`） |
| `chartLanguage` | **零消费** | 源码仅 2 行命中，全是 schema 声明 |
| `audioLanguage` | **零消费** | 同上；与 P11「顶层 `audio` 永久不可达」同源 |

**判读陷阱实测命中两处**（本项目已因此多次误报惰性字段）：
① `camera` 既是 `useDesign()` 导出又是 `CameraRig` 的 prop —— 按词匹配得 6 个「消费方」，真实只有 **1** 个；
② `grep -c director` 的 40 处命中里 **39 处是 `directory`**、1 处是散文 —— 必须按词形拆开数。

**指挥窗口纠正了执行 agent 一条、也被执行 agent 纠正两处**：

- **指挥窗口的工单错了**：「交付图谱设过 4 键」**实测只有 1 键**（`typography`）。另 3 键在 `7bef0a8` **已被删除 —— 因为它们是惰性的**；工单采信的那 4 键里有 3 键来自 `studio/public/jobs/`（gitignore 的 staging 副本）。**照 4 键设计会把三个已被判无效而删的键当成成功先例。**
- **执行 agent 报告自己的守卫第一版读了自己的被测对象**：它把 `styleBible.tsx` 算作消费方，而 resolver 定义了全部 9 个导出、因而命名了全部 9 个。已修并写进注释。**这一条与 P11「治愈式重绑定」同族：守卫问错了对象。**
- 另主动上报五条自身失误（第二版用词匹配判消费方造成 6 个假消费方、文档写坏 30 个中文字符、两处 grep 数字写错、node 探针 `npx` 路径失败等），均如实记录。

**反向缺陷已闭合（`836f532`，复验通过）** —— 四段逐段裁定 A/A/A/B：

| 段 | 裁定 | 依据 |
|---|---|---|
| `radius` | **A 接进 schema** | **2 处真实读**（`BrowserStack.tsx:159` / `KpiHero.tsx:143`）。与**已声明的 `spacing` 同型**（都是 `Record<string, number>`）、同类（都是 brand/不变式），却待遇不同 |
| `shadow` | **A 接进 schema** | **3 处真实读**（`BrowserStack.tsx:293` / `DataColumns.tsx:142`/`:237`）。与 `palette` 同为「主题表面」，而 `palette` 在 schema 里 |
| `depthCue` | **A 接进 schema** | 见下 —— 6.8 的成果在图谱层原本**完全不可达** |
| `depth` | **B 删掉合并** | 零消费（三重确认）**且输入结构上不可能存在** → `mergeSection(..., undefined)` 是恒等空操作，不可能改变任何输出 |

**指挥窗口的消费者证据漏了三处**（只列了 `BrowserStack`），执行 agent 实测另有 `KpiHero.tsx:143`（`RADIUS.chip`）与 `DataColumns.tsx:142`/`:237`（`SHADOW.glowAccent`）—— 方向不变，但把 A 的论据从「一处弱消费」加强到**跨两个场景的 5 处真实读取**。

**执行 agent 收窄了 B 的边界并报请裁定**：它删掉了图谱侧接线（merge 行 / `StyleBible.depth` 字段 / `useDesign().DEPTH` / 悬空 import），但**明确不删 `tokens.ts` 的 `DEPTH` 表** —— P6.8 当年正是在那里写下「删 token 是更大的决定」。理由记在该文件 docstring 里。**这个边界是对的。**

**`depthCue` 与 6.8 的关系（本项最关键的一条）**：6.8 把 ramp 从 3 层拟合外推到 5 层并**渲染真场景验证** —— 修的是 **theme 层**；**graph 层全程不可达**：`b.depthCue` 恒为 `undefined`，`BrowserStack` 永远只拿到 `themes.ts` 的字面量。**即 6.8 的成果在图谱层面是死的，且没有报错。** 裁定 A 关闭的正是这个缺口，**成本为零**（两端合并逻辑都已存在，只差一个键）。

**守卫（最重要交付物）**：`tests/test_style_bible_merges_only_declared.py` —— **解析** `StyleBibleSchema` 键集合与合并行做差集，**双向**：

- **正向**：抓到「合并了但未声明」（本项的原始缺陷形态）
- **反向**：抓到「删掉声明但保留 merge 与消费方」—— **第二个编辑产生完全相同的症状，正向断言抓不到**

豁免通道是**代码里 merge 行上的 `not-graph-controlled` 标记**，不是守卫里的名单（名单会与代码漂移）。**全文零文本存在性断言** —— 执行 agent 指出：P12 之后 `radius` 一词照样出现在 `showcase-v1.ts` 的 docstring 里，`assert 'radius' in schema_text` 会为一个已回退的 schema 报绿。

**执行 agent 纠正了指挥窗口三处**：① 消费者证据漏三处（见上）；② **工单称 `showcase-v1.ts` 是 LF，实测是 CRLF**（339 CRLF / 0 裸 LF）—— 照工单会写坏整个文件；③ 它自报**自己写的守卫第一版有真 bug**：`bleed` 没有 `useDesign()` 导出时抛 `KeyError` 而非正常断言 —— **红在错误的理由上，等于没红**。已修。

另它抓出**第五处文本存在性断言**：`test_depth_cue_layers.py` 的 `assert 'depth' not in schema_text` 被 `depthCue` 的子串触发 —— 它报告了一条 P12 并未违反的规则。已改为解析键集合。

**指挥窗口独立复验**：node 探针实测 `radius`/`shadow`/`depthCue` **三段 SURVIVED 带真实值**、`depth` 按裁定被剥离；正向变异（加未声明的 `bleed` merge）→ 5 条红；反向变异（删已声明且被消费的 `spacing`）→ 6 条红，含镜像一致性与两侧解析。还原后 git 干净、全量 346→**355 passed, 2 skipped**（+9）。

**根已关：`.strict()` 已加（`f1a591e`，复验通过）** —— 上一项修的是实例，本项关的是温床：

- **zod 侧** `StyleBibleSchema` 加 `.strict()`；**JSON Schema 侧** `definitions/StyleBible` 加 `"additionalProperties": false`（10 键）。**两侧镜像同步**，`test_showcase_schema_parity.py` 仍绿。
- **查全比工单宽得多**：工单测的是 19 份图谱，**执行 agent 扫了全仓 563 份 JSON**（含 `pipeline/**`、`studio/public/**`、`tests/**`、`studio/bin/**` 及 `node_modules` 之外的一切）：**携带 `style_bible` 的仅 3 份，未声明键 0 处 → 加 `.strict()` 不会让任何现存图谱转红。**
  `tests/**` **零 JSON 夹具**（图谱在内存里构造），其 `style_bible` 夹具把未知键放在**已声明段内部**（`palette: {nope: 1}`），而 `.strict()` **管不到那里**。
- **上一位 agent 说这是破坏性变更，指挥窗口实测推翻了**（19 份零处），agent 用 563 份复核后确认。**但账本要写清区别：「今天不破坏」不等于「永远不破坏」** —— `.strict()` 的价值恰恰是把「静默失效」提前到**编写时**变成一次指名道姓的报错。

**`.strict()` 关掉了什么 / 没关掉什么**（同一输入实测三态）：

| 形态 | 结果 | 键 | 
|---|---|---|
| 加之前（开放） | `success: true` | `['typography']` —— **静默消失** |
| `.passthrough()` | `success: true` | `['typography', 'ghostKey']` —— **被保留** |
| 加之后（严格） | **`success: false`** | `Unrecognized key: "ghostKey"` —— **报错并指名** |

**没关掉**：袋子内部（`palette.card` 仍合法，**两条既有跨镜像测试依赖它**）、`Scene.layout` / `Scene.content`、`depthCue` 的列表形状。

**执行 agent 抓到一条指挥窗口预见了但没想透的反直觉形态**：**`.passthrough()` 与不加 `.strict()` 在同一条断言上表现相反** —— 前者 `success=true` 且**键被保留**、后者 `success=true` 但**键被剥掉**。**一条断言「键不存在」的守卫会抓住后者、并且整个漏掉前者。**
守卫因此断言 `success is False`（两种形态都红），并有一条 `test_both_mutations_are_caught_by_the_same_assertion` 把这个性质钉住。

**守卫是真调 `safeParse` 断返回值**（工单硬要求），docstring 明写 `assert '.strict()' in src` 会因字符串出现而通过 —— 本项目已被文本存在性断言骗过五次。

**执行 agent 主动上报的三条自身失误**：
① 加严格性的当天 **12 条测试转红**，而它的 grep 只预测 2 条 —— 根因是 `declared_style_bible_keys()` 用了**贪婪的 `.*?` 加固定 2 空格缩进**，对象换行后匹配到 `SceneSchema` 的收尾括号，把 Camera/Motion/Transition 的键一起扫进来；② **第一版修复只修了一半** —— 改 2 空格为 4 空格后，它的变异用旧锚点删 `spacing` 行只删掉一半缩进，固定宽度解析器随即把下一个键误报为未声明；现改为 `[ \t]+` 无关、变异的锚点也一并改；
③ **手工注入的变异 A 把对象体压塌了**，守卫把它报成第三条失败 —— 是它自己造成的噪声，如实上报并重做（保留对象体）。

另：**工单写的「`showcase-v1.ts` 339 CRLF」已过期**（实测改前 371、改后 400）—— 分类（CRLF）判对了，具体数字变了。

**指挥窗口独立复验**：node 探针实测未声明键 → `success=false` 且 `issues: ["(root): Unrecognized key: \"ghostKey\""]`（**报错指名**，不是只说 schema 错了）；`palette: {nope: 1}` + `radius: {card: 4}` → `success=true`（**袋子内部仍开放**）。独立注入 `.passthrough()` → **3 条红**，含那条专钉此形态的。还原后 git 干净、四个 sha256 与自报逐字节相同、全量 355→**365 passed, 2 skipped**（+10）。

**一处判断留档**：`test_style_bible_no_dumb_declarations` 曾断言 schema 是**开放的**、并注明「若有人加 `.strict()` 需重新推导本文件」—— agent 做了那次重新推导而没有停下，理由是「它点名了确切的改动与预期结果」。**这个判断可接受**（工单正是要求加 `.strict()`），但若当初工单没写，改动一个被测试"钉住"的前提确实是应当上报的。

**原提请裁定已了结**：`StyleBibleSchema` 是否该加 `.strict()` —— **已裁定该加，且已实施**（见上「根已关」一节）。原顾虑「会把现有写 `depth` 的图谱变成硬报错」经 563 份 JSON 全仓实测**证伪**（零处）。

**未动**：`chartLanguage` / `audioLanguage`（P11 方向）—— 方向相反、修法不同，不在授权范围。
**比工单所问更严重的反向缺陷（本项最重要发现）**：
`styleBible.tsx:72/:73` 合并 `radius`/`depth`，`:98/:99` 合并 `shadow`/`depthCue`，场景**确实消费**——
但**这四段都不在 7 键 schema 里**。指挥窗口独立 node 探针实测：
`safeParse` 返回 **`success=true`**，而 `radius`/`shadow`/`depthCue`/`depth` **四段全部被静默剥掉**；对照组 `palette` 存活。**这是 P11 `audio` 缺陷转 90° —— 不是读了不可能发生的值，而是读了一个永远喂不进去的值**：这四段永远只能拿到 `tokens.ts` 的默认值。
**修法未定**（补进 7 键 schema = 承认它们是图谱词汇，还是删掉这些合并 = 承认它们不是），**留待裁定**。

**指挥窗口独立注入的变异**：在 `showcase_demo.json` 的 `style_bible` 里插 `ghostKey` → **2 条守卫红**（`ghostKey -> no-declaration` 与「图谱设的键必须可达」），均红在正确断言上；还原后 git 干净，三个工单基线 sha256 **逐字节相同**。全量 334→**346 passed, 2 skipped**（+12）。

---

## P13 — Scene Cache / 增量构建　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 13.1 | `job_state.json`（scene 级 input/asset/render hash + qa_status + version） | ⬜ |**裁定 B：不值得建。** 全仓检索 `job_state`/`sceneCache` **零实现**。**bundle 只占单次渲染 6%**（实测 **1.2s / 19.6s**，三次 1.2/1.3/1.2 复现）：`studio/public` 是 **127 文件 / 810.6 MB** —— **体积大但文件数只有 127**，bundler 逐文件 `copyFile`，所以快。**800 MB 从来不是瓶颈。** 且 `render.mjs:57` 每进程 `mkdtempSync` + `finally` 删除，**当前形态下这 1.2s 根本省不掉**；要省它必须先变**长驻进程 = P14** | 
| 13.2 | 改一个 scene 只重跑该 scene 的 preview/QA/final | ⬜ |**裁定 C：收益够大，但现在建不了。** 实测收益 **63–72%**（s01: 19.6→7.3s；s03: 19.6→5.5s），**挡住它的不是收益**，是三个实测事实：**① 产物不可复现** —— 同图三次得 **711054 / 710851 / 712303** 字节三个 sha256，**`concurrency=1` 亦然**，而 ffmpeg 对同一输入逐字节相同 ⇒ **缓存不能靠「重渲比对」验证命中**（这一条直接决定缓存方案的可验证性）；**② 没有任何一层能察觉「改了一个 scene」** —— 把 `s01` 值改成 9999，`visual_qa.py` 报告**逐字节相同**、退出码相同，无代码比较图谱；**③ 拼接后 re-encode 成本未实测**，所以 63–72% 只是上限。**且无 scene 级入口**（`bin/` 只有全片 `render.mjs` / 单帧 `still.mjs`；`visual_qa.py:746-751` 只有 `--props` 无 `--scene`）。**瓶颈不在 bundle，在「没有 scene 级入口」和「没有 scene 级 diff」——都不是 `job_state.json` 能解决的** | 

**勘察记录**：`docs/P13_CACHE_PAYOFF.md`；**事实守卫** `tests/test_p13_scene_cache_facts.py`（+8 条，钉住上述「现状」而非「应然」）。全量 365→**373 passed, 2 skipped**。

**执行 agent 自抓的一条严重测量错误**：第一版局部性守卫断言「被改 scene 之外逐像素相同」，实测 delta 达 **198** —— 根因是它在 **480×270 下采样**上做的测量，**差异被平均掉了**。**「在错误的尺度上测量等于没测」**，这条已写进 docstring 与 commit。

**变异存活且应当存活**：把图谱里一个 scene 的值改掉 → `373 passed`，**因为现有系统真的察觉不到**，那正是被记录的发现；agent 用第三条变异（让某规则真去读 scene 值）证明这个存活**不是守卫空转**，而非造 contrived 输入去杀它。

**本阶段附带修掉一处更危险的失效（`6e86b46`）**：**`visual_qa.py` 被喂错东西时报告「通过」** —— `:761` 的 `args.props.exists()` 条件在文件不存在时静默跳过 → `props` 保持 `None` → `:773` 整段 `rule_missing_asset` 被跳过 → **一次什么都没跑的 QA 输出「无发现」报告、退出码 0**（实测：`0 FAIL, 0 UNVERIFIABLE, 4 UNAVAILABLE` + `EXITCODE=0`）。**CI 里等价于绿灯。**

- **裁定走 B（报 `UNVERIFIABLE`）而非 A（`ap.error()`）**，依据是**房屋约定**：`qa_report.py:17` 写明「Exit 1 on any FAIL, and on any UNVERIFIABLE」，`visual_qa.py` 自身表头 §2 定义 UNVERIFIABLE 为「仪器测不了」。A 被否决是因为它会**毁掉报告** —— `--json` 消费方会拿到非零退出码**且完全没有 findings 数组**。- **接上了那个零调用方的 `rule_duplicate_check_props`（`:615`）而不是重新发明** —— 它本就实现了 B 的语义（UNVERIFIABLE + 带路径）。- **两个工具现在约定一致**：缺失 props 时 `visual_qa.py` 退出 **1** 并指名路径，`ab_field.py:471-472` 退出 **2** 并指名文件。方向一致（都非零）。- **那条钉住「现状」的守卫被重写而非删除或放松**（161 行变更），agent 读后确认它钉的是现状、并按其注释要求「刻意回来重写」——**红在了正确的理由上**（规则不再消失，而是改变判定）。

**指挥窗口独立复验**：真实退出码 **1**（**第一次测时用管道读到的是 `tail` 的退出码，差点误判** —— 这正是本项目反复批的那类错误，复查后纠正）；报告指名 `props.json does not exist`；健康图谱仍退出 **0** 且零 UNVERIFIABLE；`ab_field.py` 缺失 props 退出 **2** 并指名。全量 373→**379 passed, 2 skipped**。

**未决（agent 提出）**：`--frame` + 坏 `--props` 的组合**未测**；且 props 分支的 finding 现在排在 frame findings **之前**，既有排序守卫只覆盖「`--frame` 无 `--props`」故仍通过。

---

## P14 — Render Worker / Fast Preview　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 14.1 | 长驻 bundle 的 render worker | ⬜ |**裁定 B：不值得建。** **指挥窗口的假设错了一个数量级** —— 「800 MB bundle → 800 MB 常驻」**不成立**：**bundle 是磁盘上的目录，不是常驻对象**，Remotion 从磁盘读它、从未上过堆。实测常驻成本 **262 MB**（对照进程 57 MB vs 常驻 serveUrl 318–328 MB，`process.memoryUsage().rss`、两次 `global.gc()`、5 次采样须一致；空闲 90 秒 **0 MB 增长**）。**决定性的一条**：`render_with_remotion.py:70` **一个进程渲一部片子** ⇒ **生产路径净省 0.0 s**（暖渲 18693/19277 ms vs 冷渲 21368/20633/20069 ms，**全部差额就是 bundle**，别的都不会变快）。**且它靠放松 46 GB 事故的清理逻辑换来那 1.2 s** —— 用每次泄漏换永久 800 MB 占用 | 
| 14.2 | still/scene/draft/full 分级渲染（preview 540p30 快编码） | ⬜ |**裁定 C：现在不建。** 固定开销 **1.9 s（9%）** / 可变 **18.4 s（91%）**；**瓶颈不是 P13 说的「没有 scene 级入口 / scene 级 diff」，而更基础的一句：** **单次渲染没有值得回收的重复**。**bundler 不 watch**（实测 `durationInFrames={150}`→`{151}` 后 5 秒仍是 150，**只有显式重新 bundle 才变 151**）—— 但**失效判据极便宜**：mtime **0.21 ms**（56 文件）/ 内容 hash **2.15 ms**，对照省下的 1200 ms。**指挥窗口工单猜「失效判据是最大复杂度来源」，实测它是最便宜的一环** | 

**勘察记录**：`docs/P14_WORKER_PAYOFF.md`（505 行）；**入口守卫** `tests/test_p14_render_entry_points.py`（8→10 条）。全量 373→**387 passed, 2 skipped**。**什么都没实现。**

**执行 agent 自抓两条严重测量错误**（本项目最贵的一类教训）：
① **第一次失效实验测的是死代码** —— 注入一个未使用的 export 然后 grep bundle，**webpack tree-shake 掉了**，据此差点得出「编辑永不生效」的结论；改用构造级可观测的编辑（`durationInFrames={150}`→`{151}`）重做。**「测了不存在的东西」与「在错误的尺度上测」（P13 的 480×270 下采样）是同一族错误**；
② 它**不信任 `render.mjs` 自己的 `150f` 输出**，用 `ffprobe -count_frames` 独立复核了帧数 —— **这个态度值得保留**。

**本阶段附带修掉两处「入口静默通过」（`306f327`）** —— 与 `6e86b46` 的 `visual_qa.py` **同构**：工具在被喂错东西时报告成功。**这不是一个 bug 是一类**：「入口接受任意输入，错的那个和对的那个返回同样的成功」。

- **`render.mjs` 静默忽略任何未知 flag**。**带默认值的 flag 拼错时连 `requireArg` 兜底都没有**：`--cosdec vp9`（`codec` 拼错）过去**退出 0 并产出一部 h264 片子**，**输出里没有任何东西能把它和成功区分开**。已修：退出 2 + 指名该 flag + 列出全部已知 flag。
- **`still.mjs` 早就修过这个 bug、`render.mjs` 漏了**：`still.mjs:31-33` 的注释原话是「Unknown flags are now an error, because a typo that silently selects a different frame produces a wrong image rather than a failure」—— **同仓库、同类 bug、修一处漏一处**。
- **已知 flag 集合是逐个手工找出来的**，因为 `get()` 会藏起调用点：除顶部读的六个外，**还有三个在 `renderMedia()` 内部内联读取**的 `pixelfmt` / `imageformat` / `colorspace` —— **任何从解析辅助函数推导出来的清单都会漏掉这三个**。
- **布尔型 flag 不存在**（`render.mjs` 无任何 `argv.includes(...)`；`still.mjs` 有 `--clean` 正因为它读布尔）⇒ `--clean` 现在被当作未知 flag 拒绝。
- **两条钉住旧行为的守卫被重写而非删除**（agent 确认两条都明写 「pins the ABSENCE of that fix, so it has to be rewritten deliberately rather than deleted」）。方向 (b)（所有已知 flag 仍能渲染）的 flag 清单**从工具自己的错误消息里读**，**两者无法静默漂移**。

**执行 agent 的预检抓到文本存在性陷阱**：删掉检查后 `Unknown flag` 仍留在**解释该修复的注释里**，若不是预检，这轮变异会假绿 —— **这正是本项目记录在案的第六类失效**。

**指挥窗口独立复验**：`--cosdec vp9` → **真实退出 2**（未用管道 —— 本窗口上一次就是用 `| tail` 读到 `tail` 的退出码、差点误判），错误消息列出 11 个已知 flag 且含三个内联读取的。全量 387→**389 passed, 2 skipped**。

**已排除的既有残留（报告未删）**：`C:\Users\pc\AppData\Local\Temp\` 下两个 10 月 2 日的 Remotion 遗留（`remotion-v4.0.529-assetsw5235hsi3b` 4 KB、`remotion-webpack-bundle-pyY1Lw` 39 MB）—— **体积小，但形态正是能躲过全部清理逻辑的泄漏路径**，已记为未决项。

---

## P15 — SR 路由升级　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 15.1 | SR Router：程序化内容 native 直出免 SR；H3 走 sr_pipeline_v2 | ⬜ |**裁定 B：不值得建。** 全仓检索 `sr_pipeline`/`flashvsr`/`real.?esrgan`/`seedvr`/`super.?res` **只命中 8 个 markdown、零个代码文件** —— P15 从未实现。**且路由信号本身是哑的**（见下），**已交付内容按设计全部该免 SR**（`video` / `data-plane-3d` 在 14 个场景里出现 **0 次**） | 
| 15.2 | FlashVSR 仅纹理丰富镜头（hair/fabric/architecture/hero） | ⬜ | 同上 | 

**`generative` 的死法与本项目修过的所有哑声明都不同 —— 它死在类型边界上，差一步就能到达**（记录文档 `docs/P15_SR_ROUTER_EVIDENCE.md`，守卫 `tests/test_generative_signal_has_no_consumer.py` 6 条）：

```tsx
const resolved = useMemo(() => resolveScenes(doc, false), [doc]);   // ← 算出 generative
{resolved.map((r) => {
  const scene = doc.scenes.find((x) => x.id === r.id);                // ← 回头从 RAW doc 取
  return <SceneRenderer scene={scene} ... />                        // ← 传 scene，不传 r
```

`generative` 活在 `r` 上，**下一行就被丢弃**；而 `SceneRenderer` 的类型是 `React.FC<{scene: Scene}>`，**`SceneSchema` 是 `.strict()` 且无 `generative` 键** ⇒ **它在类型层面根本过不去**。`resolveScenes` **确实在生产里被调用**（`:146`）、`resolved.map()` **确实在跑**（`:155`）—— **差一行**。

**这不是「声明了没人读」的形态**，所以关键词检索是错的工具。执行 agent 逐条关闭了间接路径（props 展开 / `useDesign()` / 方括号访问 / `JSON.stringify` / `Object.keys` / `GENERATIVE_SCENE_TYPES` 的 import——**无人 import**）。Python 侧 `scene_graph.py:179` 确实消费它，**但那是规划器读自己的模型，不是渲染器读这个 prop**。

**来历**：`a707d31`（P3）引入，commit message 写的是 routing「declared, not guessed」；`git log -S generative -- studio/` **只有这一个提交** —— **TS 消费方从未存在过**。parity 测试钉住的是两侧的**声明**，所以它一直绿着、也一直没被质疑。

**建议（未实施，提请裁定）**：**标注，不删、不接线。**
- 删 TS 那一半 → **为去掉一个惰性的一半而破坏一条活着的 parity 守卫**；
- 本项目已有先例：`tests/test_undeclared_field_reads.py:26-28` 把六个惰性字段列为 「ledger entries… tracked separately」—— **记账，不要静默删除**。

**指挥窗口独立复验**：注入真实读取（`KpiHero.tsx` 加一行 `.generative`）→ **2 条守卫红，且指名 `KpiHero.tsx:line 28: .generative`**；还原后 git 干净、全量 389→**395 passed, 2 skipped**。

**执行 agent 纠正了指挥窗口一处**：工单写「13 个场景」，实测 **14 个**（`charts_demo.json` 有第二个 `bar-chart`：`c10_bar_long`）—— 结论不变。
**它主动上报四条自身失误**：`_run_ts` 辅助函数**在失败路径上泄漏探针文件**（`studio/__probe_gen_*.mts`），靠 `git status` 抓到、加 `try/finally` 修掉（**仓库既有守卫本来就做对了，是它自己那份没做对**）；自己守卫里的三个真 bug（正则语法错、`String(ESM_namespace)` 抛错、`in` 操作数写反）；以及**最初把生产者排除钉在行号 316/373 上 —— 正是那种会造出「一遇无关编辑就误报」的守卫的脆弱性**，提交前改成形状匹配。

**变异 C 存活且判定为「等价、不该杀」**：只在注释里提一句 `generative` → 6 passed。**理由正是 `render.mjs` 那个陷阱**：注释不是消费方，**为它造守卫会造出一个「文档一改就误报」的守卫**。并用邻侧守卫验证（散文下同样 42 passed）+ 变异 A 验证真实读取仍被抓住，证明这不是可达性缺口。

**「入口静默通过」这一族确认无第三处**：`render.mjs` / `still.mjs` 与四个 `argparse` 脚本都拒绝未知 flag；`check_contract.py` **不接受任何参数** —— 无此面。仅记录，未扩大范围。

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
| 17.1 | 16:9 / 1920×1080 / 60fps / 45–60s 商业级 demo | ⬜ |**裁定 B：现在做不出来**（时长那半边可建，见下）。**硬缺口：没有 H3 渲染器** —— 渲染树里 `H3`/`h3_` 只有两处命中，**一处是注释**（`showcase-v1.ts:86`）、**一处是模板标题字符串**（`Phase0Probe.tsx:33`）；`video` 与 `data-plane-3d` 都在 9 个「无渲染器」类型里 → 落 `MissingScene`；**运行时确认：四个 `video` 场景的图谱给出 `graph_scene_renderable FAIL`、退出 1。** **⇒ 若 P17 要「含 1–3 个 H3 cinematic shot」，那将是第一批渲染成 "not implemented in P4" 的内容。** 另：**「明显达到 premium product film」被记为不可判定** —— 无仪器、无语料、无正类；**比 `collision`/`flicker`/`contrast_frame` 更彻底**（那三个至少还有不分离/不双峰的总体可测）。**没有为它编造任何指标。** |

---

## P18 — 最终 QA（四类）　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 18.1 | Technical / Layout / Motion / Visual 四层门禁 | ⬜ |**裁定 B：不值得建（缺的不是规则、不是分层、不是总闸）。** 记录文档 `docs/P18_QA_LAYERS.md`，分类数据 `studio/scripts/qa_layers.py`，守卫 `tests/test_p18_qa_layer_partition.py`（20 条）。全量 395→**415 passed, 2 skipped**。 |

**实测分布是 3/3/2/2，不是四个可比的分桶** —— 「四层」读起来像均匀四份，实际是 3+3 和 2+2。

| 层 | 规则 |
|---|---|
| Technical | `aspect` / `black_frame` / `missing_asset` |
| Layout | `safe_area` / `clipping` / `font_size` |
| Motion | `freeze` / `duplicate` |
| Visual | `blur` / `contrast` |

**分类基于规则函数实际 emit 的 `Finding.rule` 名**（调用全部 11 个函数得出），**不是函数名** —— `rule_duplicate_check_props` **emit 的是 `missing_asset`**，按函数名分类会给一条规则两个主人。

**工单的怀疑「总闸可能不存在」被推翻**：`visual_qa.py:855` `return 1 if hard or unver else 0`，`6e86b46` 让 UNVERIFIABLE 也非零。**实测退出码（无管道）：`--frame`→1、`--frame-pair`→1、`--props <不存在>`→1。总闸存在且已对齐。**

**但真正的问题是「永久红的闸和没有闸无法区分」**：

- `rule_contrast()` **零参数**、同一张 24 对表 → **333 帧全部 FAIL** → `--frame` 永远不可能 exit 0。**不是强制，是噪声。**
- `rule_missing_asset` **从不读 props** → `--props` 路径的绿灯里 4/5 findings 是 UNAVAILABLE 占位符，**唯一那条规则不检查交付物**。

**指挥窗口独立复现了这条（实测，非采信）**：把图谱里**每一个字符串**毒化成 `POISONED_…`（含 4 个 scene 的全部内容）—— **QA 报告逐字节相同、退出码相同（0）**；且**干净图谱也是退出 0**。**这条路径既不拦错误、也不拦正确，是完全的装饰。**

**没人会预料到的盲点**：`flicker` 既是 Motion 规则又是 UNAVAILABLE —— **四层里唯一缺席的层成员，恰好是该层语义上本该存在的那条**。

**真正缺口按严重度**（最小设计已给但**未实施**）：

1. **不读产物的规则就通过了**（2/10 条描述的是仓库和主题文件，不是渲染）
2. **永久红的闸** —— 不是强制，是噪声
3. **没有基线** —— `--frame-pair` 跨场景 exit 0 是「通过」的最接近形态，但**那取决于你指了哪两个 PNG**

**建议**：per-job 基线文件 + **任何偏离即拦**，而不是任何绝对 FAIL —— 同时解掉 2 和 3。

**本项抓到的最深一条失效（值得单列）**：守卫第一版从 `LAYER_OF` **派生**分层，于是所有结构断言都在**校验从被守卫对象派生出来的结构** —— 变异 M1（`blur` 从 Visual 改到 Technical）**首轮存活 16 passed**。**不是守卫写错了，是守卫从它要守卫的东西里派生出来** —— **那是本项目被骗六次的那个形状，从另一扇门进来**。已反转派生方向：`PINNED_LAYERS` 在测试文件里**独立写死**，`LAYER_OF` 反过来从写出的分组派生。**三条变异最终零存活。**

**它诚实报了一条杀不掉的漏洞**：`PINNED_LAYERS` 若在同一处一起改，变异就能活 —— **pin 按定义可以移动**；它**没有造 contrived 输入去补这个洞**，并说明那是 pin 的正确边界。

**执行 agent 自报五条失误，其中三条是本项目记录在案的复发**：

① **写了假测量，且它看起来像结果** —— 探针 80×120、内容落在 `EDGE=40` 内 → `safe_area` 两个输入都 UNVERIFIABLE → `static: True`，**读起来像「这条规则不看输入」，实际是「这个探针什么都测不出」**。已加 `probe_is_sensitive()`；
② **在 docstring 里断言了一个会被推翻的数字** —— 写 `duplicate` 对相邻帧「报 FAIL」，实测是 20/40；还写了从未测过的区间。最终注明实测值（53956 对，两侧 0.498465 / 0.500140）；
③ **整文件行尾污染** —— `qa_layers.py` 经多次 `python -c` `write_text` 后变成 **459 行 CRLF**，而全仓是裸 LF，**一行的改动会显示成 459 行 diff**。实测才发现；
④ 把长跑探针**管道进 `tail`**，十分钟里读的是 `tail` 的缓冲，**差点把空当「没发现」**；
⑤ 333 次 `subprocess` 扫描没在 15 分钟内跑完，改进程内后约一分钟完成。

**未决项（提请裁定）**：

1. ~~**`duplicate` 阈值与其输入错配**~~ → **已修（`fa6cbb5`，P19）**，见下。
2. ~~`contrast` 永久失败~~ → **已修（`bc19ffa`，P22）**，见下；
3. ~~`--props` 路径不检查任何交付物~~ → **已修（`8a2b090`，P21）**，见下；

---

## P21 — `--props` 路径从装饰变成闸门　状态：✅

守卫 `tests/test_p21_props_path_gates_the_deliverable.py`（12 条）。全量 431→**443 passed, 3 skipped**。

**裁定 C（部分），且两个半边的答案不同 —— 执行 agent 明确指出指挥窗口工单的前提在「有判别力的那一半」上是错的。**

### 半边一（B）：那三个样式段**不该**接受文件存在性检查 —— 已实测

它用 `npx tsx` 跑真实 `resolveStyleBible`、三个段全部毒化后实测：

- **`radius` 根本装不下路径** —— `mergeSection` 只在 `typeof v === typeof base[key]` 时保留值，而 `RADIUS` 全是数字；毒化成 `url("../../assets/NOPE.png")` 后**解析结果与默认值逐字节相同**，**在任何文件能被命名之前就被丢掉了**。`spacing` 同理；
- **`shadow` / `depthCue` 确实会让字符串通过** —— **而这正是检查在那儿错的原因，不只是没必要**：它们是交给 `boxShadow` 的 CSS 声明，**`url()` 目标缺失是浏览器解析的绘制失败，不是这条闸门该管的缺失交付物**。

**账本早已裁定过同一件事**：`:250` 的 12.3（Asset Router）正是因此被记为死头。**本次把该「缺失」钉成了断言，防止它被悄悄翻案。**

### 半边二（A）：这条路径现在检查的东西 —— **一个阈值都不需要**

`MissingScene`（`FinanceShowcaseWide.tsx:95`）是任何 `SCENE_RENDERERS` 未命中的类型的兜底，**它渲染出类型名加上「not implemented in P4」**。实测：**22 个类型已声明、13 个有渲染器、9 个落在中间**（`video` / `browser-window` / `stat-card` / `card-grid` / `data-table` / `quote` / `data-plane-3d` / `logo` / `outro`）。

**与 `collision` 不同，这里没有需要发明的判断** —— 问题就是**「有没有渲染器」这个存在与否**，**直接从渲染器派发的那个 map 上读出来**。

**⚠️ 这是同一缺陷的第二次发作**：`:80-83` 的注释记着上一次 —— **P7.1 修了七个图表类型**（它们「从 P3 起就在 schema 里、却没有渲染器，所以要图表的图谱拿到一帧写着 not implemented 的画面 —— **schema 承诺了没人交付的能力」**）。**那七个修完了，剩下九个非图表类型还在。**

**实测能拦住什么（跑出来的，不是断言的）**：把交付图谱的四个 scene 全改成 `quote` →

```
[FAIL] graph_scene_renderable value=4  → 退出 1
  4 scene(s) have NO renderer and will render the MissingScene placeholder
  ("not implemented in P4"): scenes[0]=quote, …
干净图谱: [PASS] value=0 → 退出 0
```

**这九个类型是被报告，不是被修** —— 那是一个渲染器决定，超出本项范围。

**指挥窗口独立复验**：同上（4 个 `quote` → 退出 1 并逐个指名 scene；干净图谱 → 退出 0），**报告差异逐行可查**。并复现了它指出的那半边：`SCENE_RENDERERS` **确实只有 13 个键**（`:75-93`），`:115-116` 确认未命中即走 `MissingScene`。

**为新规则付出的三处成本，全部更新、无一删除**（这是本项目的既定做法）：

- P18 的 `UNTOUCHED` 哈希 + `PINNED_LAYERS`（**Technical 3→4**，所以头条从 3/3/2/2 变成 **4/3/2/2**）；
- P13 的 `readable == unreadable` → 改成严格**子集**关系（需要图谱的规则没有图谱就跑不了），**并断定了方向**，使那条测试本来要抓的「反向消失」仍然会红；
- `test_visual_qa.real_props` 原本是个**不含 `scenes` 的格式桩**（**无效**，因为 `scenes` 是 `min(1)`）—— 现在带一个可渲染 scene。

**执行 agent 上报的两条自身失误**：

① **它在确认变异是否生效之前就宣称「变异存活」** —— 第一次注入变异三时它把 `gaps` 的定义注释掉了，产出的是 `NameError` 而不是行为变异。**这正是工单点名的那个错误。** 它靠直接调用（而非套件）抓到，上移到 `gaps` 计算之前后才被杀；
② **它在 `UNTOUCHED` 里先填了一个占位 sha256** 才去测 —— 正是工单要求的那条（先证明、再断言），顺序反了。已换成实测值。

**变异 4 是「无效变异」而非存活**：从 `SceneType` 删九个类型，**它没有被本守卫杀掉，是 schema 的 parity 守卫先杀** —— 因为 **schema 编辑不可能单独发生，Python 镜像必须同动**。**它如实记为真实缺口而没有糊过去。**

**第三把尺子与 `unavailable_findings()` 均未动**；`rule_duplicate_check_props` / `SIGNATURE_EQUAL` / `DUP_THRESHOLD` / schema / `FinanceShowcaseWide.tsx` 全部**与 HEAD 字节相同**。

---

## P23 — `flicker`：旧理由是假的，替换成实测的两条障碍　状态：✅（仍 UNAVAILABLE，但理由已换）

守卫 `tests/test_p23_flicker_stays_unavailable.py`（9 条）。全量 458→**467 passed, 3 skipped**。

### 旧理由已证伪

旧 UNAVAILABLE 理由写的是「**no existing render in out/ provides as a sequence**」。**实测为假**：`out/p13_probe` 里有 **329 帧 PNG、跨 9 个有序目录**（`fr_a`/`fr_b`/`full_a`/`full_b`/`full_r2`/`xc1a`/`xc1b` 各 41、`s1`/`s2` 各 21）。**仪器有对象了。**

**新理由写明旧理由是假的** —— **一条已经不成立的 UNAVAILABLE 理由，比一个诚实的 UNAVAILABLE 差**。

### 真正挡住它的两条（指挥窗口完全没看出来）

**(a) 序列是跨步的，不是连续的。** 按逐帧全字节匹配对齐到各自那次渲染实测：`full_a` 是视频帧 **0,20,…,800**（41/41 逐字节相同），`s1` 是 **0,40,…,800**（21/21）⇒ **相邻语料帧相隔 20 个源帧**（60fps 下 333 ms）。**按 Nyquist，它对快于 1.50 Hz 的振荡完全失明**（跨步 40 时 0.75 Hz）。实测：合成的 2 帧周期、深度 50% 的闪烁，**跨步 1 时 p2p = 0.006583，跨步 20 时恰好 0.000000** —— **整个 3–100 Hz 闪烁带、以及 50/60 Hz 市电纹波，全部混叠成一条平线**。

**(b) 没有正类。** 329 帧**全是已交付的干净渲染**，**零个闪烁样例** ⇒ **统计量没有可放切口的缺陷总体**。

### 定义与实测分布（已写进理由，即使 UNAVAILABLE）

**闪烁 = 同一 scene 内振荡的、正负交替的亮度偏移**，用**均值线性亮度的二阶差分** `|L[n+1] − 2·L[n] + L[n−1]|`，按 scene 归一化（**一阶差分会对切点与漂移有反应；二阶差分对线性斜坡免疫** —— 而线性斜坡是有意的淡入淡出）。**297 个内部样本 / 16 个 scene 段**：p5 = 0.000043、p50 = 0.009428、p95 = 0.695292、max = 0.776885，**单峰**（64.3% 的质量落在最低十分位，最大内部峰 22 对全局 191）。

### 裁定 B：仍 UNAVAILABLE，但理由换成实测

**没有建那条规则** —— **一条量不出东西的规则比层里少一条规则更糟**。

**⚠️ 执行 agent 指出指挥窗口工单本身的一处错误（我认）**：工单说「P19 记录 `fr_a`/`fr_b` 是同一次渲染的两帧」。**不对** —— `rank_takes.py:33-38` 与 `docs/P19_DUPLICATE_POPULATION.md:102` 都记录它们是**重跑对**（同种子重跑逐字节相同，`EP01 S06_T01 vs S06_T02` 实测 mean abs diff == 0.000）。它自己的测量也一致（41 帧里 18 帧逐像素相同）。**它按代码 + 实测走，并要求更正账本。**

**指挥窗口独立复验**：`full_a` 与 `full_r2` 各 41 帧、**30/41 逐字节相同** ⇒ **确实是同一次渲染的两次运行**，与上述记录一致（也印证 P13 的"产物不可复现"：同图三次得三个不同字节数）。**但跨步那条我未独立复现**（需逐帧解码 mp4 做对齐，成本过高）—— **该论断自洽且可检验，但此处记为未独立复验，不当作已证**。

**两条变异都被杀掉**（都在跑 pytest 前先证明生效）：永远 FAIL → 17 红、永远 PASS → 7 红，**均红在 `verdict == UNAVAILABLE` 这条正确断言上**；还原后最终哈希 `7e7d586a…` 与变异前逐字节相同。`qa_layers.py` **完全未变**。

**执行 agent 上报的五条失误，其中三条值得记**：

① **引用的数字错了** —— 先写「61.3% 的质量落在最低十分位」，重测发现 **61.3% 是最低二十分位、最低十分位是 64.3%**；**在提交前就在理由和测量表两处都改正了**；
② **第一次行尾检查是错的** —— `grep -c $'\r$'` 报 `visual_qa.py` 1372/1371 行 CRLF、**读起来像整文件 CRLF**；字节级检查显示它是 **LF**。**它在编辑前先对了 git，而不是采信那个读数**；
③ **编辑 `UNIMPLEMENTED` 时短暂造出一个重复的 `'flicker'` 字典键**，**在任何测试跑之前就抓到并回退** —— 这正是本项目记录在案的 dict 陷阱；
④ 两个守卫首跑有 bug（`n_samples` 把全语料的 297 与单目录重算的 37 比、以及传了 `capsys=None`）；⑤ **两个草稿脚本本身有 bug**（f-string `SyntaxError`、硬编码 `n=41` 与段数不符），**它丢弃了它们的输出、重新干净地测了一遍，而不是照着有 bug 的脚本汇报**。
4. ~~`flicker` 是缺失的 Motion 规则~~ → **已处理（`c70ce27`，P23）**，见下；
5. 总计划的「四层」行现在有实测分布 3/3/2/2，**是否要更新措辞**。
   **分布已随 P21/P22 变为 4/3/2/3，四层与总闸的未决项至此全部处理完毕**（见下各节）。

---

## P24 — 给 `--frame` 一条出路：基线比的是**判定**，不是数值　状态：✅

新模块 `studio/scripts/frame_baseline.py`，守卫 `tests/test_p24_per_job_baseline.py`（11 条），记录 `docs/P24_PER_JOB_BASELINE.md`。全量 467→**478 passed, 3 skipped**。**`visual_qa.py` 与 `qa_layers.py` 字节未变**（`7e7d586a…` / `ba519e9e…`）—— **基线是独立模块，不是一条新规则。**

### 核心发现（本项最有价值的部分，比"基线能建"更重要）

**基线比的是判定，不是数值。** 在 `out/p13_probe` 里**六对真实的重跑对**上、**每条规则 226 帧比较**：

| 规则 | 测量 | **数值不同** | **判定不同** | 最大相对摆幅 |
|---|---|---|---|---|
| `black_frame` | 226 | 86 | **0** | 0.4250% |
| `blur` | 226 | 91 | **0** | 16.1488% |
| `clipping` | 226 | 18 | **0** | 1.6667% |
| `contrast_frame` | 226 | 0 | **0** | — |
| `font_size` | 226 | 37 | **0** | **96.8750%** |
| `safe_area` | 226 | 9 | **0** | 3.2967% |

**判定可复现 1356/1356 = 100.00%**（独立重推 1130/1130；第三次在解码后的 demo mp4 上跑，0/243 判定变化）。

**⇒ P13 那条「产物不可复现」比账本上写的更严重**：**不只是字节不同，像素也不同** —— **同一次渲染的两次运行之间，801 帧里有 220 帧不同**；**`font_size` 的数值在一次未变的渲染上就能摆动 96.88%**。**所以数值基线确实是噪声** —— 而**判定是唯一被测出来稳定的量**。

### 裁定 A，三条判据逐条满足

- **稳定** —— 1356/1356，既作为值钉住、也从语料在断言的采样上重测；
- **能拦住东西** —— 用的是**仓库里已有的真实一对**（`out/dark3/f00440.png` vs `out/debug/f00440.png`，同 job 同帧，规则判定不一致）。**⚠️ 没有造 contrived 输入**；
- **比较对象明确** —— **判定、按相等比较；没有容差，因而没有可调阈值**。

### ⚠️ 指挥窗口与执行 agent 各纠正一处

- **指挥窗口工单的前提是错的**：「没有任何路径能走到退出 0」—— **加上 `--declared-px` 与一份匹配的图谱之后，`--frame` 能退出 0**；**指挥窗口亲自复核**：`--frame fr_a/0020.png --declared-px 1080`（图谱声明 1080p、而该帧实为 480×270）→ `EXIT=1, 1 FAIL aspect`；**改成该帧自己的 270 仍 FAIL，因为图谱仍声明 1080p**。**⇒ 它的说法需要前提**（图谱与帧必须匹配），而 **291/333 那个数字取决于用哪份图谱**。**两边都不完全对，账本两边都记。** 它已用一条守卫钉住"退出 0 确实可达"。

### P18 三个缺口的今日状态

| 缺口 | 状态 |
|---|---|
| 不读产物的规则就通过了 | **已关**（P21；重测：`graph_scene_renderable` 对 `video` FAIL、对 `kpi-hero` PASS） |
| 永久红的闸 | **已关**（P22；9 条逐帧规则、`theme_contrast` 已移出、4 条 UNAVAILABLE） |
| 没有基线 | **本项关闭** |

**三条变异全部杀掉**（都在跑 pytest 前先 assert 生效）：永远判一致 → 2 红、永远判偏离 → 3 红、**静默重建（基线缺失就判 AGREES）→ 2 红**。**「删掉基线文件」被测得是一个明确失败，绝不静默重建** —— 这正是工单要求的。

**执行 agent 上报的五条失误，其中三条直接改变了结果**：

① **`NameError: 'vqa'` —— 本项目「变异产出 NameError 而非行为」的第三次复发，且发生在它**自己的守卫**里**：导入绑的是 `vq`、某处调用写成 `vqa.main`。**单独跑通过、全量跑才失败**；
② **227/333 是它自己造出来的数字** —— 它给一个**含两种尺寸的语料**（82 帧是 480×270）统一声明 1920×1080。**正确数字是 291/333**；
③ **断言采样值 142/710 是在测量之前就写下的** —— 实测 33/165，最终交付写的是 17/85（跨步 16）；
④ 写错了 scene 类型名 `kpiHero`（真名 `kpi-hero`），**让一条正确的规则看起来像坏了**；
⑤ 守卫要跑 11 分钟 → 降到一个**已断言的 85 次测量采样**（约 50 秒），全量数字单独测。

**⇒ P18 的五项未决至此全部处理完毕**（1 已由 P19 修、2 由 P22 拆、3 由 P21 修、4 由 P23 处理、5 由本项关闭）。

---

## P17 — Showcase Demo：做不出来，且**做出来了也没有东西拦它**　状态：⬜（裁定 B）

记录 `docs/P17_SHOWCASE_DEMO.md`，守卫 `tests/test_p17_showcase_demo_verdict.py`（16 条）。全量 478→**494 passed, 3 skipped**。**未渲染任何成片，未改任何生产代码。**

### 规格逐条（指挥窗口实测 + 执行 agent 复核）

| 要求 | 现状 |
|---|---|
| 16:9 / 1920×1080 / 60fps | **已达标**（两份已交付图谱都是 1080p@60） |
| 45–60s | **最长的 `charts_demo` 是 32.5s**，离下限差 12.5 秒（schema 无时长上限，**45s 的图谱能写出来**） |
| **1–3 个 H3 cinematic shot** | **硬缺口：没有 H3 渲染器** |
| 「明显达到 premium product film」 | **无任何可测量判据** |

### 真正致命的那条：**没有任何东西拦得住一份 demo**

实测（不是引述）：**`--props` 对 1.0s 的片子、300.0s 的片子、以及 640×480@24 都退出 0**；**没有任何生产路径调用 `visual_qa`**；**`render.mjs` —— 每一次渲染都必经的那个文件 —— 不含任何 QA 调用**。

**⇒ 「一份 45s、1080p60 的 demo 今天就能写出来，但无法被察觉。**`pipeline_manifest.yaml:198-204` 本来就写着「质量门禁（当前全部无自动执行）」/`enforced: false`。

**执行 agent 选 B 而不是 C 的理由值得记**：「一份 45 秒的 demo 在没有任何验收标准的情况下交付，**那是一个文件，不是 P17 的一半**」——**时长的缺口可补，验收的缺口补不了。**

**⇒ P18 提的 per-job 基线（已由 P24 建）恰好能解这一条**：**基线不需要"正确的阈值"，只需要"上一次是什么样"**，而 P24 实测**判定可复现 1356/1356 = 100%**。

### ⚠️ 执行 agent 收窄了自己的一个主张（这一点比结论更值得记）

它最初写「没有任何东西在拦」，随后**主动收窄**：`ceo_mindread_ep01` / `third_lantern` 的 `qa_final.py` **确实**被它们自己的 `run_post_chain.sh:133` 调用。**⇒ 它的断言被改成可验证的那部分**：**没有任何东西运行那套能审判 showcase 图谱的门禁。**

**指挥窗口独立复核**：`qa_final.py` 有**三个副本，全在其他管线的目录里**（`ceo_mindread_ep01` / `piyao_2026` / `third_lantern`），调用方是它们自己的 `render_with_remotion.py` 与 `run_post_chain.sh` —— **没有一条路径能审判 showcase 图谱。收窄后的主张成立。**

### 执行 agent 自报的两条失误（都是本项目记录在案的形状）

① **它的第一版守卫数到了一条注释** —— `render.mjs:141` 的注释里写着 `qa_final.py`，于是它被算成了一个调用点。**这与本项目已付过钱的 `Unknown flag` 缺陷同一形状**。它自己发现并收窄了主张；
② **第一次全仓扫描漏了 `out/`** —— **Windows 路径分隔符不匹配 `startswith('out/')`**，**这让一个 30fps 的探针一度被读成 65s 的片子**。**指挥窗口实测的真值：最长 32.5s @60fps。**

**四条变异全部杀掉**（每条都在跑 pytest 前先在文件里确认落地、事后按 sha256 复原），**红都落在 `assert 'PASS' == 'FAIL'` —— 判定本身。**

**未动**：`FinanceShowcaseWide.tsx` 的 `resolved.map` 那一行（P15 记录的「`generative` 差一行就能到达每个组件」—— **它确认那条线索至今未修**，并按工单要求没碰）；`GENERATIVE_SCENE_TYPES`；P19–P24 的成果。

   **分布已随 P21/P22 变为 4/3/2/3**（见下两节）。

---

## P22 — 把「主题缺陷」和「这一帧坏了」拆开　状态：✅

守卫 `tests/test_p22_contrast_is_not_a_per_frame_gate.py`（15 条）。全量 443→**458 passed, 3 skipped**。

### 指挥窗口提示的假设被证伪

指挥窗口在工单里提示「`inkFaint` 按命名就是最淡一档墨，4.5:1 未必适用」，并要求先查它的实际消费点。**实测把这个提示推翻了**：

| 角色 | 站点 | **文本站点** | 用在哪 |
|---|---|---|---|
| `inkFaint` | 10 | **10（全部）** | Y 刻度标签 `ChartFrame.tsx:320`、轴标题 `:339`、X 类目标签 `:379`、`types.tsx:244/:344/:350/:429/:499/:523/:530`、`DataColumns.tsx:244` |
| `accent` | 8 | 3 | KpiHero eyebrow `:84`、后缀 `:118`、`Chart.tsx:196`（另 5 处是标记填充） |
| `positive` | 2 | **2（全部）** | KpiHero delta `:139`、RankTable delta `types.tsx:593` |

**`inkFaint` 不是装饰性的** —— 10/10 都是文本标签或数据数字。**本主题里真正装饰性的角色叫 `grid` / `hairline` / `column` / `columnBright`，而它们一个都不在被测的六个角色里。**

**为什么"按大字号降档"也救不了它**：`s = min(w/1920, h/1080)`。在 `s=0.5625`（9 份图谱里 6 份）时 `inkFaint` 渲染成 **8–12px** ⇒ 适用 4.5:1、不合格；在 `s=1.333` 时是 **24–29px** ⇒ 属大字号、门槛降到 3.0 —— **而它仍然不合格（dark 2.83 / light 2.16）**。**两个主题、两档标准，都不过。**

**附带发现**：333 帧语料**全部被检出为 `premium-dark`** —— **8 个失败里有 6 个从未被渲染过**。

### 裁定 A，以及总闸怎么知道

- `rule_contrast` → emit `theme_contrast`，由**新的 `--theme-contrast`** 报告，**逐帧路径上完全不 emit**；
- 新增 `rule_contrast_frame` → **UNAVAILABLE**，**因为仪器不存在，而这是实测出来的**：

  - 333 帧语料里每个像素与其自身背景的对比度 **p1=1.026、p50=1.046**，**97.8% 的像素落在 [1.0, 1.5)** —— **那是 `Backdrop` 的渐变坡道，不是字**；`Backdrop` 在 `backgroundAlt` 与 `background` 之间画径向渐变，spread 6+6+8，而 `PALETTE_TOL` 是 24 ⇒ **坡道像素与墨像素按「到背景的距离」分不开**；
  - 天真的规则（「任一像素低于 3:1 就 FAIL」）在 **333/333 帧全红**、每帧 ≥96% 像素低于 3:1 ⇒ **那会是第二道永久红的闸**，正是本函数要避免的东西；
  - **总体不双峰**：在 **531,100,800 个像素**上直方图是 `1.0→1.5 (97.765%)`、`1.5→2.0 (0.882%)`、`2.0→3.0 (0.095%)`…… **没有谷可以切**。

**⇒ 核心判断**：**对比度是 (前景,背景) 这个「对」的性质，像素不带角色。**

- **总闸不需要「知道」**：**逐帧路径上那条 finding 根本不 emit。****按作用域分离，而不是按名字豁免** —— `FRAME_SCOPED_RULES` 由**调用每一个规则重新推导**，所以一个「不再读帧」的规则会**失败**而不是**继承豁免**。

**归类：同 P19 一族** —— 阈值与问题错配，于是**问题被改写**，**而不是"把红变绿"**：`WCAG_TEXT` 仍是 4.5，`themes.ts` **字节未变**（`6cf58d0f`），**调色板依然如实地红着**。

**三条变异全部杀掉**：`WCAG_TEXT→2.0`（5 红）、`contrast_frame→FAIL`（7 红）、**把 `theme_contrast` 重新挂回逐帧路径**（4 红 —— 直接杀掉"按名字豁免"这条退路）。

**指挥窗口独立复验**：`inkFaint` 确实出现在 `ChartFrame.tsx:320/339/379`（刻度标签、轴标题、类目标签）—— **我的"装饰性"提示被证伪**；并读了新规则的 UNAVAILABLE 理由全文。

**它主动报备的三处超出拆分范围的改动**：

1. **`THIN_LAYERS` 的 Visual 项被删除而非改写** —— 该集合是**按数量**（`<=2`）算的，而 Visual 变成 3 条，但其中**只有一条**（`blur`）真能对帧说得上话。**数量不再是覆盖度的代理**，留着那一项会在上一层重复同一个错误；
2. **`test_the_two_qa_scripts_are_byte_identical_to_head` 对 `visual_qa.py` **被释放**（而非重新基线化）** —— 理由是「重新基线化只是记了一个哈希、没记任何论证」，`visual_qa.py` 改由**四条行为守卫**守住，`qa_report.py` 的 pin 保留。**P19/P21 的先例是重新基线化，它判定此处那样做是错的并写进了 docstring** —— **这是对本项目既有做法的有意偏离，提请指挥裁定**；
3. `PINNED_LAYERS['Visual']` 变成 3 ⇒ `docs/P18_QA_LAYERS.md` 的头条已过期；**该文件不在授权范围内，留给指挥窗口**。

**它上报的两条失误里有两条是本项目高频复发**：

① **用 Edit 工具把 CRLF 引进了 3 个文件** —— 正是工单点名的那个陷阱，**被 P18 已有的行尾守卫抓到**；
② **它自己的退出码表达式有一段死分支**，因而 emit 了 `NameError`（`theme_find` vs `theme_fail`）—— **与 P21「变异产出 NameError 而非行为」同一族**；**它在宣称任何结论之前就抓到了**。

**提请裁定（未实施）**：`inkFaint` 在两个主题、两档标准下都不合格，`premium-light/accent` 3.23 对 4.5 的文本门槛 —— **这些是真实的设计缺陷，改色板超出本项范围**。

---

## P19 — `rule_duplicate` 的尺子量错了对象　状态：✅

P18 未决项 1 的处置。记录文档 `docs/P19_DUPLICATE_POPULATION.md`，守卫 `tests/test_p19_duplicate_population.py`（9 条行为测试）。全量 415→**424 passed, 2 skipped**。

**指挥窗口的疑点成立：`rule_duplicate` 的 docstring 声称的「复用 take_ranker 阈值」从来不存在。** `take_ranker.py` 里那些 0.5 是 `m_sharpness`/`m_exposure`/`m_temporal_stability` 的空输入兜底、`calcOpticalFlowFarneback(pyr_scale=0.5)` 与 jitter 中性值 —— **不是重复判定阈值**。那个文件里真正像重复检测的是 `m_duplicate`（`:165-171`），但它是**另一把尺子另一个刻度**：`mean abs diff / 255`，切在 **0.0015**（≈0.38 灰阶）。**0.5 的真身是 `rank_takes.py:44` 的 `DUP_THRESHOLD`** —— **数字是真的，但在别处，复用从未发生**。

**因此裁定 B（docstring 撒谎）优先于 A（阈值错配）** —— 一个声称的性质不存在，比一个阈值不合适严重得多（`55b3ac5` 的教训：**docstring 声称的性质必须由代码兑现**）。

**但 A 之所以不可选，是因为实测证明「换更好的切口」根本不存在**：
在 329 帧语料上给两个总体打分（相邻帧应 PASS vs 重跑应 FAIL），**这把尺子上最好的一刀 balance 0.9969，落在恰好 0.0 之上，且仅由一对真实重跑帧撑着**（`fr_a`/`fr_b` 是同一次渲染的两帧，不是两帧对比）—— **两个总体不分离**。**这就是 `collision` 规则至今 UNAVAILABLE 的同一种处境，所以它没有编一个阈值 —— 与 P18 的 `collision` 处置一致。**

**它让规则改问一个入口真能回答的问题**：**这两个文件是不是同一帧** —— 切口因此是**精确的 0.0**（`SIGNATURE_EQUAL`），与 `rule_freeze` 同一种判据、同一类凭据，且是**实测在 0 而非假设**。**连续那个问题不丢**：`rule_freeze` 在同一次 pair 运行里跑同样这两个文件，问的是这条规则问不了的连续问题。`DUP_DISTANCE = 0.5` 保留为 `extra['reference_cut']`；**旧口径抓到的 15 对全部正好在 0.0，什么都没丢**。

**C（规则不该存在）被考虑并否决** —— 规则可达、且能回答一个可问的问题；删它不修任何误判。

**指挥窗口独立复验**：第一次只抓到 4 张平铺 PNG、**语料取错了**（帧序列在 `fr_a`/`fr_b`/`full_*` 等**目录**里）——**测了不存在的东西**，本项目第 N 次同族错误；改按真实帧序重测：`fr_a` 41 帧 → 40 个相邻对，**`p50 = 0.486258`、`min = 0.000279`、`max = 13.288225`**，**恰 20/40 落在旧阈值 0.5 之下**（与自报一致），而新口径 `<= 0.0` 命中 **0/40** —— **「同一帧」判据在这段真实序列里从不误报**。**`p50 = 0.486` 紧贴 0.5 正是「任何切口都无解」的直接证据**：那不是一个干净的分布。

**它主动上报四条自身失误，其中两条正是本项目记录在案的复发**：

① **自己写的守卫抓住了它自己两个假测量** —— 它断言「两张相差 1 个灰阶的纯色帧在 0.0 相撞」，实测是 **1.0**（纯色帧的签名就是那个灰阶本身）；它引用的「柱状 vs 平移文字在 0.040597 相撞」实测是 **18.548967**。**两处都先写进了测试和文档、才去测** —— 与 P18「在 docstring 里断言会被自己推翻的数字」同族；
② **它第一版 B 守卫本身就是文本存在性断言**（且 sanity check 方向是反的，断言旧说法仍然存在）—— **那将是本项目记录在案的第七次**，已改为从 AST 读数字字面量；
③ 漏掉一个 fixture 参数导致 `TypeError`，并一度用旧 docstring 里从未测过的 0.033/0.055 覆盖了实测值 0.151228；
④ 把 `.p19_*.txt` 写进仓库根后**移出去**（未用 `git checkout` 丢工作）。

**两处超出最小范围的改动，都已报备**：

- `qa_layers.MEASURED_NOTE['duplicate']` 原本断言「3042 对在切口下、50914 对在上、两侧落在 0.498465 / 0.500140」即「一把真实数据上的真切口」—— **它的测量推翻了这个结论**，留着就是在本项自己的文件里留一句已过时的断言。已改为实测值。**`PINNED_LAYERS` 语义未动**（`duplicate` 仍在 Motion —— **层跟着输入走，不跟着切口走**），由既有 partition 测试钉住；
- `tests/test_p18_qa_layer_partition.py:107` 用 sha256 钉住 `visual_qa.py`，**它正确地响了** —— 已在同一提交里更新**并写明理由**，正如该测试自己要求的那样。

---

## P20 — 同一个问题三处三个数字　状态：✅

记录文档 `docs/P19_DUPLICATE_POPULATION.md` §1a 的处置；守卫 `tests/test_p20_one_ruler.py`（5 条）。全量 424→**431 passed, 3 skipped**（+1 skip 见下）。

**两把尺子：逐位相同，但不该合并。** `visual_qa.py:311/331` 与 `take_ranker` 各有一份 `signature_distance`/`signature` —— 实测 **120 对真实语料 + 12 档合成幅度 (`repr()` 级别，float32 噪声会显形) 零差异**，且**它们按构造相等**（两边都字面是 `float(np.abs(a - b).mean())`）—— **这恰恰是两份拷贝会漂移的原因**。**但 `visual_qa` 不能 import `take_ranker`**（cv2；`test_the_module_does_not_import_the_renderer` 明令禁止）⇒ **裁定不合并**（超出本项范围，且可能伸进 `ceo_mindread_ep01` 那条独立管线），**改为加守卫防漂移**。

**⚠️ 顺带发现（未修）**：`visual_qa.signature()` 用 **PIL** 读 PNG，`take_ranker.pixel_signature` 用 **cv2** 读视频 —— 同一真实帧上两次重采样的差异是 **4.106** 均绝差，**约为最紧的"真实不同 take 对"（31.264）的 13%**。真实存在、但仍落在间隙里，未修。

**阈值裁定 A：让 `select_takes.py` 引用 `rank_takes.DUP_THRESHOLD`，且它明确拒绝判断哪个数字对** —— 因为测量判不了：

- **总体**：12 个磁盘 shot 目录（= `select_takes` 的 12 个 `shot_targets`），只有 S05A(4 take) 与 S06(2 take) 有多于一条 ⇒ **7 对**进入任一循环；
- **分布**：那 7 对 = **{0.000} ∪ [34.543, 62.820]}**；扩到全部 120 对 = **{0.000} ∪ [31.264, 105.839]}** —— **P1 的间隙仍成立**；
- **它定不下来的部分**：**(0.0, 34.543) 里的任何值对现存每一对都给出相同判定**，**0.5 与 1.0 都在这个空隙里、都只抓到那一个 0.000 对**。

`git log -S` 显示那个 `1.0` 是 P1（`47d2f79`）写进来的 —— **与它并不依据的那份测量同时写下**。

**⚠️ 指挥窗口复验时纠正了执行 agent 的一处方向性错误**：它写「a near-duplicate at 0.7 is caught by 0.5, missed by 1.0」—— **反了**。判定是 `d < threshold`，**阈值越大判得越宽** ⇒ **1.0 抓得到 0.7、0.5 漏掉它**。它自己跑出的变异输出第 2 行也是 `duplicate=False`，**与它 docstring 里那句相反** —— 注释与自己的输出口径不一致。**指挥窗口独立复核：** `0.7 < 0.5` 为假、`0.7 < 1.0` 为真；**统一到 0.5 是收窄盲区，不是放宽**。**结论（删掉第二个字面量）不受影响 —— 理由方向错了，结论方向对。**

**`DUP_THRESHOLD = 0.5` 的值未被改动**（`rank_takes.py` 仅注释变更），`take_ranker.py` 与 `visual_qa.py` 字节未变。

**五条变异全部杀掉**（每条都先 assert 落盘、并从活模块读回值，再读结果）。其中 mut2 造的正是**裁定 B 的形状**（一个数字 / 两个问题），由三尺守卫以 `assert 0.5 == 0.0` 抓住。

**执行 agent 主动上报的失误里，有三条造出了假绿，值得单列**：

① **`sys.modules.setdefault('cv2', stub)` 在 `import cv2` 失败之后是空操作** —— 此时 `sys.modules['cv2']` 已被置为 `None`，于是 `take_ranker` 导入失败、`select_takes` 打印「take_ranker unavailable」、`_auto_rank` **每个用例都返回 `[]`** —— **守卫根本没有上膛**。已改为直接赋值，并新增 `test_the_guard_is_actually_armed` 断言 `_RANKER is not None`；
② **它跑的是 `out/` 里的一份快照副本**，`ROOT = parents[1]` 解析到 `E:\Minimax-H3\out` —— **测了一棵没有 `studio/` 的树**（与指挥窗口本轮 glob 到 4 张平铺 PNG 属同一族错误）；
③ `_auto_rank(raw_root)` 会追加 shot id 而 `rank_shot(shot_dir)` 不会，把同一个目录传给两者 ⇒ `_auto_rank` 什么都看不到 —— **读起来像「没有 take 会相撞」，而不是一个错误**；
④ 一处 stub 名复用于两条 take，导致每个 metric 的 `take_id` 都是 `B_T01`。

**另**：它有一次**把命令管道进 `tail`，从一个真失败里读到 `EXIT=0`** —— **正是工单点名的那个陷阱**；此后所有退出码改由 `subprocess` 取，**不再用管道**。

**一处偏离（已报备，且我认为处理得当）**：py-3.10 有 cv2 但**没有 pytest**，所以语料测量**在本机无法跑进 pytest**。它把测量放进普通函数 `measure_within_shot_distribution()`，用 3.10 脚本驱动（输出在 `out/p20_probe/measure_310.txt`），**在 3.12 套件里 skip 而不是撒谎**。**所以那些断言本身是验证过的，但 3.12 套件跑绿并不等于它们被跑到** —— **这个「skip 不等于通过」的诚实标注，正是本项目反复要求的东西**。

**第三把尺子没有强行判等**：`visual_qa.rule_duplicate` 是第三份 `signature_distance`，但 P19 给它 `SIGNATURE_EQUAL = 0.0` 因为 `--frame-pair` 递给它的是**同一次渲染的两个相邻帧**（另一个总体，且语料证明不分离）。**这个差异被记录并附证据，而不是靠断言三者相等掩盖掉。**
**记录未修（超范围）**：`ceo_mindread_ep01/scripts/select_takes.py:90` 对同一比较用 **1.0** 而非 0.5 ⇒ **三个调用点持有三个数字**。
**这条本身就是一个「同一个问题三个答案」的实例，值得单列**，已写入 `docs/P19_DUPLICATE_POPULATION.md` §1a。

---

## 变更记录

- 2026-09-30：升级总规划立项（docs/UPGRADE_MASTER_PLAN.md + UPGRADE_PROGRESS.md）。
- 2026-09-30：**P0 完成**。审计发现 12 条风险；当场修复 4 条高危：R1 公开仓库泄露（gitignore 失效，紧急推送）、R3 mtime 猜测+无限轮询、R4 CWD 注入 PATH、R5 fit 二次拉伸。产出 pipeline_manifest.yaml + config/ 配置层 + 审计报告。链 A 复测 16/16 PASS。**下一步 P1 TakeRanker**（select_takes T01 默认 → 自动评分选片）。
- 2026-09-30：**P1 复验裁定（独立取证）**。R-01/R-02/R-03 三工单全过；从仓库外 `/tmp` 跑测试 20 passed 证明可移植性（非仅 grep）。**阈值安全性用真实数据裁定**：9 对真实 take 的像素距离分布 = `{0.000} ∪ [34.5, 67.2]`，中间为空 —— 0.5 精确落在真重复上，距最近的真实不同 take 有 34.5 倍余量。
  - **新事实**：`03_video_raw_v2_archive/S01/S01_T02.mp4` 距 S01_T01 为 67.175，是**真正不同的生成而非重复** —— 是被 T01 硬默认埋掉的**有效素材**，不是浪费的 GPU。P1 价值的第二次独立确认。
  - **已知边界一（样本量薄）**：真实数据仅 9 对，其中真重复仅 1 例（n=1）。后续每积累多 take 镜头应重测该分布。
  - **已知边界二（语义已收窄）**：0.5 只抓「逐像素完全相同」，不再抓「近重复」。若将来出现「同 seed + 非确定性采样器」的重跑（距离小但非零）会漏检。已写入 `rank_takes.py` 阈值注释。
- 2026-09-30：**P1 完成**。TakeRanker 上线：9 项客观指标 + 像素级冗余检测 + 人工 override 最高优先 + fail-closed。EP01 实测：S05A 自动改选(闪烁缺陷 take 被淘汰)、S06_T02 判定同 seed 冗余(像素差 0.0)。select_takes 全 12 镜头走自动排名，QA 16/16 PASS。**边界认知：客观指标只能淘汰坏的，无法在「都好」里挑出更好的——S06 两 take 全指标相同，VLM critic 留作增量。**
- 2026-09-30：**P6.2 完成 —— Browser Stack 真正居中**（commit `5be9a46`）。60 passed，tsc 干净，完整渲出 `out/showcase_p6_centred.mp4`（1920×1080@60，`yuv420p(tv, bt709)`，过 `qa_final` 严格 pix_fmt）。
  - **上一条的归因是错的，已更正**：原记录「光学重心偏右 = 近端窗口被透视放大」只是三个缺陷之一，而且是次要的那个。量像素后才发现真正的缺陷①大得多。
  - **过程失败（第四次同类，但这次是「读源码代替量像素」）**：上一轮我判「参数已生效」的标准是**读代码确认组件读了这些参数**，不是**量渲染结果**。这个标准是无效的 —— 本轮三个缺陷全部能通过读源码发现「代码看起来对」：①注释写得像已修、②新写的反解数学读起来完全合理、③一行分数方向写反。**新规则：构图/排版类改动，验收标准只能是像素测量，不能是「代码读起来对」**。已落成工具：`studio/bin/still.mjs`（单帧渲染）+ `studio/scripts/measure_frame.py`（剪影/内容 bbox）。
  - **隔离实验推翻了自己的假设**：先归因于 `perWindowRotateY` 的 3D 旋转，把旋转与相机全归零重渲 —— 仍 +33px，假设被证伪。手算才发现是 `screenScaleFor` 把分数写反了。**先证伪再修，比先修再验便宜**。
  - **取舍已显式化而非隐式**：精确居中 ↔ 真透视尺寸在数学上互斥（透视下中心对称与剪影对称不可兼得，已推导）。做成图谱里的 `equalOnScreen` 显式二选一，两种都渲了都量了（+1.5px / +30.0px），默认精确居中。**没有偷偷选一个然后声称只有一个是对的**。
  - **方法论边界（新发现）**：`measure_frame.py` 的表面色剪影判据**只在无损 still 上可信**。同一帧从 h264 mp4 抽出来，Calendar 的剪影从 −0.5px 变成 −34px，而内容 bbox 仍是 0.0px —— 压缩噪声推过了颜色阈值。以后量交付视频一律用内容判据，量 still 才用剪影判据。
  - **顺手修的真缺陷**：`test_real_binary_still_prepends` 用 `os.environ['PATH'] = ...` 裸赋值且从不还原，**把被清空的 PATH 泄漏给整个测试会话**。此前没暴露只因没有别的测试需要 node。这是本项目第一次出现「一个测试污染另一个测试」。
- 2026-09-30：**P6.5–6.8 Design System 收尾 —— 双主题真正生效**。67 passed，tsc 干净，完整渲出 `out/showcase_p6_theme.mp4`（`yuv420p(tv, bt709)`）。四场亮色 + 四场暗色逐场目检。
  - **主题系统第一次渲染出来是坏的，而且是本项目最典型的一类事故**：演示图谱的 `style_bible` 声明了 15 个键，**只有 1 个真的生效**（`cameraLanguage.perspective`，且恰好等于默认值）。`palette` 抄的是暗色主题的原值 —— 对暗色渲染毫无作用，却把亮色主题打成了**明暗交替的半成品**（实测：bgAlt=#FFFFFF 亮、bg=#0A0A0C 暗、surf=#141418 暗、surfE=#FBFAF6 亮，全在同一个调色板对象里）。`typography` 写的是 `"900 120px Bahnschrift"` 这种 CSS 简写字符串，而 token 是 `{size,weight,tracking,leading}` 对象，`mergeSection` 的类型守卫把 4 个全部**静默丢弃**，而且角色名（display/kpi/body）根本不存在。
  - **定位过程值得记**：先量像素（背景 217→10，算出渐变两端一亮一暗）→ 网格采样确认是渐变本身而不是遮挡 → **把解析结果直接渲染进画面**（`DEBUG theme=… bgAlt=… bg=…`）才拿到确证。**推测（"是不是两个组件用了两套调色板"）错了一整轮，最后的答案在图谱文件里，我从头到尾没打开过它**。教训：组件层的值可疑时，先查喂给它的数据。
  - **删掉的比加上的重要**：删掉那份哑 style_bible，换成**一个**真生效的声明（`typography.numericDisplay.tracking`），并 A/B 验证 —— 0.92% 像素变化、变化区域精确落在 x[289..744] y[408..598]（就是那个大数字）。**一个能证明的声明，胜过十五个看起来像声明的东西。**
  - **顺手接上了一个哑字段**：`cameraLanguage.perspective` 之前没有任何代码读（`CameraRig` 只看 `scene.camera`）。已接为缺省值（场景自己的优先）。注意这份图谱每个场景都自带 perspective，所以对它是缺省而非覆盖 —— 已在图谱里不放该声明，**不声明一个接上了但对这份图谱无效的东西**。
  - **测量工具自身也有主题盲区**：`measure_frame.py` 原来按暗色表面色（`R≥19`）判剪影，亮色四场全部 EMPTY。**只对一个主题有效的验收工具，会安静地给另一个主题发错通行证。** 已重写为**背景相对**判据（取画面边框环的众数作背景，再按偏离量取 bbox），两个主题通用。同时把误导性的 `ink` 标签改成 `marks` 并写明它测的是内容范围不是居中。
  - **仍未做（如实记）**：`SPACE` 尺度仍是 8/16/24/40/64/104/168，与总任务书要求的 4…96 步长不一致；`DEPTH` 阶梯无场景使用；`CameraRig`/`primitives` 仍静态 import `MOTION`，所以 `motionLanguage` 的覆盖到不了它们（与本轮发现同类的哑声明，已记录未修）。
- 2026-09-30：**P6 复验通过并已推送**（`1595732..7bef0a8`，3 个提交）。复验官用我方工具独立复现了全部关键数字：Browser Stack 静止帧 **+1.5px**（与声称逐位一致）、亮色 backdrop **(244,241,234)** vs 暗色 (10,10,12)、图谱 `style_bible` 只剩 `['typography']`。复验官指出两处遗留问题，**两处都复现成立并已修**：
  - **(1) 居中判据对亮色不可靠 —— 已修，且是我这个工具的第三次同类错误。** 复现：`extent x[0..1805] offset=−57.5px`，而同一帧的 `marks x[411..1157]` 与暗色**完全一致**（说明构图没问题，是判据坏了）。根因：v2 用「边框众数当背景 + 固定阈值 8」，而**亮色背景自身动态范围 11 > 8**（暗色只有 6，所以一直没暴露）——大半个画面被当成内容。**固定阈值在这里根本不成立**：构图与自身背景的对比度和背景渐变量级相同，而这是逐主题的设计选择。<br>修法：逐行拟合背景（取该行左右边缘采样做线性模型，径向渐变在行内近似线性，且构图居中所以边缘是背景），再对残差取阈值；**模型解释不了这一帧时直接拒绝出数并返回非零退出码**，而不是给一个自信的错数字（错数字会被写进账本然后被争论，拒绝才会被修）。<br>复测：亮色 **+21.5px**、暗色 **+3.0px**；四场两主题逐一对齐（s01 −531.5/−531.5、s04 −0.5/−0.5）。s02 两主题差 18.5px 是**真实性质不是 bug**：暗色阴影 alpha 0.50 压在 10 亮度上只偏 5（低于阈值量不到），亮色阴影 alpha 0.19 压在 244 上偏 43（量得到）——所以 **`extent` 含能量到的阴影，跨主题不可比；`marks` 可比**（已写进脚本文档与本条）。<br>**新增 3 项测试**（`tests/test_measure_frame.py`，合成帧，不依赖任何一次渲染，因此可移植）：亮色窗口必须量到 ~0、同一窗口在两主题下 `marks` 必须一致、模型解释不了时必须拒绝且退出码非零。**变异测试通过**：把工具退回 v2 实现，亮色那条转红；还原后 3 项全绿。**这个工具错了三版，每一版在暗色上都对** —— 教训是验收工具必须**跨主题验证**，而且要在有第二个主题之前就写好跨主题测试。
  - **(2) `still.mjs --out` 把文件当目录且不提示 —— 已修。** 现在识别 `.png` 后缀（单帧时按文件写），并显式打印「output directory」与最终写入清单与数量；`.png` 配多帧直接拒绝（exit 2）。三种模式实测通过。
  - **顺带修了一个自己写的输出格式坑**：`offset={offset:+7.1f}px` 的宽度限定符会补前导空格，输出成 `offset= +3.0px` —— 按空白切分的解析器会把它拆成两个 token。已去掉填充（字段保持单 token），测试解析器改用正则。
  - **70 passed**，tsc 干净，工作树干净。
- 2026-09-30：**P7.0 守卫 —— 复验官发现守卫本身会给假通过，阻塞 P7.1**。守卫已修，与守卫合入同一提交。
  - **缺陷（我提交时自己没发现，复验官做对照实验抓出）**：`diff_dir` 用 `next(dir.glob('*.png'))` 取文件，**不排序、不按帧号配对**，而输出目录从不清空。后果：早先运行残留的 `f00200.png` 与本次的 `f00400.png` 被拿来比较 —— **拿同一部片的两个不同帧做比较**。<br>**我自己构造复现**：a/ 放 f00200+f00400、b/ 只放 f00400，两侧 f00400 是同一张图，`diff_dir` 仍报 **「2.89% changed, box (600,400,899,599)」**。三个 `--set`（包括绝无可能生效的 `nonexistent.deep.key=1`）返回**逐位相同**的 33025px / 1.59% / 同一区域。<br>**为什么这是最坏的一类错**：它输出一个精确到小数点后两位的百分比和一个坐标框，看上去毫无问题，而它是 P7 全部图表字段的裁判。**会给任意字段都报「已验证」的守卫等于没有守卫，而且更危险 —— 它让哑字段拿到通行证。**
  - **我上一轮报的 33025 / 1.59% / (289,408,767,598) 是残留噪声，不是真实 A/B 结果**，在此更正。修好后用 `-0.01em` 第 60 帧重测得 **39106 / 1.89% / (264,404,759,601)**，与复验官实测**逐位一致** —— `typography.numericDisplay.tracking` 确实接通。
  - **修法（按复验官建议）**：`diff_dir` 接收 frame，按 `f{frame:05d}.png` 精确配对，缺失时报错并**列出目录里实际有什么**（让原因一眼可见）；`ab_field` 渲染前清空输出目录；`still.mjs` 打印目录里的既有 PNG 及哪些会被覆盖，并支持 `--clean`。
  - **同时把「模型解释不了就拒绝出数」扩展到输入校验**。复验官那轮自己错了三次，工具**一次都没提示**，这才是要害：
    1. `--frames`（工具要 `--frame`）→ **静默用默认 400**。改用 argparse，未知 flag 现在报错退出 2。
    2. `tracking=5`（该字段现值是 `"-0.055em"`）→ **静默接受**，CSS 无效、React 丢弃声明、像素零变化 —— 于是**一个打字错误被读成「这个字段是哑的」**，这是能拿到的最具误导性的答案。现在**值类型与图谱现值不符直接拒绝**（REFUSED，退出 2），并把两个值都打出来。Python 的 `bool` 是 `int`，所以 `True` vs `1` 单独判。
    3. 在第 455 帧测 `numericDisplay`，而那一帧根本没有大数字 → **静默报 0px**。现在零变化时会一并报告**该帧的内容占比**（沿用 measure_frame 的逐行背景模型），把「字段没用」和「你测了一帧没有目标的画面」区分开。
  - **变异测试通过**：把 `diff_dir` 退回 `next(glob(...))`，`test_a_stale_frame_in_the_directory_cannot_be_compared` 转红；还原后 14 项全绿。**84 passed**，tsc 干净。
  - **端到端三态复核**（修之前三者返回同一个数字）：真字段 39106px/1.89%/exit 0；接上但对本图谱无效的 `cameraLanguage.perspective` 0px/INERT/exit 1；不存在的 `nonexistent.deep.key` 0px/INERT/exit 1。
  - **一个仍未解释的细节（如实记）**：`cameraLanguage.perspective` 已接为缺省（`CameraRig` 读它），但这份图谱每个场景都自带 `perspective`，所以它对本图谱确实无效。要让它生效需要移除场景级 perspective，那是艺术判断，**未擅自改**。
- 2026-09-30：**P7.1 完成 —— 九种图表，逐场渲出，A/B 证据 23/23**（103 passed，tsc 干净，完整渲出 `out/charts_demo.mp4`，1920×1080@60 `yuv420p(tv, bt709)`）。
  - **先做的不是图表，是数学**：`scale.ts` 零 React 零 Remotion，配 `scale.check.ts`（50 项）。**两个真缺陷在渲染里根本看不出来**：`niceTicks` 的好数阶梯缺 2.5 且是向下取整（0..1 要四格却只给三格），以及**反向定义域返回空**。两条都变异测试过。
  - **变异测试抓到我自己的断言有洞**：第一次变异（把 Fritsch–Carlson 加权换成切线平均）**没被抓住** —— 因为那组测试数据的内部切线全走了极值分支，加权那行根本没执行。改测真正防过冲的极值分支，转红（`escaped: 116.67`，正是手算的 100+3.33×5）。**断言本身也有洞**：我按空白切分路径取数字，而路径里是 `"100,"` 这种带尾随逗号的 token，`Number("100,")` 是 NaN 被跳过 —— **等于没在检查**。正则化之后才转红。
  - **`-0` 是不止显示的 bug**：`Math.ceil(-1e-9)` 是 `-0`，一路传到刻度，而 V8 的 `(-0).toLocaleString()` 真的给 `"-0"` —— 轴上会出现 "0, 20, 40, **-0**"。定义域和格式化两处都堵。
  - **目检抓到 9 个渲染缺陷，全部是「读源码看不出来」的**（每个都渲出来看才发现）：
    1. Y 轴刻度标签跑到画面外 —— `right: W - plot.x` 方向搞反（`right` 是从容器右边缘量的）
    2. X 轴标签全部叠在一起 —— `xLabels.map` 每次渲染了一个包含**全部**标签的 div
    3. X 标签和柱子不对齐 —— 我一度写了注释说"均匀分布而非对齐"，那是回避；改为标记自己提供 `xAt`
    4. 最高柱顶到画面顶部、数值标签被压在柱子里 —— 定义域没留 headroom
    5. 曲线冲出右边界 —— `plot.w` 用 `comp.width` 算，而绘图区在**带 padding** 的 div 里
    6. **`showArea` 对 line 图无效** —— 硬编码 `withArea={false}`，而注册表显示它"被读过"
    7. Slope 的系列名压在它自己的线上（中点标签正好落在线上）
    8. Heatmap 的 Y 轴数字刻度和行标签相撞 —— 而 heatmap 的 Y 轴是**分类**的，数字刻度不仅无意义还撞了有意义的标签；`colLabels` 更是**完全没渲染**，又一个哑字段
    9. Rank 的 Δ 换行、Y 轴数字刻度同样无意义、四行只占上部三分之一
  - **`TYPE_OPTIONS` 当运行时闸门是个设计错误**（第 6 条和 volume 的 `emphasisIndex` 都源于此）。一张过时的声明表能让一个能用的选项静默失效，而守卫看不见，因为名字在文件里。**已去掉闸门，表降级为文档，准确性另测。**
  - **磁盘事故（未解决，需要你决定）**：C: 盘 **0 字节空闲**。根因是 **125 个 Remotion 临时 bundle，共 58 GB** —— 每个都把整个 `studio/public/`（773 MB，含 EP01 的 mp4 暂存副本）复制了一份进去。**我这边的根因已修**：`still.mjs` 加 `--public-dir`，A/B 工具把临时目录指向 E:（有 2.7 TB）并用空的 public 目录。**但那 58 GB 在你的系统盘上，删除不可逆，等你授权再动。**
- 2026-09-30：**P7.1 复验后修正**。复验官独立核实了 A/B 23/23、七个类型已接渲染、`option()` 闸门已拆，并指出**闸门只拆了一半**。
  - **只拆了一半，且我自己的注释是假的**：`pickOptions` 仍在**入口**用 `ALL_OPTION_KEYS`（派生自 `TYPE_OPTIONS`）过滤图谱传进来的值，图谱设的值在 `option()` 看到之前就被丢掉。而 `option()` 的 docstring 写的是「a stale table cannot silence a graph」—— **一句关于设计保证的不实陈述，正是本项目已经栽过三次的那一类**（半帧、33025、已修），且出现在一个看起来像承诺的位置。<br>**差集算过：当前 17 个选项全覆盖，今天没丢任何值**，所以不是活 bug；但「新加一个选项忘了填表」会同时绕过注册表检查和 A/B 覆盖检查 —— **两张网都从同一张表出发**。<br>**没有只改文案**：改成用 `Object.keys(DEFAULT_CHART_OPTIONS)` 作键。该对象类型是 `ChartOptions`，所以**少一个默认值 TypeScript 就编译不过** —— 这张表在结构上无法像手维护表那样落伍，加一个选项即刻生效、无需改别处。`option()` 的 docstring 现在描述的是一条**成立**的保证，并加了测试把入口路径也钉住。
  - **slope 端点标签避让**：emphasis 系列的端点圆点是金色（线上最显眼的东西），数值标签原本只距圆点 8px，看起来像「19 被金点盖住一半」。间距提到 30px、与圆点垂直居中、加 `nowrap`。重渲目检确认。
  - 复测：**104 passed**、注册表 0 问题、**A/B 矩阵 23/23 仍全活**（`pickOptions` 改过，证据必须重新成立而不是沿用）、tsc 干净。
  - **磁盘（仍未处理，等拍板）**：复验官独立核实系统 TEMP 下 `remotion-webpack-bundle-*` 共 **127 个 / 59 GB**，**内容只有 webpack 构建产物（`*.bundle.js`、`*.bundle.js.map`），无任何项目数据**。前置条件两条：①先关掉正在跑的 node 进程（复验官看到 PID 36356 / 11888），否则可能打断进行中的渲染；②**只删这一类**，同一 TEMP 下还有 `DiagOutputDir`（3.5 GB）是别的东西，**不要连带清**。<br>我这边的根因修复已生效（TEMP/TMP 指向 E: 的 2.7 TB、`--public-dir` 用空目录），**不删也能继续干活，但会复发 —— 删除是唯一的永久解**。
- 2026-09-30：**A/B 工具的盲区 —— 「我路径写错」和「字段是哑的」在产物里长得一模一样**。复验官在复验中把工具用错五次，得到三个 0px，其中两个**无法与真缺陷区分**。
  - **我复现了那条复现不出来的矩阵行**：根因是路径写成 `scenes[0].content.chart.emphasisIndex`（**方括号**）。我的 `_set_path` 把 `scenes[0]` 当成普通键名，**凭空造出一个顶层对象** `scenes[0]`，没人读它，于是 0px，工具报「INERT」—— 听起来像刚抓到一个 bug。
    - 矩阵原样（`scenes.0...`，值 0，帧 120）：**212,569px (10.25%)**，区域 (235,187,1728,940)
    - 复验官的值（正确点号路径，值 1，帧 60/130）：**197,522px (9.53%)**，区域 (**568**,187,1728,940)
    - **区域起点从 235 变 568，正好是高亮柱从第 0 根换到第 1 根** —— 定位信号确实能指出哪根动了。**矩阵行是真的，复现不出来是路径打错。**
  - **但这仍是工具的缺陷，而且是最要命的一种**：一个专门产出证据的工具，把调用方的笔误报成「这个字段是哑的」。**能被误读成结论的输出就是缺陷** —— 三次假账的教训在这里完全适用，而这次它会写进账本然后被争论。
  - **(a) 报告带全溯源**：`chart_ab.md` 每行现在给出 `选项 / 场景下标+场景类型+图表类型 / 精确点号路径 / was→now / 帧号 / ink% / 像素数 / 百分比 / 区域 / 判定`，并附上可复制的命令模板。**一个没人能重跑的数字是传闻，不是证据。**
  - **(b) `_set_path` 区分「新建叶子」和「新建容器」**：规则是**只有最后一段可以不存在**。设置图谱从未提过的字段是合法的（那正是 A/B 一个没人设过的选项的方式）；凭空造三层之上的容器是笔误，**直接拒绝而不是测量**。方括号语法单独报错并给出正确写法。**BAD PATH（调用错误，exit 2）与 INERT（关于代码的论断，exit 1）是两种不同的词** —— 报告一个笔误用「字段没接线」的措辞，就是让笔误变成账本里的一行发现。
  - **过程中我自己写错两次**：`_descend` 在 `create=False` 时没抛错，裸 KeyError 逃出了我新加的 PathError；以及测试断言 `main()` 抛 SystemExit，而它其实是 return 2。两处都记在提交里。
  - 复测：**106 passed**、注册表 0 问题、**A/B 矩阵 23/23 全活且报告带溯源**、tsc 干净。
- 2026-09-30：**P7.2 统一 chart 生命周期**（`charts/lifecycle.ts`）+ **用测量抓到一个自 P7.1 就存在的柱状图入场缺陷**。
  - **九个标记各自一套入场，是设计缺陷而非执行遗漏**：`Bar` 用 `land` 弹簧长、`PathMark` 用 dash offset 画、`Slope` 从左往右伸、`Heatmap` 缩放格子 —— 同一个「到达」发生了九种。**统一为纯函数 `lifecycleAt(frame, duration, count, opts)`**，五阶段 `intro / settle / highlight / focus / exit` **按场景时长的比例而非固定帧数**，所以 90 帧和 600 帧都读得对；**入场长度封顶**为 `min(场景的 34%, 标记实际所需)`，否则 40 帧场景会在没画完时就切掉。`emphasis` 是**阶段**的属性而非第二套动画：intro 升起 → settle 到位 → highlight/focus **保持不动**。<br>`lifecycle.check.ts` **60+ 项（10-01 复验订正为 29 个 `check(` 调用点 / 54 条断言 —— 原数字两种读法都到不了 60）**，含三条渲染里看不出的：阶段在任意时长上无缝无重叠、封顶确实生效、**stagger 必须让最后一根比第一根晚到**（同步的 stagger 不是 stagger）。
  - **`types.tsx` 现在零 Remotion import**：九个标记是 frame 上下文的纯函数，时钟只有一个来源。迁移后 `useCurrentFrame` / `useVideoConfig` / `spring` / `interpolate` 全部失去最后一个读者，**删掉了而不是留着误导后来的人**；文件高度改由 frame 提供。
  - **测量抓到一个四次稳定帧渲染都没暴露的缺陷**：柱子**从顶端往下长**而不是从基线往上长。`top: min(y, zeroY)` 是常数、height 增长，柱子从顶端垂下、**只在满高时恰好落回基线** —— 稳定帧看着完全正确，入场中间帧全错。**自 P7.1 就在，我之前渲的四帧全是稳定帧。**<br>修法是把柱形几何抽成纯函数 `barBox(valueY, baselineY, progress)` 放进 `scale.ts`，9 条检查钉住：零进度贴在基线上、满高到自己的顶、单调上升、**底边从不动**。`VolumeBars` 同一缺陷一起修。<br>**判据是黄金区域上下边随帧的变化**：修前 top 恒 187、bottom 从 268 漂到 909；修后 top 从 828→510→320→202 上升而 **bottom 恒定 909**。
  - **A/B 矩阵 24/24，报告带完整溯源**（`option / measured / scene / scene frames / chart type / path / was→now / frame / ink / px / % / region / verdict`）。这一轮三个数字全是我「考错对象却得到格式正确的答案」：<br>① **`enterFrames` 被封顶**：150 帧场景封顶 51，`34` 和 `90` 都夹到 51 —— 该时长下选项确实无效（**正确行为、无用测量**）。加 `c10_bar_long`（600 帧，封顶 204）专供测运动项。<br>② **`--frame` 是绝对帧号**：第 10 场在 1350..1950，我写 90 落进第 1 场。<br>③ 报告加 `scene frames` 列正是为了让这类错误**一眼可见**；**`measured` 列写进报告头部** —— 运动项只能在低 ink 帧测、静态项只能在高 ink 帧测，**同一张矩阵两类选项取帧规则相反**，不写明将来有人拿稳定帧测运动项会得到一个「看起来像结论的零」。
  - **过程中的工具失误，如实记**：本轮**六次**补丁因文件是 CRLF 而**静默匹配失败**（`
` 对不上 `
`），还有一次替换脚本在写盘前异常退出 —— 所以我说「已应用」的东西实际从未落盘。**我在一个报告工具上重复了同一类静默失败**，最后改成「先定位所有索引、一次算完、写一次」。静默的失败比明确的失败危险，这是老教训的新实例。
  - 复测：**106 passed**、tsc 干净、三份可执行 check 全过（projection / scale / lifecycle）、**A/B 24/24 exit 0**、完整渲出 `out/charts_demo.mp4`（1950 帧 32.5s，`yuv420p(tv, bt709)`）。
  - **未做**：P7.3（annotation 避让 / 数字格式 / theme / stagger / emphasis 收口）；矩阵接进 `tests/` 成为 CI 项（复验官建议 P8 收尾做）。

- 2026-10-01：**复验官独立核实交接状态**（接手 `docs/HANDOFF_VERIFIER_20261001.md`，`git log` 交叉核对）。**抓到 3 处账实不符 + 1 个当下生效的机制缺口**，进度表滞后已按 `git log` 订正。
  - **订正进度表**：`7.2` 行 ⬜ → ✅（实际 `7a6bcaf` 已提交）、P7 表头 ⬜ → 🔄、`7.1` 行补注第 10 场（1950 帧）、`7.1b` 行补注矩阵 24/24。**changelog 判定可信、任务行与表头滞后 —— 这条判断经核实成立。**
  - **假账一：「60+ 项」不成立**。`lifecycle.check.ts` 实测 **29 个 `check(` 调用点、跑出 54 条断言**（`dur` 循环把 29 展开为 54）；`scale.check.ts` 为 59 调用点 / 58 断言。已在上方 P7.2 条内就地订正。
  - **假账二：「106 passed」当前不可复现**。`python -m pytest tests/ -q` 直接 collection ERROR（`No module named 'cv2'`）—— **pytest 只装在 Python 3.12、cv2 只装在 3.10，106 = 102 + 4 劈在两个解释器里**，两个都不是完整环境。实测 **102 passed / 3.16s**（`--ignore=tests/test_take_selection_behaviour.py`，该文件 4 条测试全部需要 cv2）。**裁定：不动环境**（用户决定），缺口记录在此。
  - **机制缺口：`lifecycle.check.ts` 没接进 pytest**。`tests/` 全库零引用；而 `scale.check.ts`（`tests/test_chart_math.py:27`）与 `projection.check.ts` 都接了。**P7.2 的 54 条守卫目前纯靠自觉**，且 `out/` 被 `.gitignore:33` 忽略、矩阵报告不入库。**这不再是 P8 的事 —— 对 P7.2 已经生效**，已并入 7.3 待办。
  - **订正交接文档的错误判断**：交接第二节称「表头 `P6 状态：🔄` 滞后」—— 实测 **准确**（6.7 `SPACE` 仍是 8…168 而非规定的 4…96、6.8 `DEPTH` 四场无一使用，两处均已诚实标注）。只有 P7 表头滞后。**教训又一次兑现：交接文档本身也是待验证的主张。**
  - **核实通过项**：`out/charts_demo.mp4` = 1950 帧 / 32.5s / 1920×1080 / yuv420p / bt709；`charts_demo.json` = 10 场 1950 帧；`out/chart_ab.md` = **24 行全 LIVE**；`barBox` 在 `scale.ts:276` 且有基线锚定检查；`types.tsx` 零 remotion 引用；`lifecycle.check.ts` exit 0、`scale.check.ts` 58 ok；C: **77.62 GB** 可用、TEMP **5.28 GB**；工作树干净；`origin/main` 落后本地 1 个提交（`014ebe7` 交接文档）。
- 2026-10-01：**P7.3 审计（先审计，再修改）—— 收口点全部列出，两条最重的主张先像素坐实**。渲 `out/p73_audit/f120/f00120.png`（bar 场稳定帧）与 `f570/f00570.png`（slope 场稳定帧），量出来的：
  - **[实测] 柱状图数值标签沉进自己的柱子里 —— `declutter` 的排序假设对柱状图不成立**。`declutter` 注释声称「value labels in these charts are already ordered by value」，但 `Bar` 按**类别顺序**（Overview/Retention/Errors/Signups/Revenue = 48.2/39.9/52.1/36.8/61.4M）传入，y 序是乱的；declutter 保序下推，把后面的标签推到前一个下面。实测 label 中心相对柱顶：0/1/3 号 **−10/−9/−9px（正确）**，**2 号 +160px、金色 emphasis 柱 4 号 +322px —— 标签在自己柱体内部**（近白字压金色底）。修法：按 y 排序后 declutter（`declutterByY`），上界从整屏收到 plot 底（否则短柱标签会压上 x 标签行）。
  - **[实测] Slope 自建 y 映射，和它所在的轴不同尺度**。frame 域带 headroom（showValues=false 时 +4%），Slope 却用 `local=[min,max]` 自算 —— 正是 `ChartFrame` 存在的理由所禁止的「标记与轴不同尺度、可读而错误」。实测：刻度带间距均匀 **210.5px/10 单位（=21.05px/单位，frame 尺度）**，"60" 刻度中心 y=114，而 61 值的线顶在 **y≈58**（frame 尺度应为 93）—— **顶端偏 36px ≈ 1.7 个刻度单位**，恰为 headroom 的量。`test_no_chart_mark_owns_its_own_scale` 只查 `domainFor`/`niceTicks` 两个**名字**，漏了内联 `const domain: Extent` + `const y = (v)=>` —— 守卫也要长牙。
  - **[源码] annotation 其余**：line 点值标签无 declutter（n≥15 才撞，但选项已声明）；slope 两端列与中点系列名无 declutter；**bubble 标签双渲** —— frame 底行（`xAt=(i+0.5)/n` 对多行网格本身错位）+ 圆下各一份，c05 的 Mon..Sat 出现两遍，且 `showValues` 门控的是**类别名**不是数值（`labels?.[i] ?? valueText`，有名字时 showValues 不显示任何值）；**Bar/Bubble 标签缺 `life.presence`**，其他七种标记退场时淡出、这两个的标签留到硬切。
  - **[源码] 数字格式**：rank Δ 手写 `toFixed(1)%` 绕过 `formatValue`；Δ 方向色用 accent —— 而 `options.ts` 的文法写明 accent 只给 emphasis，主题里 `positive/negative` 两个 token 正是给方向的。
  - **[源码] theme**：heatmap 格子填充硬编码 `rgba(245,242,234,α)` —— 亮主题下**色阶反向**（值越高越白，在纸色底上越看不见）；emphasis 格文字硬编码 `#14140F` 而 `PALETTE.onAccent` 的注释写明就是为这个格子准备的；`useMarkPaint().fade` 硬编码 rgba 且**零读者**；Chart.tsx 无值报错文案硬编码 `#E8C464`。
  - **[源码] stagger/emphasis**：**Sparkline 整个不在生命周期上** —— 无入场、无退场淡出、无 emphasis，c09 满帧场景硬弹出而另外八种都在走五阶段；frame 家具（网格/基线/刻度/轴标签/x 标签）**没有退场** —— 合成里没有 SceneExit，标记按 presence 淡出时轴还满亮度挂着直到硬切；死代码四处（Bar 的 `{SPACE ? null : null}`、Slope 的 `* 0` no-op、未用 import `scaleFrom`/`staggerPosition`）；`TYPE_OPTIONS.slope` 声明了 `showValues` 但 Slope 从不读它（只影响 frame 留白）。
  - **[守卫] 注册表被注释满足**：`check_registry` 是**名字出现**检查，`enterFrames` 登记在 types.tsx —— 它在 types.tsx 里只出现在一句**文档注释**里，真实读取者是 ChartFrame。和 showArea 同一类：名字在文件里、不在那个组件上。修法：检查前剥离注释 + 把条目移到 READER_FRAME（先演示转红再修）。
  - **附带事实核对**：磁盘已由复验官实测解决（C: 77.62GB、TEMP 5.28GB，现存 7 个新 bundle），该项从待办销账；`014ebe7`/`6abbaf2` 两个文档提交已在 main 且已推送。
- 2026-10-01：**P7.3 完成 —— 标签在说谎、轴与线不同源、第九个标记不在时间线上；两条实测缺陷修后复测归位**。
  - **修后复测（同一套量法；修前数字见上一条审计）**：
    - **柱标签**：渲 `out/p73_fix/f120` 实测五个 label 中心相对柱顶 **−10/−9/−10/−10/−9px**（修前 2 号 +160、金色 emphasis 柱 +322）。**测量本身也修了一处**：修前 3 号柱 "top=492" 是标签恰好挡住填充像素的污染读数（按其余四柱线性插值真值 477）——修后标签在柱上方，检测不再被挡。
    - **slope 轴线同源**：渲 `out/p73_fix/f570`——刻度字形与修前**逐位同坐标**（x 113..131，五带 y=114/324/535/745/953，间距 210.5px/10 单位），线顶从 y≈45..60 移到 **y=83（圆心 93）**；frame 尺度下 61 应在 114−21.05≈93 —— **线顶与 "60" 刻度相距 21px = 数据差 1 单位**（修前 57px、偏 36px ≈ headroom 量）。
    - **bubble 不再双渲**：mp4 抽帧（修前）vs 新渲 f720——底行文本 **388px → 0px**；圆下文本 **367 → 968px**（名字+数值两行；`showValues` 现在真的显示数值，修前有类别名时它一个数值都不出）。
    - **热力图色阶跟主题**：`scenes.5.theme=premium-light` A/B 对（2,073,383px）实测——暗主题格子比底**亮**（最高 +131），亮主题格子比底**暗**（最深 −144，采样折算 ~1.14M px 单向变暗、几乎无变亮像素）；修前亮主题格子用的是暗色墨的字面量，与纸底只差约 1px、近乎不可见。emphasis 格文字改用 `PALETTE.onAccent`（token 注释本就写着这个用途）。
  - **收口清单其余**（源码级、测试钉住）：rank Δ 走 `formatValue('percent')`、方向色 accent → `positive/negative`（accent 按文法只给 emphasis）；Sparkline 上共享生命周期（dash 画入 + presence 退场，`TYPE_OPTIONS.sparkline += enterFrames`）；frame 家具（网格/基线/刻度/轴标签/x 标签）加 presence 退场 —— 合成没有 SceneExit，否则标记淡出后轴满亮度挂到硬切；Bar/Bubble 标签补 presence；line 点值标签与 slope 三列标签（两端列+中点系列名）全部 `declutterByY`；`TYPE_OPTIONS.slope` 撤掉从未被读的 `showValues`；死代码删除四处（`{SPACE ? null : null}`、Slope 的 `* 0`、未用 import、零读者的 `fade`）；Chart.tsx 报错文案 `#E8C464` → `PALETTE.accent`；`xAt` 的 useMemo 挪到 early-return 之上（既有的 hooks 顺序违规）；`ChartFrame` 的 `useCurrentFrame` 从 useMemo 回调里提出并进依赖（原写法靠 options 每渲染换身份才碰巧成立）。
  - **守卫三件**：
    1. **注册表拒绝注释充数**：`check_registry` 先剥离注释再查 —— 先演示转红（**唯一**一条：`enterFrames` 只在 types.tsx 的文档注释里），移到 `READER_FRAME` 后转绿。这是 showArea 类失效的最后一层：名字在文件里、不在代码里。
    2. **`lifecycle.check.ts` 接进 pytest**（`tests/test_chart_lifecycle.py`，3 条：跑 check + 覆盖面断言 + 纯度断言）—— 复验官 10-01 待办销账，7.2 的 54 条守卫不再靠自觉。
    3. **变异测试过**：把 `declutterByY` 临时改回普通 declutter → 检查立刻转红 3 条、报 `[300,400,426]`（出厂缺陷同形）；还原后全绿。
  - **过程中自己踩的两个坑，如实记**：
    1. **子进程输出按 gbk 解码**：我给 check 加的分节标题带 em-dash，`capture_output` 的 locale 解码把 reader 线程炸掉 —— **跑通时只是 warning（输出截断），跑挂时会吞掉全部断言信息**：守卫的失败路径恰好是最需要输出的路径。四个捕获子进程的测试文件统一 `encoding='utf-8', errors='replace'`。
    2. **编辑器把文档内容里的裸 LF 归一成 CRLF**：账本里「（LF 对不上 CRLF）」那句记录行尾区别的例句，其 LF 字面量在一次**针对别的行**的编辑中被静默归一，句子变成「CRLF 对不上 CRLF」。**又一次静默失败，这次在编辑工具上** —— 按字节修复后才提交（终验：与 HEAD 的逐行差异仅剩预期两处 = 任务行 + 变更记录块，该例句字节已还原）。
  - **终检**：**110 passed**（102 基线 + 新 8：lifecycle 3 + registry 5；cv2 的 4 条按复验官裁定仍 `--ignore` 分解释器跑）、tsc 0、三 check exit 0、**A/B 26/26 exit 0**（`out/chart_ab.md`，每行 13 溯源字段；新增行 = sparkline `enterFrames` 287px @进入帧、heatmap `theme` 2,073,383px）、完整渲出 `out/charts_demo.mp4`（1950 帧 32.5s，`yuv420p(tv, bt709)` 编码契约保持）。
  - **未做（明确留后）**：A/B 矩阵接进 `tests/` 当 CI 项（P8 收尾，与复验官约定）；P6 遗留 6.7 SPACE 尺度 / 6.8 DEPTH 无场景使用；`shot_specs.json` 创作字段与音频听感（人工）。
  - **推送状态**：本条与同日审计条**等推送授权**（铁律：不自动 push）。原尾行「本条与 `014ebe7` 一并等推送授权」已过时 —— `014ebe7`/`6abbaf2` 实测已在 `origin/main`（tip=6abbaf2），就地订正。

- 2026-10-01：**P7.3 复验裁定 —— 通过**（复验官独立取证，未采信施工方自述）。**逐条重测两条最重的主张，并实测三条新守卫能否失败。**
  - **渲染噪声地板先测**：同 props 连渲两次 `f01220.png`，`array_equal=True`、**差异 0 px**。**不先钉死地板，任何小数字都无法判定** —— 这是「取错对象拿到格式正确的答案」的第 N 次同型，所以先测地板再看数字。
  - **柱标签（独立复现）**：修前 bar2 / bar4 **柱上方 0 像素标签**（标签沉在柱体内，与声称的 +160/+322px 一致）；修后 **−10 / −9 / −10 / −10 / −9**，五根全部在柱顶之上。
  - **slope 轴线同源（独立复现）**：刻度列 `113:132` **修前修后逐位相同**（80 px ink，`np.array_equal`），即刻度本身没动；顶部墨迹由 y51 移到 y86。按刻度中心反解 **21.0 px/单位**，frame 尺度 y(61)=114−21=**93**。修前顶端落在 y≈58，**偏 36px = headroom 的量**，与「自建 `[min,max]` 局部域」一致。
  - **bubble 双渲（独立复现）**：修前底部轴标签带 y931-946 有 253px 墨 / **6 个分组**（Mon..Sat）；修后该带仅 11px / 1 分组，圆下文字 87px → 551px（名字 + 数值）。
  - **三条新守卫实测全部能红**（守卫的价值不在通过，在能失败）：
    | 守卫 | 变异 | 实测结果 |
    |---|---|---|
    | `declutterByY` | 排序退回类别顺序 | scale.check **3 条转红，报 `[300,400,426]`**（出厂缺陷同形）+ pytest 1 failed |
    | 注册表拒绝注释充数 | `enterFrames` 指回 `READER_TYPES` | `--registry` **exit 1**：`that file's CODE never mentions enterFrames` |
    | lifecycle 接进 pytest | `WEIGHTS.focus` 0.36→0.40 | **pytest 1 failed**，报 `1 check(s) FAILED` |
    变异全部还原，终态工作树干净、110 passed、tsc 0。
  - **两条新增 A/B 行单独查**：两条都是极端值（一端 287px、一端 2,073,383px = 100% 帧），**越是极端越要查是不是「测错了对象」**。结论：地板为 0，287px 是真信号（独立重渲复现 325px，同一区域）；`theme` 行 100% 是因为换主题必然重画整帧背景 —— **该行只证明「主题到达了场景」，不证明「色阶跟了主题」**；另按单元格与底色亮度差直接量色阶方向：暗底 **+108…+493（变亮）**、亮底 **−87…−399（变暗）**，**单向**，与声称一致。
  - **遗留空隙（不阻塞，已记入 7.3 行尾注）**：`declutterByY` 的**调用点**若被改回 `declutter`（函数本身不动），**110 条测试全绿、三份 check 全过**。守卫只证明纯函数对，不证明九个标记真的调它 —— 与 `showArea` 同型。留给 P8 的 A/B 矩阵 CI 化时一并处理。
  - **复验这一侧也犯了一次静默失败，如实记**：第一次变异改 `options.ts`，但 `FIELD_READERS` 实际在 `ab_field.py` 里 —— replace **匹配 0 处**、`git diff` 为空、注册表照样 exit 0。**我差点把「守卫没反应」当成结论**；改对文件才转红。**这是账本里那个老教训的第三次实例，且发生在复验一侧** —— 变异测试自身的失败模式，与它要检验的缺陷是同一种。
- 2026-10-01：**P8 开工 —— 先审计 8.1/8.2 的现状**（照 P7.3 的规矩：先测量再动代码）。审计从「竖版和 4K 到底渲不渲得出来」开始，结论是：**仓库里两个示例图谱都是 1920×1080@60，竖版与 4K 从来没有被渲过一帧**。
  - **探针（入库，可复现）**：`studio/scripts/make_format_probes.py` 读 `pipeline/examples/showcase_demo.json`，**只替换 `format` 三个数**，产出 `hd / vertical / uhd / fps30 / broken` 五份到 `out/p8_probes/`。`broken.json` 的 `width` 是字符串（schema 要求 integer）。**基线图谱本体逐字节不动** —— 它是交叉验证的对照。
  - **审计的判据**：内容 bbox 与边距，**像素阈值不落在背景渐变的动态范围里**。这一点本项目吃过亏（`measure_frame v2` 用绝对阈值，亮色背景动态范围 > 阈值 → 整片误判）：背景渐变最大通道 ≤18、内容（卡片/柱/字）≥49，故取 `max channel > 30`，两侧都留足余量。

- 2026-10-01：**P8 三条缺陷已修 + 复验裁定：通过**（复验官独立重测，未采信施工方自述；三条修复全部复现，三条新守卫实测能红，**116 passed** / tsc 0 / `showcase_demo.json` 与 HEAD 逐字节相同）。
  - **A 竖版横向溢出坐实**：修前 v515 / v343 / v259 **三帧全部 `x 0-1079` 双向裁切**；修后 **v515 x 255-824（边距 L255 R255）、v343 x 231-857、v259 x 255-844**。**16:9 不变性精确复现**：`orig` vs `scaleonly` @f343 = **0 px 逐位相同**。`scaleFrom` 全库无残留，`/1080` 只剩 `scaleFor` 自己那行。
  - **B 误导性回退坐实**：新模块 `schemas/showcaseMeta.ts` 只依赖 zod，抛错并指名 `format.width`；`isAbsent` 判据从「有没有 `scenes` 数组」改成「有没有声明 showcase-v1 任一顶层字段」（第一版用 `scenes` 做判据时，**护栏当场抓出一个真洞**：带 `format` 无 `scenes` 的图谱会静默拿默认值，而它是一个缺必填字段的图谱）。**变异复核**：判据退回 `!('scenes' in doc)` → `showcaseMeta.check` 转红。
  - **C 相机 ramp 坐实，施工方主动更正自己上一轮**：HEAD 的 `Math.max(1, seconds*fps/sceneFrames)` 对 229 帧场景算出 `max(1, 156/229) = max(1, 0.68) = 1` —— **clamp 只往上抬，ramp 恒为 1.0，`premiumCameraSeconds: 2.6` 在所有已交付场景里都是死的**。施工方上一轮报告称「60fps 只差不到一帧」，**是把 `Math.max` 的方向写反了**，本轮自行更正并给出 `git stash` 对照（原作者码与审计期渲染 **0 px 差异**，环境可证稳定）。**复验用变异复核**：把 `(seconds*fps)/sceneFrames` 注回去 → `test_camera_ramp_is_not_a_fraction_of_the_scene` 与 `scale.check` 双双转红。
  - **像素数字必须带阈值 —— 复验侧发现的一个记账规范问题**：施工方报 ramp 在 f343 变化 `70071 px`、f515 `8733 px`；复验在 **tol>0** 下量到 **228308 px / 26784 px（3.26x / 3.07x）**，把阈值提到 **tol>6** 才落到 `70955 / 9370`，与其同量级。**方向、符号、0 px 对照全部一致，因此不是假账 —— 但「多少像素变了」不带判据就无法复现**，与本项目「工具给错数字」是同一个洞。**此后报像素数一律写清阈值。**
  - **守卫三件**（新增 `scale.check.ts` / `showcaseMeta.check.ts`，均无 react/remotion 依赖；`tests/test_p8_format_scale.py` 6 条跑它们 + 源码级断言）：

    | 守卫 | 复验注入的变异 | 结果 |
    |---|---|---|
    | `scaleFor` 两轴 | 退回 `height/DESIGN_HEIGHT` | 2 failed（含 `test_scale_is_asked_for_both_axes`） |
    | ramp 非场景分数 | 注回 `(seconds*fps)/sceneFrames` | 2 failed（含 `test_camera_ramp_is_not_a_fraction_of_the_scene`） |
    | 图谱判据 | 退回「有没有 scenes」 | 1 failed（`showcaseMeta.check`） |

    全部还原，终态工作树与施工方版本逐字节相同、**116 passed**、tsc 0。**另有两条源码级断言**「没有任何文件再除以 1080」与「每个 `scaleFor` 调用方都传两个轴」—— 这一层把 P7.3 遗留的「函数对、调用方可以不调它」那类洞在 tokens 侧堵住了，**但九个标记的调用点仍未覆盖**。
  - **复验这一侧也犯了两次错，都在测量环节，如实记**：
    1. **搜索范围不足就下结论**：只 `Get-ChildItem out/p8` 一个目录就断言「所有渲染产物都早于修复 90 分钟、不存在产物」，实际产物在 `out/p8_fix/` 与 `out/p8_det/`。**差点凭不完整的搜索发出「记为已修但无产物」的指控** —— 那正是本项目抓到过三次的假账形态。
    2. **阈值落在渐变内部**：像素判据取 18，而 4K 下背景渐变自身动态范围就是 19，于是左右边缘被误判为裁切，**差点反过来指控已经修好的东西是坏的**。**与账本里 `measure_frame v2` 那条旧教训同型，复验侧重犯一遍。** 改成 `max channel > 30` 后与施工方数字吻合。
    **两条合起来是一件事：验证者给的数字和施工方给的数字，会以同样的方式错。**
  - **未做（明确留后）**：**chart 场景（`charts_demo.json`）未做像素验证** —— `ChartFrame.tsx` 换了缩放器调用，而 P7.3 的整条证据链（柱标签 −9/−10px、slope 21px、A/B 26/26、成片 1950 帧）**全部建立在 1920×1080 单档上**；缩放器是共享的，`min(2,2)=2` 的算术成立，**但 P7.3 的像素数字在 4K 下一个都没验过**。连同 P7.3 遗留的 `declutterByY` 调用点守卫与 A/B 矩阵进 `tests/`，**一并放在 P8 收尾**。
  - **另有人工项在册未动**：P6 遗留 6.7 `SPACE` 尺度（仍 8…168 而非规定的 4…96）/ 6.8 `DEPTH` 四场无一使用；`shot_specs.json` 创作字段；音频听感。
- 2026-10-01：**P8 收尾 —— chart 场景三档像素验证抓到 P7.1 遗留缺陷（已修）+ 守卫三件 + 账本双表清理**。P8 完成。
  - **最大的一处不是新写的代码，而是一直没人渲过的那一档**：`ChartFrame.tsx` 的 `H = comp.height - padY` 来自 **`11b9274`（P7.1）**，把**原始帧高**当作设计量。`scaleFor` 早就改成两轴了，`W` 那一行也恰好正确（因为三档都满足 `comp.width = DESIGN_WIDTH × s`），**只有高度在首个非 16:9 格式上分家** —— 所以 16:9 与 4K 两条路径都「看着对」，缺陷自 P7.1 潜伏至今。实测竖版柱高 **1223/1012/1331/943/1557** vs 设计值 **319/285/345/260/406**（**拉伸 3.4 倍**，基线 y=1824 而非 532）。
  - **修法与证明**：plot 盒 = **设计盒 × s**。**16:9 与 4K 各四帧共 8 张渲染 `0 px` 逐位相同** —— 构造上即 no-op，用像素证明而非论证。竖版柱高回到 318/263/353/252/406，slope 顶部 hd 87 / 竖版 48 / 4K 174，全部按 `s` 缩放。
  - **顺带居中**：`offsetY = max(0, (comp.height - DESIGN_HEIGHT × s) / 2)`。修前竖版图表贴顶、下方空 **1385px**；修后上下 **690/729、703/710、762/714、689/714**，与场景一致。**同样 16:9/4K 0 px**。
  - **守卫**：
    | 守卫 | 变异 | 结果 |
    |---|---|---|
    | `test_the_chart_plot_box_is_the_design_box_scaled_not_the_frame` | `W` 注回 `comp.width` | 转红（断言表达式形状，禁 `const W/H` 行出现 `comp.*`） |
    | `test_the_nine_marks_place_labels_with_the_by_y_variant` | `declutterByY` → `declutter`（**P7.3 遗留、110 条全绿的那个空隙**） | 转红（禁 `types.tsx` 出现裸 `declutter(`） |
    | `showcaseMeta.check.ts` 新增 fps 段 | 帧总数改为随 fps 缩放 | 转红（30/60/120fps 报 401/801/1602） |
  - **A/B 矩阵接进 `tests/`（P7.3 遗留的机制化，销账）**：新建 `tests/test_chart_ab_matrix.py`，按成本拆两半 —— **便宜的一半永远跑**（注册表 17 项与矩阵行交叉核对；反向漂移检查；**timing 选项不得声明为 `settled`**，这条正是矩阵 docstring 记录「live 行被报成 dead」那次事故的规则化）；**贵的一半 52 次渲染用 `H3_AB_MATRIX=1` 门控**（实测 146s 通过，CI 可设）。**矩阵从此不是「跑一次存一份报告」而是测试项。**
  - **fps 轴结论（实测，非推断）**：`showcase_demo.json` 在 **30 / 60 / 120fps 下 `durationInFrames` 恒为 801**，成片 26.70s / 13.35s / 6.67s —— **场景时长是帧锚定的**。但**同一帧号在不同 fps 下是不同画面**：帧 515 处 30fps 与 60fps 相差 **16.57%** 的像素，因为**相机 ramp 是墙钟锚定**（`cameraMoveFrames = seconds × fps`）。**即「改 fps 让渲染变快」会静默改变相机运动**，已把这条后果写进 `showcaseMeta.check.ts` 的注释里 —— 改 fps 的人会先读到它。
  - **账本双表清理**：P3 / P4 / P5 各有**第二张任务表**，编号与上表重复、状态全为 ⬜（立项时的原始清单，后来走了别的结构，表留在那儿）。**任何按任务行统计的读法都会把它们算成未完成** —— 我第一次解析就得出「P3 完成度 60%」这种结论。加 caption 标注「已被上表取代，不计入任务」并把行号加删除线、状态改 `—`。**现在账本可被无歧义解析：75 条真任务行，未完 26，其中 22 条是 P9–P18 未开工，4 条是有记录的例外**（`1.3` VLM Critic 延后、`4.9`/`6.0` 是记录下来的失败而非未完、`6.7`/`6.8` 真未完）。P6 的第二张表是**合法续表**（6.5–6.8 不重复），未动。
  - **我这一侧又错了两次，都记下**：① 柱带检测的 run 收尾条件写成 `x-prev>4`，**永远不成立**，一度得出「0 根柱」；② 做双表清理的解析脚本**先按「只数第一张表」统计，把 P6 的 `6.7`/`6.8` 漏掉了** —— 我刚制造的规则立刻产生了新的漏读，**说明「消除了歧义」这句话必须由解析器证明，不能由改表的人宣称**。改成按 caption 规则解析后才拿回 6.7/6.8。
  - **终检**：**122 passed + 1 skipped**（原 116 + 矩阵 4 + 调用点 1；skip 是 52 渲那一半）、tsc 0、`showcase_demo.json` 与 `charts_demo.json` 均与 HEAD 逐字节相同。
- 2026-10-01：**P9 完成 —— 先审计 12 步（3 批），三处假账式记账问题全部量出**。**先审计，不动代码**；每批的规矩不变：**守卫先红后改数据、不动已交付渲染路径、数字必须带判据**。
  - **最大的一处：tempo 是错的，而且是量出来的**。`bgm_beats.json` **入库、自述「for the renderer」、`studio/src` 读取者 = 0**（与 P3 七个场景类型「声明了却无渲染器」同形）。它自报 **129.2**，图谱写 **126** —— **208 拍后相差 2.45 秒**。**最小二乘拟合给出 129.00**（RMS 7.9ms / max 18.0ms）：**选对 tempo 把误差从 2452ms 压到 ≤18ms，136 倍**，且网格**不必携带逐拍时刻**。
  - **accent 必须来自分析，`i%4` 无任何支持**。12 最响拍的 `i%4` 占满四个余数、间隔中位数 5；`bass>0.3` 选 34/208、间隔中位数 **2**。**置换检验 200 次：mod 2/3/4/8/16 全部低于打乱零假设 95 分位** —— 没有 index modulus 能预测 bass，`beatGrid.ts` 里**连 `%` 都没有**。**施工方先写了一个「mod 8/16 是 structure」的结论，补置换检验后自己撤回** —— 保留这个撤回比保留那个结论有价值。
  - **用拟合值 128.998，不写 129**（斜率标准误 ±0.0025；129 会掩盖这值是拟合来的）。**修法不是改数字而是不许它静默错**：由分析拟合、图谱 `bpm` 必须相符（容差 0.5），**先立守卫再改数据**（守卫红时报「declared 126, fitted 128.998, off by -3.00 — compounds to 2302 ms by beat 208」）。
  - **四级基准是 1/4 拍而非小节，不是风格选择**：60fps 下独立取整与 `4×round(6.977)` **恰好相同 —— 在图谱自己的 tempo 上这个错误根本测不出来**；131.4 bpm 就分叉。守卫扫 9 tempo × 4 fps 报告分歧格数。**「测不出来」比「测出来」更危险**，所以要主动换 tempo 去撞。
  - **一个既有测试的绿灯本身是偶然的**：`test_beat_snap_does_not_accumulate_drift` 用硬编码 126 造时间线，却拿 `sc.beat_distance_frames`（**图谱的** bpm）去量 —— 两个 tempo 混用，**只因图谱也恰好是 126 才一直绿**。tempo 变成实测值后它报 12.9 帧「漂移」，而那段 snapping 从未漂移。改为用自己的 receiver（`long.`），断言原意完整保留。**测试通过不等于断言成立。**
  - **两条断言被自己的 check 纠正，且都纠正对了**：① 「camera settle 必须落在场内」错 —— 相机装不进 114 帧的 s03（60fps 下 2.6s = 156 帧），`cameraMoveFrames` 文档本就写明「move 允许越过场景」，要求 ≤ 场景等于要求相机别动；② 「chart finish 随时长翻倍」错 —— `lifecycleAt` 把入场**封顶在 marks 的实际需要**（单 mark 48 帧），只有 34% 上限起作用时（dur < ~141）才随时长增长。实测三档 fps 恒 **93**，随场景时长 **58/93/138/228**（单调但次线性）。
  - **`beat_snap` 的损耗被量化并门控有界**，且**符号不固定**：`resolveScenes` 逐场独立取整，**片亏损是各场亏损之和**（6+5+3+6 = **20** = film delta −20）→ 按片长门控实际在门控**场次数**。精确界是 **`bf/2 + 1`** 而非 `bf/2`（解算时长 `round((k+b)·bf) − round(k·bf)`，**两个边界各自取整**），20 格全绿。**独立扫出 6/20 格让片变长**（最大 **+68 帧** @174/120）—— **「beat_snap 丢帧」不是普遍成立**。126 的「几乎免费」是**运气不是设计**（130.435 bpm 下同一场反丢 8.2 帧）。**交付路径走 `false`，故对成片零影响。**
  - **9.2 只做有查询面的两个**：`camera settle`（墙钟锚定，78/156/312 帧 @30/60/120fps）与 `chart finish`（真 `lifecycleAt` 二分查找，**不从 `WEIGHTS` 重算 —— 后者是漂移的温床**）。`cut`/`card arrival` 有输入无查询面、`number finish` 连输入面都没有（`countUp` 的 1.6 **既是默认参数也是调用点字面量**）、`hit` 全模板不存在（`onAccent` 是调色板色）。四个不可用的 `source` 必须写明原因（守卫断言长度 ≥20 字符，防 `n/a`/`todo` 混过）。
  - **9.3 先量再定**：**whoosh+impact 同屏 8/8 屏**、2.25 次/屏、只有 `ding` 与 `riser` 有条件 —— 这就是要压掉的毛病，已钉成基线。覆盖率 **3/6**，三个洞恰是既无帧也无输入的三个事件。**`cut` 的映射是有条件的**（有输入但无可查询帧，而连响正是要压的东西）—— **先接上帧、再接上声音**。
  - **守卫 16 项变异测试全被抓住**，控制组 29 passed。**总账：151 passed / 1 skipped**（P9 前 122）、tsc 0、**九份 check 全绿**。**`git status` 里没有任何渲染路径文件** —— `FinanceShowcaseWide.tsx`/`scenes/`/`primitives.tsx`/`design/`/`ReportVertical` 全部未触碰，**已交付画面零像素变化**。
  - **复验这一侧的三处修正，如实记**：
    1. **我给的 `beat_snap` 判据问错了对象**：`abs(film delta) < 一个 beat` 门控的是**场次数**，不是正确性 —— 7/20 格转红不是缺陷。**接受更正**，并把它改成有界的逐场界 `bf/2 + 1`。
    2. **施工方的「film 变长 7/20 格」实测 6/20**（他们含 90@30 = +21，我扫的格集不同）；方向与最大值 +68 全对。**差 1 格是扫描集不同，不是错** —— 但数字必须能复现，所以记下来。
    3. **我复核时自己错了一次**：第一版比对我写成 `sum(snapped) - sum(requested)` 而亏损已是 `requested - snapped`，输出「sum == film delta: False」；我的 `max deficit` 列口径也错了（算成相对请求时长的差），报出一列无意义的 215/599。**更严重的是我构造的 CLAIM 3 算例用了 0.49 帧/场，根本构造不出反例，等于没验**。真正坐实它的是前面的直接算术。**判据被推翻时，要重新构造能推翻新判据的算例，而不是换一个更弱的相关数字。**
  - **两点必须写进账本，否则下一个人会误读**（复验已独立确认）：① **两个图谱顶层都没有 `audio` 字段**（`showcase-v1.ts:80/101` 只有可选的 `audioLanguage`/`audioEvents`），所以「`bpm` 相符于拟合值」这条守卫**约束的是一个渲染路径从未读取的字段** —— 它现在是对的，但作用是**防未来**，不是描述现状；**showcase 并未在跟音乐对拍**。② `beat_snap` 的语义修改（末场补齐 / 允许分数拍）按裁定归 9.2，**本阶段未动**；`report-data.ts:62` 的 schema 默认仍是 126，report 侧同类守卫不在本阶段范围。

- 2026-10-01：**P10 完成 10.1（10/14 条）—— 审计先行，四个「仪器不存在」与两处已证实漏洞**。**10.2 先查清承诺与现状后裁定依赖 `P1.3`，本轮不做。**
  - **本阶段最贵的结论不是缺陷，是「仪器不存在」**：`overflow` / `collision` **三次检测器各失败一次，且失败方式不同** —— 行带+列游程测的是**字形**（5 个 3 字符标签报 54 个游程），且**标签重叠时融成一个游程，于是「重叠 0px」恰恰因为重叠才出现**；柱体检测把坐标轴并成 1668px 的「柱」；连通域把柱+网格并成 **1668×745** 吞掉整个标签列。**这三条不是靠更多努力能解决的**，需要 mark 布局输入。**因此 14 条只做 10 条，并以 `UNAVAILABLE` + 理由呈现，而不是凑数。**
  - **阈值之外还有一条设计结论**：**clipping 不能用背景模型**。`padX=0` 与 `padX=-200` 的背景模型残差都是 **208**（正常帧 **3**）—— **一个「检测内容触边」的检测器，靠帧边缘建模背景就无法测量触边帧**。改走固定调色板色路径。**这条与 `measure_frame v2` 那次同源，但这次错的是「仪器」而不是「阈值」。**
  - **contrast 已经红了，不需要构造**：24 配对里 **8 对 < 4.5:1**。**`inkFaint` 就是图表数值标签的默认色**（`types.tsx` 的 `emphasised ? ink : inkFaint`），**亮主题下 2.16:1** —— 那是 P7.3 刚用 declutter 修好、让它们露出来的那五个数字。**亮主题 accent 3.23:1**，`KpiHero` 的 eyebrow 用它且 20px/weight 500，**按 WCAG 不构成大字** → 实打实不达标。**修 accent 会动已交付画面，本轮只记账。**
  - **safe area 放弃正阈值，用「边距 == 0」精确判据**：193 帧四边分布**连续无空隙**（最小正值 左 16 / 右 24 / 上 **7** / 下 25）—— 7px 阈值在 1080 帧上等于 0.65%，任何合理留白都会被判红。**14/193 帧边距为 0 的归类作为独立待办入册，不阻塞规则建立。**
  - **`qa_report.py` 两处漏洞已封**，且都是**审计用真 ffmpeg 造文件跑真工具**证实的：① 绝对 0.6s 容差让 **14.75% 漂移**穿过 → 改**相对容差** `max(0.05, expect × 0.02)`，**长片上反而放松了正确量**（121.2s vs 120s：旧 FAIL → 新 PASS），证明是真相对化；真实 demo 0.056% 误差对 2% 有 **35 倍余量**。② **props 无 `totalDuration` 时整条检查 PASS** —— 而 `report_demo/props.json` 正是这个形状，**这条检查在唯一一份已交付 props 上从来没运行过** → 现为 **`UNVERIFIABLE` 且非零退出**。**「我不知道」被写成第三种状态，而不是伪装成通过。**
  - **变异测试 11/11 全杀，且诚实区分了坏测量与真存活**：11 个里前 6 个是**坏变异**（两个改了 docstring、一个方向性无效 —— `FREEZE_DIFF` 只选像素而判据是 `changed == 0`、一个提高门槛让更多帧红、一个以 `NameError` 而非行为死掉）。**「变异没杀掉」与「变异不是有效变异」是两件事**，把前者报成后者等于给自己一个假的安全感。
  - **一个真 bug 在交付前被抓到**：`model_mask` 对不可信背景返回 `None`，任何在检查 `trusted` 之前就量 bbox 的调用方会拿到 `ValueError: Calling nonzero on 0d arrays` —— **仪器崩了，而不是给出判定**。已修并加守卫。
  - **10.2 的裁定基于查证而非推测**：`take_critic.py` **被 docstring 承诺但不存在**（全仓库仅那一句注释）；VLM 三维度权重 **0.20/0.15/0.15 只活在注释里**，`prompt_adherence` 标识符全仓库仅 1 次命中；**无 provider 抽象、无 key、无 endpoint、无推理客户端**。**标为依赖 `P1.3`、不合并** —— 推理层必须只建一次，而合并会让「scene 级五帧抽帧 + repair 建议」这个明显更大的范围被 provider 抽象那一行盖住。
  - **两处必须写进账本、否则会误导下一个人**（复验已独立确认）：① **10.1 的 14 条只做 10 条**，`overflow`/`collision`/`flicker`/`broken_font` 是**仪器不存在**（`flicker` 需帧间亮度序列、`broken font` 需字体文件校验，都不是「拿现有渲染一测就知道」），**不是「没做」**。② **`report_demo/props.json` 仍无 `totalDuration`，duration 门禁是 `UNVERIFIABLE`** —— 唯一一份已交付 props 上**这条检查至今无法运行**；那四个 section 时长是 TS 字面量，复制到 Python 会引入四个魔数，**故刻意不做派生**，测试改为断言这个事实。
  - **复验这一侧的修正，如实记**：① 我上轮说 `qa_report.py` **74 行**、**10.1 是 8 条规则** —— 实测 **91 行**、**14 条**（我数错两条，已按 ledger 原文更正）；② 我给的交叉验证判据沿用 P0 的 **0.04%** 误差地板，**那是 mp4 抽帧的地板，PNG 无损不适用** —— 施工方指出后按 0.0000% 逐位相同复核；③ 我在独立重算 contrast 时**先后两次写错量法**（键名是 `background`/`backgroundAlt` 不是 `bg`/`bgAlt`；`[^,\n]+` 把 rgba 的逗号截断导致只有 3 个分量），**第一次甚至在一条都没算出来时就打印了表头**。**量法错了而结论看起来成立，是本项目最难防的一种错。**
  - **账本本身出过一次事故，如实记**：写 10.1/10.2 两行时我把两个长字符串放进一个列表再展开，**分隔用的换行符落进了单独元素**，两行被写成一个残缺的 `|` 和一个空行 —— **账本差点记下一个「已完成」的行号却查不到内容**。用 `git checkout` 还原后改为逐行替换。**这条与本项目记录的「编辑器吃掉字面量」同族，而这次是我自己的脚本。**
  - **终检**：**182 passed / 2 skipped**（P9 后 151）、tsc 0、`git status` **恰好三个文件**（`visual_qa.py` / `qa_report.py` / `test_visual_qa.py`）、**渲染路径零触碰**。