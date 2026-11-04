# P54 — `c05_bubble` 声明的 `chart.sizes`：判定、修复与守卫

> 工单：`docs/WORKORDER_P54_BUBBLE_SIZES.md`。本报告只陈述测量与判定，不做放行裁定。
> 工作树：`E:\Minimax-H3`（分支 `claude/suspicious-lichterman-8ead0a`，worktree）。

---

## 一、判定 (a)：哪个位置是这个字段的合法位置

**结论：`chart.sizes`（顶层）是合法位置。缺陷在渲染器，不在图谱。**

### 论证

**1. 渲染器自己对同一条规则的另一半已经接受了顶层拼写。**
`Chart.tsx:238` 改前的原文是：

```tsx
<Bubble series={{values: spec.series?.[0]?.values ?? values,
                 sizes:   spec.series?.[0]?.sizes}} … />
```

同一个对象字面量里，`values` 走的是「`series[0]` 覆盖顶层」的**双位置**规则，`sizes` 只有单位置。
所以「顶层拼写非法」这个说法站不住：如果顶层对 `sizes` 非法，它对 `values` 也一样非法 ——
而 `values` 在顶层是被读的（P48 实测改 `chart.values[0]` 动 5,923 px，就在这棵树上复现）。
缺陷的形状因此不是「图谱写错了位置」，而是**一条既有解析规则只接了一个字段**。

**2. 形状差异说明的是「同一序列的两条通道」，不是笔误。**
工单第 1.4 节要论证的形状：`chart.sizes` 与 `chart.values` 在图谱里并列，正如
`series[0].sizes` 与 `series[0].values` 在 `ChartSpec` 里并列。作者写的是
「一组 y 值 + 一组半径」= 一个序列的两条通道，而**这个仓库所有图谱都把数据写在顶层**：

| 事实 | 测量 |
|---|---|
| 带 chart 场景的 tracked 图谱 | 只有 `pipeline/examples/charts_demo.json`（10 个场景） |
| 其中用 `chart.series` 的 | **0 个** |
| 顶层拼写的数据键 | `values` / `labels` / `rows` / `rowLabels` / `colLabels` / `items` / `before` / `after` / `baseline` —— 全部在顶层 |
| `p29_new_renderer_showcase.json` 的 `series` | 在 `content.series`（stat-card 的数据列），**不是** `content.chart.series` |

⇒ 顶层是这个仓库**事实上的数据词汇**；`series[]` 是一条没有任何图谱走过的备用通路。
把 `sizes` 判给 `series[0]`，等于宣布「`values` 在顶层合法、`sizes` 在顶层非法」——
同一对象里两个并列数组走两套规则，而下一次有人把它们并排写出来时，**坑还活着**。

**3. 仓库对本仓库内同类问题已有先例裁定。**
`Chart.tsx` 的 `normaliseChart` 文档块（P28 写的）就是这件事：`baseline` 当年读在
`content` 而不是 `content.chart`，于是作者把 `baseline` 写在 `values`/`labels` 旁边
「所有其它 chart 字段去的地方」，得到的是沉默。裁定是**把读的位置改到作者会伸手的地方**，
并留下那句话：「作者凭直觉伸手的那一层必须就是有效的那一层，否则坑只是被标注了，没被关掉」。
P54 的形状与此完全相同，只是方向反过来（图谱在正确层，读在错误层）。

### 「两个位置同时存在谁赢 / 是不是第二个真相来源」

- **谁赢**：`series[0]` 赢 —— 与 `values` 已有的优先级一致（更具体的那条声明赢）。
- **是不是第二个真相来源**：不是。真相来源是**那条规则**（`series[0].X ?? X`），
  不是位置数量。`values` 早就有两个位置、一条规则；本次改动是把 `sizes` 并进同一条规则，
  而不是新增第二条规则。若两处并存时行为未定义，那才是两个真相 —— 这一点已用像素钉住
  （`test_the_two_spellings_of_a_channel_render_the_same_picture`，五帧一 bundle）：
  顶层拼写 == `series` 拼写 == 两处一致；两处冲突时 == 只有 `series[0]` 的那一帧，
  且 != 只有顶层的那一帧。

**被否决的方案**：只改图谱，把 `sizes` 搬进 `chart.series[0]`。否决理由：
(a) 它让 `c05_bubble` 成为全仓唯一用 `series` 拼写的场景，而它的 `values` 仍在顶层 ——
把一个序列拆成两层写，这才是真的两个真相；
(b) 顶层 `chart.sizes` 继续无人读，下一张图谱照样掉进去；
(c) 它改的是**已被 P27 验收过的图谱内容**，而不修渲染器就修不到这一类。

---

## 二、判定 (b)：`values` / `sizes` / `sizeBy` 的语义

| 字段 | 语义 | 读它的代码 |
|---|---|---|
| `values` | **y 通道**：`cy = plot.y + … - plot.h*0.28*v/100`，并在 `showValues` 时打印 | `types.tsx` Bubble 的 `series.values.map` |
| `sizes` | **半径通道**：`r = (16 + 46*(sizes[i]/maxSize))*s` | `types.tsx:404` |
| `sizeBy` | **半径是否由数据驱动**：`'none'` → 固定 `26*s`；`'value'` → 正比于半径通道 | `types.tsx` Bubble |

`sizeBy` 名字里的 "value" 指**半径通道的值，不是 y 值**。证据是声明面自己写的注释
（`options.ts:104`，紧跟 `options.ts:105` 的 `sizeBy: 'value' | 'none';`）：

> `/** bubble: radius is proportional to this field's value, not the y value */`

「not the y value」把 `values` 排除掉了 —— `values` 正是 y（`cy` 用它）。
所以缺陷不只是「一个字段没读到」：**它产出的画面恰好违反了这个选项文档明写的语义**
（半径正比于 y 值）。这是比 0 px 更硬的一条判据。

**回退 `series.sizes ?? series.values` 保留，不删。** 理由：
1. 它只在**两条拼写都没声明半径**时触发 —— 那是单通道气泡图的合理默认（半径复制 y 是
   常见画法，且 `options.ts` 的 `sizeBy` 默认就是 `'value'`）；
2. 缺陷从来不是「回退存在」，而是「声明了半径却被回退静默替换」。修好后 `c05` 不再走回退；
3. 删掉它会改变 P47 守卫的合成渲染（`PAYLOAD_TYPES` 用只有 `values` 的 payload 渲 bubble，
   其 ink 0.104% 与 `MIN_PAIR_DIFF` 都是按现状实测钉的）—— 那属于动 P47 的成果。

---

## 三、改动（4 处，零行漂移）

`studio/src/templates/finance-showcase/charts/Chart.tsx`：

| 行 | 改动 |
|---|---|
| 22-24 | 文档块：把「一条规则、`series[0]` 赢」写进适配器的声明 |
| 30 | `ChartSpec` 声明顶层 `sizes?: number[]` —— 合法位置必须**被声明**，否则它只是从 `[key: string]: unknown` 漏进来的（P28 的抱怨正是「两层都没声明，于是两层都被接受，且无从追溯」） |
| 140 | `normaliseChart` 用 `numArray` 归一化顶层 `sizes`，与 `series[].sizes`（`:137`）同一待遇 |
| 238 | `sizes: spec.series?.[0]?.sizes ?? spec.sizes` |

**图谱未改**（判定是渲染器缺读者）。`types.tsx` 未改（回退保留，见第二节）。

行号纪律：`Chart.tsx:137/196/211/238` 与 `types.tsx:404` 被 `docs/P22*`、`docs/P48*`、
`studio/scripts/visual_qa.py` 按行号引用，且 `tests/test_line_refs_land_on_code.py` 守着它们。
所以四处全部**原地改写、不增删行**：文件仍 267 行，改后逐行核对引用位仍在原处。
行尾：改前后均为纯 CRLF（267 CRLF / 0 裸 LF，字节计数验证）。

---

## 四、像素证据

一帧 = `still.mjs` 渲 `c05_bubble` 单场景 props，`--public-dir` 指空目录，无损 PNG，
场景内帧 100（settle 后、离场前 38 帧）。

| 测量 | 改前 | 改后 |
|---|---|---|
| `frame_ink(base)` | 2.110050 % | 2.019387 % |
| 改 `sizes` → 全 1 | **0 px**（sha256 与基线帧完全相同） | **134,808 px** |
| 改 `values[0]` 12→11 | 5,923 px | — |
| 同一图谱 改前 vs 改后 | — | **19,521 px** |

ink 用仓库仪器 `ab_field.frame_ink()`（每行背景模型），不是临时阈值。

### 改后画面变在哪（连通域实测直径，非目测）

| 气泡 | values | sizes | 直径 改前 | 公式预测 | 直径 改后 | 公式预测 | 变化 |
|---|---|---|---|---|---|---|---|
| Mon | 12 | 8 | 44×43 | 43.0 | 41×39 | 39.7 | −3 px |
| Tue | 28 | 22 | 58×59 | 57.8 | 54×54 | 53.3 | −4 px |
| Wed | 45 | 40 | 75×73 | 73.4 | 72×71 | 70.7 | −3 px |
| Thu | 66 | 61 | 94×93 | 92.7 | 92×93 | 91.1 | −2 px |
| Fri | 88 | 79 | 114×115 | 113.0 | 110×110 | 108.5 | −4 px |
| Sat | 100 | 95 | 126×126 | 124.0 | 126×126 | 124.0 | 0 px |

最小/最大直径比 0.349 → 0.325。构图、网格、标签位置、强调逻辑、轴刻度全部不变。

---

## 五、⚠️ 新的还是不是一件好作品

**是。** 但工单第 1.5 节要的那个「若不好看也是发现」的答案，在另一个方向上：

1. **画面没有变坏。** 半径仍单调递增（`sizes` 与 `values` 同为升序），最小/最大对比度
   略微**增强**（0.349 → 0.325），标签跟着自己的圆走（`top = cy + r + 8*s`，r 变小 1–4 px，
   没有引入任何重叠或裁切）。P27 验收的那个构图作为一个构图仍然成立。
2. **但这次修复在画面上几乎看不出来 —— 因为图谱的 `sizes` 值本身有问题。** 实测：
   `values` 与 `sizes` 的**皮尔逊相关 = 0.9989，Spearman 秩相关 = 1.00**，逐点比值
   `[0.667, 0.786, 0.889, 0.924, 0.898, 0.95]`。
   ⇒ 作者声明的半径通道**基本是 y 通道的等比复制**（只在低端压了一点）。
   气泡图的半径本该编码第三个量；这组数没有编码任何 y 之外的信息。
   **所以「声明的意图」被接回来之后，得到的仍是一句近似重复的话。**
   这是图谱内容问题，不是渲染问题：改数字会动 P22 的数值锁定（`values` 锁为
   "the plotted series is the claim"），本项无权也无意替作者重编这组数 ——
   **登记给指挥窗口裁定**。
3. 这一条同时解释了缺陷为什么能活这么久：**替换值与被替换值几乎相等**，
   所以不仅存在性检查是绿的，连肉眼对比都是绿的。

---

## 六、守卫：`tests/test_p54_declared_chart_data_reaches_the_mark.py`

### 判据

> 对每张 tracked 图谱的每个 chart 场景的每个**声明的数据键**：只改这一个通道
> （保持形状与长度），渲出的帧必须变。基线帧自身必须有 ink。

- 遍历的是**图谱声明的键**，不是谁维护的表 ⇒ 新图谱自动被覆盖，改名逃不掉；
- `WAIVED`（声明但不渲染）是**带理由的显式清单**，今天为空；
  `test_the_waiver_table_is_live` 会在「被豁免的键其实又开始动了」时变红，
  也会拒绝无意义的理由和拼错的豁免 —— 这就是对 P43「声明了没渲染器合法」的答复：
  把它写下来，而不是把判据放松；
- `test_no_declared_chart_key_escapes_the_sweep` 用 `ab_field.FIELD_READERS`
  （`test_chart_registry` 已守着的登记表）分类，图谱里出现「既不是数据通道
  也不是选项」的键就点名 —— 未分类的键就是无守卫的键，这正是本缺陷藏身的地方；
- 判据是**函数**，`test_the_criterion_can_say_no` 用合成帧驱动它（相同帧必须判 NO、
  空背景必须报"无主体"）⇒ 「判据恒真」不会靠类守卫暴露，靠自测暴露。

### 与 P47 那条同族守卫：补充，不是重复（实证）

`options.check.ts` 的「no chart type may discard a value the graph supplied」遍历的是
`Object.keys(DEFAULT_CHART_OPTIONS)` —— **选项面**。`sizes` 是数据，从来不在那个列表里，
所以那条守卫在结构上看不见本缺陷。P47 的像素守卫用单一 payload 渲九个类型
（`PAYLOAD_TYPES` 里的 bubble 只有 `values`，没有 `sizes`），也看不见。

实测（缺陷在位 = 变异 1 时）：

```
tests/test_chart_type_defaults_are_real.py + test_chart_ab_matrix.py + test_chart_registry.py
38 passed, 1 skipped in 33.35s          ← 全绿
tests/test_p54_declared_chart_data_reaches_the_mark.py
AssertionError: a data key the graph declares does not reach the frame:
    charts_demo.json c05_bubble.sizes: 0 px changed while only this channel moved
    (baseline ink 2.110050%)
```

⇒ 不复用而是新建，理由不是「找不到」，是**测的是不同的面**：P47 = 选项默认，
A/B 矩阵 = 选项是否活，P43 = 场景类型是否有渲染器，本守卫 = `content.chart` 的**数据半区**。

### 三条变异（各贴 -rf 摘要）

| # | 毒 | 结果 |
|---|---|---|
| 1 | **还原缺陷**：`Chart.tsx` 退回 `sizes: spec.series?.[0]?.sizes` | 守卫红，点名 `c05_bubble.sizes: 0 px`；P48 翻转测试同时红；P47 家族 38 条仍绿 |
| 2 | **另一种落空**：`types.tsx:404` 改成 `const sizes = series.values;`（mark 收到半径却不用） | 同样红在 `c05_bubble.sizes: 0 px` ⇒ 守卫不是只盯 `Chart.tsx` 那一行 |
| 3 | **判据恒真**：`_arrived()` 直接 `return True` | 5 条仍绿、`test_the_criterion_can_say_no` 红：`the criterion called an identical pair "arrived" -- it cannot say NO` |

变异 1 第一次下毒时我把毒写成了 `sizes}}}`（多一个右括号），那会让 bundle 语法报错、
守卫红在探针异常上而不是判定上 —— 已重下为语法合法的版本再跑。三条变异各自
从字节快照复原，复原后 sha256 与预期一致（见第八节）。

---

## 七、全量数字与环境

| 项 | 值 |
|---|---|
| 跑法 | `cd /tmp && py -3.12 -m pytest <worktree>/tests/ -q --ignore=<worktree>/tests/test_take_selection_behaviour.py` |
| 开工基线 | **7 failed, 766 passed, 14 skipped**（23m22s，**无并发**，未清探针） |
| 收尾 | **7 failed, 772 passed, 14 skipped**（9m40s，**无并发**） |
| 差值 | +6 passed = 本项新增的 6 条守卫；失败集合**逐条同名**，未新增未消失 |
| 7 个基线失败 | `test_beat_bindings`(2 sfx 资产)、`test_comment_citations_resolve`、`test_p0_regressions`(experiments 清单)、`test_p16_reference…`(references 目录)、`test_undeclared_field_reads`(sfx)、`test_visual_qa`(report props) —— 涉及的路径 `scripts/experiments`、`references`、`studio/public/jobs/report_demo/props.json`、`studio/public/audio/sfx` **在主树里同样不存在**，与 P54 无关 |
| 单跑确认 | 这 6 个文件单独跑：**7 failed, 77 passed, 4 skipped（27.93s）** —— 同一集合，不是并发假红 |
| 用时差异 | 基线 23m22s → 收尾 9m40s：remotion bundle 缓存被本项的渲染跑热了，不是测试变少 |

⚠️ 本项在 **git worktree** 里做（`E:\Minimax-H3\.claude\worktrees\suspicious-lichterman-8ead0a`），
不是主树。worktree 无 `node_modules`，用 `pnpm install`（store 在 `E:\LabCairn`，缓存
`E:\LabCairn\.local\npm-cache`）装在 worktree 内，未触碰 C 盘。

---

## 八、sha256 与磁盘纪律

| 文件 | 开工前 | 收尾 |
|---|---|---|
| `charts/types.tsx` | `af416bcf…341feb6` | **同值**（未改） |
| `charts/Chart.tsx` | `08c27447…573f39b2` | `df72a1b9…c2951158`（4 处，零行漂移） |
| `pipeline/examples/charts_demo.json` | `61620122…e0a1d8fc` | **同值**（判定：图谱是对的） |
| `tests/test_p48_reaccept.py` | 主树半成品 `4991e276…a3486106` | **同值**（半成品原样接入，注释已由其作者翻转） |

- 输出全部在 `E:\Minimax-H3\.claude\worktrees\suspicious-lichterman-8ead0a\out\p54\`
  （gitignore 内）；`TMPDIR` 指项目内；`--public-dir` 指空目录（避免每 bundle 复制 773 MB）。
- 未删 `studio/.remotion/water-renewal-bundle`。未向 E 盘根目录、未向 C 盘写任何数据。
- 帧/图未复制进仓库。

---

## 九、我的操作失误（如实）

1. **误报 pnpm 失败**：我第一次 `pnpm install` 是后台任务，没读它的输出就断言
   「EPERM 被沙箱挡了」。实际它 exit 0、3m15s 装完。我随后还基于这个错误结论去建
   junction（失败原因是 `DirectoryNotEmpty`，不是权限）。**结论：没读输出就下判断。**
2. **两次渲染写进同一目录**：`render_scene.py` 的输出目录不含变异名，
   变异帧覆盖了改前基线帧（sha 相同，才发现）。基线帧重渲一次才拿到对照。
3. **变异 1 的毒语法非法**（`sizes}}}`），会让守卫红在 bundle 报错上而不是判定上 ——
   正是工单禁止的形状；重下毒后才有上面那三条结果。
4. **判据写反了一次**：`both_diff == series_a` 是错的（`series_a` 装的是 A，`both_diff`
   的 `series[0]` 装的是 B）。补了第五帧 `series_b` 才把「谁赢」测对。
   第一版守卫文件里还留了一段废掉的 fixture 代码和一个多余的 `key_disp`，已清。
5. **一次注释改动多插了一行**（3 行改 4 行），会造成 `Chart.tsx:238` 等被引用行号漂移；
   发现后改回 3 行，并用 `wc`/字节计数确认文件仍 267 行。
