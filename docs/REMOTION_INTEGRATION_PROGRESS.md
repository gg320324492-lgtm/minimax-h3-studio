# Remotion × MiniMax-H3 融合 — 实施进度跟踪

> 方案文档：[REMOTION_INTEGRATION_PLAN_20260929.md](REMOTION_INTEGRATION_PLAN_20260929.md)
> 本文档是唯一进度源：每完成一步打勾并记录关键数据/结论，新任务随时追加。
> 状态图例：⬜ 未开始 ｜ 🔄 进行中 ｜ ✅ 完成 ｜ ⏸️ 暂停/阻塞

---

## Phase 0 — 环境验证与渲染基准（0.5 天）　状态：✅ 完成（2026-09-29，实际用时约 20 分钟）

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 0.1 | 建立进度跟踪文档 | ✅ | 本文档 |
| 0.2 | EP01 真实资产摸底 | ✅ | 12 片段 768×1344/24fps/yuv420p 共 1454 帧=60.583s；混音 AAC 48k stereo 60.63s |
| 0.3 | 搭建 `studio/` workspace | ✅ | remotion@4.0.529 全家族 + React 19.3.0 + TS 5.9.3；render.mjs 桥 |
| 0.4 | `pnpm install` | ✅ | 31s；`.npmrc` shamefully-hoist |
| 0.5 | `remotion browser ensure` | ✅ | chrome-headless-shell 113MB 自动下载至 node_modules/.remotion/ |
| 0.6 | `gitignore` 补充 | ✅ | studio/{node_modules,public/jobs,out,.remotion} |
| 0.7 | 中文渲染验证 | ✅ | simhei.ttf 自托管 + 系统雅黑都正常，无豆腐块（probe.png 目检） |
| 0.8 | EP01 dummy props 生成 | ✅ | `emit_phase0_props.py`：12 shots+19 字幕，硬链接零拷贝，boundary 与源帧数全一致 |
| 0.9 | 全时间线渲染（x264 crf18） | ✅ | **38.8s（≈1.55× 实时）**，bundle 1.0s |
| 0.10 | 并发扫描 | ✅ | c8=40.0s / **c16=38.8s 最优** / c24=42.8s 退化；32 线程默认(=16)即最优 |
| 0.11 | NVENC vs x264 A/B | ✅ | NVENC 37.3s 仅快 1.5s，但 Main profile + 文件翻倍（110MB）→ **定稿 x264 crf18** |
| 0.12 | 输出规格 QA 检查 | ✅（发现并修复一坑） | jpeg 默认输出 yuvj420p 挂 QA → **`colorSpace:'bt709'` 修复**，yuv420p+tv+bt709 全过，无速度损耗；另：Node API 不读 remotion.config.ts；videoBitrate 是 "14M" 字符串且与 crf 互斥；hw 取值是 "disable" |
| 0.13 | 撰写基准报告 | ✅ | [studio/BENCHMARK_20260929.md](../studio/BENCHMARK_20260929.md) |
| 0.14 | Phase 0 收尾（文档+记忆） | ✅ | 记忆已更新 |

**Phase 0 验收**：全部达成。渲染基准 38.8s/60.58s 成片；最优并发 16；编码配置 x264 crf18+jpeg+bt709；
中文无豆腐块；规格全过 QA 容器检查。**Phase 1 可以开工。**
（遗留决策点：cover 裁切 vs 拉伸、逐片段超分接入、字幕令牌精确移植 —— 已记录在基准报告 §6）

---

## Phase 1 — EP01 包装层迁移（1–2 天）　状态：✅ 完成（2026-09-29，qa 16/16 PASS）

**决策记录**：
- 逐片段超分（原计划 2.4）提前到 Phase 1——没有它 Remotion 版画质比不过 v2（浏览器插值 vs Real-ESRGAN）。
- fit 模式定 `fill`（拉伸）：v2 超分链是 Lanczos 直接拉到 1080×1920，A/B 对齐要求 v3 同几何；`cover` 留给未来项目。
- zod schema 用 parse-in-component 方式接入渲染路径（不用 `<Composition schema>`，规避 zod v4 兼容风险）；JSON Schema 导出走 `z.toJSONSchema()`。
- 字幕字体：系统雅黑（与 PIL 的 msyh.ttc 同字形）为主、自托管 simhei 兜底；描边用 `-webkit-text-stroke` 2× 宽度补差（居中描边 vs PIL 外描边）。

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 1.1 | `schemas/timeline-v2.ts`（zod）+ JSON Schema 导出 | ✅ | zod v4 + `z.toJSONSchema`；tsc 通过；schema 快照 `timeline-v2.schema.json`（draft 2020-12） |
| 1.2 | `build_timeline.py` 升级写 v2（v1 字段兼容） | ✅ | timeline_v2.json：12 shots/1454 帧/19 字幕，与 v1 同源同数值；路径为项目相对，staging 时改写 |
| 1.3 | `drama-vertical` 模板 MVP | ✅ | zod parse 守门 + 精确 STYLES 移植（心声=暖黄 FFEB64 等六样式）+ fit fill/cover + webkit 描边 2× 补差 |
| 1.4 | `stage_assets.py` + `render_with_remotion.py` | ✅ | schema 校验→硬链接 staging→路径改写→props.json；一键 stage→render→`--qa`（临时目录伪装 EP01_DOUYIN_FINAL.mp4） |
| 1.4b | （提前）逐片段超分 sr_takes.py | ✅ | 12/12 全成，x2plus fp16 tile768/64 → 1080×1920，~3.5-4 fps，VRAM 3.6GB，全程约 6.5 分钟 |
| 1.5 | EP01_v3 全程新链出片 → qa PASS | ✅ | **16/16 PASS**（响度 −13.7 LUFS/TP −3.7、yuv420p、60.58s）；渲染 ~57s（1080p 源解码更重，近实时）；⚠️ 教训：`pnpm install` 会清掉 node_modules/.remotion 里的浏览器，装完依赖要重跑 `npx remotion browser ensure` |
| 1.6 | v2 成片 vs v3 并排 A/B + 记录 | ✅ | 4 时间戳目检（studio/out/ab_*.png）：样式/位置/配色全对齐，**v3 画质明显更锐**（去整片二次编码）；字体渲染略粗（CSS vs PIL 光栅化，可接受）；结尾三事件同屏碰撞为 v2 既有的数据层设计问题（见 Phase 2 新增 2.7） |

**验收标准**：`09_final/EP01_DOUYIN_FINAL` 由新链产出且 qa_final 14/14 PASS；字幕视觉与 v2 对齐（宽度/位置/样式）。

---

## Phase 2 — 全模板 + 转场 + 封面（2–3 天）　状态：✅ 完成（2026-09-29 当天）

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 2.1 | transitions（帧内转场，不动时间轴） | ✅ | schema `transitionIn`（none/fade/flash）+ ShotFrame 组件；EP01 v4：S01 从黑起 12f、S03C 闪白 8f，QA 16/16 PASS，字幕在转场层之上保持可读。**关键设计：不用 TransitionSeries 重叠式转场（会挪动绝对秒），改用镜头自身首帧的 fade/flash** |
| 2.2 | `psa-wide` 模板（piyao 迁移） | ✅ | 13 个样式全移植（含 msg/step/card 底板、corner 左对齐、end_ai 药丸）；真实数据验证渲染 109.3s@1080p 用时 52.9s（2× 实时）；结束卡/AI 声明药丸/角标全部正确 |
| 2.3 | `story-animation` 模板（liaozhai 迁移） | ✅ | 2560×1440@24，样式坐标按 1920×1080 设计稿 ×1.333 等比映射，雅黑粗体；titlecard（3.5s）+ endcard（5s）段支持；75.75s@2K 用时 60.2s（1.26× 实时） |
| 2.4 | 逐片段超分 | ✅（Phase 1 已完成） | EP01 12 片段全 SR；piyao/liaozhai 的正式交付前各跑一次 sr（本次验证用原片） |
| 2.5 | 封面 renderStill 模板化 | ✅ | `CoverCard` 模板（背景帧+角标+标题+钩子+品牌色下划线+渐变遮罩）；EP01 封面已出（studio/out/ep01_cover.png）；标题支持 `\n` 强制换行（whiteSpace pre-line） |
| 2.6 | overlays 体系 | ✅ | progress 进度条 / lower-third 人名条独立渲染；**text 花字并入字幕碰撞布局**（首版独立渲染与旁白叠字，已修复并复验）；schema: overlays[] 判别联合 |
| 2.7 | 多字幕事件碰撞修复 | ✅ | 集中布局算法：不可移动样式（msg/step/corner 等屏幕元素）先占位，可移动字幕按模板优先级（special>opening>ending>normal>inner_special>inner）+出现时间排序，冲突时向上让位；EP01 结尾三事件从叠字变整齐纵向堆叠 |

**Phase 2 新增工具**：`studio/scripts/emit_props.py`（任意项目 timeline v1 → v2 props + 硬链接 staging，支持 03_video_raw take 回退与 titlecard/endcard 推导）。
**新教训**：zod v4 的 `.default()` 必须给完整输出值（内层 default 不算数）；Composition 的 `defaultProps` 类型跟随组件 props 签名。

---

## Phase 3 — 新类型 + 词级字幕 + 模板工厂（2–3 天）　状态：✅ 完成（2026-09-29 当天）

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 3.1 | `report` 纯程序化模板（模式 B 打通） | ✅ | `ReportVertical`：自动时间轴（标题→统计卡弹入→条形图生长→要点→结尾标语），report-data zod 契约 + JSON Schema 导出；demo 29.9s 成片 13.1s 渲染（2.3× 实时，**零 GPU**）。daily-brief 由同引擎换数据承载，不单独建模板 |
| 3.2 | 词级卡拉OK字幕 | ✅ | `word_timestamps.py`（faster-whisper small + VAD）：**ASR 词面只当对齐标尺，文字用已知原文**（字符对齐，标点/省略号保留）；相似度守卫拒绝"音频念的≠字幕写的"事件（钩子/结束卡→静态）；14/19 事件卡拉OK，台词行验证完美（"顾总，这是"高亮+逗号保留） |
| 3.3 | 心声打字机动效 | ✅ | inner/inner_special 强制打字机（前 35% 时长逐字显形，原文渲染无 ASR 错字）；验证帧：与红色 HOOK_3 同屏不重叠 |
| 3.4 | Remotion Agent Skills 安装 + 项目技能沉淀 | ✅ | 官方 12 skills 装入 `.claude/skills/`（注意：不支持 -g 全局）；项目技能 `.claude/skills/minimax-video-templates/SKILL.md`（模板配方卡/铁律/生成层速查） |
| 3.5 | codegen 工作流 + review 门禁 | ✅ | 六项入库门禁写入 SKILL.md（tsc/schema导出/真实渲染/ffprobe/目检/QA接入）；外部代码仅 MIT/Apache |

---

## Phase 4（可选）— 常驻渲染 / 预览 UI / 批量队列　状态：⏸️ 搁置（2026-09-29 确认：暂无批量生产计划，非待办）

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 4.1 | bundle 常驻 + 任务队列（批量产能需要时） | ⏸️ | 现有一次性渲染（bundle ~1s + 渲染近实时）在单项目节奏下完全够用 |
| 4.2 | `@remotion/player` 网页预览 或 Electron 桌面壳 | ⏸️ | 迭代预览用 `npx remotion studio` 即可 |

> 若未来出现批量产能需求（如日更多集/矩阵号），从本表恢复，无需重新设计。

---

## Phase 6 — 全面收尾（2026-09-30 启动）　状态：🔄 进行中

> 目标：解决 Phase 5 盘点出的未解决问题/缺口/流程债，把管线从"能出片"推进到"可日常交付"。

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 6.1 | **母带自动化** | ✅ | `master_audio.py`：WAV 中转 loudnorm + 最多 2 轮自动增益/限幅收敛（跨盘 move/缓冲文件名两个 bug 修复）；集成 `--master`。实测 v4：pass1 −18.8 → 2 轮 → **−14.5/−0.9 OK** |
| 6.2 | **BassPump 离线包络** | ✅ | `pump_envelope.json`（20-150Hz STFT 按帧归一化）；**全屏 pump 是渲染 ×2.5 的元凶**（背景每帧重光栅化）→ 改为只缩放内容层；19.4s（v3 36.8s → 降 47%） |
| 6.3 | **report QA 门禁** | ✅ | `qa_report.py` 10 项（规格/时长/响度区间/TP）；**首跑即抓到 96kHz 采样率 bug**（loudnorm 缺 -ar 48000）——门禁价值立现 |
| 6.4 | **卡拉OK并入正式流程** | ✅ | `render_with_remotion.py --karaoke`：转录→注入→staging→渲染一条命令（EP01 实测 14/19 匹配，61s 出片） |
| 6.5 | **字体验证 + 资产说明** | ✅ | Bahnschrift 全家族在列（Windows 自带 DIN 类，数字排版达标，headless 可用）；`public/audio/README.md`（真实素材替换规范+许可审计 manifest） |
| 6.6 | **听感样张** | ✅ | `out/audio_preview.m4a`（BGM+SFX 按成片时间戳预混）——**等人耳验收，这是剩余最大未知数** |
| 6.7 | **契约同步自检** | ✅ | `check_contract.py`：schema 重导出 git diff + 全部 props jsonschema smoke；发现并修复按文件名猜 schema 的配对错误（改为按内容路由） |
| 6.8 | **代码清理** | ✅ | phase0 废弃 job、out/ 临时帧/旧渲染清理；基准文档引用的 ep01_bt709.mp4 一并清理（已被 v3/v4 取代） |
| 6.9 | **Git 整理提交** | ✅ | 4 个主题 commit：Docs / Skills / Studio / Pipeline（既有无关改动保持未提交，未混入）；push 需先建远端 |
| 6.10 | **文档收尾** | ✅ | studio/README.md 快速上手 + 本表终版 + 记忆同步 |
| 6.11 | **真实素材通道打通**（用户修复代理后） | ✅ | Clash 7897 恢复 → Kenney CC0 音效包 + Mixkit SFX/BGM 全部可直连下载（Pixabay 403 反爬弃用，Mixkit 音乐库替代）；`import_real_assets.py`：librosa 实测 BPM/拍网格/呼吸包络 + 峰值归一化 + 许可 manifest。**"Digital Clouds" 129.2 BPM 入主**（拍间隔 CV 0.020 最稳），合成 BGM 降级为 bgm_synth_126 备胎。v5 成片：渲染 14.1s + 母带一轮 −14.4/−1.8 + QA 10/10 |

**Phase 6 收尾结论**：收尾前盘点的 12 项未解决问题/缺口/阻力中——母带不收敛（✅ 自动化）、BassPump 性能（✅ 包络化+作用域收窄）、report 无 QA（✅ 10 项门禁）、卡拉OK旁挂（✅ 并入流程）、契约漂移风险（✅ 自检脚本）、**素材通道（✅ 代理修复后 Mixkit/Kenney 全量入库，import_real_assets.py 固化流程）**已关闭；**合成音频听感验证已被真实素材取代（v5 用真实 BGM/SFX，仍待用户最终听感确认）**。项目处于"可日常交付"状态。

---

## Phase 7 — 全项目体系化整理（2026-09-30）　状态：✅ 已封版

> 目标：遍历全项目，建立目录规范与体系文档。原则：**生产引用面不动**（ffmpeg_env.py / sr_pipeline_v2.py 留守根级——被 5+ 生产文件引用），一次性实验脚本归档，文档归位，补齐根 README。

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 7.1 | 遍历盘点 + 引用面分析 | ✅ | 根级 29 个一次性实验脚本、6 份散落文档、3 个 workflow JSON、2 个空目录；引用面：ffmpeg_env/sr_pipeline（生产锁死）、workflow JSON（liaozhai/piyao 各 1 行常量）、outputs_paths（无外部引用） |
| 7.2 | 目录迁移：experiments/（实验脚本+分析残留）、docs/（6 份报告）、workflows/（H3 workflow + 归档备份） | ✅ | 29 脚本+2 dump → experiments；6 md → docs；r2v/t2v → workflows，backup → archive；根目录从 ~40 文件收敛到 4 系统文件+README | |
| 7.3 | 引用更新：liaozhai/piyao workflow 常量、SKILL.md 路径、gitignore 补 .agents/.workbuddy-ai/.zcodeignore | ✅ | 2 个 Path 常量 + SKILL.md 文档路径 + 8 行忽略规则（外部工具目录/acestep-env/生成音频/嵌入仓库） | |
| 7.4 | 根 README.md 体系文档（五层架构/项目模板规范/约定表/命令速查/仓库地图） | ✅ | README.md：五层架构图 + 仓库地图 + 项目模板规范 + 7 条铁律 + 命令速查 + 文档索引 + 许可注意 | |
| 7.5 | 提交推送 + 记忆同步 | ✅ | commit b3f553d（110 文件，git mv 保历史）已推 GitHub；**补齐关键遗漏：ffmpeg_env/sr_pipeline 此前从未入库** | |

---

## Phase 5 — 动效张力提升（2026-09-30）　状态：✅ 完成

> 目标：参照抖音爆款数据/知识类视频的动效语言，把 Remotion 模板的动效、配乐、数据展示视觉张力提升一轮。
> 三路并行调研：① 抖音爆款动效模式拆解 ② Remotion 高级特效技术栈（noise/three/lottie/gsap/effects/transitions）
> ③ 配乐与音效（ royalty-free BGM/SFX 源 + 卡点节拍数据 + 混音规范）

| # | 任务 | 状态 | 结论/数据 |
|---|---|---|---|
| 5.1 | 三路深度调研 | ✅ | 三报告齐：①抖音动效语法（量化参数表）②Remotion 特效栈（版本精确，采纳 noise/media-utils/effects(媒体件用)/pushCut；暂缓 three/lottie/gsap/motion-blur，理由见计划文档）③音频（合成方案+母带链定稿）|
| 5.2 | 提升计划文档 | ✅ | [REMOTION_MOTION_UPGRADE_20260930.md](REMOTION_MOTION_UPGRADE_20260930.md)（模式表/v4 候选清单） |
| 5.3 | 执行：模板动效升级 | ✅ | ReportVertical v2：AnimatedNumber（count-up+tabular-nums+后缀保留）、ImpactWrap（punch 1.1×→spring+白闪3f+±9px指数衰减震动+暗角冲击）、KineticChars 逐字slam（1f错峰 scale1.45→1）、卡点量化（bpm prop→分段起点吸附拍边界）、柱状图 spring d20/s100+7f错峰+冠军条金发光、SpeedLines 集中线、标题光扫、进度条。渲染 14.4s/28.1s 仍 2× 实时 |
| 5.4 | 执行：配乐/音效资产库 | ✅ | **网络受限改全合成方案**：`make_audio_assets.py` numpy 确定性合成 126BPM BGM（kick/hat/bass/pumping pad，32s 四段结构）+ 5 音效（whoosh/impact/pop/ding/riser）+ 精确拍网格 JSON——卡点零检测误差、零版权风险。模板 sfxAuto 自动铺设（whoosh 提前 0.18s+impact 落点+ding+riser） |
| 5.5 | v2 演示成片 + 迭代 + 性能 | ✅ | `out/pure_remotion_demo_v2.mp4`（28.1s）；修复：图表单位换行/outro字号/narration音量字段；**母带后处理**：首渲 −19.2LUFS/TP+1.3 超标 → loudnorm+gain+alimiter → **−14.8 LUFS/−0.1 dBTP** 达标。渲染期迭代 3 处模板细节 |
| 5.6 | v3 增强：BGM 呼吸脉冲 + noise 震动 + RGB 分离 | ✅ | 装 `@remotion/noise`+`@remotion/media-utils`；BassPump（低频能量→全屏 2.8% 脉冲，visualizeAudio optimizeFor speed）；ImpactWrap 震动改 noise2D；逐字入场 3f RGB 分离闪光。渲染 24.9s；**母带定稿流程：WAV 中转 loudnorm(TP −2 余量)→AAC320k → −14.2 LUFS/−1.1 dBTP**。成品 `out/pure_remotion_demo_v3.mp4`（10.3MB） |

---

## 变更记录

- 2026-09-29：Phase 0 启动。进度文档建立。
- 2026-09-29：**Phase 0 完成**（约 20 分钟）。基准：60.58s 成片 38.8s 渲染（1.55× 实时）；定稿配置 x264 crf18 + jpeg + colorSpace bt709 + 并发 16；关键坑修复：jpeg 默认 yuvj420p 挂 QA，bt709 修复且零损耗。详见 [studio/BENCHMARK_20260929.md](../studio/BENCHMARK_20260929.md)。下一步：Phase 1（timeline v2 zod 契约 → build_timeline.py v2 → drama-vertical 正式模板 → EP01_v3 过 QA）。
- 2026-09-29：**Phase 2 完成**。三模板家族成型（drama-vertical / psa-wide / story-animation = TimelinePlayer × 格式 × 样式集）；帧内转场（fade/flash）、碰撞修复、overlays、CoverCard 封面全部验证通过。EP01 v4 QA 16/16；piyao 109s@1080p 52.9s；liaozhai 75.75s@2K 60.2s。架构核心：`TimelinePlayer`（titlecard?→shots→endcard? 确定性装配）。下一步：Phase 3（report/daily-brief 纯程序化模板、词级卡拉OK字幕、Agent Skills 模板工厂）。
- 2026-09-29：**Phase 3 完成——四阶段全部落地**。模式 B 打通（ReportVertical 数据报告模板，29.9s 素材 13.1s 渲染，零 GPU）；词级卡拉OK（ASR 词面只当对齐标尺、文字用原文、相似度守卫拒错配）；心声打字机；官方 12 skills + 项目技能 minimax-video-templates（配方卡/铁律/六项入库门禁）。剩余可选项：Phase 4（常驻渲染服务/Player 预览 UI/批量队列）。
- 2026-09-29：**Phase 4 确认搁置**（暂无批量生产计划）。项目状态 = 交付完成，日常使用即：改 timeline/数据 → render_with_remotion.py / render.mjs 出片。
- 2026-09-30：**Phase 5 完成**（动效张力提升：三路调研 + ReportVertical v3 + 全合成音频管线 + 母带链定稿）。
- 2026-09-30：**Phase 7 完成（体系化整理）**：experiments/docs/workflows 三分类落地，ffmpeg_env+sr_pipeline 首次入库，liaozhai/piyao/third_lantern 三项目入库（含排除规则），根 README 体系文档，引用面全更新并验证。
- 2026-09-30：**Phase 6 完成（全面收尾）**。母带自动化、BassPump 包络化（渲染 36.8s→19.4s）、report QA 10 项门禁（首跑抓到 96kHz bug）、--karaoke 一条命令全链路、Bahnschrift 数字字体确认、听感样张、契约自检、out/ 清理、**4 个主题 commit 入库（Docs/Skills/Studio/Pipeline）**、studio/README。**剩余两项外部依赖：真实素材投放（网络恢复/手动下载）、合成音频听感结论（样张 out/audio_preview.m4a）。**
- 变更记录（2026-09-29 Phase 0/1 详见上文与 git 历史）：
  - Phase 0 启动与完成（渲染基准、bt709 修复）
  - Phase 1 完成（EP01_v3 新链 QA 16/16，A/B 对齐）

### Phase 7 附：全面清扫（2026-09-30）

- 删除（可再生/陈旧）：`tests/` 2GB 旧基准残留、`upscale_frames*/` 258MB 帧缓存、`preview/`、`work_frames/`、全部 `__pycache__`、`experiments/{oi,hist}.json` dump、`_deprecated.py`（远端同步移除）、`07_edit/EP01_K6_TEST.mp4` 55MB 测试渲染、`studio/out` 旧版本渲染（262MB→7.7MB，只留 v5 成片+封面+探针帧）。
- 归档（不删）：4 个 `.pre-v2.bak` + `09_final.pre-v2.bak`（233MB 旧交付备份）→ `ceo_mindread_ep01/_archive_prev2/`；`_archive_20260910_rerun/`（407MB v1 交付存档）保留原位。
- 保留：`logs/`（活跃管线日志）、`09_final*/` 现行交付。

### Phase 7 附：全面清扫（2026-09-30）

- 删除（可再生/陈旧）：`tests/` 2GB 旧基准残留、`upscale_frames*/` 258MB 帧缓存、`preview/`、`work_frames/`、全部 `__pycache__`、`experiments/{oi,hist}.json` dump、`_deprecated.py`（远端同步移除）、`07_edit/EP01_K6_TEST.mp4` 55MB 测试渲染、`studio/out` 旧版本渲染（262MB→7.7MB，只留 v5 成片+封面+探针帧）。
- 归档（不删）：4 个 `.pre-v2.bak` + `09_final.pre-v2.bak`（233MB 旧交付备份）→ `ceo_mindread_ep01/_archive_prev2/`；`_archive_20260910_rerun/`（407MB v1 交付存档）保留原位。
- 保留：`logs/`（活跃管线日志）、`09_final*/` 现行交付。
- 2026-09-30：**仓库转公开**（隐私/凭据/IP 四类审计通过）。出库：4 个 Mixkit 派生音频（本地保留，gitignore）+ 12 个 vendor 技能目录（可重装）。当前公开内容 = 模板代码 + 契约 + 文档 + CC0/自研音频；H3 prompt/种子/剧本按用户决策一并公开。
- 2026-09-30：**仓库转公开前完成历史净化**（用户决策：prompt/种子/剧本/timeline 只留本地）。git filter-repo 从全部历史清除 37 个敏感文件（workflows JSON、各项目 seed_manifest/story/dialogue/shots/timeline、prompt 型生成脚本）；本地文件备份于 `E:/H3_local_private/repo_backup/` 并已恢复为 gitignore 的未跟踪状态；强制推送重写后的历史（999088a），远端树验证 0 敏感路径。同轮：仓库转 PUBLIC + About/topics（remotion/comfyui/text-to-video/ai-video/douyin/real-esrgan）。

---

## ✅ 阶段封版（2026-09-30）

**范围**：Phase 0–7 全部（Remotion 融合落地 → EP01 迁移 → 三模板家族 → 数据报告/卡拉OK/模板工厂 → 动效张力提升 → 全面收尾 → 体系化整理 + 全历史净化 + 转公开）。

**交付物清单**
- 合成层：`studio/`（TimelinePlayer × 三时间线模板 + ReportVertical 数据模板 + CoverCard，zod 双契约）
- 管线桥：`build_timeline.py` v1/v2 双出、逐片段 SR、staging、一键渲染（`--karaoke/--master/--qa`）
- 质量链：qa_final 16 项、qa_report 10 项、check_contract 契约自检
- 音频链：合成兜底 + 真实素材导入（librosa 拍网格/包络）、母带自动化（−14 LUFS 自动收敛）
- 文档：README（体系首页）+ 6 份报告 + 本进度总账

**运行基线（RTX 5090 / 32 线程）**
| 场景 | 耗时 |
|---|---|
| EP01 60.6s 短剧新链 | 渲染 ~61s，qa_final 16/16 |
| 横屏 109s@1080p | 52.9s（2.1× 实时） |
| 横屏 75.8s@2K | 60.2s |
| 数据报告 28s | 14.1s（2× 实时），母带一轮过，qa 10/10 |
| 逐片段超分 | ~3.5 fps，VRAM 3.6GB |

**仓库状态**：公开 `gg320324492-lgtm/minimax-h3-studio`；历史已净化（37 敏感文件全历史清除）；本地生产内容（prompt/种子/剧本/timeline/生成脚本/Mixkit 音频）gitignore + 备份于 `E:/H3_local_private/`。

**已知遗留（供下阶段参考）**
1. 合成 BGM 兜底版质量有天花板（真实素材已可经代理获取并导入）
2. drama 模板未接电影感 LUT/辉光（`@remotion/effects` + `--gl=angle` 未实测）
3. v4 动效候选：冻结-爆发、百分比环、odometer、赛跑图、15/30/60s 档位、循环结尾、pushCut 迁移
4. 动效无自动质检（仅目检 + 响度量化）
5. 报告/数据模板无 LLM 自动填数据入口（现为手工 JSON）
