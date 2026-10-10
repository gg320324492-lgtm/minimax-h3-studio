# P43 裁定 —— `data-plane-3d` **判 C（不做）**

> 执行 agent 交付。**未改任何生产代码**，只提交本文件。
> 全部结论均为**实测**，非引述、非推断。测量原始输出见文末附录。

---

## 0. 结论一句话

**工单的前提「引入 `@remotion/three` 就能建」未被检验过；实测它不成立。**
把 `data-plane-3d` 挂到任何一个渲染器上（**一行改动、不装任何依赖**），
会让 **9 条守卫转红**，横跨 **6 个已完成的工作单**，
**其中一条正是工单要求我「转绿」的那条 P21**。
而且这不是「补个内容」能解决的 —— P29 的孤儿渲染器守卫要求
**必须同时有一个 tracked graph 用到它**，而 tracked graph 里 `data-plane-3d` 出现 **0 次**。

---

## 1. (a) 它画的是什么 —— **没有依据**

### 1.1 实测范围

| 检索 | 结果 |
|---|---|
| `git log --all -S'data-plane-3d'` | **27 个 commit**，逐个看过 diff |
| `git log --all -S'data_plane'` | **0**（该 token 从未以蛇形出现过） |
| 首次出现 `71da3cd`（P0） | 只有**依赖裁定** + 名单里一个**类型名**，无任何画面描述 |
| 全树 `point cloud`/`点云`/`particle`/`粒子`/`立体`/`plane-3d` | **0 处**相关内容描述 |
| `docs/ARCHITECTURE_AUDIT_20260930.md` | **0** 次提到该类型 |
| `SHOWCASE_SCHEMA.md` | **不存在**（总计划 `:100` 列为待产出，从未写） |

### 1.2 唯一「像描述」的东西，**不是描述**

`docs/UPGRADE_MASTER_PLAN.md:110`（§3 视觉目标，描述的是**参考片**）：

> `- 3D 数据表面 + 蓝色柱体、图表快速轮换、窗口墙`

⚠️ **这一条从未与 `data-plane-3d` 绑定。** 证据是 P26 自己做的裁定 ——
`docs/P26_MISSING_RENDERERS.md:57` 明确把 §3 逐条点名过的 7 个类型列了出来
（数据卡 / 表格矩阵 / Quote / Logo / CTA / 窗口墙 …），
**`data-plane-3d` 不在其中**。

### 1.3 两处「描述」实为**引擎陈述**，不是画面陈述

```
studio/.../FinanceShowcaseWide.tsx:131
 *  - `data-plane-3d` — a 3D data surface. It is routed to H3 by
studio/.../FinanceShowcaseWide.tsx:147
  'data-plane-3d': 'needs a 3D surface; routed to the generative set and @remotion/three is not a dependency',
```

两句都在**解释「为什么没有渲染器」**，都在讲**引擎**，都不含
content 键、图元、编码方式、相机、交互。**「needs a 3D surface」是依赖说明，不是画面说明。**

### 1.4 P43 之前，项目已经两次正面回答过这个问题

- **P26 `:36` 判 B**（缺引擎），**未判 C**（缺规格）—— 因为先撞上引擎这道墙，
  C 这一层**从未被裁定**。
- **P37 `:239`**（逐帧实测参考片后）：`| **P17 的 video / data-plane-3d** | 本项**不提供**渲染器 |`
  —— 参考片分析**产不出**这个场景的视觉描述。

⇒ **(a) 判定：没有依据。** 按工单 `:88`，这本身是合法交付。

---

## 2. (b) 数据从哪来 —— **没有契约，且实测无数据**

### 2.1 `content` 是完全开放的袋子

```json
// pipeline/schemas/showcase-v1.schema.json:144-146
"content": { "type": "object" }
```
```ts
// studio/src/schemas/showcase-v1.ts:256
content: z.record(z.string(), z.unknown()).optional(),
```

**没有 `properties`、没有 `description`、没有按 `type` 的 `oneOf` 分派。**
任何形状的对象对**所有 22 种类型**都合法。
`data-plane-3d` 没有 `ChartSpec` 那样的等价物。

### 2.2 实测：**零个** graph 用到它

```
tracked graphs: ['charts_demo.json', 'showcase_demo.json', 'p29_new_renderer_showcase.json']
data-plane-3d used in ANY tracked graph: False
```

⇒ **今天建出来的渲染器，没有任何数据可读。**

### 2.3 与已交付渲染器的对比（这就是差距）

| | `data-plane-3d` | `bar-chart` 等 10 种 | `data-table` |
|---|---|---|---|
| content 规格 | **无** | `ChartSpec`（TS 类型，14 个字段） | docstring `:11-36` 列出 columns/rows |
| 用到的 graph | **0** | 10 场景 | 1 场景 |

---

## 3. (c) `visual_qa` 能验它吗 —— **不能（已实测）**

### 3.1 像素仪器本身是可用的

```
[still] bundle 1.4s
[still] frame 30 -> E:\Minimax-H3\out\p43_probe\still_check\f00030.png
```
`visual_qa.py` 确实读像素（PIL + numpy，`load()` `:434`、laplacian、signature 等）。
⚠️ 注意 `studio/public/jobs/showcase_demo.json` 是**过期 staging 副本**（仍带 P11 已删的 `ease`），
渲染会抛 `Unrecognized key: "ease"`；tracked 图在 `pipeline/examples/`。

### 3.2 ⚠️ 但「有结构 / 有内容」这类判据是**误报机** —— 实测

同一套候选像素统计，两帧对比：

```
MissingScene(data-plane)   ink_frac=0.0026 lap_var=    35.9 mean|grad|=0.351 p99|grad|=0.500
real kpi-hero frame        ink_frac=0.0211 lap_var=    18.4 mean|grad|=0.533 p99|grad|=0.500
```

**`MissingScene`（就是那个写着 "not implemented in P4" 的占位帧）
边缘能量比真帧还高**（35.9 > 18.4）——
因为它画的是 48px 大字 + 22px 副标题，**对比极强**。
⇒ 任何「有边缘 / 有墨 / 非空白」的判据**都会放过 `MissingScene` 本身**。
这正是 P34 的教训（造了一台误报机）。

### 3.3 而且**没有可校准的正解**

- 可用的判据必须是「与已知正确的参照帧比对」；
- 而实测 **tracked graph 里 0 帧 `data-plane-3d`**，全仓无参照帧、无探针、无 VLM 判据；
- P37 实测参考片**只给到布局层面**，给不出这个场景该长什么样。

⇒ (c) **判定：无法验收。** 而**无法被验收的东西不该建**（工单 `:101`）。

---

## 4. ⚠️ 工单未预见的新阻断：**建它会让 9 条守卫转红**

工单 `:43-49` 认为「引入 `@remotion/three` 即可」。**这一点从未被实测。**
我做了实测：**一行改动、零新依赖**，把该类型挂到已有渲染器 `DataColumns` 上：

```diff
   outro: Outro,
+  'data-plane-3d': DataColumns,
 };
```

⇒ **9 failed, 61 passed**（原始输出见附录 A）：

| 转红的守卫 | 归属 | 为什么红 |
|---|---|---|
| `test_no_h3_renderer_exists_in_the_render_source` | **P17** | `data-plane-3d ∈ GENERATIVE_TYPES`，断言 `not (registered & GENERATIVE_TYPES)` |
| `test_every_generative_type_is_gated_not_only_video` | P15 | 同上，生成式集合被破坏 |
| `test_the_failure_direction_names_the_offending_scene_and_type` | **P21** | 见 §4.1 |
| `test_every_scene_type_is_rendered_or_recorded_as_unrendered` | **P26** | 该类型已不在「未渲染」表里 |
| `test_the_unrendered_set_is_the_two_generative_types_not_nine` | **P12** | 未渲染集合不再是那两个 |
| `test_every_renderer_is_used_by_a_tracked_graph` | **P29** | 见 §4.2 |
| `test_the_guard_is_red_when_a_graph_stops_using_a_renderer` | **P29** | 语料里没人用它 |
| `test_the_registry_names_real_collections_with_computable_sizes` | **P40** | 注册表规模变了 |
| `test_every_cited_collection_size_equals_the_computed_size` | **P40** | `visual_qa.py` 注释里的 22/20 漂移成 22/21 |

### 4.1 ⚠️ **硬要求 ②「让 P21 转绿」在数学上不可能 —— 它只能变红**

P21 的失败方向测试**拿 `data-plane-3d` 当「没有渲染器的类型」的样本**，并断言 FAIL：

```python
# tests/test_p21_props_path_gates_the_deliverable.py:183-192
"""...the fixture's `outro` now has a renderer, so it was swapped for
`data-plane-3d`, which is still left to `MissingScene`."""
doc['scenes'].append({'id': 'g_gap', 'type': 'data-plane-3d', 'durationInFrames': 60})
...
assert _verdict_for(report, RULE) == vqa.FAIL, report
```

`graph_scene_renderable` **今天就是绿的**，因为**没有任何 graph 用这个类型**
（§2.2 实测）。给它渲染器，这条测试立刻红。
⇒ 「类型不再落空」在这里**不是一个能转绿的目标，而是一次回归**。

### 4.2 P29 的孤儿渲染器守卫：**渲染器必须被 graph 用到**

```python
# tests/test_p29_renderers_are_used_by_a_graph.py:253-260
'the these renderers are reachable in SCENE_RENDERERS but NO tracked graph asks for them: ...'
'A renderer nothing renders is not a capability. Either add a scene that uses it, or ...'
```

而 P29 自己的 docstring 写明，它当年修的就是**同一个病**：

> `This was B-4. It was green-with-a-hole before P29: the seven keys were real
> components with single-frame evidence and no graph anywhere named them, so
> nothing in the pipeline could ever put them on a screen.`

⇒ 建一个没人用的 `data-plane-3d` 渲染器，**就是复刻账本里的 `LOCKED_SCENE_TYPES`
（「放了几个月没人读」）**。
P29 当时的解法是**补一个用到它的 graph** ——
而补 graph 需要内容，**内容需要 §1 里那个不存在的依据**。**死锁。**

---

## 5. 依赖：`@remotion/three` —— **未引入，且本仓早已裁定「暂缓」**

**我没有跑 `pnpm add`。** 判 C 就不该为一个不建的东西改 `package.json`。

⚠️ **这不是我的判断，本仓 2026-09-30 就已经裁定过了**
（`docs/REMOTION_MOTION_UPGRADE_20260930.md:32`，标题「暂缓（附理由）」）：

> `@remotion/three`（WebGL 3D）——headless 需 `--gl=angle`，
> 已知 angle 内存泄漏需分段渲染；**纯数据视频 3D 张力/成本比低**。
> **真 3D 需求时** `<ThreeCanvas>` + 5090 可行

⇒ **总计划 `:205` 说「data-plane 可以用 `@remotion/three`」，是授权边界，不是开工令。**
它授权的是「**有真 3D 需求时**」—— 而「真 3D 需求」正是本项缺的东西。
在无依据的情况下引入 WebGL 依赖，会同时背上 `--gl=angle` 的
内存泄漏与分段渲染成本，换一个实测「张力/成本比低」的画面。

**版本怎么定（若将来解封）**：必须与 `remotion` **同 minor**。
本仓所有 Remotion 包都钉死在 **`4.0.529`**（`package.json` 实测），
所以应是 `@remotion/three@4.0.529` + 配套 `three`，**不用 caret** ——
本仓对 Remotion 一律精确钉版本，只有 `react`/`zod`/`tsx` 等用 `^`。

---

## 6. 裁定

| 选项 | 判定 |
|---|---|
| **A（照做）** | ❌ 无依据即编造（工单 `:91` 明禁） |
| **B（等引擎）** | ❌ 引擎**已到位授权**，卡的不是引擎，是**依据**；且 B 会误判为「装个包就能做」 |
| **C（不做，记录）** | ✅ **采纳** |

**解封条件（可测、有据后再开本项）**：
1. 有人写下 `data-plane-3d` 的**视觉规格**（哪些图元、哪些轴、值怎么编码）；
2. 据此定下 `content` 的键（并同步 JSON Schema + zod 两面）；
3. 随之**必带一个 tracked graph 用到它**（P29），否则不得注册渲染器；
4. 此时才引入 `@remotion/three@4.0.529` 并处理 `--gl=angle`。

**在此之前，`UNRENDERED_SCENE_TYPES` 是正确的记录，不是欠账。**
它已被 **9 条守卫**（§4）看着——实测每一条都会在有人偷建时转红，
本项**不需要再加守卫**：再加一条只会成为第十一个「声明了但没人读」。

---

## 附录 A —— 实测原始输出

### A.1 基线（全量，`--ignore=test_take_selection_behaviour.py`）

```
1 failed, 718 passed, 4 skipped in 402.20s (0:06:42)
FAILED test_markdown_text_is_intact.py::test_no_tracked_markdown_contains_a_replacement_character
```

⚠️ **这 1 条失败不是本项造成的**，是 HEAD 里的既有损坏，已实测确认在**已提交的 blob** 中：

```
$ git show HEAD:docs/WORKORDER_P42_B2_B3_VERDICTS.md | sed -n '37p' | od -c
0000000   #   #   #       B   -   2 357 274 232 346 234 253 345 270 247
...
0000120 277 275 357 277 275 346 230 257 347 211 207 345 255 220 347 274
                      ↑↑↑ EF BF BD = U+FFFD（三个连续的替换字符）
```

工单写的基线是「上次 719 passed, 4 skipped」，与实测差 1 —— 差额就是这条 U+FFFD。
**它需要指挥窗口裁决**（改文档还是改守卫），本项未动。

### A.2 变异 M1：注册渲染器（**一行、零依赖**）

```
FAILED ::test_the_failure_direction_names_the_offending_scene_and_type - Asse...
FAILED ::test_every_scene_type_is_rendered_or_recorded_as_unrendered - Assert...
FAILED ::test_every_generative_type_is_gated_not_only_video - AssertionError:...
FAILED ::test_no_h3_renderer_exists_in_the_render_source - AssertionError: SC...
FAILED ::test_the_unrendered_set_is_the_two_generative_types_not_nine - Asse...
FAILED ::test_every_renderer_is_used_by_a_tracked_graph - AssertionError: the...
FAILED ::test_the_guard_is_red_when_a_graph_stops_using_a_renderer - Assertio...
FAILED ::test_the_registry_names_real_collections_with_computable_sizes - As...
FAILED ::test_every_cited_collection_size_equals_the_computed_size - Assertio...
9 failed, 61 passed in 33.34s
```

红在**正确的理由上**（不是 `NameError`/`SyntaxError`）：
pytest 正常收集 70 条、正常执行，红的是断言本身，例如

```
E  AssertionError: studio/scripts/visual_qa.py: cites "`SceneType` declares 22 values and
E  `SCENE_RENDERERS` names 20 of them, so" -- SCENE_RENDERERS has 21, not 20.
```

### A.3 复原验证（**证明变异可逆、守卫是活的**）

同一组 7 个文件在复原后：

```
......................................................................   [100%]
70 passed in 33.40s
```

⇒ 9 条红**由本变异造成**（非既有损坏、非死分支）。

### A.4 像素测量（§3.2）

```
MissingScene(data-plane)   ink_frac=0.0026 lap_var=    35.9 mean|grad|=0.351 p99|grad|=0.500
real kpi-hero frame        ink_frac=0.0211 lap_var=    18.4 mean|grad|=0.533 p99|grad|=0.500
```

全帧 97.89% 的像素落在中位亮度 ±24（`PALETTE_TOL`）带内，
与 `visual_qa.py` 记录的 97.8% 一致 —— 只有 2.11% 的像素携带信号。

### A.5 sha256 收尾比对

| 文件 | 开工 | 收尾 | |
|---|---|---|---|
| `FinanceShowcaseWide.tsx` | `c56e836d…3fd88` | `c56e836d…3fd88` | ✅ 一致 |
| `visual_qa.py` | `1674d5e7…b1f4d4` | 未改动 | ✅ |

`FinanceShowcaseWide.tsx` 全文件为**纯 CRLF**（292 CRLF / 0 bare LF）；
变异期间实测 293/0，**复原后 292/0，字节级一致**（用 `read_bytes`/`write_bytes` 快照复原，
未使用 `git checkout --`）。

---

## 附录 B —— 本项**没有**做的事（以及为什么）

| 没做 | 原因 |
|---|---|
| 引入 `@remotion/three` | 判 C；且本仓 `:32` 已裁定暂缓 |
| 写渲染器组件 | 无视觉依据 = 编造（工单 `:91`） |
| 加新守卫 | 9 条已在看着；第十条会成为「声明了但没人读」 |
| 改 `GENERATIVE_SCENE_TYPES` | 工单明禁 |
| 改 `UNRENDERED_SCENE_TYPES` 的措辞 | P17 守卫对该文件的引擎名有约束 |
| 修 `WORKORDER_P42_B2_B3_VERDICTS.md` 的 U+FFFD | 不在本项授权内，**留指挥窗口裁决** |
| 做 `video` | 不在授权范围，且 `studio/public` 零个视频文件 |