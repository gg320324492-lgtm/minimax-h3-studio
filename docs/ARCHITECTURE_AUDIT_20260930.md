# 架构审计报告（2026-09-30）

> P0 全库只读审计。方法：分区深挖 + 跨切面 grep/运行时实证；**所有行为均以生产解释器 `E:/ComfyUI/venv/Scripts/python.exe` 验证**（系统 Python 3.10 会给出误导性错误）。
> 配套：[UPGRADE_MASTER_PLAN.md](UPGRADE_MASTER_PLAN.md) · [UPGRADE_PROGRESS.md](UPGRADE_PROGRESS.md)

---

## 0. 现状一句话

> 26 GB 磁盘、13 MB / 177 文件入库的仓库。**两套并行的出片系统**（ffmpeg 6 段链 vs Remotion 单命令），**没有一条端到端自动化**，**无 CI、无测试、无依赖清单**。已交付母版由一条「已被自己淘汰、当前无法运行」的超分脚本生成。

---

## 1. 现状架构图

```
【AI 生成层】ComfyUI @8188（MiniMax-H3 ref2va int8 + turbo LoRA）
   gen_references → gen_reference_sheets → gen_office → gen_keyframes_v3
        ↓ 【选片】select_takes.py        ← T01 硬编码，无评分（R2）
        ↓ 【超分】
   链A: run_post_chain.sh → sr_pipeline_v2（整片 tile768）
   链B: sr_takes.py          → sr_pipeline_v2（逐 take →1080×1920）
        ↓ 【装配】
   链A: build_timeline(v1) → mix_audio_v4 → burn_subtitles_v2 → finalize → qa_final
   链B: build_timeline(v2) → stage_assets → render.mjs → [master] → [qa_final]
        ↓ 【QA】qa_final 16项 / qa_report 10项 / check_contract 2项
```

**关键结构性事实**：

| 事实 | 证据 |
|---|---|
| **只有链 A 有编排器** | `run_post_chain.sh` 是全库唯一编排器，对 Remotion 引用数为 **0** |
| 链 B 无编排者 | 只能手工单条命令（README:68 / SKILL.md:17） |
| 两条链**上游全是手工** | H3 生成、TTS、BGM/SFX 无自动衔接 |
| 两者仅共享 `build_timeline` 输出 | 其余阶段互斥（画面装配二选一） |
| 交付母版（09-19）出自链 A | Remotion 产物**未提升为交付**（仅存 07_edit/） |

---

## 2. 风险清单（按严重度）

### 🔴 R1 — 敏感文件未受 gitignore 保护（**已于本日修复**）
文档曾声称敏感文件「已 gitignore」，实测 `git check-ignore` 全部 NOT-IGNORED；`git add -A` 会把 40 个文件（剧本/种子/timeline/workflow JSON/14 个生产脚本）重新提交进**公开**仓库。根因：规则段被历史重写覆盖。
**修复**：`**/00_project/{timeline,dialogue,seed_manifest,story,shots,sfx_times}*.json`、`workflows/`、12 个 prompt 型脚本、归档目录，逐条 `git check-ignore` 验证 12/12（提交 c8014af / b4bcb54）。

### 🔴 R2 — 已交付母版由当前无法运行的脚本生成
`09_final_v2/render_report.md` 记录母版超分来自 `pipe_4k_fast.py`；该脚本 `import _deprecated`（模块已删），生产解释器下**直接崩溃**。现行 `sr_pipeline_v2.py` **从未产出过交付母版**。→ 升级报告的对比基准已断。

### 🔴 R3 — mtime「猜最新文件」在生产路径静默生效
`comfy_utils.py:55` `fallback_newest: bool = True` 是**默认值**；3 个调用方（`gen_office/gen_references/gen_reference_sheets`）既不传参也不告警——正是该模块立项要消灭的 bug。`gen_keyframes_v3.py` 自建副本，另有 4 份跨项目副本。
**附带**：4 个生产 ComfyUI 脚本轮询**无 deadline、无异常守卫**（ComfyUI 挂起即永久阻塞）；正确答案（`bench.py:123` 1800s / `flashvsr_upscale.py:240` 7200s）就在仓库里，只是没被采用。

### 🟠 R4 — `ffmpeg_env.py` 会把 CWD 注入 PATH
`tools/` 被 gitignore → 新 clone 缺自带 ffmpeg → `_resolve_dir()` 返回 None → `prepend_to_path()` 对裸 `ffmpeg` 做 `abspath` 解析得到 **CWD** 并前置到 PATH（已实测复现）。13+ 生产脚本依赖此函数。

### 🟠 R5 — 契约双向沉默，漂移产出错误画面而非报错
两个导出 JSON Schema 的 `additionalProperties` 出现次数 = **0**；zod v4 `z.object()` 默认 strip，从未用 `.strict()`。→ 字段拼错/stale 字段同时通过 Python 校验**并**在渲染时被静默丢弃。
叠加 `fit` 默认值是 `'fill'`（非更安全的 `'cover'`）：漏写 `fit` → 静默拉伸。
另：`emit_props.py` 接受 `--fit contain` 而 schema 不允许 → 必炸（契约裂缝）。
**P0 已修**：`fit` 改为 `auto`（SR 直出 fill，原始片 cover）。

### 🟠 R6 — 全部质量门禁无自动化执行
无 CI、无 pre-commit；`check_contract.py` / `qa_report.py` **零调用方**；`package.json` 无 lint/typecheck/test 脚本。
**且** `check_contract.py` 的 props 检查在干净 clone 上是空的（`studio/public/jobs/` 被 ignore）→「通过」但一个 props 都没验。

### 🟡 R7 — 命名与文档的系统性误导（给 Agent 的直接干扰源）
| 名称 | 实际 |
|---|---|
| `09_final_v2/` | 2026-09-19 的**链 A**产物；与 `09_final/` 三个 mp4 **md5 全同**、非硬链接，~89 MB 纯冗余 |
| `seed_manifest_v1_20steps.json` | 与当前 `seed_manifest.json` **md5 全同**，内容写的是 4step |
| `select_takes.py` | 无任何评分函数，T01 硬编码 |
| `REMOTION_INTEGRATION_PLAN:209-256` | 与代码有 **11 处实质字段不一致**（含 `transitionIn` 默认值静默变更） |
| `README.md:35` | 称 render.mjs 内置 crf18/concurrency16，实际两者默认 `undefined` |
| `BENCHMARK_20260929.md:57` | 引用的两个样本渲染已删除；其再生成器产出版本 0，通不过现行 schema |

### 🟡 R8 — 无依赖清单、无测试、无版本约束
零个 `requirements.txt`/`pyproject.toml`/`pytest.ini`。Python 依赖全部隐式寄居 ComfyUI venv（torch/kokoro/librosa/jsonschema…）。`qwen-tts` 未装 → `liaozhai_demo/scripts/gen_narration_v2.py:35` 是死分支。`tests/` 目录（SR 升级决策的全部证据脚本）已随删除消失。

### 🟡 R9 — 混音总线是视频容器，~495 MB 死重量
`master_audio.py` 在**视频文件上原地母带**，`audioBus.premixed` 指向该 MP4。7 个 job 的 `PREMIXED.mp4` 全部含高码率 h264 视频轨（liaozhai 单个 233 MB / 25.5 Mbps），而 `<Audio>` 只取音频 → 97% 重量被丢弃。

### 🟡 R10 — 生成链完全串行，无并发原语
`gen_keyframes_v3.py` 严格串行双层循环；生产脚本零并发/零锁（grep `threading|concurrent.futures|flock` 零命中）。这正是 mtime bug 的触发条件，也是未来 Director + Scene Graph 架构的阻塞项。

### 🟡 R11 — 14/195 脚本 + workflows/ 未入库
含全部 4 个 `build_timeline.py`、3 个 `gen_clips.py`、`gen_keyframes_v3.py`、`gen_tts_kokoro.py`、全部 3 个 `tools/` 脚本。
且 `workflows/` 副本**既不被读也不在版本控制**——生产脚本硬编码读 `E:\ComfyUI\user\default\workflows\`（当前两份字节相同，但无同步机制）。

### 🟡 R12 — 12 个 vendor skill 只存在于本机
`.claude/skills/remotion-*` 全是未入库 symlink；`skills-lock.json` 不 pin commit 且哈希与磁盘不匹配。**全新 clone 只有 1 个可用 skill**。

---

## 3. 生产入口清单

### production（链 A 编排器 `run_post_chain.sh`）
`select_takes` · `build_timeline` · `mix_audio_v4` · `burn_subtitles_v2`（兼作 qa_final 的库）· `finalize` · `qa_final` · `comfy_utils` · 根级 `ffmpeg_env` / `sr_pipeline_v2`

### production（链 B，无编排者）
`render_with_remotion` · `stage_assets` · `sr_takes` · `studio/bin/render.mjs` · `studio/scripts/{master_audio,qa_report,word_timestamps,emit_props,check_contract,make_audio_assets,import_real_assets}`

### production（上游，手工）
`gen_tts_kokoro` · `gen_audio_assets` · `gen_office`（其产物被 gen_keyframes 硬引用）

### experimental（不在任何链中，但产物被消费）
`gen_keyframes_v3`（含全库最精心的 resume 逻辑）· `gen_reference_sheets` · `gen_references`（deprecated 但被依赖，删则 sheets 断）

### experiments/ 28 脚本分类
- **production candidate** 1：`flashvsr_upscale`（唯一具备 deadline+重试+纯 history 解析；`/object_info` schema 发现与 `system_stats` 预检是生产侧完全没有的能力）
- **useful benchmark** 6：`bench`（干净 poller）· `bench_log`（VRAM 探针）· `multi_bench` · `bench_4k_chain`（结论仍被 flashvsr 引用）· `bench_dtype` · `bench_real_esrgan`
- **superseded** 6 · **unsafe legacy** 4（`gen_round_a` 删仓库根文件 / `test_seedvr2` 纯 mtime 主路径 / `download_models` 硬编码代理+误删 20GB 下载）· **archive candidate** 11（含 5 个已崩溃脚本 + `pipe_4k.py` 无 `__main__` 守卫、import 即执行）

---

## 4. 重复代码（可抽取共性）

三个旧项目 10 个同名脚本**零字节相同**，但：
- **63 行字节级完全相同**：`get_font`/`wrap_text`/`text_width`（字幕排版 32 行）· `outputs_from_history`（11 行）· `record_seed` · `submit`/`log`/`check`/`enc_args`/`adur`
- **仅差一个常量**：`api`（timeout）· `wait_for` · `run` · `normalize` · `clip_path` · `save` · `mix_audio.main`（162 行仅差 4 行）· `qa_final.main`
- **hoist 先例已在库中**：`ffmpeg_env.py`（21 个调用点）证明该模式在本仓库已验证可行
- **未传播的重构**：`third_lantern/scripts/gen_clips.py:104-134` 的 `_base_graph()` 是 H3 sampler graph 的 DRY 抽取，未向另两个项目传播
- **不可抽取**：`gen_sfx.py`（三套互不相交声音库，相似度 24.6%）与 `gen_bgm.py`（14.6%）——创作而非管线

---

## 5. 硬编码路径

| 前缀 | 命中 | 分布 |
|---|---|---|
| `E:\Minimax-H3` | 202 | 98 文件 |
| `E:\ComfyUI` | 103 | 43 文件 |
| `C:\Users\...` | 40 | 26 文件 |

仅 4 个路径 env 可覆盖（`EP01_MASTER` / `EP01_FINAL_DIR` / `EP01_DESKTOP_DIR` / `EP01_LOCK_CRF`）。
**做对了的例外**：`studio/src/**`、`studio/bin/**`、`remotion.config.ts`、`package.json`、`tsconfig.json` 零硬编码（`render.mjs` 的 entryPoint 来自 `import.meta.url`）；`emit_phase0_props.py:19` 从 `__file__` 推导 ROOT。

---

## 6. 后续 Phase 依赖关系

```
R1（已修）─┐
R5 fit（已修）─┤
        ├─→ P1 TakeRanker ──→ P2 Atomic Shot ──→ P15 SR 路由
R3 mtime/deadline ─→ P0.3 ─┘                      ↑
R4 CWD 注入 ──→ P0.4 config 层 ──────────────────┘
R6 无 CI ──→ P0 门禁接线 ──→ P10 Visual QA ──→ P11 Repair Loop
R10 串行 ──→ P14 Render Worker（并发前置）
R9 混音总线 ──→ P0 附：premix 提为纯音频
R7 文档误导 ──→ 随各 Phase 同步修正（不单列）
R2/R8/R11/R12 ──→ 生产硬化项（不阻塞主线）
```

---

## 7. 给 Agent 的三条硬约束

1. **一切行为必须用 `E:/ComfyUI/venv/Scripts/python.exe` 验证。** 系统 Python 3.10 会给出与生产无关的错误。
2. **不存在单一的「生产链」。** 判断某脚本是否生产，必须分别对照 `run_post_chain.sh`（链 A，唯一编排器）与 `render_with_remotion.py`（链 B，无编排者）；**两者上游均为手工**。
3. **`docs/REMOTION_INTEGRATION_PLAN_20260929.md:209-256` 不是契约**（11 处字段不一致）。真正契约是 `studio/src/schemas/*.ts` + 其导出物。
