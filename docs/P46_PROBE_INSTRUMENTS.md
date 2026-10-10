# P46 — 把 P37 的五个 B 维度从「缺仪器」推进到「有仪器」

> Work order: `docs/WORKORDER_P46_PROBE_INSTRUMENTS.md`.
> 本文件记录**实测数字**、**逐维度裁定**，以及**我犯的错**。
> ⚠️ **本项不裁定 `premium`。本项只补仪器。**「premium」至今不是一个可判定的东西。

---

## 零、一句话结论

**五个 B 维度：1 个变 A（色彩，RGB 通道真的进了 `reference_probe`），
1 个变 C（图表，分类器建成了但口径对不上片子），3 个仍是 B
（布局、相机、字体）—— 而那三个 B 的死因已经从「假设」变成了「实测」。**

最值钱的不是那个 A，是三个 B 现在各自**指名了缺什么**，而且其中两条
（相机、字体）是我这次**造了仪器、量了、量出来是负结果**才敢下的判定。

---

## 0.1 五个维度的裁定

| # | 维度 | P37 | P46 | 一句话理由（死因指名） |
|---|---|---|---|---|
| 3 | **色彩** | B | **A** | RGB 通道**已实现**进 `reference_probe.measure_colour`，逐帧原生分辨率，模态色 + 占比。口径是声明的（5 bit/通道、桶心报数），可与 `themes.ts` 的 token 并排比较。**这不是「又量了一次」——它在探针的解码路径上，跑在任何片子上。** |
| 4 | **布局** | B | **B** | 死的不是仪器。`measure_frame.py` 在，**缺的是一个声明的参照框**：参考片没有、我们也没有可比的对齐契约。我没有自己定一个（P16 的教训）。 |
| 6 | **相机** | B | **B** | 仪器建了一半并**验证过**（植入平移 → 残差 0.000；画面内物体动 → 解释率 0.0000）。但**实测**：全片 17 个采样点，平移解释率 **0.0000**、平移+缩放解释率 **≤0.005**。**缺的仍是单应/投影模型**——而这个实测**推翻了 P37 的一条判断**（见 §4）。 |
| 7 | **图表** | B | **C** | 分类器建成并实测（8/12、0/4 假阳性、28 次调用 0 处分歧）。但片子的图表类型（蜡烛图、期权链）**在本项目的词汇表里没有名字**，且片子没有标注语料 ⇒ **量到了，填不进去**——与 P37 对「转场」判 C 是同一种形状。 |
| 8 | **字体** | B | **B** | 试了**三台**仪器，全灭：帧级笔画对比（云重叠）、字形级笔画对比（**分开了，但方向是反的**）、VLM 闭合问句（**5 张 sans 卡里 3 张答 SERIF，60% 假阳性**）。**分类器是有偏的，不是没有的。** |

> ⚠️ **这三条 B 不是"没做事"**。P37 判 B 时手里只有"零仪器"这一句话；
> 现在每一条 B 后面都跟着一组数字，说明**仪器做到了哪一步、剩下那一步是什么**。

---

## 一、环境与基线

| 项 | 值 |
|---|---|
| HEAD（开工时） | `9a53c9f` |
| **基线测试** | **`719 passed, 4 skipped`**（实测，与工单数字一致） |
| 基线跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=.../test_take_selection_behaviour.py` |
| ollama | 在跑；`qwen2.5vl:7b`，`5969245856` 字节。**未安装、未下载、未修改。** |
| 参考片 | `C:/Users/pc/Documents/xwechat_files/wxid_uibqlezvenv522_4379/msg/video/2026-10/47b43f61516c23d169ddd34b00695ab2_raw.mp4`（`ffprobe` 实测 1280×720 / 60fps / **5082 帧** / h264 / 有 aac 音轨） |
| ffmpeg | 4.2.11（**无 `drawtext`**——这一点后面有用） |
| Python | 3.12 有 numpy 2.5.0 / scipy 1.18.0 / Pillow 12.2.0，**无 cv2**；3.10 有 cv2 4.11.0 但无 pytest |

---

## 二、维度 3（色彩）：**B → A**

### 2.1 补了什么

`studio/scripts/reference_probe.py` 新增 `measure_colour()` 与
`decode_frames_rgb()`，`adjudicate()` 的 `v['色彩']` 由常量 `B` 改为**读测量**：

```python
c = m.get('colour') or {}
v['色彩'] = A if c.get('frames_sampled', 0) > 0 else B
```

判据挂在**测量**上，不是挂在"这段代码存在"上——这正是 P37 说的
「量到 ≠ 建了仪器」的分界线，也是 P37 自己没跨过去的那一步。

### 2.2 口径（声明在 docstring 里，不是声明在脑子里）

- **原生分辨率**逐帧解码 `-pix_fmt rgb24`，`-vsync 0`（P37 记的 89 帧率转换坑照旧成立）；
- **模态色**：RGB 每通道量化到 **5 bit（32 级）**，取众数；报数取**桶心**不是桶底
  （报 248 而不是 252，会把 P37 实测的 `[252,252,252]` 和工单假设的
  `[224,224,224]` 在恰好不能相等的地方判成相等）；
- **`dominant_share`**：众数像素占已采样像素的比例；
- **`channel_mean`**：R/G/B 三通道均值；
- **`per_frame`**：每采样帧各自的众数与占比（下面 §2.4 证明为什么必须有它）。

**⚠️ 我第一版固定 `every=30` 采样，结果 2 秒的测试片只采到 1 帧**
（`frames_sampled: 1`）——两秒的片和八十四秒的片看起来一样"被测过"。
改成按容器帧数算步长（目标 ~20 帧）后才修好。

### 2.3 实测：参考片

```
stream {'width': 1280, 'height': 720, 'fps': 60.0, 'nb_frames': 5082,
        'codec': 'h264', 'has_audio': True}
colour frames_sampled 170   stride 30   pixels 156,672,000
channel_mean      [159.01, 152.79, 147.62]
dominant          [252, 252, 252]      dominant_share 0.0961
```

`measure_colour` 全片单遍耗时 **163.3 s**（不是外推，是这一次跑出来的）。

### 2.4 ⚠️ 一个只有仪器才暴露的问题：**整片一个主色是错的摘要**

全片众数 `[252,252,252]` 只占 **9.61%** 的像素。原因很简单：**这部片按段落换底色**。
逐帧众数（连成段，`f` 为全局帧号 / `t` 为秒）：

```
  f    60-  90  t= 1.00- 1.50s  rgb=[220, 196, 156]  mean_share=0.018
  f  1410-1860  t=23.50-31.00s  rgb=[252, 252, 252]  mean_share=0.241
  f  2160-2340  t=36.00-39.00s  rgb=[252, 252, 252]  mean_share=0.214
  f  2850-3060  t=47.50-51.00s  rgb=[252, 252, 252]  mean_share=0.194
  f  3120-3300  t=52.00-55.00s  rgb=[12, 12, 12]      mean_share=0.187
  f  3570-4050  t=59.50-67.50s  rgb=[252, 252, 252]  mean_share=0.278
  f  4080-4260  t=68.00-71.00s  rgb=[12, 12, 12]      mean_share=0.241
  f  4290-4380  t=71.50-73.00s  rgb=[20, 20, 12]      mean_share=0.190
  f  4560-4620  t=76.00-77.00s  rgb=[12, 12, 12]      mean_share=0.177
  f  4830-4890  t=80.50-81.50s  rgb=[28, 20, 20]      mean_share=0.187
  f  4920-4980  t=82.00-83.00s  rgb=[20, 20, 12]      mean_share=0.181
  f  5010-5070  t=83.50-84.50s  rgb=[20, 28, 44]      mean_share=0.331
```

**⇒ 仪器复现了 P37 §1.2 的整张分段表**（0–23s 暖米 `[220,212,188]`、
23–51s 近白 `[252,252,252]`、51–55s 近黑 `[12,12,12]`、67–83s 近黑
`[12,12,12]`/`[20,20,12]`、83s 后深蓝 `[20,28,44]`）——**而 P37 自己说过
那次量法"在仓库外、未固化为仪器"。现在它在仓库里，能被重跑。**

### 2.5 与本项目 token 的并排（**这是"口径明确"的证据，不是裁定**）

`design/themes.ts` 的 `premium-dark`：`background #0A0A0C` = `[10,10,12]`。

| 片段 | 实测众数 | 与 `[10,10,12]` 的最大分量差 |
|---|---|---|
| 0–23s 暖米口播 | `[220,212,188]` | 176 |
| 23–51s 近白数据看板 | `[252,252,252]` | 242 |
| 52–55s 近黑期权链 | `[12,12,12]` | **2** |
| 68–83s 近黑产品段 | `[12,12,12]` / `[20,20,12]` | **2 / 10** |
| 83.5–84.5s 片尾 CTA | `[20,28,44]` | 32 |

⚠️ **这张表不裁定任何事**。它只说明两件事：
(1) 仪器能同时读片子和读我们声明的 token，**单位是同一个**（sRGB RGB）；
(2) 片子里确实有一段与 `premium-dark` 的 `background` **逐通道差 ≤10**。
**底色冲突怎么处置是 P37 §3 留给人的决定，不是本项的。**

### 2.6 为什么判 A 而不是 C

P37 对「亮度」判 C 的理由是"我们的亮度语料是我们自己的渲染帧"。
色彩不一样：`themes.ts` **声明了十六进制 token**，所以"片子的实测模态色"
与"我们声明的 token"之间**有一个已声明的比较对象**——这正是亮度维度缺的。
⇒ 仪器现在能量，量的东西有明确口径 ⇒ **A**。

⚠️ **A 的意思是"现在能量、量出来有口径"，不是"我们的颜色对"，
更不是"premium"成立。**

---

## 三、维度 7（图表）：**B → C**

### 3.1 正类怎么证明的（**不是相信一个标签**）

工单 §二.2 提醒：P45 的第一条血训是「一个声明面能让一个能工作的选项变成惰性」。
所以 `chart.type: 'bar'` **不算证据**。

`studio/scripts/p46_chart_control.py` 做的对照渲染：
**同一份 payload（c01_bar 的 `values` + `labels`），只改 `chart.type`，渲同一个全局帧**。

```
=== source scene c01_bar  global frame 100  types ['bar','line','area','volume','sparkline'] ===
sha256[:16] of each rendered frame:
  bar        f3dd999afc728bd0
  line       d9df712a6e8c72ca
  area       d9df712a6e8c72ca     ← 与 line 逐字节相同
  volume     618fdc434c583362
  sparkline  84f43c29acb4bad6
pairwise differing pixels (per-channel tol 24):
  bar|line               changed_px=393393 bbox=[112, 166, 1844, 977]
  bar|area               changed_px=393393 bbox=[112, 166, 1844, 977]
  bar|volume             changed_px=218717 bbox=[209, 170, 1754, 914]
  bar|sparkline          changed_px=387294 bbox=[112, 91, 1815, 976]
  line|area              changed_px=0       bbox=None
  line|volume            changed_px=601806 bbox=[112, 166, 1844, 977]
  line|sparkline         changed_px=16075  bbox=[119, 91, 1844, 977]
  area|volume            changed_px=601806 bbox=[112, 166, 1844, 977]
  area|sparkline         changed_px=16075  bbox=[119, 91, 1844, 977]
  volume|sparkline       changed_px=599513 bbox=[112, 91, 1754, 951]
9 of 10 pairs differ; 1 are identical.
```

### 3.2 ⚠️ 我的守卫抓到一个**真缺陷**（在只读的 `studio/src` 里，故只报告不修）

`line` 与 `area` **逐字节相同**。追下去：

- `types.tsx:268`：`withArea={option('line','showArea',f.opts) ?? defaultArea}`
- `options.ts:201`：`option()` **从不返回 undefined**，它回落到
  `DEFAULT_CHART_OPTIONS[key]`，而 `options.ts:120` 里 `showArea: false`。

⇒ **`defaultArea` 永远不可达**，`area` 只有在图谱显式写 `showArea: true` 时才与
`line` 不同。对照已发布的图谱：`c02_line` 声明 `showArea: true`、
`c03_area` 什么都没声明 ⇒ **这两个已发布场景的填充与它们的名字是反的。**

⚠️ `studio/src/**` 是本项**只读**的，所以这是**报告**，不是修复。
⇒ **`area` 被排除出可评分集合**（`INERT_TYPES`）。在一台产不出该类的渲染器上
给分类器打分，量到的是零。

### 3.3 ⚠️ 我第二帧又踩了退出段（**我自己的错**）

我第一版把 `FRAME = 140`（"场景末尾附近，应该是 settled"）。
`lifecycle.ts` 给 150 帧的场景留 `max(EXIT_MIN=6, round(150*0.08))=12` 帧退出，
所以 **`exitStart = 138`，帧 140 已经在退场**。实测：

```
bar        f060 vs f100 changed_px=  0     |  f100 vs f140 changed_px=387430
sparkline  f060 vs f100 changed_px=  0     |  f100 vs f140 changed_px=   5131
```

⇒ 帧 60 与 100 **逐像素相同**（真稳态），帧 140 是半退场的图。
**在退场帧上给分类器打分 = 在半张图上打分**，穿着"稳态帧"的外衣。
改用 `FRAMES = (60, 100)`，并把这条写进守卫。

### 3.4 分类器（`studio/scripts/p46_chart_probe.py`）

**为什么用强制单选而不是逐类 yes/no**：本项目的 `volume` 由 `VolumeBars` 画，
它自己的注释写着 "baseline-anchored, **same as Bar** — see barBox"。
所以"这张图里有没有柱状图"对一张 volume 图**真的成立**，逐类 yes/no 的假阳性率
量的是**问题的歧义**而不是分类器的准不准。强制单选把这个歧义在构造上消掉了。

问题与选项（闭合，一个字母回来）：

```
This image shows a screen. Which of these describes it?
A) a bar chart: solid filled rectangles standing side by side on one common baseline, each a different height
B) a line chart: a single thin line drawn through a series of points, with no area filled in beneath it
C) a volume chart: the same baseline-anchored rectangles as a bar chart but noticeably WIDER, with rounded top corners
D) a sparkline: a small bare line drawing with no axis, no tick numbers and no frame around it
E) there is no data chart in this image at all
Answer with exactly one letter: A, B, C, D or E.
```

### 3.5 ⚠️ 阴性样本是怎么确认的（P45 那个 y 轴刻度的教训）

**这是本项最重要的一次"差点出错"。**
我本来拿 `showcase_demo.json` 的四个无 `chart` 字段的场景当阴性。
**我先看了每一帧**，结果：

| 场景 | 图谱声明 | 画面实际 | 能不能当阴性 |
|---|---|---|---|
| `s01_kpi` | 无 chart | 一个 KPI 数字 + 涨跌胶囊 | ✅ 可以 |
| `s02_dash` | 无 chart | **窗口里有一张迷你柱状图和一张迷你折线图** | ❌ **不行** |
| `s03_columns` | 无 chart | **一排竖直柱子——按 A 的定义就是柱状图** | ❌ **不行** |
| `s04_calendar` | 无 chart | 一月日期格 | ✅ 可以 |

⚠️ **四个候选里有两个画布上真的有图。** 若照图谱声明把它们记成"没有图"，
分类器答 A 就是**对的**，而我会把它记成假阳性——**造出一个 50% 的假阳性率**。
和 P45 用 `45×1.01→50` 当阴性是同一类错，方向相反。

修正：阴性只用两个**逐帧看过**的渲染 + 两个 ffmpeg `color` 合成的纯色帧
（构造上无图），那两个"声明无图但画里有图"的帧放进 **CONTESTED** 桶，
**`expected=None`，只报告、绝不计分**。

### 3.6 实测（`studio/scripts/p46_chart_measure.py`，14 帧 × 每帧问两遍）

```
type_bar/f00060.png       expected=A       raw=['A', 'A'] letter=A 0.58s
type_bar/f00100.png       expected=A       raw=['A', 'A'] letter=A 0.63s
type_line/f00060.png      expected=B       raw=['B', 'B'] letter=B 2.09s
type_line/f00100.png      expected=B       raw=['B', 'B'] letter=B 0.43s
type_volume/f00060.png    expected=C       raw=['A', 'A'] letter=A 1.72s
type_volume/f00100.png    expected=C       raw=['A', 'A'] letter=A 0.63s
type_sparkline/f00060.png expected=D       raw=['B', 'B'] letter=B 1.96s
type_sparkline/f00100.png expected=D       raw=['B', 'B'] letter=B 0.66s
nochart/f00200.png        expected=E       raw=['E', 'E'] letter=E 2.01s
nochart/f00770.png        expected=E       raw=['E', 'E'] letter=E 2.15s
flat/flat0.png            expected=E       raw=['E', 'E'] letter=E 2.36s
flat/flat1.png            expected=E       raw=['E', 'E'] letter=E 2.16s
nochart/f00430.png        expected=<none>  raw=['E', 'E'] letter=E 0.71s
nochart/f00545.png        expected=<none>  raw=['A', 'A'] letter=A 0.49s

summary: {"asked": 14, "scored": 12, "unscored_no_ground_truth": 2,
          "unreadable": 0, "correct": 8, "recall": "8/12",
          "false_positives": "0/4", "not_reproducible": [],
          "wall_seconds": 28.01, "calls": 28,
          "per_frame_seconds_max": 3.237, "per_frame_seconds_median": 2.697}

CONTESTED (declares no chart, visibly contains one) — REPORTED, NOT SCORED:
  f00430.png: answered E      ← 漏掉了窗口里的迷你图表（真·漏检）
  f00545.png: answered A      ← 按图谱声明算假阳性，按画面算它是对的
```

| 指标 | 数字 |
|---|---|
| **召回**（12 个有地标的帧） | **8/12 = 66.7%** |
| **假阳性**（4 个确认无图的帧） | **0/4 = 0%** |
| **可复现性**（28 次调用逐字比对） | **0 处分歧** |
| **真实成本** | 28 次调用 **28.01 s**；单帧**逐帧求和** median 2.697 s / max 3.237 s |

⚠️ **两次错都落在视觉上重叠的那一对**：volume→答 A（柱状图），
sparkline→答 B（折线图）。这是**分类器的能力边界，不是标错的题**：
本项目的 volume 和 bar 本来就是同一个 mark。

### 3.7 片子上的普查（**量到了，但不能计分**）

28 帧（t=23…50s，每秒一帧），**全部 `expected=None`**：

```
  A (bar): 3      B (line): 4      C (volume): 2      E (no chart): 19
  sum of first-ask seconds = 8.84 | per-frame median = 0.31
  not reproducible: []          （56 次调用 0 处分歧）
```

⚠️ **19/28 答"没有图表"几乎肯定不是真相**——我看过那些帧，它们是期权看板，
满是蜡烛图和期权链表。**它们不在 `OPTIONS` 里，所以分类器只能说 E。**

### 3.8 为什么判 **C** 而不是 A

- 仪器**存在且被量过**：8/12、0/4、0 处分歧，测的是"图谱声明 → 画面"的正类。
- 但维度 7 要回答的是**这部片子里有几张图、什么类型**。
  - 片子的图表类型（蜡烛图、期权链、散点）**在本项目的 `CHART_TYPES` 里没有名字**；
  - 片子**没有标注语料**，所以 19 个 E **无法被判为错**。

⇒ **量到了，但填不进本项目的词汇表，也没法验证。**
这与 P37 对「转场」判 C 是**同一种形状**（"测出了一种转场"没有可填的类型名）。
⇒ **C**。

⚠️ 缺的东西要说清是**哪一种缺**：**仪器不缺，缺的是「片子的图表类型词汇」与
「片子帧的标注」——两者都是输入缺失，不是仪器缺失。**

---

## 四、维度 6（相机）：**仍是 B，但死因从假设变成了实测**

### 4.1 帧间差分够不够？——**不够，而且这次能说清差在哪**

P37 的死因是"需要光流/单应估计"。工单要求回答"帧间差分够不够"。

**差在哪，一句话**：`frame_difference` 只回答"整帧变没变"，
**它对"相机平移"和"画面中间出现一个矩形"给出完全相同的数字**。
只有把全局运动估出来再补偿，残差才分开。实测（见 §4.2 的守卫）：

```
object-only change -> shift=(  0,  0) frame_diff=2.995 explained=0.0000
```

⚠️ **这里不叫光流。** 本项建的是**全局平移估计（相位相关）+ 全局缩放搜索**，
它假设整帧只平移或只缩放；它对单个物体一无所知。

### 4.2 正类/负类的对照（在测试套件里，不只是在散文里）

一台只能返回 0 的仪器就是**自信的零**。所以先把植入的位移喂给它：

```
POSITIVE-CLASS CONTROL (real film frame, planted shift):
  planted(  0,  0) -> shift=(  0,  0) frame_diff=   0.000 residual=0.000 explained=0.0000
  planted(  3,  0) -> shift=( -3,  0) frame_diff=   4.804 residual=0.000 explained=1.0000
  planted(  0,  5) -> shift=(  0, -5) frame_diff=   5.845 residual=0.000 explained=1.0000
  planted( -7, 11) -> shift=(  7,-11) frame_diff=  14.860 residual=0.000 explained=1.0000
  planted( 40,  0) -> shift=(-40,  0) frame_diff=  20.874 residual=0.000 explained=1.0000
  object-only change-> shift=(  0,  0) frame_diff=   2.995 residual=2.995 explained=0.0000

CONTROL: planted ZOOM only (no translation) on a real film frame
  planted=0.95 -> recovered=1.05  expl_trans=0.1139  expl_sim=0.8960
  planted=0.97 -> recovered=1.03  expl_trans=0.1100  expl_sim=0.9271
  planted=1.03 -> recovered=0.97  expl_trans=0.1496  expl_sim=0.9224
  planted=0.96 -> recovered=1.04  expl_trans=0.11    expl_sim=0.92
```

（`recovered` 的 scale 取倒数，因为我的 warp 朝另一侧缩放；量级对得上。）
⇒ 纯平移残差 **0.000**；纯物体变化解释率 **0.0000**；纯缩放时 scale 项解释
**≈0.90** 而平移项只有 **≈0.11**。**仪器确实分得开。**

### 4.3 参考片实测（17 个采样点，t=2s…80s）

```
      t  frame_diff    dy    dx   expl_trans   scale  expl_sim
   2.00      3.8882     0     0       0.0000    1.00    0.0000
   8.00      1.3828     0     0       0.0000    1.00    0.0000
  12.00      7.0753     0     0       0.0000    1.00    0.0000
  18.00      3.6046     0     0       0.0000    1.00    0.0000
  25.00      0.1732     0     0       0.0000    1.00    0.0000
  30.00      0.7341     0     0       0.0000    1.00    0.0000
  35.00      0.0075     0     0       0.0000    1.00    0.0037
  40.00      0.3659     0     0       0.0000    1.00   -0.0001
  45.00      0.0165     0     0       0.0000    1.00   -0.0017
  52.00     15.2116     0     0       0.0000    1.01    0.0050
  53.00      1.1573     0     0       0.0000    1.00    0.0000
  54.00      5.0726     0     0       0.0000    1.00    0.0000
  58.00      0.2452     0     0       0.0000    1.00    0.0000
  62.00      0.2518     0     0       0.0000    1.00    0.0001
  70.00      2.0515     0     0       0.0000    1.00    0.0000
  75.00      0.0397     0     0       0.0000    1.00    0.0010
  80.00      0.9908     0     0       0.0000    1.00    0.0000
```

⇒ **全片 17 个采样点，平移解释率 0.0000；平移+缩放解释率 ≤0.005。**
帧间差本身从 0.0075（t=35s，几乎冻结）到 15.21（t=52s，立柱升起那段）。

### 4.4 ⚠️ 这**推翻了 P37 的一条判断**

P37 §2 写：「**片子确实有 3D 透视运动**（51–55s 段肉眼可见立柱升起），
所以这是「输入有但仪器没有」，不是「片子没有」」。

实测：t=52s 是全片帧间差最大的一处（15.21），而它
**既不是平移（0.0000）也不是缩放（0.0050）**。

⇒ 剩下的可能只有两种，**本项分不开**：
(a) 这是**物体/元素的运动**（柱子自己在升起），不是相机运动；
(b) 这是**投影性的相机环绕**（`camera.rotateY` 类），平移+缩放模型表达不了。

⚠️ **P37 的"肉眼可见"是对的，但把它读成"相机运动"这一步没有被像素支持。**
分不开的那一步需要**单应/特征对应 + RANSAC**，而 **py-3.12 下无 cv2**
（3.10 有 cv2 4.11 但无 pytest；工单 §三.11 要求这种情况在 3.12 里 skip 而不是撒谎）。

### 4.5 为什么仍是 **B**

- 仪器部分**建成并验证过**（§4.2）；
- 但"镜头运动 vs 物体运动"的**完整分离**仍缺单应模型；
- 且**"同样的相机语言"这个判据本项目仍然没有定义**（P16 §4 已记）。

⇒ **B**。缺的是：**一台单应估计器**（仪器），**外加一个"相机语言"的定义**（判据）。

---

## 五、维度 8（字体）：**仍是 B，三台仪器全灭**

### 5.1 为什么不用 VLM 问"这是衬线体吗"

那是一个**关于风格的判断**（"看起来像"），正是工单 §二.2 排除的形态。
所以先试**可复核的形状**。

### 5.2 仪器一：帧级笔画对比——**云重叠，不可用**

13 个 Windows 字体，**字体由写帧的代码选定**（P45 的对照做法），
同一版面、同一串文字、同一字号、同一颜色，**只换字体文件**：

```
font       class   stroke_contrast  row_mass_contrast     glyph_med  glyphs
georgia    serif            7.0000             4.1287     2.1600      94
georgiab   serif           11.3333             4.7169     1.7500      91
times      serif           11.7647             5.4801     1.6000      81
constan    serif            6.3333             5.8255     1.6000      93
cambria    serif            6.0000             3.2816     1.8500      92
pala       serif           10.0000             5.1479     1.7417     102
arial      sans            22.0000             5.9561     2.5000      85
segoeui   sans             6.3333             4.2619     2.8000      99
seguisb   sans             6.2500             4.4673     2.6800      99
trebuc     sans             5.2500             4.9171     2.7500      97
verdana    sans             7.6667             5.0871     2.8750      95
consola    mono             6.0000             4.4338     2.6000      94
cour       mono            12.0000             4.8386     2.0000      73

separation by stroke_contrast:
  serif {min 6.0  max 11.7647}  sans {min 5.25 max 22.0}
  gap_sans_min_over_serif_max 0.4463   overlapping: true
```

⚠️ `arial` 的 22.0 是**噪声**：`p10` 被抗锯齿碎片支配，与字体类别无关。

### 5.3 仪器二：字形级笔画对比——**分开了，但方向是反的**

隔离到单字形（去掉尺寸混合），`p90/p50` 的水平墨迹游程比：

```
separation by glyph_contrast_median:
  serif  n=6  min 1.60   max 2.16   mean 1.7836
  sans   n=5  min 2.50   max 2.875  mean 2.721
  gap_sans_min_over_serif_max 1.1574   overlapping: false
```

**云不重叠了——但 sans 整条云在 serif 上方。**
一个把 Arial 的笔画判得比 Georgia 更"有对比"的衬线检测器，
**不是弱检测器，是指错了方向的检测器**。

⚠️ **不发布。** 因为"它能分开"就发布它，正是 P17 说的
「一个可能对正确产物判断错误的判据，比没有判据更糟」。
这条**留在了代码里并被守卫断言**（`test_the_measured_font_negative_result_is_still_on_record`），
免得以后有人因为"它 work"就捡起来用。

### 5.4 仪器三：VLM 闭合问句——**有偏，不是没有**

问题（闭合，定义写在问题里，两个词回来）：

```
Look at the LETTERS in this image. Do their strokes end in small horizontal finishing strokes
(SERIF, as in a Times or Georgia face), or are the strokes plain and unadorned with no finishing
strokes (SANS SERIF, as in an Arial or Helvetica face)? Answer with exactly one word: SERIF or SANS.
```

在**字体由构造已知**的 11 张控制卡上打分（mono 被跳过：二分类问题对它没有正确答案）：

```
font/control_georgia.png    expected=SERIF  raw=['SERIF', 'SERIF']
font/control_georgiab.png   expected=SERIF  raw=['SERIF', 'SERIF']
font/control_times.png      expected=SERIF  raw=['SERIF', 'SERIF']
font/control_constan.png    expected=SERIF  raw=['SERIF', 'SERIF']
font/control_cambria.png    expected=SERIF  raw=['SERIF', 'SERIF']
font/control_pala.png       expected=SERIF  raw=['SERIF', 'SERIF']
font/control_arial.png      expected=SANS   raw=['SERIF', 'SERIF']   ← 假阳性
font/control_segoeui.png    expected=SANS   raw=['SERIF', 'SERIF']   ← 假阳性
font/control_seguisb.png    expected=SANS   raw=['SERIF', 'SANS']    NOT REPRODUCIBLE
font/control_trebuc.png     expected=SANS   raw=['SANS', 'SANS']
font/control_verdana.png    expected=SANS   raw=['SERIF', 'SERIF']   ← 假阳性

summary: {"scored": 11, "correct": 7, "recall": "7/11",
          "false_positive_serif_on_sans": "3/5",
          "missed_serif_answered_sans": "0/6",
          "not_reproducible": ["...control_seguisb.png"],
          "calls": 92, "per_frame_seconds_median": 0.564}
```

| 指标 | 数字 |
|---|---|
| 召回 | 7/11 = 63.6% |
| **sans 上的假阳性** | **3/5 = 60%**（Arial / Segoe UI / Verdana 全答 SERIF） |
| 漏检衬线 | 0/6 |
| 可复现性 | **1/11 帧两次回答不同** |

⚠️ **一个在 sans 上假阳性 60% 的衬线检测器是不能用的**——
它会把本项目自己声明为无衬线的字体报成衬线。

### 5.5 ⚠️ 附带发现，以及**为什么我不能拿它下结论**

对本项目自己的渲染与片子跑同一问句（**全部 `expected=None`**，真值未知）：

```
nochart/f00200.png  raw=['SERIF','SERIF']   ← 我们的 KPI 大数字
nochart/f00770.png  raw=['SERIF','SERIF']
type_bar/f00100.png raw=['SANS','SANS']  ×4
film/film_000.png   raw=['SANS','SANS']
film/film_006.png   raw=['SERIF', '<no ollama ... WinError 10055 ...>']
```

`design/tokens.ts` 声明的是
`FONT_NUM = '"Bahnschrift", "DIN Alternate", "Segoe UI", sans-serif'`。

⚠️ **分类器说我们的 KPI 数字是衬线体，而图谱声明的是无衬线栈。**
**但这台分类器在 sans 上的假阳性是 3/5，所以这条读数不能支持任何结论。**
**两个可能的解释都还开着**：`FONT_NUM` 栈在本机回落到了衬线字体；
或者分类器就是不准。**分不开——而分不开就不该说。**

⚠️ 另外注意 `film_006` 那一行：一次 `WinError 10055`（WSAENOBUFS）让第二次
调用变成 UNAVAILABLE。**它没有被当成一次"一致的回答"**，正是 `vlm_critic`
那条纪律在起作用。

### 5.6 为什么仍是 **B**

- 三台仪器全部实测失败，且**失败方式各不相同并已记录**；
- 缺的**不是"能不能问"，而是"一个 sans 假阳性足够低的分类器"**；
- 片子那侧还额外缺**字体的真值标注**（输入缺失）。

⇒ **B**。这是本项目**第十四次**接受"实测说不出想要的结果"。

---

## 六、维度 4（布局）：**仍是 B，而且死因与仪器无关**

P37 的死因原文：「对齐布局」需要一个**声明的参照框**；
参考片没有、我们也没有可比的对齐契约。

**核对结果：死因成立，且本项没有动它。**

- `studio/scripts/measure_frame.py` 在（仪器不是缺的）；
- `design/tokens.ts` 只有 `DESIGN_WIDTH=1920` / `DESIGN_HEIGHT=1080`，
  **没有 margin / safe-area / inset 的声明**（`grep -n "MARGIN\|SAFE\|PAD"` 无命中）；
- 参考片没有对齐契约；我们也没有。

⚠️ **我故意没有自己定一个参照框。** 工单 §二.3 引的正是 P16 的教训：
「自己写的守卫读自己的被测对象」。定一个框再拿它判片子，
就是**用我自己的输出去定义"对"**。

⇒ **B**，缺的是**参照框的声明**，不是仪器。
⚠️ 顺带一提：这与维度 8 的缺口是**同一个形状**——
两处都要"一个声明的对照物"，而两处都没有。

---

## 七、变异测试（`tests/test_p46_probe_instruments.py`）

工单 §三.9 要求：本项动了 `reference_probe`，必须配变异测试，
且守卫**绝不能依赖 ollama 在跑**。

新增守卫 `19 passed, 1 skipped`（skip 的是报告表格断言，报告当时还没写）。
全部 VLM 路径都走 `transport=` 注入或指向死端口 `http://127.0.0.1:1`，
**不开 socket、不加载模型**。

| # | 变异 | 期望 | 实测 |
|---|---|---|---|
| **M1** | 色彩：什么都没测到却判 A | 守卫红 | 见下 |
| **M2** | 色彩：verdict 写成常量 | 守卫红 | 见下 |
| **M3** | 色彩：判据不读测量值 | 守卫红 | 见下 |
| **M4** | 图表分类器：模型缺席仍报字母 | 守卫红 | 见下 |
| **M5** | 字体：忽略期望值 | 守卫红 | 见下（⚠️ **第一轮存活了**，见 §七.1） |

<details>
<summary>逐条 <code>-rf</code> 原始输出（点击展开）</summary>

### M1 — 色彩：无测量却判 A

```
$ python -m pytest tests/test_p46_probe_instruments.py -rf -q
# 变异前 sha256[:16] = 33b0cd53c7ce11e5   变异后 = 093acf15e14f7181   退出码 = 1
================================== FAILURES ===================================
________________ test_colour_is_b_when_no_colour_was_measured _________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000022A79DBB560>

    def test_colour_is_b_when_no_colour_was_measured(monkeypatch):
        """M1. An empty colour pass must not read as a measurement.
    
        This is the shape that would make dimension 3's B->A move a lie: the
        verdict would follow the PRESENCE of the code path, not the existence of a
        number. `adjudicate` is fed a ProbeResult whose measurements say the colour
        pass sampled nothing, and the verdict must be B.
        """
        res = rp.ProbeResult(path='<synthetic>', available=True,
                             stream={'nb_frames': 100, 'fps': 60.0,
                                     'width': 16, 'height': 16, 'has_audio': False},
                             measurements={'frames_measured': 100,
                                           'cuts_detected': 1,
                                           'density_ink_share': 0.5,
                                           'colour': {'frames_sampled': 0}})
>       assert rp.adjudicate(res)['色彩'] == rp.B, (
            'a colour pass that sampled ZERO frames was adjudicated A. That is the '
            'always-green shape: the verdict is following the code path, not the '
            'measurement.')
E       AssertionError: a colour pass that sampled ZERO frames was adjudicated A. That is the always-green shape: the verdict is following the code path, not the measurement.
E       assert 'A' == 'B'
E         
E         - B
E         + A

E:\Minimax-H3\tests\test_p46_probe_instruments.py:114: AssertionError
_________ test_a_failed_colour_pass_cannot_take_the_other_eleven_down _________

    def test_a_failed_colour_pass_cannot_take_the_other_eleven_down():
        """A broken colour channel must not become another dimension's verdict.
    
        P31 and P34 each lost a day to a pair of IDENTICAL exceptions being
        compared as agreement. So the failure is injected and the other eleven
        verdicts are asserted to be unchanged.
        """
        boom = RuntimeError('the colour decode fell over')
        res = rp.ProbeResult(path='<synthetic>', available=True,
                             stream={'nb_frames': 100, 'fps': 60.0,
                                     'width': 16, 'height': 16, 'has_audio': True},
                             measurements={'frames_measured': 100,
                                           'cuts_detected': 3,
                                           'density_ink_share': 0.5,
                                           'colour': {'frames_sampled': 0,
                                                      'error': str(boom)}})
        v = rp.adjudicate(res)
>       assert v['色彩'] == rp.B
E       AssertionError: assert 'A' == 'B'
E         
E         - B
E         + A

E:\Minimax-H3\tests\test_p46_probe_instruments.py:155: AssertionError
=========================== short test summary info ===========================
FAILED ::test_colour_is_b_when_no_colour_was_measured - AssertionError: a col...
FAILED ::test_a_failed_colour_pass_cannot_take_the_other_eleven_down - Assert...
2 failed, 18 passed in 6.43s
```

### M2 — 色彩：verdict 写成常量 `B`

```
$ python -m pytest tests/test_p46_probe_instruments.py -rf -q
# 变异前 sha256[:16] = 33b0cd53c7ce11e5   变异后 = 504d926a21e81584   退出码 = 1
================================== FAILURES ===================================
___________ test_colour_is_a_only_when_frames_were_actually_sampled ___________

    def test_colour_is_a_only_when_frames_were_actually_sampled():
        """The other side of M1: a real measurement must still reach A.
    
        Without this the fix would be to hard-code B and the dimension would be
        B forever — which is the "never red" failure wearing a cautious hat.
        """
        res = rp.ProbeResult(path='<synthetic>', available=True,
                             stream={'nb_frames': 100, 'fps': 60.0,
                                     'width': 16, 'height': 16, 'has_audio': False},
                             measurements={'frames_measured': 100,
                                           'cuts_detected': 1,
                                           'density_ink_share': 0.5,
                                           'colour': {'frames_sampled': 20,
                                                      'dominant': [252, 252, 252],
                                                      'dominant_share': 0.5}})
>       assert rp.adjudicate(res)['色彩'] == rp.A
E       AssertionError: assert 'B' == 'A'
E         
E         - A
E         + B

E:\Minimax-H3\tests\test_p46_probe_instruments.py:135: AssertionError
_______________ test_m2_a_constant_colour_still_reaches_a_here ________________

    def test_m2_a_constant_colour_still_reaches_a_here():
        """M2 is about what a MUTATION would do; this pins the unmutated behaviour.
    
        A colour measurement reaching A is the ONLY way dimension 3 becomes A, so
        the test that kills "always return A regardless" is `test_colour_is_b_when_
        no_colour_was_measured` above. This one exists so that killing M2 by making
        the verdict a constant B is ALSO caught: the constant must not be B.
        """
>       assert _verdict_for({'frames_sampled': 20, 'dominant': [10, 10, 12],
                             'dominant_share': 0.4}) == rp.A
E       AssertionError: assert 'B' == 'A'
E         
E         - A
E         + B

E:\Minimax-H3\tests\test_p46_probe_instruments.py:179: AssertionError
=========================== short test summary info ===========================
FAILED ::test_colour_is_a_only_when_frames_were_actually_sampled - AssertionE...
FAILED ::test_m2_a_constant_colour_still_reaches_a_here - AssertionError: ass...
2 failed, 18 passed in 6.47s
```

### M3 — 色彩：判据忽略测量值

```
$ python -m pytest tests/test_p46_probe_instruments.py -rf -q
# 变异前 sha256[:16] = 33b0cd53c7ce11e5   变异后 = 61144b829213f748   退出码 = 1
================================== FAILURES ===================================
________________ test_colour_is_b_when_no_colour_was_measured _________________

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x00000220792B73E0>

    def test_colour_is_b_when_no_colour_was_measured(monkeypatch):
        """M1. An empty colour pass must not read as a measurement.
    
        This is the shape that would make dimension 3's B->A move a lie: the
        verdict would follow the PRESENCE of the code path, not the existence of a
        number. `adjudicate` is fed a ProbeResult whose measurements say the colour
        pass sampled nothing, and the verdict must be B.
        """
        res = rp.ProbeResult(path='<synthetic>', available=True,
                             stream={'nb_frames': 100, 'fps': 60.0,
                                     'width': 16, 'height': 16, 'has_audio': False},
                             measurements={'frames_measured': 100,
                                           'cuts_detected': 1,
                                           'density_ink_share': 0.5,
                                           'colour': {'frames_sampled': 0}})
>       assert rp.adjudicate(res)['色彩'] == rp.B, (
            'a colour pass that sampled ZERO frames was adjudicated A. That is the '
            'always-green shape: the verdict is following the code path, not the '
            'measurement.')
E       AssertionError: a colour pass that sampled ZERO frames was adjudicated A. That is the always-green shape: the verdict is following the code path, not the measurement.
E       assert 'A' == 'B'
E         
E         - B
E         + A

E:\Minimax-H3\tests\test_p46_probe_instruments.py:114: AssertionError
_________ test_a_failed_colour_pass_cannot_take_the_other_eleven_down _________

    def test_a_failed_colour_pass_cannot_take_the_other_eleven_down():
        """A broken colour channel must not become another dimension's verdict.
    
        P31 and P34 each lost a day to a pair of IDENTICAL exceptions being
        compared as agreement. So the failure is injected and the other eleven
        verdicts are asserted to be unchanged.
        """
        boom = RuntimeError('the colour decode fell over')
        res = rp.ProbeResult(path='<synthetic>', available=True,
                             stream={'nb_frames': 100, 'fps': 60.0,
                                     'width': 16, 'height': 16, 'has_audio': True},
                             measurements={'frames_measured': 100,
                                           'cuts_detected': 3,
                                           'density_ink_share': 0.5,
                                           'colour': {'frames_sampled': 0,
                                                      'error': str(boom)}})
        v = rp.adjudicate(res)
>       assert v['色彩'] == rp.B
E       AssertionError: assert 'A' == 'B'
E         
E         - B
E         + A

E:\Minimax-H3\tests\test_p46_probe_instruments.py:155: AssertionError
=========================== short test summary info ===========================
FAILED ::test_colour_is_b_when_no_colour_was_measured - AssertionError: a col...
FAILED ::test_a_failed_colour_pass_cannot_take_the_other_eleven_down - Assert...
2 failed, 18 passed in 6.46s
```

### M4 — 图表分类器：模型缺席仍报字母

```
$ python -m pytest tests/test_p46_probe_instruments.py -rf -q
# 变异前 sha256[:16] = 171711c355fc59c5   变异后 = 22928242425180f5   退出码 = 1
================================== FAILURES ===================================
________ test_chart_probe_reports_unavailable_when_the_model_is_absent ________

tmp_path = WindowsPath('C:/Users/pc/AppData/Local/Temp/pytest-of-pc/pytest-211/test_chart_probe_reports_unava0')

    def test_chart_probe_reports_unavailable_when_the_model_is_absent(tmp_path):
        """M4, chart probe. A dead host must produce UNAVAILABLE, not a letter."""
        frame = _frame(tmp_path)
        got, why = chart.ask(frame, host=DEAD_HOST)
>       assert got is None, f'the chart probe answered {got!r} with no model running'
E       AssertionError: the chart probe answered 'E' with no model running
E       assert 'E' is None

E:\Minimax-H3\tests\test_p46_probe_instruments.py:220: AssertionError
=========================== short test summary info ===========================
FAILED ::test_chart_probe_reports_unavailable_when_the_model_is_absent - Asse...
1 failed, 19 passed in 6.44s
```

### M5 — 字体：忽略期望值

```
$ python -m pytest tests/test_p46_probe_instruments.py -rf -q
# 变异前 sha256[:16] = 9a74fdbf61e6d132   变异后 = 50fbbea20b727e05   退出码 = 1
================================== FAILURES ===================================
_____ test_font_probe_ignoring_the_expectation_scores_worse_than_reading ______

tmp_path = WindowsPath('C:/Users/pc/AppData/Local/Temp/pytest-of-pc/pytest-212/test_font_probe_ignoring_the_e0')

    def test_font_probe_ignoring_the_expectation_scores_worse_than_reading(tmp_path):
        """M5. A reader that always says SERIF must NOT score like a reader.
    
        \u26a0\ufe0f THIS TEST WAS WRONG THE FIRST TIME AND THE MUTATION PROVED IT.
        The original version re-implemented the comparison inline, so the mutation
        that rewrote `p46_font_measure.run`'s `ok` to `len(distinct) == 1` left
        the suite at **20 passed, exit 0** — a green run on a neutered criterion.
        That is P16's own lesson (`_analysis_artifacts`): *a calibration that
        tests a copy of the predicate is not a calibration*.
    
        So the test now calls `score_one`, the function the report actually calls,
        and asserts on the `correct` field that the report actually reads.
        """
        import p46_font_measure as fm
    
        always_serif = _answering({'*': 'SERIF'})
        serif = _frame(tmp_path, 'serif.png')
        sans = _frame(tmp_path, 'sans.png')
    
        on_serif = fm.score_one(serif, 'SERIF', times=1, transport=always_serif)
        on_sans = fm.score_one(sans, 'SANS', times=1, transport=always_serif)
    
        assert on_serif['correct'] is True, on_serif
>       assert on_sans['correct'] is False, (
            'the always-SERIF reader was marked CORRECT on a sans card. The '
            'criterion is ignoring the expected class — which is exactly mutation '
            f'M5, and this row is the only thing standing between it and the '
            f'report: {on_sans}')
E       AssertionError: the always-SERIF reader was marked CORRECT on a sans card. The criterion is ignoring the expected class — which is exactly mutation M5, and this row is the only thing standing between it and the report: {'path': 'C:\\Users\\pc\\AppData\\Local\\Temp\\pytest-of-pc\\pytest-212\\test_font_probe_ignoring_the_e0\\sans.png', 'expected': 'SANS', 'answers': ['SERIF'], 'raw': ['SERIF'], 'seconds': [0.001], 'correct': True, 'not_reproducible': False}
E       assert True is False

E:\Minimax-H3\tests\test_p46_probe_instruments.py:296: AssertionError
=========================== short test summary info ===========================
FAILED ::test_font_probe_ignoring_the_expectation_scores_worse_than_reading
1 failed, 19 passed in 6.41s
```

</details>

⚠️ **注意 M4 的性质**：它杀掉的是"**没有模型也能给答案**"。
这与工单 §三.4「别让探针的异常变成判定」是同一条纪律。

### 7.1 ⚠️ M5 第一轮**存活了**，而这才是本节最该记的事

第一轮跑五条变异时，前四条 KILLED，**M5 打印 `20 passed, exit 0`**——
守卫在一个被阉掉的判据上是绿的。

**原因**：我的 M5 测试**自己重写了一遍比较逻辑**（`run(...) == expected`），
而 M5 变异改的是 `p46_font_measure.run` 里的 `ok`。
**测试测的是判据的一份拷贝，不是判据。**

这正是 P16 守卫文件自己写着的那句：
*"a calibration that tests a copy of the predicate is not a calibration"*。
本项目把它写在 `tests/test_p16_*.py` 里，我又在另一个文件里重新犯了一次。

**修法不是换断言，是把判据变成可达的**：把打分逻辑抽成
`p46_font_measure.score_one()`，测试直接调它、断言它返回的 `correct` 字段。
重构后重跑五条：**M5 KILLED（1 failed, 19 passed, exit 1）**。

⚠️ 顺带暴露的第二个坑：重构把 `ok = (...)` 的缩进从 8 空格变成 4 空格，
我第一版变异脚本的锚点字符串因此**找不到目标**（`AssertionError: anchor not found`）。
**变异脚本自己坏了，而变异脚本坏了是静默的**——必须断言"变异确实改了文件"（本项的脚本里是 `assert before != after`），否则会以为变异跑过了。

---

## 八、⚠️ 我犯的错（这一节比数字重要）

| # | 错 | 怎么发现的 | 影响 |
|---|---|---|---|
| 1 | **选帧选了退出段**（`FRAME=140`，而 150 帧场景的 `exitStart=138`） | 逐帧量墨迹，发现 140 比 100 少 387,430 px | 若不查，分类器是在**半张图**上打分，8/12 这个数字作废 |
| 2 | **阴性样本里两张画布上真的有图**（`s02_dash`、`s03_columns`） | 逐帧看图 | 若不查，会**凭空造出 50% 假阳性率** |
| 3 | **字体对照语料的空集**：`scored_corpus()` 的注释被写进了 `if` 体里，语句只在 `mono` 分支可达，而 `mono` 被 `continue` 掉 ⇒ 语料恒空、汇总打印 `recall: 0/0` | 看到 `scored: 0` | **一个看着像结果的空集**。已加硬失败：`if not items: raise SystemExit` |
| 4 | **`NameError: name 's' is not defined`**（在 `probe()` 里把推导式变量 `s` 当成了 stream） | 防御性 `try/except` 捕到并写成 `colour.error` | **这正是那条防御的价值**：色彩维度报 B，其余十一个维度不受影响 |
| 5 | **`np.full_like(uint8, np.nan)`**：`compensate()` 的裁剪边框没写成 NaN，`~np.isnan` 选中了**每一个**像素 | numpy 的 `RuntimeWarning: invalid value encountered in cast` | 残差被边框稀释。修好后植入平移的残差从 0.847 变 **0.000** |
| 6 | **缩放搜索只能表达一半刻度**：`((h-nh)//2, ...)` 对 `s<1` 恒为负、`s>1` 的 paste 直接抛 `could not broadcast (734,1305) into (7,13)` | 植入缩放对照跑不通 | 一台表达不了自己一半刻度的缩放仪，会对**推轨**回答"没有相机运动" |
| 7 | **固定采样步长 `every=30`** 让 2 秒测试片只采到 1 帧 | `frames_sampled: 1` | 两秒的片和八十四秒的片看起来一样"被测过" |
| 8 | **注释里引用了一个不存在的文件**：`tests/test_p46_chart_probe.py` | 全量套件里 `test_comment_citations_resolve` 转红 | 那条守卫**正是为这个缺陷写的**（它自己的 docstring 讲的就是八个文件引用了一个不存在的 `tests/test_design_system.py`）。我在一处犯了它要抓的错，已改成真实路径 |
| 9 | **变异脚本自己的锚点失效**：重构把 `ok = (...)` 的缩进从 8 空格改成 4，第一版 M5 锚点找不到目标（`AssertionError: anchor not found`） | 脚本抛错才没静默 | 若那条断言写成"变异成功"，我就会**以为变异跑过了**。现在脚本里有 `assert before != after` 与 `assert sha(f) == before` 两条 |

⚠️ 第 5、6 两条是我**自己写的仪器里的 bug**，都是"红在错误的理由上"的近亲：
它们不会让红消失，它们会让**绿变成一个假数字**。

---

## 九、改动的文件清单

**新增（`studio/scripts/`）**
- `p46_chart_control.py` —— 同数据换类型的对照渲染；**自带惰性检测**并把 `area` 排除
- `p46_chart_probe.py` —— 强制单选的图表分类器（含 `transport` 注入缝）
- `p46_chart_measure.py` —— 图表普查驱动（正类/阴性/争议三分桶）
- `p46_font_probe.py` —— 字体仪器：两台几何统计（**均已失败，保留为证据**）+ VLM 闭合问句
- `p46_font_measure.py` —— 字体普查驱动
- `p46_camera_probe.py` —— 相位相关全局平移 + 缩放搜索 + 补偿残差

**改动**
- `studio/scripts/reference_probe.py` —— 新增 `decode_frames_rgb()` / `measure_colour()` /
  `_unquantise()`；`probe()` 接入并对失败做隔离；`adjudicate()` 的 `色彩` 改为读测量

**新增测试 / 文档**
- `tests/test_p46_probe_instruments.py`
- `docs/P46_PROBE_INSTRUMENTS.md`（本文件）

⚠️ **未改动**：`studio/src/**`（§3.2 的缺陷只报告）、`vlm_critic.py`、
`visual_qa.py`、`take_ranker.py`、`locked_fields.py`、`docs/P37_*`、`docs/UPGRADE_*`。
⚠️ `vlm_critic.py` 的判定逻辑**未发现 bug**，未改一行。

---

## 十、sha256 与磁盘纪律

### 10.1 sha256 与行尾（收尾实测）

⚠️ 每条毒变异之后都从**字节级快照**复原，并断言 sha256 回到原值
（变异脚本里是 `restore(f); assert sha(f) == before`）。
本项自己的脚本也断言"变异确实改了文件"（`assert before != after`）——
否则变异脚本自己坏掉时是**静默**的（见 §7.1 末尾）。

| 文件 | 字节 | CRLF / LF | sha256[:32] |
|---|---|---|---|
| `studio/scripts/reference_probe.py` | 22634 | 0 / 507 | `33b0cd53c7ce11e58c19132b2c3a0fa9` |
| `studio/scripts/p46_chart_control.py` | 11190 | 0 / 246 | `40317cf3207efc1a6910196d552361b3` |
| `studio/scripts/p46_chart_probe.py` | 10065 | 0 / 225 | `94d9000849fa545c569d9c5785afa7cf` |
| `studio/scripts/p46_chart_measure.py` | 7909 | 0 / 185 | `bb2b3482eead73439b1598bf0c658d7d` |
| `studio/scripts/p46_font_probe.py` | 14992 | 0 / 364 | `728750adb23332606d2dc4288639c572` |
| `studio/scripts/p46_font_measure.py` | 8947 | 0 / 202 | `9a74fdbf61e6d132c2a13556e0138b01` |
| `studio/scripts/p46_camera_probe.py` | 13461 | 0 / 294 | `51113e80a4ac13edd6c0e940318bc7db` |
| `tests/test_p46_probe_instruments.py` | 21241 | 0 / 453 | `88cf1cf1479e73e5bd9751fe9cbf54f9` |

⚠️ **行尾全部为 LF，CRLF 计数为 0**——工单 §三.7 记着指挥窗口曾因此毁过 2049 行
（`read_text` + `write_text` 把纯 CRLF 翻成 LF）。本项**只新建、不重写**
任何既有文件的行尾；`reference_probe.py` 的改动是用 `Edit` 做的定点替换。
⚠️ `docs/P46_PROBE_INSTRUMENTS.md` 用 `write_bytes` 写入并复核
**U+FFFD 计数 = 0**（工单 §三.10）。

### 10.2 磁盘

| 造了什么 | 在哪 | 大小 | 处置 |
|---|---|---|---|
| 类型对照渲染 5 类型 × 2 帧 | `out/p46_probe/ours/` | 11 M | **保留**（`out/` 已被 gitignore；删了要重渲 20 s） |
| 参考片抽帧 28 张 | `out/p46_probe/film/` | 12 M | **保留** |
| 无图 / 争议渲染 4 帧 | `out/p46_probe/nochart/` | 3.3 M | **保留** |
| 字体控制卡 13 张 | `out/p46_probe/font/` | 816 K | **保留**（也可由 `p46_font_probe.py` 重建） |
| 纯色阴性帧 2 张 | `out/p46_probe/flat/` | 24 K | **保留**（ffmpeg 合成，随时可重建） |
| 三份测量 JSON | `out/p46_probe/*.json`、`camera/` | 32 K | **保留** |
| **合计** | **全部在 E: 盘（仓库 `out/`）** | **≈ 26 M** | |

⚠️ **C: 盘零增长，实测而非推断**：`still.mjs` 的 bundle 落在
`%TEMP%/remotion-*`。该目录现有 13 个 `remotion-v4.0.529-assets*`
与 1 个 `remotion-webpack-bundle-*`，**mtime 全部落在 2026-10-02 ~ 10-10 14:47**，
而本项的 21 次渲染发生在 **2026-10-11 02:12–02:35** ——
**今天没有任何一个新 bundle 留下**，`still.mjs` 自己清了。
（那 13 个是**别人/别的会话**的，**本项没有删它们**。）

⚠️ **未触碰** `studio/.remotion/water-renewal-bundle`（工单明说不是我的）。
⚠️ **未把任何帧/图复制进仓库**（本项目从不跟踪媒体，`git status` 见 §10.3）。
⚠️ `out/p45_vlm/**`、`out/p13_probe/**`、`out/*.mp4` 全程**只读**。

### 10.3 交付时的仓库状态（`git status --porcelain`）

```
 M studio/scripts/reference_probe.py
?? docs/P46_PROBE_INSTRUMENTS.md
?? studio/scripts/p46_camera_probe.py
?? studio/scripts/p46_chart_control.py
?? studio/scripts/p46_chart_measure.py
?? studio/scripts/p46_chart_probe.py
?? studio/scripts/p46_font_measure.py
?? studio/scripts/p46_font_probe.py
?? tests/test_p46_probe_instruments.py
```

⇒ **本项只碰了这 9 个文件**，`studio/src/**` 一行未改。
提交时**只 stage 上列路径**（显式路径，未用 `-A`），**提交但不推送**。

## 十一、全量测试

```
$ cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q \
      --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py
```

| 轮次 | 结果 |
|---|---|
| 基线（开工时，HEAD `9a53c9f`） | **719 passed, 4 skipped** |
| 加了 P46 之后，第一轮 | **2 failed, 737 passed, 4 skipped** |
| 修掉 §八 第 8 条之后（最终） | ****739 passed, 4 skipped** (517.30 s)** |

⚠️ **第一轮那两条红，性质不同，必须分开说**：

**（1）`test_comment_citations_resolve` —— 是我的错**（§八 第 8 条）。
我在两处 docstring 里写了 `tests/test_p46_chart_probe.py`，
而真实文件名是 `tests/test_p46_probe_instruments.py`。
**这条守卫的 docstring 讲的正是"八个文件引用了一个不存在的
`tests/test_design_system.py`"—— 我在一处重新犯了它要抓的错。**
已改；单独重跑 **5 passed**。

**（2）`test_p14_render_entry_points::test_every_known_flag_still_renders`
—— 不是本项的改动**，红在一个**并发 socket 耗尽**上：

```
E  Symbol(kError): Error: connect ENOBUFS 127.0.0.1:65531 - Local
E    at internalConnect (node:net:1169:16)
E    errno: -4060, code: 'ENOBUFS', syscall: 'connect', port: 65531
E  assert 1 == 0
E:\Minimax-H3\tests\test_p14_render_entry_points.py:323: AssertionError
```

⚠️ **我没有因为"单跑是绿的"就把它记成环境问题**——那正是
「红在错误的理由上不算通过」。所以本项**重跑了整轮整轮**。
单独重跑该文件：**10 passed in 91.84s**（它要起 node 渲染）。
⚠️ 与 P45 记录过的 `WinError 10055` / WSAENOBUFS **同一族**：
本机在连续本地 socket 连接下会耗尽发送缓冲区。

## 十二、⚠️ 留给下一个人的四件事

1. **`studio/src` 有一个真缺陷待修**（§3.2）：`defaultArea` 不可达，
   `c02_line` 与 `c03_area` 的填充与名字相反。本项只读，故只报告。
2. **图表分类器在 `volume`↔`bar`、`sparkline`↔`line` 上混淆**（8/12 的两次错）。
   要修就得改问题的选项描述，而改选项描述就是在改判据——**需要人决定**。
3. **片子的图表词汇**（蜡烛图、期权链、散点）在本项目没有类型名。
   要么扩 `CHART_TYPES`，要么接受维度 7 永远是 C。**需要人决定。**
4. **相机维度的下一步是单应估计**，而 **py-3.12 无 cv2**。
   工单 §三.11 的处理是"用 3.10 脚本驱动、3.12 里 skip 而不是撒谎"——
   **本项没有走到那一步**，所以没写那条 skip。**如果要做，先解决这个依赖问题。**

> ⚠️ **本项不裁定 `premium`。** §2.5 那张并排表只说明两边的数可以在同一个
> 单位下被读出来；**底色冲突怎么处置是 P37 §3 留给人的决定**。
> §7.5 那条"我们的 KPI 数字被判成衬线体"同样**不能支持任何结论**——
> 那台分类器在 sans 上的假阳性是 3/5。