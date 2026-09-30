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

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 4.1 | 模板骨架 1920×1080@60fps（premium 语言，不复用 energetic 特效） | ⬜ | |
| 4.2 | Scene A — KPI Hero（count-up/odometer/eyebrow/micro-settle/自定义数字字体） | ⬜ | |
| 4.3 | Scene B — 3D Dashboard Stack（BrowserWindow/PerspectiveCard/DepthStack/CameraRig） | ⬜ | |
| 4.4 | Scene C — Big Number + 3D Columns（camera tilt/纵深柱阵/staged build） | ⬜ | |
| 4.5 | Scene D — Calendar / Data Grid（SVG calendar/高亮/mask reveal/表格动效） | ⬜ | |
| 4.6 | 扩展：Quote/Rank/Dashboard Overview/Data Plane/Window Wall/Logo/CTA | ⬜ | |

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

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 5.1 | Camera primitives：CameraRig/DepthStack/ParallaxLayer/FocusLayer | ⬜ | |
| 5.2 | Layout：SafeArea/Grid/Stack/WindowFrame/Card | ⬜ | |
| 5.3 | Typography：KpiNumber/Odometer/AnimatedText/MaskText/Label | ⬜ | |
| 5.4 | Motion：MaskReveal/SlideReveal/ScaleReveal/DepthPush/CameraPush/CameraOrbit/SharedAxis/StaggerGroup | ⬜ | |
| 5.5 | Visual：SpecularSweep/SoftGlow/Vignette/NoiseTexture/GridBackground | ⬜ | |
| 5.6 | `motionTokens.ts` 集中 spring 预设（micro/standard/hero/slowCinematic/camera/overshoot/settle） | ⬜ | |

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
| 6.7 | Spacing 尺度 | ⬜ | `SPACE` 已存在并接进 StyleBible。**尺度本身仍是 8/16/24/40/64/104/168，与总任务书要求的 4…96 步长不一致**，未统一 |
| 6.8 | Depth 层级 | ⚠️ **不算完成** | `DEPTH` translateZ 阶梯存在，**但四个场景没有一个用它** —— 场景的深度是构图函数（图谱给的 spreadZ），不是固定台阶。已在 tokens.ts 注明诚实状态。另外**新增了真正在用的深度 token：`DEPTH_CUE`**（每层一个阴影，远→近），因为屏幕等大之后景深只能靠阴影读；此前每个窗口都是同一个 `SHADOW.floating`，最近的那个看起来并不比最远的近 |

---

## P7 — 图表引擎　状态：⬜

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 7.1 | 自研 SVG 图表：Bar/Line/Area/Slope/Bubble/Heatmap/RankTable/Sparkline/VolumeBars | ✅ | 9 种全部实现并**逐场渲出目检**（`pipeline/examples/charts_demo.json`，9 场 1350 帧）。<br>**先发现一件事**：`bar-chart / line-chart / area-chart / bubble-chart / rank-chart / slope-chart / heatmap` **七个场景类型从 P3 起就在 schema 里声明了，却没有任何渲染器** —— 图谱要一张柱状图，得到的是一屏 "not implemented in P4"。**schema 承诺了没人兑现的能力，正是本项目反复踩的那一类。** 引擎做完这七种才变成真的；另补声明 `volume-chart` / `sparkline-chart`（引擎支持但 schema 没有，同样是不对称）。<br>**结构**：`charts/options.ts`（声明面，先写）→ `charts/scale.ts`（纯数学，零依赖）→ `charts/ChartFrame.tsx`（轴/网格/刻度/数值标签，**拥有定义域**）→ `charts/types.tsx`（九个标记）→ `charts/Chart.tsx`（适配器）。标记一律从 frame 拿已解析的比例尺，**不许自己算定义域** —— 否则标记可能和它所在的轴不是同一个尺度，而那种图是可读且错误的。 |
| 7.1b | 选项面与 A/B 证据 | ✅ | 按纪律先注册再实现。`FIELD_READERS` 18 个选项全部注明读它的文件；**检查会读那个文件的源码确认它真的提到这个名字**（只查注册表自己的账本分不清能用和哑的）。<br>**A/B 矩阵 23 个选项全部实测为「活」**（`studio/scripts/chart_ab_matrix.py`，退出码 0，报告 `out/chart_ab.md`）。**过程中抓到一个源码级检查抓不到的真 bug**：`showArea` 登记为"被 types.tsx 读过"、也真的出现在 types.tsx —— 但在 **Area 组件**上，于是每一张 line 图的 `showArea` 都是哑的。根因更深一层：`option()` 拿 `TYPE_OPTIONS` 做**运行时闸门**，所以一张过时的表就能让一个能用的选项变哑，而守卫看不见（名字在文件里）。**修法：闸门去掉，表降级为声明，准确性另测。** 修后 volume 的 `emphasisIndex` 从 0px 变 50,730px（2.45%，区域正好一根柱）。<br>**顺带删掉 `inline`**：声明了、没有任何标记读它。与其糊一层，不如删。<br>**新增两条机械化的纪律**：每个声明的选项都必须在 A/B 矩阵里有实测行；`option()` 不得再按表过滤。 |
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
