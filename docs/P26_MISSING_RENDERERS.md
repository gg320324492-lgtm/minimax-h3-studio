# P26 — 9 个无渲染器的场景类型：逐个裁定、实现取证、守卫

> 工单：`docs/WORKORDER_P26_MISSING_RENDERERS.md`。本文件记录**实测**（不是引述）：
> 9 个类型逐个 A/B/C 裁定、判 A 的**渲染取证**、`logo` 与 `LOCKED_SCENE_TYPES` 的关系、
> 全量测试数字、逐条变异、三个 sha256。
>
> **一句话结论**：**7 个判 A 并已实现 + 渲染取证；2 个判 B（需另一个引擎，本仓没有）。**
> 账本 3.2「20 种 scene 类型注册」的下一层缺口——「注册」≠「能渲染」——至此闭合。

---

## 零、缺口的确切形状（实测，非引述）

| 事实 | 值 | 来源 |
|---|---|---|
| `SceneType` 声明 | **22** | `studio/src/schemas/showcase-v1.ts:60` |
| `SCENE_RENDERERS` 修复前注册 | **13** | `FinanceShowcaseWide.tsx`（修复前） |
| 落在中间（走 `MissingScene`） | **9** | `video` / `browser-window` / `stat-card` / `card-grid` / `data-table` / `quote` / `data-plane-3d` / `logo` / `outro` |
| `SCENE_RENDERERS` 修复后注册 | **20** | 本次 |
| 仍走 `MissingScene` | **2** | `video` / `data-plane-3d`（且是**记录在案的决策**：`UNRENDERED_SCENE_TYPES`） |

`MissingScene`（`FinanceShowcaseWide.tsx`）渲染出**类型名**加上 **"not implemented in P4"**，
占满整段时长。P21 的 `graph_scene_renderable` 会在**图谱用到**这类类型时报 FAIL，
但**表本身**（schema 声明领先于渲染器）没有任何东西在看 —— 这正是本项补的第二条缝。

---

## 一、9 个类型的逐个裁定（最重要的一节）

裁定标准（工单第二节）：**A** = 纯程序化、有真实设计、**能定义"渲染对了"**；
**B** = 缺输入（需 H3 或外部素材）；**C** = 缺设计（做了就是编）。

| 类型 | 裁定 | 依据（实测） |
|---|---|---|
| `video` | **B** | `GENERATIVE_SCENE_TYPES` 成员；渲染源里**无 H3 渲染器**（P17 实测）。**未做** —— 做了就是无内容的空帧。 |
| `data-plane-3d` | **B** | **两条路都不通**：① 被 `GENERATIVE_SCENE_TYPES` 路由到 H3（无渲染器）；② 主计划 `:205` 说 data-plane 走 `@remotion/three`，而 **`three` / `@remotion/three` 不是依赖**（`package.json` 实测），连 Three.js 也建不起来。**未做**。 |
| `browser-window` | **A** | 参考视觉目标写「Dashboard 多窗口透视景深」；主计划 `:82` 把 **Browser Window** 明确划给 Remotion（"UI 绝不交给 H3"）。单窗口是**已有的设计词汇**（`BrowserStack` 的窗口 chrome：红绿灯 token、标题条、度量、mark）。 |
| `stat-card` | **A** | 视觉目标「日历/**数据卡**/表格矩阵」；主计划 `:82` 把 **Card** 划给 Remotion。`tokens.ts` 的 `numericTable` 角色正是为"表格/卡片里的数字"而存在。 |
| `card-grid` | **A** | 「**窗口墙**」（账本 4.6 命名 Window Wall）+ 数据卡矩阵。与 `stat-card` 共用同一个 `Card` 组件（一张卡重复成墙）。 |
| `data-table` | **A** | 视觉目标「表格矩阵」；主计划 `:82` 把**表格**划给 Remotion，原则「文字/数字/表格/UI 必须程序化，100% 精准」。表格是**不同于图表**的 mark（对齐的文本 vs 编码量值的位置）。 |
| `quote` | **A** | 视觉目标「**黑卡 Quote + 极大留白**」—— 留白是这条要求的核心，因此「渲染对了」可定义：**画面一busy就是错的**。 |
| `logo` | **A** | 视觉目标「**金色 Logo Lockup**」。锁up 是一条**语法**（mark + 字标 + 标语 + settle），graph 供字、设计系统供语法。见第三节。 |
| `outro` | **A** | 视觉目标「**CTA 结尾**」，账本 4.6 命名 CTA。 |

**⇒ 7 A / 2 B / 0 C。**

### 1.1 ⚠️ 与工单给的分类表的差异（独立复核）

工单的表把 7 个都标「✅ 可能做」，与本次实测**一致**。但**依据不同**，逐条独立复核：

- **`data-plane-3d` 的 B 比工单说的更硬**：工单说它「要 H3」。实测它还额外缺一条路——
  主计划本来把它指定给 **Three.js**，而 `three` 不是依赖。**两条路都不通**，所以即便
  未来"H3 是什么"被定下来，data-plane 也另需 `@remotion/three`。这一条**工单没说**。

### 1.2 为什么没有一个判 C

C 的条件是「没有可依据的视觉规格」。**7 个都有**：`docs/UPGRADE_MASTER_PLAN.md`
第 3 节「视觉目标」逐条点名了它们对应的构图（数据卡 / 表格矩阵 / 黑卡 Quote + 留白 /
金色 Logo Lockup / CTA 结尾 / 窗口墙），第 1 节的「职责划分」表把它们**明确划给
Remotion**（不是 H3）。这不是本项发明规格，本项是**照着一份已存在的规格**做。
**⇒ 这是本项不判 C 的理由，而不是"为了凑数"。**

---

## 二、判 A 的渲染取证（必须真渲一次）

**方法**：一张图谱（`E:/p26_work/p26_all.json`，本地，不提交）串起 9 个类型各 120 帧；
`still.mjs` 一次 bundle 渲 9 帧（每类型在其窗内取一帧）。**输出到 E: 盘**。

渲染的是 `1920x1080@60`，帧 90/210/330/450/570/690/810/930/1050（对应各 scene）。
`studio/bin/still.mjs` 的 bundle 各 **1.2–1.5s**。

### 2.1 直接的判据：**真渲染器会动，占位符一动不动**

`MissingScene` 是**静态**的——它没有任何随帧变化的样式，所以同一个 scene 的**两帧逐像素相同**。
判 A 的每个都不行：它们有 spring 入场。这给出一个**不需要发明阈值的、干净的判别量**：

取每个 scene 窗内的**早帧**（第 10 帧，入场中）与**晚帧**（第 90 帧，已 settle），
量 `max|Δ| > 8` 的像素数（对 RGB 三通道取最大差）：

| scene 类型 | 裁定 | 早帧→晚帧变化像素 | 占位符? |
|---|---|---|---|
| `browser-window` | A | **125,666** | 不是 |
| `stat-card` | A | **24,606** | 不是 |
| `card-grid` | A | **401,197** | 不是 |
| `data-table` | A | **40,593** | 不是 |
| `quote` | A | **596,866** | 不是 |
| `logo` | A | **13,029** | 不是 |
| `outro` | A | **27,966** | 不是 |
| **`video`** | **B** | **0** | **是（占位符）** |
| **`data-plane-3d`** | **B** | **0** | **是（占位符）** |

**⇒ 7 个 A 全部动（最少 13,029 px），2 个 B 一动未动。** 这正是"出的不是
`MissingScene` 那个占位符"的**运行期证据**（不是源码阅读）。

### 2.2 补充证据：与占位符帧的像素差

把每个 A 帧与 `video` 的占位符帧（同 backdrop / 同主题）逐像素比，`>8` 的像素占比：
`browser-window` **37.8%**、`quote` **28.1%**、`card-grid` **27.0%**、`data-table` **19.9%**、
`stat-card` **9.5%**、`outro` **1.4%**、`logo` **0.65%**；
而**占位符对占位符**（只差类型名那几个字）**0.25%**。

> `logo`（0.65%）和 `outro`（1.4%）的差偏小，因为它们的内容本来就稀疏（金 mark + 短字）。
> **这一条单独不足以区分 `logo`**，所以**承重的是 2.1 那条**（占位符恒 0、logo 动 13,029 px）。
> 两个量一起写在这里，是因为只报对自己有利的那个量，是本项目记录过的坑。

### 2.3 人眼看帧

7 个 A 帧逐张看过（`E:/p26_work/frames/`）：浏览器窗口（红绿灯 + 标题条 + 大数字 + spark）、
数据卡（金标签 + 数字 + 涨跌 chip + spark）、3×2 数据卡墙（一张 accented）、
表格（表头 + 右对齐数字列 + accented 行 + 金色底线）、黑卡 Quote（超大引号 + 标题级句子 + 署名）、
Logo Lockup（金 mark + 字标 + 标语）、CTA（lockup + 大 CTA + 副题 + 规则线）。
**没有一个像占位符。**

---

## 三、`logo` 与 `LOCKED_SCENE_TYPES` 的关系（工单点名要说明）

**核实为真**：`studio/scripts/locked_fields.py:100`

```python
LOCKED_SCENE_TYPES: frozenset[str] = frozenset({'logo'})
```

注释（`:22-24`）写明了理由：**`logo` 是 showcase-v1 里的一个场景类型，不是 content 字段**，
所以品牌锁只能锁**类型本身**——"locking the type is what stops a repair from rerouting it
to a chart to make it fit"。

**本项核实并纠正工单的一句表述**：

- 工单说「锁防的是一个**还没有渲染器的**类型」。**修复前为真，修复后不再为真。**
  P26 之前，`logo` 类型确实没有渲染器——一个 repair loop 保护 `logo` 不被改道，
  保的是一段**无论如何都会渲染成 "not implemented in P4"** 的场景。**这不使锁错**
  （11.2 的命题「repair 不得改道品牌场景」与是否画得出来无关），但使锁**不可证伪**：
  没有任何渲染路径能观察到"改道 `logo`"改变了输出。
- **P26 之后**：`logo` 有了渲染器，锁因此**有了可保护的产物**。
  **锁本身未改**（`locked_fields.py` sha256 一字未变），
  `tests/test_locked_fields.py::test_the_three_kinds_from_the_ledger_are_all_present`
  仍钉着 `LOCKED_SCENE_TYPES == {'logo'}`。

**⇒ 一句话**：`LOCKED_SCENE_TYPES` 锁的是**类型**（因为品牌 mark 是一个 scene 而不是一个字段）；
P26 之前它锁着一个无渲染器的类型（锁有效但不可证伪），P26 之后它锁着一个有渲染器的类型（可证伪）。

---

## 四、守卫

`tests/test_p26_scene_type_coverage.py`（**6 项**）。它回答的**另一条**问题（不重复 P21）：

> `SceneType` 声明的每个类型，要么是 `SCENE_RENDERERS` 的键（有渲染器），
> 要么是 `UNRENDERED_SCENE_TYPES` 的键（**记录在案的"有意不做"**），且不得同时在两边。

**判据是集合差，不是子串**（4.9 的教訓）。两个 map 都被**解析成键集合**再作差，
所以「删掉一个渲染器键而不登记」= 一个类型落在两边之外 = 红。
**注释先剥**（模板的散文里就点着这些类型名），所以注释不能冒充一个键。

**新增的是一张决策表** `UNRENDERED_SCENE_TYPES`（`FinanceShowcaseWide.tsx`，导出）：
`{video, data-plane-3d}`，各带一条理由。守卫断言 `unrendered ⊆ generative` ——
**一个可程序化画出的类型被留下不画，会红**：留下不画必须由"需另一个引擎"来解释。

6 项：① 分区无缺口；② 两份 map 的形状（解析器真的读到了东西）；
③ `unrendered ⊆ generative`（归属）；④ 每个 unrendered 都带理由；
⑤ 判别力自检（喂合成的缺口输入，必须报缺口）；
⑥ 端到端——对**真实模板文本**删掉一个渲染器键，必须报 `uncovered`。

---

## 五、变异（协议：先证明变异落地，再跑 pytest，贴 `-rf` 原始输出）

源文件是 **CRLF**（`FinanceShowcaseWide.tsx` CR=292、`showcase-v1.ts` CR=400），
变异与复原**全部用 `read_bytes`/`write_bytes`**（不经过会翻译行尾的 `write_text`），
每次落地后**读回字节数复验**。

| # | 变异 | 落地证明 | 期望 | 结果 |
|---|---|---|---|---|
| **M1** | `SCENE_RENDERERS` 里删掉 `quote: Quote,` | `LANDED`；14531→14514 字节，CR 291 | 红 | ✅ **被杀**，3 项 |
| **M2** | `SceneType` 新增 `'p26_probe'`（两边 map 都不动） | `LANDED`；18422→18438 字节，CR 401 | 红 | ✅ **被杀**，3 项 |
| **M3** | 判据空转：`partition_gaps` 的 `uncovered` 恒为 `[]` | `LANDED`；16016→15978 字节 | 红 | ✅ **被杀**，2 项 |

**无存活变异。**

**M1 — 原始 `-rf` 输出**
```
FAILED tests/test_p26_scene_type_coverage.py::test_every_scene_type_is_rendered_or_recorded_as_unrendered
FAILED tests/test_p26_scene_type_coverage.py::test_the_maps_are_the_real_ones
FAILED tests/test_p26_scene_type_coverage.py::test_a_renderer_key_deleted_from_the_map_would_be_uncovered
3 failed, 3 passed in 0.08s
```
承重的那一项红的理由（正确）：
```
E         A type with a renderer that is DELETED from SCENE_RENDERERS but not recorded in UNRENDERED_SCENE_TYPES lands in `uncovered` — that is the regression this catches.
E       assert not True
E        +  where True = any(dict_values([['quote'], [], [], []]))
E        ... = {'uncovered': ['quote'], 'both': [], 'phantom_renderers': [], 'phantom_unrendered': []}
```

**M2 — 原始 `-rf` 输出**
```
FAILED tests/test_p26_scene_type_coverage.py::test_every_scene_type_is_rendered_or_recorded_as_unrendered
FAILED tests/test_p26_scene_type_coverage.py::test_the_maps_are_the_real_ones
FAILED tests/test_p26_scene_type_coverage.py::test_a_renderer_key_deleted_from_the_map_would_be_uncovered
3 failed, 3 passed in 0.08s
```
承重项红的理由（正确）：
```
E       assert not True
E        +  where True = any(dict_values([['p26_probe'], [], [], []]))
E        ... = {'uncovered': ['p26_probe'], ...}
```

**M3 — 原始 `-rf` 输出**
```
FAILED tests/test_p26_scene_type_coverage.py::test_the_partition_check_can_say_no
FAILED tests/test_p26_scene_type_coverage.py::test_a_renderer_key_deleted_from_the_map_would_be_uncovered
2 failed, 4 passed in 0.07s
```
判别力自检红的理由（正确 —— 判据恒"通过"被这两条专抓空转的测试杀死）：
```
E       AssertionError: a rendered key removed without a record must fall in `uncovered`; got {'uncovered': [], 'both': [], 'phantom_renderers': [], 'phantom_unrendered': []}
E       assert [] == ['quote']
```
```
E         Right contains one more item: 'a'
E       assert [] == [...]
```

**复原核对**（三条变异后从快照 `write_bytes` 复原，与开工时的 sha 逐字节一致）：

| 文件 | 开工 sha256（前 16） | 复原后 | CR |
|---|---|---|---|
| `FinanceShowcaseWide.tsx` | `c56e836d8d0f0d8c` | 一致 | 292 |
| `showcase-v1.ts` | `3294bd069eb6c44f` | 一致 | 400 |
| `tests/test_p26_scene_type_coverage.py` | `d0c4026f3064e509` | 一致 | 0 |

---

## 六、改动文件清单

| 文件 | 性质 |
|---|---|
| `studio/src/templates/finance-showcase/scenes/Cards.tsx` | **新增**：`StatCard` + `CardGrid`（共用 `Card`） |
| `studio/src/templates/finance-showcase/scenes/DataTable.tsx` | **新增**：`DataTable` |
| `studio/src/templates/finance-showcase/scenes/Quote.tsx` | **新增**：`Quote` |
| `studio/src/templates/finance-showcase/scenes/BrowserWindow.tsx` | **新增**：单窗口 `BrowserWindow` |
| `studio/src/templates/finance-showcase/scenes/Brand.tsx` | **新增**：`Logo` + `Outro`（共用 `Lockup`） |
| `studio/src/templates/finance-showcase/FinanceShowcaseWide.tsx` | 注册 7 个渲染器；**新增** `UNRENDERED_SCENE_TYPES` 决策表；`resolved.map` 一行**未动** |
| `tests/test_p26_scene_type_coverage.py` | **新增**：6 项守卫 |
| `tests/test_p21_props_path_gates_the_deliverable.py` | **改写 4 处 fixture**（3 个测试）：`quote`/`outro`/`card-grid` 现在是渲染类型，换成仍无渲染器的 `video`/`data-plane-3d`。**断言一字未改。** |
| `docs/P26_MISSING_RENDERERS.md` | **新增**：本文件（执行 agent 写；账本由指挥窗口改） |

**未动**：`visual_qa.py` / `frame_baseline.py` / `render.mjs`（sha256 见下）；
`GENERATIVE_SCENE_TYPES`；`FinanceShowcaseWide.tsx` 的 `resolved.map` 行；
已有的 13 个渲染器（`BrowserStack.tsx` / `DataColumns.tsx` 等**一行未改**，见下）；
`locked_fields.py`；`docs/UPGRADE_PROGRESS.md` / `UPGRADE_MASTER_PLAN.md` / `P1*.md` / `P2*.md`。

**为什么没有抽取 `BrowserStack` 的单窗口部分**（工单允许"为复用而抽取公共部分"）：
`tests/test_p4_9_ledger_numbers_resolve.py` 按**行号/字段**读 `BrowserStack.tsx:231/232`
的 `spreadX`/`spreadZ` 默认值（4.9 两次假账的守卫），抽取会移动那些行。
故 `BrowserWindow.tsx` 是**独立的、尺寸更大、构图不同**的组件（单窗口居中大图 vs
栈在 z 轴扇开），复用共享 token（`TRAFFIC_LIGHTS`、`useDesign()` 角色），**不动 `BrowserStack.tsx`**。

---

## 七、`test_p21` fixture 的改写（必须单独记，因为它动了 P21 的文件）

**为什么动**：`test_p21_props_path_gates_the_deliverable.py` 的 3 个失败方向测试
把 `quote` / `outro` / `card-grid` 当作"**没有渲染器**的类型"的**例子**。P26 给这三个
（及其余四个）加了渲染器，那些例子**因此变成假的**，3 个测试转红 —— **这是正确的行为**。

**怎么动**（按 P14 先例）：**就地改写 fixture**，换成**仍然**没有渲染器的类型
（`video` / `data-plane-3d`，都是 `GENERATIVE_SCENE_TYPES`），并在每处 docstring
写明改了什么、为什么。**断言（`== FAIL`、`code != 0`、"not implemented in P4" in report）
一字未改**，守卫覆盖的**命题**不变：`graph_scene_renderable` 必须对"用到无渲染器类型"的图谱报 FAIL。

**复核**：改后 `test_p21` 全绿（见第八节），且 `test_p21` 里那条"健康方向"测试
（`_clean_graph` 用 `kpi-hero` + `bar-chart`）不受影响。

---

## 八、测试数字（实测）

| | 结果 |
|---|---|
| **本项开工基线**（实测，本机） | `522 passed, 4 skipped in 319.22s` |
| **本项改完后**（实测，无并发改动） | **`528 passed, 4 skipped in 305.85s`**，退出码 0 |

**522 + 6 = 528**：新增的 6 项全部来自 `tests/test_p26_scene_type_coverage.py`，
**无回归**。跑法（标准）：
```
cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q \
  --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py
```
（**未导出 `PYTHONIOENCODING`** —— 它会污染 `test_visual_qa.py`。）

**`test_p21` 单独**：`32 passed`（含 P17 一起跑的 32 项）。

**`tsc --noEmit`**：`studio/` 下**零错误**。

**端到端 sanity（跑 `visual_qa.py --props`，非读源码）**：
```
quote+stat-card+data-table+logo 图谱  → [PASS] graph_scene_renderable value=0 → EXIT 0
video 图谱                          → [FAIL] ... 20 of 22 declared scene types have a renderer ...
```
**20 of 22**（修复前是 **13 of 22**）—— 与 `SCENE_RENDERERS` 的键数一致。

---

## 九、三个受保护文件的 sha256（收尾实测）

```
7e7d586a747c9fb1...  studio/scripts/visual_qa.py     （工单要求 7e7d586a…）✅
91e3463cf0fe25a2...  studio/scripts/frame_baseline.py（工单要求 91e3463c…）✅
120b11dacf1a6230...  studio/bin/render.mjs           （工单要求 120b11da…）✅
```

---

## 十、磁盘纪律

- **造**：`E:/p26_work/`（props 图谱、`frames/` 9 张 still、`frames_early/` 9 张 still、
  `snap/` 3 个变异快照、`scratch/` Remotion bundle 临时目录）。**全部在 E: 盘。**
- **删**：收尾删除 `E:/p26_work/`（含 `scratch/`）。`still.mjs` 自己在 `finally` /
  `exit` 里清理 bundle，未在 C: 盘残留。
- **未污染 CRLF**：所有变异/复原用字节读写；三个源文件收尾 CR 计数与开工一致
  （`FinanceShowcaseWide.tsx` 292 / `showcase-v1.ts` 400 / 新测试 0）。

---

## 十一、本项的失误（如实记录）

1. **`FinanceShowcaseWide.tsx` 第一次落 `UNRENDERED_SCENE_TYPES` 时，
   理由字符串里写了 `H3` 字样**，把 P17 的
   `test_no_h3_renderer_exists_in_the_render_source`（它剥注释后在本文件的**代码**里
   禁 `H3`）**弄红了**。那不是回归，是我的字符串。改成不含该字面量、理由留在注释与本文档。
   **记在这里因为它是"断言存在时排除注释"的近亲**：那条守卫禁的是**代码**里的名字，
   而我一开始把它当成了**注释**。
2. **`SPACE.hero` 一开始被新 scene 用了**，于是 `test_space_scale.py` 的"死 token 集合"
   从 `('xs','xxl','hero')` 缩到 `('xs','xxl')` 而转红。**两种处理都合法**（消费一个保留
   token 是该守卫**允许**的方向）。我选择**不消费**它——把三处 `SPACE.hero` 改成
   `SPACE.xl`（`× 2`）——以**不动 `tokens.ts`（P6 产物）与其冻结集合**，把改动面留在工单
   授权的 `scenes/**` 内。**记下来因为这是我为了"少动文件"而做的一次设计取舍，不是纯技术选择。**
3. **第一版守卫正则漏了 `export` 是可选的**（`SCENE_RENDERERS` 没有 `export`，
   `UNRENDERED_SCENE_TYPES` 有），且 `GENERATIVE_SCENE_TYPES` 的 `Set<…>` 里有 `>`，
   `[^>]*` 匹配不上。两处都在首次运行时暴露并修正。

---

## 十二、给指挥窗口的账本订正建议（本项不改账本）

| 位置 | 现表述 | 本项实测建议 |
|---|---|---|
| `UPGRADE_PROGRESS.md:73`（3.2「20 种 scene 类型注册」，划掉当作完成） | 已划掉 | 建议补一行：**"注册"≠"能渲染"**；P26 起 `SCENE_RENDERERS` 20/22，余 2 为记录在案的 B（`UNRENDERED_SCENE_TYPES`） |
| `:111`（4.6「扩展：Quote/Rank/Dashboard Overview/Data Plane/Window Wall/Logo/CTA」） | 待办 | Quote / Window Wall(`card-grid`) / Logo / CTA(`outro`) 已实现；Data Plane 判 B |
| `visual_qa.py:1052` 与 `test_p21`/`test_p17` docstring 里的「22 declared / 13 rendered / 9 in between」 | 散文 | 现在是 **20 rendered / 2 in between**（散文不是断言，未导致红；但读起来会误导） |

**本项未改账本**（工单第四节：账本由指挥窗口统一更新）。
