# P17 — Showcase Demo：能不能做出来，以及做出来会被什么拦住

> 结论 **B**，含 **C** 的一半。下面每一个数字都是本次实测，不是引述。
> 配套守卫：`tests/test_p17_showcase_demo_verdict.py`（16 项，本次新增）。

---

## 零、一句话结论

**P17 现在做不出来**，因为「含 1–3 个 H3 cinematic shot」没有任何东西可以渲染
（H3 渲染器不存在）；而如果有人**绕过**这一条去交付，
**时长 / 分辨率 / 帧率 / "premium" 四条里没有一条能拦住他** ——
这不是"判据偏松"，是**判据不存在**。

工单问的那个问题，答案是：

> **「如果有人今天就交付一份 demo，它会被什么判定拦住？」**
> → **只有 H3 shot 那一条会拦住。其余全部拦不住。**

---

## 一、H3 cinematic shot 现在能不能有：**不能**（实测）

### 1.1 渲染器不存在

对 `studio/src/**` 全树扫 `H3` / `h3_`（`.ts`/`.tsx`），**共 2 处命中，没有一处是渲染器**：

| 位置 | 内容 | 是渲染器吗 |
|---|---|---|
| `schemas/showcase-v1.ts:86` | `/** Scenes that need H3 rather than the Remotion motion engine. */` | 否，**是注释** |
| `templates/Phase0Probe.tsx:33` | `Remotion × MiniMax-H3` | 否，**是标题字符串** |

> ⚠️ 这两处正是本项目栽过的那个坑的形状：`render.mjs` 里
> `'Unknown flag' in source` 一直匹配着**解释该修复的那条注释**。
> 所以本项没有用"源码里有 H3 字样"当证据，而是用下面的运行期证据。

### 1.2 两个 generative 类型��会渲染成占位符

- `SceneType`（`showcase-v1.ts:60-84`）声明 **22** 个类型；
- `SCENE_RENDERERS`（`FinanceShowcaseWide.tsx:75-93`）登记 **13** 个；
- 差集 **9** 个 → 全部落到 `MissingScene`（`:95-112`），渲染出
  **"not implemented in P4"**。
- `GENERATIVE_SCENE_TYPES`（`:87-90`）= `{video, data-plane-3d}`，
  **两个都在那 9 个里面**。

Python 镜像 `pipeline/scene_graph.py:179` 的 `GENERATIVE_TYPES` 是同一对
（`test_the_two_mirrors_agree_on_the_generative_set` 每次跑都核对两侧一致）。

### 1.3 运行期实测（不是源码阅读）

把已交付的 `showcase_demo.json` 四个场景**全部**改成 `type: "video"`，
送进 `visual_qa.py --props`：

```
[FAIL        ] graph_scene_renderable  value=4
               4 scene(s), 13 of 22 declared scene types have a renderer;
               4 scene(s) have NO renderer and will render the MissingScene
               placeholder ("not implemented in P4"): scenes[0]=video, ...
6 findings: 1 FAIL, 0 UNVERIFIABLE, 4 UNAVAILABLE
EXIT=1
```

**⇒ 这是 P17 唯一真正会被拦住的条款。** 并且它拦住的形态很特别：
它拦住的是**占位符帧**，不是"画质不够"——
一份含 1–3 个 H3 shot 的 demo，会成片地把那几段���染成
**"video / not implemented in P4"** 这几个字。

### 1.4 P15 那条"差一行"的线索：至今没改，且比记录的更彻底

`tests/test_generative_signal_has_no_consumer.py`（P15）已经钉住"`generative` 无消费者"。
本次实测**确认它至今没改**，并把边界说得更准：

- `generative` 在 `showcase-v1.ts:373` 被算出，在 `:316` 被声明；
- 对**整个 `studio/src`** 扫 `generative` —— **只有那两行**，
  **零消费者**。
- P15 说"信号死在 `resolved.map` 那一行"；
  **实测是信号从没进过 `SceneRenderer`，而 `SceneRenderer` 的 prop 类型是 `{scene: Scene}`**，
  `SceneSchema` 是 `.strict()` 且没有该键。

**⇒ 那正是 H3 渲染器该待的地方，本项按工单要求没动它。**

---

## 二、时长 45–60s：**差 12.5 秒，且这是唯一"能用现有能力补上"的缺口**

### 2.1 已交付两份图谱（实测复现，与指挥窗口一致）

| 图谱 | 场景数 | 总帧数 | 规格 | 时长 |
|---|---|---|---|---|
| `pipeline/examples/charts_demo.json` | 10 | 1950 | 1920×1080@60 | **32.5s** |
| `pipeline/examples/showcase_demo.json` | 4 | 801 | 1920×1080@60 | **13.35s** |

**规格（16:9 / 1080p / 60fps）已达标；最长的离 45s 下限差 12.5 秒���**

> ⚠️ **一处需要纠正的读数**（本项自己踩到并修正）：
> 全仓扫描时**出现过 65.00s 的条目** —— 那是**同样的 1950 帧跑在 30fps**，
> 不是更长的内容。**声明"最长 32.5s"时必须限定 60fps**，
> 否则会拿一个 fps 探针冒充成片。（第一次扫描时我的 `out/` 过滤没生效 ——
> Windows 反斜杠路径不匹配 `startswith('out/')` —— 把 `out/**` 的探针也算进来了。
> 已修正为归一化路径后重扫。）

按 60fps 限定，**全仓被 git 跟踪的、带 `scenes`+`format` 的图谱只有 4 个**
（另两个是 `studio/public/jobs/**` 的 staging 副本，只读，不算数）。
**最长 = 32.5s。**

### 2.2 加长是纯算术，不是能力缺口

实测构造 2700 帧（4 × 675）@60fps = **45.0s**，全部用**有渲染器**的类型：

```
[PASS] graph_scene_renderable  value=0
6 findings: 0 FAIL, 0 UNVERIFIABLE, 4 UNAVAILABLE
EXIT=0
```

schema 侧也没有上限：`Scene.durationInFrames` 是
`{"type": "integer", "minimum": 1}`，**无 `maximum`，无总时长约束**。

**⇒ 「45–60s」是 AUTHORABLE 的。今天就能写出来。**
**⇒ 它不是 P17 的阻塞项，缺的只是编排（多写/加长几个场景）。**

**但** —— 它**���样不会被任何东西拦住**（见第三节）。

---

## 三、⚠️ 最危险的一条：另外三条判据**根本不存在**

### 3.1 实测：`visual_qa.py --props` 对时长和分辨率**完全无感**

三个图谱，同一条命令，**退出码全是 0，全 PASS**：

| 图谱 | 时长 | 规格 | `graph_scene_renderable` | 退出码 |
|---|---|---|---|---|
| 单场景 60 帧 | **1.0s** | 1920×1080@60 | PASS | **0** |
| 单场景 18000 帧 | **300.0s** | 1920×1080@60 | PASS | **0** |
| 单场景 60 帧 | 1.0s | **640×480@24** | PASS | **0** |

**一份 1 秒的片子、一份 5 分钟的片子、一份手机分辨率的片子，
在这道门上和一份合规片子毫无区别。**

（`test_p8_format_scale.py` 钉的是"模板**读** format 读得对不对"，
**不是**"片子**有**没有这个 format"—— 两回事，前者已过，后者无人过。）

### 3.2 实测：这道门**没有被任何生产路径调用**

工单问"如果有人今天交付会被什么拦住"。我把这个问题反过来做了一遍 ——
**不是去读 `pipeline_manifest.yaml` 的 `enforced: false` 注释，
而是把全仓扫了一遍并断言结果**：

- 对 `tests/`、`out/`、`node_modules/` 之外的 `.py`/`.mjs`/`.sh`/`.json`/`.yaml`
  扫 `visual_qa`��**生产代码里零调用点**。
- **`studio/bin/render.mjs` —— 所有渲染必经的那个文件 —— 里没有任何 QA 调用。**

`pipeline_manifest.yaml:198-204` 用仓库自己的话说：
**「质量门禁（当前全部无自动执行 —— P0 接线）」/ `enforced: false`**，
并把 `qa_report.py` 标为**「零调用方」**。实测与这句话一致。

### 3.3 ⚠️ "premium product film"：**不可判定，不给它编指标**

**总计划对 P17 的成功判据是「明显达到 premium product film」。**
本项目**没有任何可测量判据**对应这句话：

- `visual_qa.py` 的 4 个 `UNAVAILABLE` 里，有 3 个正是这类"仪器在、判据缺"的：
  `collision`（**阈值从未设定**，已交付图表实测 0.278）、
  `flicker`（跨步 + 无正类，P23 实测）、
  `contrast_frame`（**像素里没有前景/背景角色**，无法双峰，P22 实测）。
- **`premium` 是这五个里最糟的一个**：前面四个至少有仪器、有语料；
  premium 连仪器都没有 —— 没有语料（没有"premium 成片"对照组），
  没有正类，没有负类。

**⇒ 明确记录：这一条不可判定。**
本项目已经接受过**五次**「实测说不出想要的结果」
（collision / rule_duplicate / rule_contrast_frame / flicker / per-job 基线）。
**这是第六次，且是唯一一次连测量对象都不存在的。**
**本项没有为它编任何指标。**

### 3.4 「达标」由什么判定 —— 本项的正面回答

即便绕开 H3，一条 45–60s 的片子交上来，今天能判定它的只有：
**`graph_scene_renderable`（有没有渲染器）+ `missing_asset`（资产在不在）**，
**而且这两个都得有人手动跑、并且手动读退出码。**

**所以「商业级 demo 达标」这件事，本质上目前是一个人的一次手动判断，
不是一个可复现、可回归、可交付的判定。**
P13 已实测「产物不可复现」，P24 进一步实测
**同一次渲染的两次运行之间 801 帧里有 220 帧像素不同** ——
**在一个不可复现的产物上，"premium" 更无从谈起。**

---

## 四、裁定

### **B（不能建）**，其中时长一条是 **C（拆开）** 的可建半

| 要求 | 判定 | 依据 |
|---|---|---|
| 16:9 / 1920×1080 / 60fps | ✅ **已达** | 实测两份图谱均 1920×1080@60 |
| 45–60s | ⚠️ **可建但差 12.5s**，且无判据 | 实测 32.5s 最长；45.0s 图谱实测 EXIT=0；schema 无上限 |
| **1–3 个 H3 cinematic shot** | ❌ **不能建（硬缺口）** | 实测无 H3 渲染器；两 generative 类型实测 EXIT=1 / "not implemented in P4" |
| **"明显达到 premium product film"** | 🚫 **不可判定** | 无判据、无仪器、无正负类；**未编造指标** |
| （隐含）**判据存在** | ❌ **不存在** | 实测 `--props` 对 1s/300s/640×480@24 均 EXIT=0；`render.mjs` 零 QA 调用 |

**选 B 而不是 C 的理由**：C 会说"时长可建，H3 不可建，拆开做"。
但**时长那一条的"可建"是有条件的** ——
按第三节，它今天既不被拦、也没有判据，**做出来也无法被判定为"达标"**。
把一个**无法被判定为达标**的 45s demo 单独交付，
交付的不是"P17 的一半"，是**一个没有验收标准的文件**。
**⇒ 拆开没有意义，整条要求不成立。**

### 要建它需要什么、按什么顺序

**前置（P0，缺了后面都白做）：**

1. **接线**：`render.mjs`（或 `render_with_remotion.py`）在渲染后调用
   `visual_qa.py --props`，**并 gate 在退出码上**。
   —— 这是本次实测的最大单点缺口：**门是好的，只是没人叫它。**
   （`pipeline_manifest.yaml:198` 已标 `P0 接线`。）
2. **时长/规格判据**：为「45–60s / 1920×1080@60」写**带阈值**的规则。
   这一条**可以有阈值**（与 premium 不同）：45–60s 是计���里写死的数字，
   `durationInFrames` 又有 `minimum: 1` 的现成下界语境，
   **这是"计划给了数、仪器给了测量"**，不是要发明判据。

**H3（真正的硬缺口，按依赖顺序）：**

3. **决定 H3 是什么**：仓库里**没有** H3 客户端、没有 provider 抽象、
   没有 `take_critic.py`（工单第六节：已裁定标依赖、不合并、不重复建）。
   ⇒ **这不是"接线"，是"从零建一条新链路"**，工作量不在 P17 之内。
4. **让 `generative` 有一个消费者**：改 `FinanceShowcaseWide.tsx` 的
   `resolved.map`，把**带 `generative` 的 `r`** 传下去，
   并让 `SceneRenderer` 能按该位分派。
   ⇒ **P15 已记录该线索，本项按工单要求未改**（待裁定）。
5. **`MissingScene` 的处置**：在 `video` / `data-plane-3d` 有渲染器之前，
   **这两个类型应该被 schema 拒绝**，而不是渲染成 "not implemented in P4"。
   `graph_scene_renderable` 已经在报，但**没人叫它**（回到第 1 条）。

**"premium"：**

6. **不要动它，直到有对照组。** 需要的是**一份公认达标的 premium 成片语料**
   加上**一个能把它和不合格样本分开的统计量**。
   在此之前，任何"premium 判据"都是编的��
   **这一条建议单独开一项，且明确允许它得出"仍然不可判定"。**

---

## 五、守卫：真的跑了，并断言了判定

`tests/test_p17_showcase_demo_verdict.py`，**16 项，本次新增**。

**没有一条断言"源码里有 `premium`"或"某个数字出现了"。**
每一条能力断言都走 `vqa.main(argv)`，读**返回值**和**打印的报告**。

### 5.1 它回答的那个问题

```
tests/test_p17_showcase_demo_verdict.py::test_a_graph_asking_for_a_generative_scene_is_blocked
tests/test_p17_showcase_demo_verdict.py::test_every_generative_type_is_gated_not_only_video
tests/test_p17_showcase_demo_verdict.py::test_a_demo_that_is_one_h3_shot_among_many_is_still_blocked
```
**⇒ 会被拦住的（实测 EXIT≠0）**，且报告必须点名 `scenes[3]=video` 这种可操作的定位。

```
tests/test_p17_showcase_demo_verdict.py::test_a_one_second_film_passes_the_graph_gate
tests/test_p17_showcase_demo_verdict.py::test_a_five_minute_film_passes_the_graph_gate
tests/test_p17_showcase_demo_verdict.py::test_a_640x480_at_24fps_film_passes_the_graph_gate
tests/test_p17_showcase_demo_verdict.py::test_no_production_script_invokes_a_showcase_qa_gate
tests/test_p17_showcase_demo_verdict.py::test_the_render_entry_point_calls_no_qa_gate
```
**⇒ ���不住的（实测 EXIT==0 / 零调用点）** —— 这几条是**钉住"什么都拦不住"这个事实**，
正是工单要求的那个答案。

### 5.2 变异（每条都先 assert 变异落地，再跑 pytest）

| # | 变异 | 期望 | 结果 |
|---|---|---|---|
| **M1** | `visual_qa.py` 的 `gaps` 恒为 `[]`（门不再拦占位符） | 红 | ✅ **被杀**，3 项 |
| **M2** | 同规则**恒返回 PASS**（永远通过） | 红 | ✅ **被杀**，3 项 |
| **M3** | 给 `data-plane-3d` 登记一个渲染器（假装 H3 缺口被本地填了） | 红 | ✅ **被杀**，2 项 |
| **M4** | 给 `Scene.durationInFrames` 加 `maximum: 3600` | 红 | ✅ **被杀**，1 项 |

**4/4 存活变异全部被杀，无无效变异。**
**M1/M2 红的理由正确**：红在 `assert 'PASS' == 'FAIL'`（判定本身），
不是红在别的断言上。

**原始 `-rf` 输出**（各变异后从快照复原，收尾 sha256 全部核对一致）：

**M1**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_a_graph_asking_for_a_generative_scene_is_blocked
FAILED tests/test_p17_showcase_demo_verdict.py::test_every_generative_type_is_gated_not_only_video
FAILED tests/test_p17_showcase_demo_verdict.py::test_a_demo_that_is_one_h3_shot_among_many_is_still_blocked
3 failed, 13 passed in 3.82s
```
```
E       assert 'PASS' == 'FAIL'
E       - FAIL
E       + PASS
tests\test_p17_showcase_demo_verdict.py:205: AssertionError
```

**M2**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_a_graph_asking_for_a_generative_scene_is_blocked
FAILED tests/test_p17_showcase_demo_verdict.py::test_every_generative_type_is_gated_not_only_video
FAILED tests/test_p17_showcase_demo_verdict.py::test_a_demo_that_is_one_h3_shot_among_many_is_still_blocked
3 failed, 13 passed in 3.85s
```
```
E       AssertionError:   [PASS        ] missing_asset   value=0
E       assert 'PASS' == 'FAIL'
tests\test_p17_showcase_demo_verdict.py:162: AssertionError
E       AssertionError: generative type 'data-plane-3d' was not gated:
E       assert 'PASS' == 'FAIL'
tests\test_p17_showcase_demo_verdict.py:184: AssertionError
```

**M3**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_every_generative_type_is_gated_not_only_video
FAILED tests/test_p17_showcase_demo_verdict.py::test_no_h3_renderer_exists_in_the_render_source
2 failed, 14 passed in 3.91s
```
```
E           AssertionError: generative type 'data-plane-3d' was not gated:
tests\test_p17_showcase_demo_verdict.py:184: AssertionError
E           AssertionError: SCENE_RENDERERS now routes ['data-plane-3d'] — a generative type has a Remotion renderer. Re-measure before claiming P17 cannot be built.
tests\test_p17_showcase_demo_verdict.py:531: AssertionError
```

**M4**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_the_schema_places_no_upper_bound_on_scene_duration
1 failed, 15 passed in 4.52s
```
```
E       AssertionError: Scene.durationInFrames now has a maximum: {'type': 'integer', 'minimum': 1, 'maximum': 3600}. The finding that duration is unconstrained has changed and this file must be re-measured.
tests\test_p17_showcase_demo_verdict.py:283: AssertionError
```

**复原核对（sha256，四个源文件全部一致）**
```
7e7d586a747c9fb13eb5b23628156e19649b1d696fa85fbff281207416d35ded  studio/scripts/visual_qa.py
e426a88febd9dd5ee6138381c2638f0f94b2abaea83678e42efcf845e1a36ed4  studio/src/templates/finance-showcase/FinanceShowcaseWide.tsx
812506600494bbaac9b9a4c237a8eb8c4a19060d91b648ac48d7ade844ee6acf  pipeline/schemas/showcase-v1.schema.json
fd7e6927b8af11ecc4aabc7b412ac5a73cc0dac74007a0c6593efe5206140d21  pipeline_manifest.yaml
```

---

## 六、本项的失误（如实记录）

1. **守卫的第一版数注释当调用点。**
   `render.mjs:141` 的**注释**里出现了 `qa_final.py`
   （解释为什么传 `--pixelfmt yuv420p`），我的第一版 sweep 直接命中它并报红，
   `test_the_render_entry_point_calls_no_qa_gate` 因此**第一次是红的**。
   **这正是本项目记录过的 `render.mjs` 'Unknown flag' 坑的形状。**
   已改成"先剥注释再扫"，并加 `test_the_comment_stripper_separates_a_call_from_a_mention`
   把这个错误本身钉住。

2. **第一版 sweep 的范围过宽，产生了 11 个"offender"。**
   逐个查证后，**诚实的只有两类**：`third_lantern` / `liaozhai_demo` 的
   `qa_final.py` 确实被自己的 `run_post_chain.sh:133` 调用
   （`"$PY" scripts/qa_final.py`，实测），其余是注释。
   ⇒ **"仓库里什么都没有 gate"是假的，我没有这样断言。**
   守卫改成只声称**可核实的那一条**：**没有任何生产路径运行能判定 showcase 图谱的那道门**。

3. **`out/` 过滤第一次失效**，把 `out/**` 的 fps 探针算进"最长的图谱"，
   一度得出"最长 65s"。原因：Windows 反斜杠路径不匹配 `startswith('out/')`。
   已改为 `os.path.normpath` 归一化后重扫（**同一条数据，两个不同结论**，
   记在这里以免下次又被它骗一次）。

4. **两处自己写错的断言**：`schema['$defs']`（该镜像是 draft-07，用
   `definitions`）、以及一个指向不存在目录的占位 fixture。
   都在首次运行时暴露并已修。

---

## 七、测试数字

| | 结果 |
|---|---|
| **改动前基线**（实测） | `478 passed, 3 skipped in 207.63s` |
| **改动后**（实测） | **`494 passed, 3 skipped in 201.06s`，退出码 0** |

478 + 16 = 494，**与新增的 16 项守卫逐项吻合**，无回归。

标准跑法：
```
cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q \
  --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py
```

---

## 八、改动文件清单

| 文件 | 性质 |
|---|---|
| `tests/test_p17_showcase_demo_verdict.py` | **新增**，16 项守卫 |
| `docs/P17_SHOWCASE_DEMO.md` | **新增**，本文件 |

**未改动任何生产代码。** 未实现 H3 渲染器，未改
`FinanceShowcaseWide.tsx` 的 `resolved.map`，未改 `GENERATIVE_SCENE_TYPES`，
未渲染任何成片（`render.mjs:83` 的 46 GB TEMP 记录未去触碰），
未动 P19–P24 的成果，未改账本。