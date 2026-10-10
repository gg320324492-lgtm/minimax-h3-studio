# P12.2 — ScenePlanner → Storyboard → showcase_v1.json：**裁定不建（C）**，以及三个答案

> 执行 agent 交付。工单 `docs/WORKORDER_P38_SCENE_PLANNER.md`，基线 `a9038d9`。
> 本文件是**测量记录**，不是放行/退回裁定。
> **本项没有实现 ScenePlanner，一行生产代码都没有改。**
> 交付物是 `tests/test_p12_2_scene_planner_verdict.py`（13 条守卫）——**守卫的对象
> 是本裁定的前提**，不是某个规划器。

---

## 摘要（先看这一段）

1. **(a) 场景类型不该由 Planner 挑**：brief 里的场景**已经带类型**，
   `generate_graph` 逐字节原样带进图谱（`is` 判定为 `True`）。
   而"挑不出会渲染成 `MissingScene` 的类型"这条规则**已经存在且已经会红** ——
   P21 的 `rule_graph_scene_renderable`，本项端到端跑过。
2. **(b) 时长判据不存在，且我能证明不存在**：唯一被提名的仪器
   `beat_aligned_durations` **对任何输入都返回空**（构造性证明 + 2 万次随机图谱
   穷举 + 1 帧/4999 帧极端输入）。而三张交付图谱在**渲染器真正使用的时间线**上
   **漂移 12.9–13.9 帧**。仪器说"没问题"，片子不在这条线上。
3. **(c) Storyboard 是恒等映射**：实测 `generated.graph['scenes'] IS brief['scenes']`。
   它要的输入就是它的输出。
4. ⚠️ **工单的两处前提已过期**（详见第六节）：「9 种渲染不出来」**实测是 2 种**；
   `beat_snap` 在渲染路径上**是关的**。

---

## 一、(a) 场景类型该从哪来

### 1.1 选择规则：**已经存在，且已经会红**

工单问的是"给出你的选择规则，并说明如何避开那 9 种"。实测答案是：
**这条规则不需要新写，P21 已经写了，而且它会红。**

`studio/scripts/visual_qa.py:1038` 的 `rule_graph_scene_renderable` 读的
就是渲染器**实际 dispatch 的那张表**（`SCENE_RENDERERS`，从
`FinanceShowcaseWide.tsx` 现场解析）。端到端跑一遍：

```
$ py -3.12 studio/scripts/visual_qa.py --props <generate_graph 产出的 video 图谱>
  [FAIL        ] graph_scene_renderable  value=1
                 1 scene(s), 20 of 22 declared scene types have a renderer;
                 1 scene(s) have NO renderer and will render the MissingScene
                 placeholder ("not implemented in P4"): scenes[0]=video
```

**⇒ Planner 若再实现一次类型筛选，那就是同一个事实上的第二道闸** ——
这正是 P21 那条疤（「一个常数两处调用，只有一处读它」）换个说法重演一遍。
工单第二节明确要求"必须与 P36 的生成器协作而不是各写一套"；
这条要求的**最强形式**是：**这道闸已经在了，不要再写一道**。

### 1.2 ⚠️ 「9 种」已过期：**实测 2 种**

工单（及 `visual_qa.py:1051-1054` 的 docstring）都写「22 声明 / 13 渲染 / 9 落空」。
实测：

| 项 | 工单/旧文档 | **实测** |
|---|---|---|
| `SceneType` 声明 | 22 | **22** |
| `SCENE_RENDERERS` 注册 | 13 | **20** |
| `UNRENDERED_SCENE_TYPES` | 9 | **2**：`video`、`data-plane-3d` |

**原因**：`a7f02b8`（P29）验收了七个新渲染器
（`browser-window`/`stat-card`/`card-grid`/`data-table`/`quote`/`logo`/`outro`）。
⇒ **按「避开那 9 种」写的 Planner 会去避开 7 种现在渲染正常的类型，
而真正渲染不出来的那 2 种一个都没提到。**

**⇒ 唯一经得起时间的规则是集合差，不是名单**：
`renderable = SceneType ∩ SCENE_RENDERERS`。
守卫 `test_the_unrendered_set_is_the_two_generative_types_not_nine` 钉住这个数字，
它一变动就红，并要求**重新测量而不是放宽断言**。

### 1.3 更根本的：**没有可供规划的「意图」**

即使要挑类型，也没有东西可供挑选：`generate_graph(brief)` 收到的 brief
**其场景已带类型**，函数体（`style_bible.py:157-198`）对 `scenes` 的处理只有一行
`'scenes': scenes`。实测：

```
F1 is-identity  : True
F1 deep-equal  : True
F1 accepts video: video
```

⇒ **P36 的生成器规划的是景深，不是场景。**
Planner 要重新决定的事，brief 已经决定了。

---

## 二、(b) 时长与节奏由什么决定

### 2.1 结论：**判据不存在**，而且**我能证明它不存在**

工单问"你的规则基于什么？定不出判据就如实说"。**定不出，且下面三条说明连尝试都是假的。**

### 2.2 证据一：唯一被提名的仪器**是恒等式**

`docs/DIRECTOR_SCOPE_VERDICT.md` §6.2 明确把
`scene_graph.py::beat_aligned_durations` 指给下一个执行 agent 当"时长判据"，
并写「**时长是 beat 对齐的，不是自由值**」。

**实测：这个函数对任何输入都返回 `[]`。**

- **构造性证明**：`beat_aligned_durations`（`scene_graph.py:565-593`）遍历
  `sc.resolve(beat_snap=True)`，而 `resolve` 在 beat 模式下把每个 start 置为
  `int(round(beat_cursor * beat_frames))`。然后它拿这个 start 去量它**离
  `beat_cursor * beat_frames` 有多远**。**它把一个四舍五入过的值，和它被四舍五入
  的那个东西比。** 由 `round` 的定义，差值**恒 ≤ 0.5 帧**，而阈值正是 `> 0.5`。
- **穷举**：20000 张随机图谱（fps 24–60 × bpm 40–220 × 1–12 场景 × 1–900 帧），
  非空结果 **0 次**。
- **极端输入**：1 帧 / 3 帧 / 7 帧 / 997 帧 / 4999 帧 / 13 帧 —— 任何带阈值的
  判据都会在这里报出东西。它返回 `[]`。

> ⚠️ **本项不修它**（工单第四节：不改 `scene_graph.py`，**它是下游**）。
> 但**必须点名**：它当前是本仓库唯一一个被文档指认为"判据"、
> 而实测**结构上无法说出"不"**的函数。它的两个"消费者"里，
> `tests/test_showcase_schema_parity.py:195` 只断言它**与 resolver 一致** ——
> 而两者同源，所以一致是必然的，**不是证据**。

### 2.3 证据二：漂移是**真的**，而且**没人测**

`FinanceShowcaseWide.tsx:201` 用 `resolveScenes(doc, false)` ——
**`beat_snap` 在渲染路径上是关的**（`test_beat_grid.py:236-254` 钉住这一点）。
所以片子真正被切出来的是**朴素的背靠背时间线**，其 start 落在哪由作者写的时长决定。

实测三张交付图谱在**已交付时间线**上的漂移：

| 图谱 | 漂移 > 0.5 帧的场景 | 最坏漂移 | `beat_aligned_durations` 的说法 |
|---|---|---|---|
| `showcase_demo.json` | **3 / 4** | **13.852 帧** | 0 problems |
| `charts_demo.json` | **8 / 10** | **13.944 帧** | 0 problems |
| `p29_new_renderer_showcase.json` | **6 / 7** | **12.857 帧** | 0 problems |

**⇒ 仪器说片子在 beat 上，片子不在。这两条合起来是一个测量，不是两条。**

### 2.4 证据三：**没有一条规则可以照抄**

| 图谱 | 时长 | 它遵循的规则 |
|---|---|---|
| `showcase_demo` | 229 / 229 / 114 / 229 | **旧 bpm 126 的整拍**（`round(8×28.5714)=229`、`round(4×28.5714)=114`）—— `41947f6` 把声明速度改成 128.998 时**没有重算时长** |
| `charts_demo` | 150 ×9 + 600 | **10 帧的整数倍**（= 60fps 下 1/6 秒） |
| `p29_...` | 150/120/210/180/160/100/200 | **同样是 10 帧的整数倍** |

实测平均离格距离：

```
showcase_demo : 当前bpm离格 4.90  |  bpm126离格 0.39  | 10帧离格 1.75
charts_demo   : 当前bpm离格 10.81 |  bpm126离格 6.43  | 10帧离格 0.00
p29_...       : 当前bpm离格 8.16  |  bpm126离格 8.16  | 10帧离格 0.00
```

⇒ 语料同时展示了**整拍规则**、**十分之一秒规则**、和**一张仍按旧速度写的图**。
**没有任何单一惯例可推导**，挑一条就是**关于已交付帧的决策**，不是从数据里的推论。

### 2.5 关于工单给的 120.19 BPM

工单把 P37 实测的 `beat ≈ 120.19 BPM` 作为参考。
**实测：它不是本仓库可以规划的数。**
`docs/P37_REFERENCE_REANALYSIS.md:84` 自己写着：

> 实测 BPM ≈ 120.19 …… ⚠️ **与 P9 的 128.998 是两个不同的音轨，不可混谈**

⇒ 那是**参考片子**的音轨。交付图谱声明的是从**本机那条真实音轨**
（`studio/public/audio/bgm_beats.json`）拟合出来的 **128.998**。
**候选规则于是只剩三条，全部走不通**：120.19（另一首歌）、
128.998（对的歌，但 `beat_snap` 关着、无人查询）、126（两张图谱的作者当时写的）。
守卫 `test_the_tempo_nominated_by_the_reference_film_is_a_different_track` 钉住这一点。

---

## 三、(c) Storyboard 是必需品还是空转

### 3.1 结论：**空转**，且是**可测量的恒等**

```
generate_graph(brief).graph['scenes'] IS brief['scenes']   →  True
```

Storyboard 若插在这两端之间，**它拿到的就是它被要求输出的东西**。
它下面没有可规划的层，上面没有想要它输出的字段。

### 3.2 每个字段会怎样（工单点名的病灶）

工单要求"storyboard 的每个字段都要有消费方"。按本项的裁定，
**Storyboard 能携带的每个字段只有两种命运**：

| 命运 | 后果 | 本项目实例 |
|---|---|---|
| 原样透传 | **恒等映射 = 一层装饰** | P36 记的 `tuple(str(x) for x in strings)` |
| 新造一个字段 | **哑声明**（"声明了但没人用"） | `chartLanguage`、`audioLanguage`、`LOCKED_SCENE_TYPES`（P29 实测零生产读点）、`cameraLanguage.durationSeconds` |

⇒ **在当前契约下，Storyboard 的每个字段都只能落在这两栏之一。**

### 3.3 生成侧现在做的事，是 brief 的一个细节

顺带实测：`generate_graph` 唯一发出的键 `depthCue`，
**只在 brief 里有 `browser-stack` 且带 `windows` 时才发**——
实测 `plan_depth(theme, 0).ramp` 为 `()`，`plan_depth(theme, 6).ramp` 长度 5。
**它的产出是 brief 一个细节的函数，不是规划的函数。**

---

## 四、为什么不建（裁定依据汇总）

| 层 | 结论 | 实测依据 |
|---|---|---|
| 场景类型选择 | **不建** | 闸已存在且会红（P21）；brief 已带类型；`generate_graph` 原样透传 |
| 时长/节奏判据 | **不建** | 被提名的仪器是恒等式；真实漂移 12.9–13.9 帧；三图三规则 |
| Storyboard | **不建** | 实测恒等映射；每个字段只能透传或变哑声明 |

**⇒ 「从意图到一张可被校验的图谱」这一段缺的不是一个 Planner，
而是 Planner 之上的那一层「意图」。** 本仓库没有它：
`docs/DIRECTOR_SCOPE_VERDICT.md` §2.1 实测 Brief 段零实现、零消费方。
**先有可测量的意图来源，Planner 才有对象。**

**这一项与 P12.1 不矛盾**：P36 建的是 `Brief → StyleBible`（其输入是 brief，
输出是图谱上唯一有实测推导的键）。本项问的是**在 brief 之前**那一段 ——
实测那里什么都没有。

---

## 五、守卫（`tests/test_p12_2_scene_planner_verdict.py`，13 条）

**守卫的对象是本裁定的前提。** 只写在文档里的裁定会静默腐烂：
一旦有人加了意图来源、修好了节拍仪器、或让 `generate_graph` 开始碰场景类型，
本项拒绝的理由就没了，而**没有人会收到通知**。所以每条前提都对着真实模块断言，
前提不成立的那天它自己会红。

| 守卫 | 钉住什么 |
|---|---|
| `test_generate_graph_passes_the_briefs_scenes_through_unchanged` | 等值 + **同一性**（`is`）。后者才是 (c) 的根据 |
| `test_generate_graph_places_no_restraint_on_the_scene_type` | brief 要 `video`，产物就是 `video`，且能过 `load()` |
| `test_the_unrenderable_type_is_gated_downstream_and_the_gate_fires` | P21 闸对 `video` 报 **FAIL** 并点名 `scenes[0]`；对 `bar-chart` 报 **PASS**（双向） |
| `test_the_unrendered_set_is_the_two_generative_types_not_nine` | 「9 种」已过期；**实测 2 种**，且要求重新测量而非放宽 |
| `test_the_nominated_duration_authority_is_a_tautology` | **1 帧与 4999 帧并排，仍返回 `[]`** |
| `test_the_delivered_graphs_drift_on_the_timeline_the_renderer_ships` | 三图漂移 > 1 帧，**且**被提名仪器报 0 |
| `test_the_three_delivered_graphs_follow_three_different_duration_rules` | 229 = 126 bpm 的整拍；两张图全在 10 帧格上 |
| `test_the_tempo_nominated_by_the_reference_film_is_a_different_track` | 120.19 是**另一条音轨**（P37 自述），不得进交付图谱 |
| `test_there_is_no_storyboard_and_the_chain_has_no_hole_for_one` | `depthCue` 的产出条件，并比对 plan 与文档里的值 |
| `test_the_graph_the_generator_produces_really_validates` | **双向**：干净图过 `load()`，脏图被 `ShowcaseError` 拒 |
| `test_the_delivered_graphs_are_all_still_loadable` | 语料没有腐烂 |
| `test_the_helpers_can_say_no` | 两个 helper 必须能说"不" |
| `test_the_renderers_are_the_real_ones_and_the_template_is_the_source` | 解析器钉在真实文件上（否则红在错误的理由上） |

**导入而非重写**：`rendered_scene_types` / `unrendered_scene_types` 从
`test_p26_scene_type_coverage` **导入**，与 P29 同一做法 ——
避免 P21 那条疤（本文件再写一份"哪些类型能渲染"，就是第二个只会写不会读的调用点）。

---

## 六、与工单前提的两处出入（如实记录）

| 工单/旧文档 | 实测 | 出处 |
|---|---|---|
| 「9 种场景类型渲染不出来」 | **2 种**（`video`、`data-plane-3d`） | P29 `a7f02b8` 验收了 7 个渲染器 |
| 「时长是 beat 对齐的，不是自由值」（`DIRECTOR_SCOPE_VERDICT.md` §6.2） | **没有任何东西在保证**；`beat_aligned_durations` 是恒等式 | §2.2 / §2.3 |
| 「参考片 P37 实测 beat ≈ 120.19 BPM」可用作依据 | **另一条音轨**，P37 自己写着"不可混谈" | `P37_REFERENCE_REANALYSIS.md:84` |
| `visual_qa.py:1051-1054` docstring 仍写「13 rendered / 9 in between」 | 已过期（20 / 2） | ⚠️ **本项未修**（不在授权内，且改它要先重测 P21 的期望值） |

**本项未修的**：`scene_graph.beat_aligned_durations` 的恒等式。
**不在授权内**（工单第四节：`scene_graph.py` 是下游，本项只该产出它能接受的图谱）。
已由 `test_the_nominated_duration_authority_is_a_tautology` **钉成已知事实**：
一旦有人真的修好它，这条会红，并要求**重新裁定 (b)**。

---

## 七、变异记录（`-rf` 原始输出）

四次毒变异，每次**先证明落地**（本项目发生过两次"变异没落地却读了结果"），
每次从快照复原并核对 sha256。

### 变异 A：把交付图谱的速度改成参考片的 120.19（另一条音轨）

落地断言：`p.write_bytes(out)` 后重新读盘确认毒行存在 →
`MUTATION D LANDED; bytes 26175 -> 26178 (delta +3)`，
`verify 126 still present elsewhere: True`

```
>       assert declared == {'showcase_demo.json': 128.998,
                            'charts_demo.json': 128.998,
                            'p29_new_renderer_showcase.json': 120.19}, (
E       AssertionError: the delivered graphs declare {'showcase_demo.json': 128.998, 'charts_demo.json': 128.998, 'p29_new_renderer_showcase.json': 126}. ...
E       assert {'showcase_de...se.json': 126} == {'showcase_demo.json': 128.998, ..., 'p29_new_renderer_showcase.json': 120.19}
E          Differing items:
E          {'p29_new_renderer_showcase.json': 126} != {'p29_new_renderer_showcase.json': 120.19}
E:\Minimax-H3\tests\test_p12_2_scene_planner_verdict.py:374: AssertionError
=========================== short test summary info ===========================
FAILED ::test_the_tempo_nominated_by_the_reference_film_is_a_different_track
1 failed, 12 passed in 0.18s
```

**红的理由已核对**：红在**速度相等性**上，且消息里两个值都打印出来了 ——
**对的理由**。

> ⚠️ **变异 A 的第一版存活了，这是本项最有价值的一次记录。**
> 第一版把断言写成 `set(declared) <= {126, 128.998}`（**子集**），
> 于是把**右边的上界**放宽到 `{126, 120.19, 128.998` —— 守卫**全绿**。
> 原因很直白：**一个子集断言看不见自己的上界被放宽**，
> 因为"已满足的子集"放进"更大的超集"里**永远还满足**。
> 改成**等值**（`declared == {...}`）后同一变异立刻红。
> **是毒变异发现的这个洞，不是读代码发现的。**

### 变异 B：让生成器的产物过不了 `scene_graph.py` 校验

落地断言：`MUTATION B LANDED; bytes 26175 -> 26280 (delta +105)`
（把待校验图谱的 `durationInFrames` 置 0 —— schema 的 `minimum: 1` 会拒）

```
E           return scene_graph.load(path)
E               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       pipeline.scene_graph.ShowcaseError: scenes[0].durationInFrames: must be >= 1, got 0
E       pipeline/scene_graph.py:600: ShowcaseError
=========================== short test summary info ===========================
FAILED ::test_the_graph_the_generator_produces_really_validates - pipeline.sc...
1 failed, 12 passed in 0.18s
```

**红的理由已核对**：红在**真的 `scene_graph.load()` 调用**上，
异常来自 `scene_graph.py:600` 的 `raise ShowcaseError` ——
**不是探针自己的异常变成了判定**（P31/P34/P36 各栽过一次）。

### 变异 C：让判据永远判"通过"

落地断言：`MUTATION C LANDED; bytes 26175 -> 26150 (delta -25)`，
并确认 `return sorted({t for t in scene_types if t not in rendered})` 已不在盘上

```
    rendered = {'bar-chart', 'quote', 'logo'}
    assert unrendered_gaps(['bar-chart', 'quote', 'logo'], rendered) == []
>   assert unrendered_gaps(['bar-chart', 'video'], rendered) == ['video']
E       AssertionError: assert [] == ['video']
E         Right contains one more item: 'video'
E:\Minimax-H3\tests\test_p12_2_scene_planner_verdict.py:474: AssertionError
=========================== short test summary info ===========================
FAILED ::test_p12_2_scene_planner_verdict.py::test_the_helpers_can_say_no - AssertionError: assert [] == ['video']
1 failed, 12 passed in 0.17s
```

**红的理由已核对**：红在**判别测试**（问 helper 一个有洞的输入）上，
而不是红在某个"应该红"的真实图谱上 —— **对的理由**。

### 变异 D（工单点名的第一条）：让 Planner 挑一个 `UNRENDERED_SCENE_TYPES` 里的类型

落地断言：`MUTATION D (v2) LANDED; bytes 26175 -> 26254 (delta +79)`，
**并单独证明它不是死分支**：

```
brief_with('video') now yields: data-plane-3d
```

```
E           assert generated.emitted_keys == {'depthCue'}, (
E       AssertionError: the generator emits [] now for a brief that P12.1 measured as emitting depthCue. ...
E       assert frozenset() == {'depthCue'}
E:\Minimax-H3\tests\test_p12_2_scene_planner_verdict.py:415: AssertionError
=========================== short test summary info ===========================
FAILED ::test_p12_2_scene_planner_verdict.py::test_generate_graph_places_no_restraint_on_the_scene_type - Assertion...
FAILED ::test_p12_2_scene_planner_verdict.py::test_there_is_no_storyboard_and_the_chain_has_no_hole_for_one - Ass...
2 failed, 11 passed in 0.19s
```

> ⚠️ **变异 D 的第一版同样存活了，而且是本项目记录在案的同一个坑。**
> 第一版把 `scene_type = 'data-plane-3d'` 追加在
> `scene: dict = {...'type': scene_type...}` **之后** ——
> 字典早就用旧值建好了，那一行是**死分支**，
> 于是 `13 passed`。**落盘了，行为没变**，正是 P36 的教训。
> 第二版把覆盖**挪到建字典之前**，并额外跑了一次
> `brief_with('video')` 打印实际产出来证明差异真实存在。

**存活判定**：四次变异，两次第一版存活（A 的子集断言、D 的死分支），
两次均已修复并复跑确认红。**最终无变异存活。**

### 复原核对（四次之后）

```
26506baf6472bb873998064c994adcae6bd99e601249317c79e107b47619d349 *tests/test_p12_2_scene_planner_verdict.py
ac3b4ad198c0ed2f02c3962f3d1232c069236a9191d89c4c830c4c7a8dd8ac39 *pipeline/director/style_bible.py
7ba78bdc14a64900c5c422195692f9ebefa25adf0a7d38cf2bf96ee4d7d843df *pipeline/scene_graph.py
9348e8651e7ec668823696b56c3a31f14baa6f92033bf1f7dd406d7c2660a5a3 *studio/src/templates/finance-showcase/design/styleBible.tsx
```

**工单指定的三个 sha256 与开工时逐字节相同。**
守卫文件 sha256 与四次变异前取的快照相同。

### 测试数字

| 时点 | 结果 |
|---|---|
| 实测基线（改代码前） | **`1 failed, 664 passed, 4 skipped in 447.89s`** |
| 交付后 | **`1 failed, 680 passed, 4 skipped in 404.96s`**（+16 = 本项新增 13 + 前次引用修复） |

⚠️ 那 1 条失败是**既有的**，与本项无关：
`test_p4_9_ledger_numbers_resolve` 因 `studio/src/water-renewal/` 里的 `330`
而红 —— 那是**另一条线**的未提交内容，工单第二节明令不得为了让它变绿而改守卫。

---

## 八、P40 接手复核（独立重测，不采信上文的结论句）

> 来源：`docs/WORKORDER_P40_FINISH_P38_P39.md`。前一个 Claude 进程结束时有 agent 还在跑，
> 本节的每一项都是**重新测出来的**，不是抄第七节的表。

### 8.1 三个答案独立复现

| 断言 | 上文自述 | **P40 独立实测** |
|---|---|---|
| (b) `beat_aligned_durations` 对任何输入返回空 | 2 万张 + 极端输入 | **复现**：随机 20000 张非空 0 次；`[1]/[3]/[7]/[997]/[4999]/[13]/[1,4999]` 全 `[]`；**45000 个 beat_snap=True 解出的场景，最坏 beat 距离恰为 0.500**（阈值是 `> 0.5`，所以永不过线 —— 这就是那个恒等式） |
| (c) `generate_graph(brief).graph['scenes'] IS brief['scenes']` | True | **复现**：`is` → True，`==` → True |
| (a) `rule_graph_scene_renderable` 已存在且会红 | FAIL on `video` | **复现**：`video` → `verdict='FAIL'`, `gaps=[{'index':0,'type':'video'}]`；`bar-chart` → `PASS`（双向） |

### 8.2 「9 种 → 2 种」独立数出来的数字

用**自己写的解析**（不复用本仓任何 test 的解析器）读取两个源文件：

```
SceneType 声明          : 22
SCENE_RENDERERS 键      : 20
UNRENDERED_SCENE_TYPES  : 2  ['data-plane-3d', 'video']
SceneType - rendered    : ['data-plane-3d', 'video']
declared 落空（两表都没有）: []
两表交集               : []
```

**⇒ 上文的纠正属实：「9」是过期数字，实测 2。** 唯一经得起时间的规则是集合差
`SceneType \ SCENE_RENDERERS`。

### 8.3 守卫变异（上文可能没跑完）

**变异：把 `UNRENDERED_SCENE_TYPES` 减到一个类型（删掉 `data-plane-3d`）。**

落地证明：`bytes 14239 -> 14128 (delta -111)`，删后重新读盘确认只剩 `video:` 一条。

```
FAILED ::test_the_unrendered_set_is_the_two_generative_types_not_nine
E       AssertionError: the unrendered set is ['video']. ...
E       assert {'video'} == {'data-plane-3d', 'video'}
E          Extra items in the right set: 'data-plane-3d'
E:\Minimax-H3\tests\test_p12_2_scene_planner_verdict.py:231: AssertionError
=========================== short test summary info ===========================
1 failed, 12 passed in 0.26s
```

**红的理由已核对**：红在**集合相等性**断言上，两条消息都打印了 —— **对的理由**，非异常。
**复原后 sha256 与快照逐字节相同**（`c56e836d...`）。

### 8.4 `visual_qa.py:1052` 过期数字已订正（本项唯一授权改的源码）

原文（`visual_qa.py:1051-1054`）：

> `SceneType` declares 22 values, `SCENE_RENDERERS` names 13, and the 9 in
> between are `video`, `browser-window`, ..., `outro`.

**这正是 P40 工单里那个错数字的来源**（docstring → 指挥窗口工单 → agent）。
**已改为**：`SceneType` declares 22 values and `SCENE_RENDERERS` names 20 of them,
so the 2 in between are `video` and `data-plane-3d`.
（同段落的「Sixteen of those twenty / the four that do not」也一并订正为 20/2。）

**⚠️ 改法服从"行号即引用"的纪律**：本仓 `test_line_refs_land_on_code.py` 要求
`visual_qa.py:1393` 落在代码行上。**改 docstring 若改变文件行数，会连带打断一条
无关的引用**（第一次改就撞了：`--props` 从 1393 漂到 1403，`test_p13_scene_cache_facts.py`
立刻红）。**最终把替换控制成 5 行换 5 行、文件仍是 1537 行**，`--props` 仍在 1393。

### 8.5 第 3 件事：给「docstring 里的集合大小」真的上了守卫

**新守卫**：`tests/test_p40_docstring_counts_match_code.py`（4 条测试）。

**它守卫的失效正是本项暴露的**：一段 docstring 写「names 13」，而代码是 20 ——
docstring 成了过期数字的来源，被指挥窗口照抄进工单，工单又把它传给下一个 agent。

**判据（窄而有意义，不是全仓所有数字）**：

- **闭集**：只有三个集合名（`SceneType` / `SCENE_RENDERERS` / `UNRENDERED_SCENE_TYPES`）
  出现在句子里并用计数动词给出大小时，才判定。时间戳、行号、`18.7s`、`0.278` 一律不碰 ——
  那正是工单警告的"海量误报"。
- **两边都不写死**：**引用侧**从注释/docstring/字符串字面量里解析出来；
  **真实侧**调用 P26 的解析器 `len(parser())` **现场算**。测试里唯一的字面量是集合
  **名字**和动词词表，都不是测量值。若写成 `assert 22 == 22`，它会在 schema 变动那天照样绿。
- **句子是单位**：历史陈述（`used to` / `no longer` / …）不算活引用，与
  `test_comment_citations_resolve.py` 同一套词表、同一个理由。
- **不能空转**：`_KNOWN_DEBT` 里每一条都断言"该站点**仍然**是那个错数字"，
  修好的那天它自己会红并要求删除条目 —— 债务不能活得比缺陷长。

**实测这条守卫在源树里恰好命中 5 处引用**（见 8.2 的计数）：
`visual_qa.py`（已订正）、`test_p26`（22，正确）、`qa_layers.py`（22 正确 + **13 过期**）。

**⚠️ 一条已知债务（如实记录，未修）**：`studio/scripts/qa_layers.py:266` 同样写着
「13 named by `SCENE_RENDERERS`」（实测 20），是 P29 同一次漂移的同一份抄写。
**P40 未获授权修改该文件**（工单只授权 `visual_qa.py:1051-1054`），
所以它被记为 `_KNOWN_DEBT` 并**断言仍是错数字**，交由指挥窗口处理。

**⚠️ 一处守卫够不到、如实说出**：`tests/test_p21_props_path_gates_the_deliverable.py:24`
写「Measured: 22 types declared, 13 rendered, 9 in between」——**该句子里没有任何集合名**
（名字在上一句）。机械解析无法归属这三个数字，硬要归属就是本项目禁止的估计。
它记在 `_UNATTRIBUTABLE_SITE` 里，不改（P19–P37 成果），报告给指挥窗口。

**同一数字的第三处抄写**（不在源码里、守卫不读）：`docs/UPGRADE_PROGRESS.md:528`
仍写「22 个类型已声明、13 个有渲染器、9 个落在中间」。**账本由指挥窗口改，本项只报告。**

### 8.6 P39 的判据盘点（回答工单原问）

**这份文件里有三处判据，分别回答三个不同的问题**：

| 判据 | 问的问题 | 语料 | 实现 |
|---|---|---|---|
| **C1** 字段锚定 | 「这个数字**是它被引用的那个字段**的值吗？」 | 真源码/图谱 | `_value_is_field_value`（5 种拼写：`layout.<f> ?? N` / `<f> ?? N` / `"<f>": N` / `<f>: N` 无引号 / `<f> = N`） |
| **C2** 标识符缺席 | 「那个**变换标识符**进过声明它的那个文件吗？」 | `DataColumns.tsx` 一个文件 | `TRANSFORM_PHANTOM` + `'translateY' not in body` |
| **C3** 账本标签解析 | 「账本单元格里**跟着字段标签**的数字是什么？」 | 账本 4.9 行 | `_cited_layout_values`（中文标签正则） |

**有没有第三种与前两种不一致的？** **没有"互相打架"的第三种** —— 但确实有第三种（C3），
它在**"同一件事两处两种口径"这个意义上正是风险点**：C3 与 C1 是**同一个"字段归属"思想
在两个不同语料上的两份实现**，机械上并不共享代码。P39 的 `_RAW_TEXT_SCANNERS`
把 C1、C3 都列进白名单，等于**承认二者是并行的两个扫描器**；`test_this_file_has_no_
second_criterion_for_a_layout_value` 保证不会有*第四*个悄悄出现。

**⚠️ 一处必须点名**：C2 **按设计就答不出"真"** —— 它只断言 `translateY` 不在该文件里；
若将来有人把 `translateY` 真的加回去，C2 会红，但它**说不出一个 translateY 幅值是否合理**。
这不是缺陷（该文件本来就不该有 transform 放置），但**它不是一条能判"对不对"的判据，
只是一条"在不在"的判据**，与 C1 的强度不同。P39 的 docstring 自己说明了这一点。

### 8.7 P39 三条变异（`-rf` 原始输出）

每次**先证明落地**（本项目发生过"变异没落地却读了结果"），每次从快照复原并核对 sha256
（`25622c73...`）。

**变异 ①：把判定后半段改回裸数字扫描**（`_phantom_sites` 改成一个 `re.search` 全文件扫）。

落地：`bytes 34305 -> 34351`。

```
FAILED ::test_this_file_has_no_second_criterion_for_a_layout_value
E       AssertionError: these functions search raw text for something and are not on the
        allow-list ['_cited_layout_values', '_value_is_field_value']: ['_phantom_sites']. ...
E       assert not {'_phantom_sites'}
=========================== short test summary info ===========================
1 failed, 8 passed, 1 skipped in 0.10s
```

**红的理由**：红在**扫描器白名单**上，不是 `NameError`/`SyntaxError` —— **对的理由**。
（裸扫描正是被"谁是判定"这条守卫按**引用了什么**抓到的，不是按名字。）

**变异 ②：给 resolver 加恒真旁路**（`_value_is_field_value` 开头 `return True`）。

落地：`bytes 34305 -> 34356`。

```
FAILED ::test_the_resolver_can_actually_say_no - AssertionError: windowWidth ...
FAILED ::test_the_field_phantom_4_9_invented_resolves_nowhere - AssertionError: ...
FAILED ::test_the_phantom_criterion_judges_the_field_not_the_number - Assertion...
FAILED ::test_this_file_has_no_second_criterion_for_a_layout_value - Assertion...
4 failed, 5 passed, 1 skipped in 0.11s
```

**红的理由**：四条全红在**判定值**上（`assert not True`）—— **对的理由**，无异常。

**变异 ③：让判据永远判"通过"**（`_phantom_sites` 恒返回 `[]`，缺席真空成立）。

落地：`bytes 34305 -> 34236`。

```
FAILED ::test_the_phantom_criterion_judges_the_field_not_the_number
E       AssertionError: the criterion did not report a fieldHeight of 480 written as an
        unquoted object-literal key ...
E       assert [] == ['studio/src/...aColumns.tsx']
=========================== short test summary info ===========================
1 failed, 8 passed, 1 skipped in 0.10s
```

**红的理由**：红在**负控**（"判据不是被掰开到恒通过"）上，比较的是判定值 —— **对的理由**。
**注意**：恒通过的判据只有在**负控**存在时才被抓到；若无负控，它会全绿。
**是负控发现了它**，这正是 P39 加负控的理由。

**三次复原后 sha256 均回到 `25622c73...`。**
