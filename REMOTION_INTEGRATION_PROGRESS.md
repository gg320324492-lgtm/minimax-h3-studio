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
| 0.13 | 撰写基准报告 | ✅ | [studio/BENCHMARK_20260929.md](studio/BENCHMARK_20260929.md) |
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
| 6.1 | **母带自动化**：master_audio.py（WAV 中转 loudnorm + 自动增益/限幅迭代 + 校验），集成 `render_with_remotion.py --master` | ⬜ | |
| 6.2 | **BassPump 离线包络**：make_audio_assets 输出 pump_envelope.json（numpy 频段能量→24fps 帧），模板改查表，淘汰 visualizeAudio（渲染时间从 24.9s 回到 ~14s） | ⬜ | |
| 6.3 | **report QA 门禁**：qa_report.py（分辨率/fps/编码/yuv420p/响度 −16..−12 LUFS/TP ≤−0.5/时长对齐 props），集成渲染流程 | ⬜ | |
| 6.4 | **卡拉OK并入正式流程**：render_with_remotion.py --karaoke 自动跑 word_timestamps（不再手工旁挂文件） | ⬜ | |
| 6.5 | **数字字体验证**：Bahnschrift（Windows 自带 DIN 类窄体）headless 渲染实测；资产投放口说明（assets/README：真实 BGM/SFX 替换规范+manifest 审计字段） | ⬜ | |
| 6.6 | **听感样张**：BGM+SFX 按成片时间戳混一条独立音频预览，供人耳验收合成音频质量 | ⬜ | |
| 6.7 | **契约同步自检**：check-contract 脚本（schema 重导出 diff + demo props 过 Python jsonschema smoke） | ⬜ | |
| 6.8 | **代码清理**：未用参数/死代码、out/ 临时产物、渲染残留 | ⬜ | |
| 6.9 | **Git 整理提交**：分主题 commits（docs / studio / python 管线） | ⬜ | |
| 6.10 | **文档收尾**：studio/README 快速上手 + 进度文档终版 | ⬜ | |

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
- 2026-09-29：**Phase 0 完成**（约 20 分钟）。基准：60.58s 成片 38.8s 渲染（1.55× 实时）；定稿配置 x264 crf18 + jpeg + colorSpace bt709 + 并发 16；关键坑修复：jpeg 默认 yuvj420p 挂 QA，bt709 修复且零损耗。详见 [studio/BENCHMARK_20260929.md](studio/BENCHMARK_20260929.md)。下一步：Phase 1（timeline v2 zod 契约 → build_timeline.py v2 → drama-vertical 正式模板 → EP01_v3 过 QA）。
- 2026-09-29：**Phase 2 完成**。三模板家族成型（drama-vertical / psa-wide / story-animation = TimelinePlayer × 格式 × 样式集）；帧内转场（fade/flash）、碰撞修复、overlays、CoverCard 封面全部验证通过。EP01 v4 QA 16/16；piyao 109s@1080p 52.9s；liaozhai 75.75s@2K 60.2s。架构核心：`TimelinePlayer`（titlecard?→shots→endcard? 确定性装配）。下一步：Phase 3（report/daily-brief 纯程序化模板、词级卡拉OK字幕、Agent Skills 模板工厂）。
- 2026-09-29：**Phase 3 完成——四阶段全部落地**。模式 B 打通（ReportVertical 数据报告模板，29.9s 素材 13.1s 渲染，零 GPU）；词级卡拉OK（ASR 词面只当对齐标尺、文字用原文、相似度守卫拒错配）；心声打字机；官方 12 skills + 项目技能 minimax-video-templates（配方卡/铁律/六项入库门禁）。剩余可选项：Phase 4（常驻渲染服务/Player 预览 UI/批量队列）。
- 2026-09-29：**Phase 4 确认搁置**（暂无批量生产计划）。项目状态 = 交付完成，日常使用即：改 timeline/数据 → render_with_remotion.py / render.mjs 出片。
- 变更记录（2026-09-29 Phase 0/1 详见上文与 git 历史）：
  - Phase 0 启动与完成（渲染基准、bt709 修复）
  - Phase 1 完成（EP01_v3 新链 QA 16/16，A/B 对齐）
