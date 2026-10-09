# P28 — `c08_volume` 的顶部裁切：成因与修复

> 执行 agent 交付。**本文件只报告测量，不做放行/退回裁定**（工单第三节：执行与裁定分离）。
> 所有数字均为本次实测。凡未测的一律标注「未测」，没有第二类数字。

---

## 零、基线与环境

| 项 | 值 | 来源 |
|---|---|---|
| HEAD（开工） | `be7ce2f` | `git log` |
| 开工基线（**未改动的树**） | **1 failed, 538 passed, 4 skipped**（378.03s） | 实测，标准跑法 |
| 收尾基线（第 1 次） | **552 passed, 4 skipped**（386.88s），**0 failed** | 实测，标准跑法 |
| 收尾基线（第 2 次） | **1 failed, 551 passed, 4 skipped**（421.60s） | 实测，标准跑法 |
| 三个 sha256（开工 / 收尾） | `7e7d586a` / `91e3463c` / `120b11da` — **三个全部 MATCH** | 实测（字节计数） |

### ⚠️ 三次跑里有两条不同的 failed，**都在开工基线那一遍就出现过**，且都不是本项的改动

| 跑次 | 树 | 结果 | 那一条 failed |
|---|---|---|---|
| 1（开工） | **未改动** | 1 failed, 538 passed | `test_every_known_flag_still_renders` |
| 2（收尾） | 已改 | **552 passed, 0 failed** | — |
| 3（收尾复跑） | 已改 | 1 failed, 551 passed | `test_a_finished_render_leaves_no_bundle_directory_behind` |

两条都是同一个签名：`render.mjs` 起 Chrome 后 DevTools 的 WebSocket 连不上，
`Unable to close browser` + `ErrorEvent … connect ENOBUFS 127.0.0.1:65531`。
**失败发生在 `render.mjs` 启动浏览器的阶段，在本项改的两个文件之外。**

**三条独立证据说明它是环境抖动，不是我引入的：**

1. 第 1 遍跑的是**未改动的树**，同一条签名已经红了；
2. 单独重跑，两条都过：`test_every_known_flag_still_renders` **2/2 passed**（62.05s / 59.63s），
   `test_a_finished_render_leaves_no_bundle_directory_behind` + 前者同跑 **2 passed**（61.87s）；
3. 第 2 遍收尾跑**一条都没红**，同一份代码。

**本项未改 `render.mjs`、未改 flag 解析、未改任何渲染入口。**
本项的判据不在这里 —— 13 条新守卫在三次跑里**全部通过**，一次也没红过。

---

## 一、⚠️ 复核成因：**工单给的成因不成立**

工单第二节把成因定位在 `ChartFrame.tsx:201` 的 `top` 与 `:334` 的标题 `top: plot.y - 34 * s`，
并说「其余八张图只是靠 `showValues` 把 `top` 抬到 46 恰好掩盖了它」。

**逐条实测之后，这个结论不成立。**

### 1.1 算式本身是对的，但它描述的不是 B-1

`opts.showValues=false` 时 `top = 18*s`，标题落在 `plot.y - 34*s = -16*s` —— **确实是负值**。
`offsetY` 实测为 **0**（`s = scaleFor(1920,1080) = 1`，`DESIGN_HEIGHT*s = 1080 = comp.height`，
故 `offsetY = max(0,(1080-1080)/2) = 0`；`CameraRig` 只发出 `perspective(1600px)`，
没有 3D 变换时它是恒等变换，实测其余八张图修前修后逐字节相同可反证）。

**但那个 `-16` 从来没有到达过画面边缘。** `ChartFrame` 画在一个带内边距的盒子里
（`padding: ${SPACE.lg * s}px ${SPACE.xl * s}px`，`SPACE.lg = 40`），
所以标题的**画面**坐标是 `40*s + (18-34)*s = 24*s > 0`。
对任何画幅都成立：`offsetY ≥ 0`，`screen_y ≥ (40-34)*s = 6*s > 0`。

**实测（`c02_line`：图谱显式写 `showValues: false` 且 `axisLabel: 'RETENTION COHORT %'`）**：

| | row 0 像素 | 首行有内容 | clipping | safe_area |
|---|---|---|---|---|
| `c02_line` f225 | **0** | **30** | **PASS** | **PASS** |
| `c03_area` f375（同样 showValues=false + axisLabel） | **0** | **30** | **PASS** | **PASS** |

⇒ **标题分支确实渲染、确实画在 `y = -16`，而它从未被切。** 工单描述的「掩盖」在这半张图上不存在。

### 1.2 `c08_volume` 上被切的东西**不是标题**

- `c08_volume` 的图谱**没有设 `axisLabel`** ⇒ `option()` 取默认 `''` ⇒ `:330` 那个分支**根本不渲染**。
  （P27 的 agent 当时报「`axisLabel` 置空后该文本仍在」，与本条一致。）
- 行 0 的 356 px **跨列 1146–1790**；而 `axisLabel` 挂在 `left: 0`（画面 x ≈ 64）。**位置对不上。**
- 把 row 0 裁下来放大看：**是柱子**，不是字。列 1750 上从行 0 一直到行 607 是一个
  连续的 `(49,49,50)` 色块（`PALETTE.column`），宽度 89 px —— 就是一根柱子的宽度。

### 1.3 `showValues` **并不掩盖** B-1

用 `still.mjs` 无损渲两个探针图谱（改动后先断言图谱内容再渲）：

| 图谱 | row 0 像素 | clipping | safe_area |
|---|---|---|---|
| `c08_volume` 原样（`baseline=40`, `showValues=false`） | **356** | **FAIL** | **FAIL** |
| **探针 B：加 `showValues: true`**（只改这一个键） | **175** | **FAIL** | **FAIL** |

⇒ **`showValues=true` 一样 FAIL。** 工单「其余八张图靠 showValues 抬到 46 恰好掩盖」的模型被推翻。

### 1.4 ✅ 真正的成因（实测，且可复算）

**`VolumeBars` 把柱子挂在 baseline 上，而 y 轴的 domain 只按 `values` 拟合。**

- `types.tsx` 的 `VolumeBars`：柱顶 `f.yOf(zero + v*p)`、柱脚 `f.yOf(zero)`，`zero = baseline = 40`。
  ⇒ 柱子实际画到的数据值是 **58..136**。
- `Chart.tsx` 交给 frame 的 `values` 是 **18..96** ⇒ `fitDomain` 给出 **[0, 99.84]**，
  `niceTicks` 给出 **0/20/40/60/80**。
- **画面证据**：`c08_volume` f1125 的 y 轴标签实测只有 **0 / 20 / 40**（0/60/80 在行 384/230/58），
  最高一条刻度是 80 —— **轴声称的量程止于 ~100，柱子却画到 136**。
- 于是最高的几根柱子的顶端落在 plot 顶边之上，其中四根越过画面上边缘。

这正是 `ChartFrame.tsx:20-21` 自己写下的那个失败形状：「a mark therefore cannot accidentally use a
different domain from the axis it is drawn against — the failure that makes a chart readable and wrong
at the same time.」

**决定性单变量实验**（同一帧、同一图谱，只动 `baseline` 一个键）：

| 图谱 | row 0 | clipping | safe_area |
|---|---|---|---|
| 原样（`baseline: 40`） | **356** | FAIL | FAIL |
| **探针 A：删掉 `baseline`** | **0** | **PASS** | **PASS** |

---

## 二、修法与理由

**改动两处，`Chart.tsx` +15 行、`ChartFrame.tsx` +28/−3 行。**

1. `ChartFrame` 新增一个可选 prop `domainValues`，**只**喂给 `fitDomain`
   （`const domainExtent = domainValues ?? values;`），其它任何量都看不到它。
2. `Chart.tsx` 在 volume 且图谱设了 `baseline` 时传 `baseline + values`。

**为什么不直接改 `top`（工单的 A/B/C 三案）**：因为 `top` 不是缺陷。
把 `showValues=false` 的 `top` 从 18 抬到 34+ 会改变 `plot.h` ⇒ 改变 **c02/c03/c04/c06/c07/c08/c09 七张图**的样子，
而换不到任何一行像素的变化（1.1 已实测）。**本项目拒绝「悄悄改画面」，故不动 `top`、不动 `headroom`、不动 `showValues` 语义、不动任何视觉常数。**

**为什么不改在 mark 里**：frame 拥有 domain（`ChartFrame` 自己的注释），是它交出了一个错的 domain。
把 domain 补齐是**恢复**既有不变量，不是新增一条。

### ⚠️ 它**确实改变画面**——而且无法避免

`c08_volume` 的轴刻度由 **0/20/40/60/80** 变为 **0/50/100**，柱高按真实量程重算。
这不是副作用而是修复本身：一个画到 136 却只标到 100 的图，不可能既正确又保持原样。
**其余九张图不受影响**，实测见第三节。

### ⚠️ 我自己踩的一次坑（如实记录）

第一版把 `baseline` 直接折进 `Chart.tsx` 的 `values` memo。**结果更糟**：那个 memo 同时是
**mark 的数据**，于是 `<VolumeBars values={values}>` 拿到 58..136，再自己加一次 baseline ⇒ 柱顶跑到
`yOf(2*40 + v)`。实测柱顶落在 **v+80**，轴仍止于 ~141，**行 0 仍有 350 px，仍然 FAIL**。
是渲染取证（不是读代码）把它抓出来的：探针打印的柱顶位置反解出的数据值恰好是 `v + 80`。
**这就是 `values` 与 `domainValues` 必须分开的理由**，也写进了 prop 的注释里。

---

## 三、渲染取证（`still.mjs` 无损，判据用出货的 `visual_qa.rule_clipping` / `rule_safe_area`）

同一图谱、同一帧，修前修后各渲一次；「逐字节相同」是 PNG 的 sha256。

| 帧 | scene | showValues | 修前=修后 | row0 修前 | row0 修后 | 上边距 修后 | clipping 修前→修后 | safe_area 修前→修后 |
|---|---|---|---|---|---|---|---|---|
| f00075 | c01_bar | true | **逐字节相同** | 0 | 0 | 58 | PASS→PASS | PASS→PASS |
| f00225 | c02_line | false | **逐字节相同** | 0 | 0 | 30 | PASS→PASS | PASS→PASS |
| f00375 | c03_area | false | **逐字节相同** | 0 | 0 | 30 | PASS→PASS | PASS→PASS |
| f00525 | c04_slope | false | **逐字节相同** | 0 | 0 | 82 | PASS→PASS | PASS→PASS |
| f00675 | c05_bubble | true | **逐字节相同** | 0 | 0 | 160 | PASS→PASS | PASS→PASS |
| f00825 | c06_heatmap | false | **逐字节相同** | 0 | 0 | 58 | PASS→PASS | PASS→PASS |
| f00975 | c07_rank | false | **逐字节相同** | 0 | 0 | 347 | PASS→PASS | PASS→PASS |
| f01060 | c08_volume | false | 不同 | 0 | **0** | 321 | PASS→PASS | PASS→PASS |
| f01090 | c08_volume | false | 不同 | **178** | **0** | 250 | **FAIL→PASS** | **FAIL→PASS** |
| f01120 | c08_volume | false | 不同 | **356** | **0** | 93 | **FAIL→PASS** | **FAIL→PASS** |
| **f01125** | **c08_volume** | false | 不同 | **356** | **0** | **93** | **FAIL→PASS** | **FAIL→PASS** |
| f01150 | c08_volume | false | 不同 | **356** | **0** | 93 | **FAIL→PASS** | **FAIL→PASS** |
| f01180 | c08_volume | false | 不同 | **356** | **0** | 93 | **FAIL→PASS** | **FAIL→PASS** |
| f01195 | c08_volume | false | 不同 | 0 | 0 | 无内容 | UNVERIFIABLE→同 | UNVERIFIABLE→同 |
| f01275 | c09_sparkline | false | **逐字节相同** | 0 | 0 | 63 | PASS→PASS | PASS→PASS |
| f01650 | c10_bar_long | true | **逐字节相同** | 0 | 0 | 58 | PASS→PASS | PASS→PASS |

- **九张未设 baseline 的图：16 帧里 9 帧逐字节相同，其余 7 帧是 c08 自己的。零一张被改坏。**
- **`clipping` 与 `safe_area` 双双转 PASS** ✅（c08 的 5 个失效帧全部转 PASS）。
- f01195 是 c08 的退场帧，修前修后**都**是 UNVERIFIABLE（画面近全黑，`palette_mask` 找不到内容）。
  **那是 B-2，不是本项**，未动。

---

## 四、守卫：`tests/test_p28_volume_domain_covers_baseline.py`（13 条）

判据一律来自 **React 真实渲染出的 markup**（`renderToStaticMarkup` + `<Player>`，无 bundle、无 Chrome，
与 `test_chart_baseline_is_read.py` 同一套已验证的 harness），**没有一条断言源码里出现某个常数**。

三条判据，分别由渲染结果独立算出：

1. **`_outside_picture`** —— 没有任何 mark 画到画面上边缘之上。上边缘位置从 markup 自己的
   `padding` 读出（不写死 `SPACE.lg`，否则改间距会悄悄移动判据）。
2. **`_outside_frame_box`** —— 没有柱子画在 frame 自己的盒子（chart y = 0）之上。**不依赖间距。**
3. **`_axis_scale`** —— 柱高必须等于「轴的像素比例 × 值」。比例由**两个刻度标签的位置反解**，
   不重新实现 `scale.ts`（重实现会让两份布局各走各的而两边都还绿着）。

**`showValues` 两种取值都断言**（`@pytest.mark.parametrize`）：该开关选 headroom hence 选 domain。
对未修复的源码实测：`false` 半边有 **6 根**柱子出画、`true` 半边有 **2 根** —— **两边都红**。

另含：交付图谱与夹具的绑定（`test_the_delivered_graph_ships_the_scene_this_file_measures`）、
`baseline=0` 与不设 baseline 必须渲染一致（**修复的爆炸半径**）、
`baseline=90` 的放大版（防止判据被调成只对 40 有效）、
以及**判据能说「不」**：`PRE_FIX` 是**本探针在 HEAD 上实测**的修复前几何，
两条判据必须都拒绝它。

---

## 五、变异结果

**每条都先断言落地（打印 MUTATION LANDED 的文件名），收尾核对 sha256 复原。**
`-rf` 原始输出逐条贴在 5.1。

| # | 变异 | 期望 | 结果 | 红在哪个断言 |
|---|---|---|---|---|
| **M0** | 把修复退回：`domainExtent = values` | 红 | **红（5 项）** | `test_no_volume_bar_is_drawn_outside_the_picture[false]` 与 `[true]`、`..._above_the_frame_box[false/true]`、`test_a_large_baseline...` |
| **M1** | **工单字面那条**：`top` 改回 18（无条件） | 红 | **🟡 存活（13 passed）** | — 见下 |
| **M2a** | 源码：让缺陷**只在 `showValues=true`** 时出现 | 红 | **红（2 项）** | `..._outside_the_picture[showValues=true]`、`..._above_the_frame_box[showValues=true]` |
| **M2b** | M2a + **守卫裁成只测 `showValues=false`** | 绿（证明裁剪版是瞎的） | **绿（9 passed）** | — |
| **M3** | 判据被阉：`assert True or not offenders` | 红 | **红（1 项）** | `test_no_assertion_in_this_file_is_neutered` |
| **M3b** | 反向阉：`assert not offenders or True` | 红 | **红（1 项）** | 同上 |
| **M3c** | `assert not not offenders` | 红 | **红，但无效变异** | 红在真判据上，但**它并没有被阉**（有 offender 时仍会红），不算杀 |

### ⚠️ M1 存活：**这是真阴性，不是守卫的漏洞**

工单要求「如果明天有人把 `top` 改回 18，答案必须是红」。**实测是绿。**
**因为 `showValues=false` 现在用的就是 18**（`top = (opts.showValues ? 46 : 18) * s`），
而 B-1 在 18 下是活的（就是它造成的）。**M1 没有改变任何与 B-1 有关的东西。**
把它改成红，等于给一个不存在的缺陷写守卫，并顺带把七张图的样子改掉。

**守卫真正回答的是 M0：「如果明天有人把这次修复退回去，会怎样？」——红，红在正确的断言上。**
M1 的存活连同 1.1/1.2/1.3 的像素证据一起，是**工单成因需要更正**的记录。

### ⚠️ M3 第一版也存活过（如实记录）

元守卫第一版只认「整个 test 是布尔常量」，而 `assert True or X` 解析成 `BoolOp` 不是 `Constant`
⇒ **漏过，13 passed**。这与 P27 第三次变异命中的是同一族失效（靠变异发现，不是靠读代码）。
改成结构化判据（test 自身是布尔常量，或某个 `or` 的操作数是布尔常量）后，
M3 与 M3b 都在**正确**的断言上被杀。**「守卫已覆盖」没被变异证过之前等于没说。**

---

## 六、⚠️ 操作失误（如实记录）

1. **第一版修复把 baseline 加了两次**，比不修更糟（行 0 只从 356 降到 350）。是渲染取证抓住的。
2. **测量脚本按文件名做 key**，`probeA` 与 `probeB` 的 `f01125.png` 互相覆盖，
   我一度把 probeB 的数字当成 probeA 的报出来。改成按目录限定 key 后重测。
   —— 与工单记的「四次 `still.mjs` 写同一个目录」同一族，只是发生在我的量具里。
3. **`PRE_FIX` 夹具我先填了修复后的刻度位置**（自己抄错了对象），于是 `_axis_scale` 读出 6.49 而不是 9.19。
   改成**真把源码切回 HEAD 跑一遍探针**把几何抓下来。**这就是「造 contrived 输入」的反面教材。**
4. 元守卫第一版被 M3 穿过（见上）。
5. 变异脚本的锚点我按 CRLF 写，而守卫文件是 LF ⇒ 两次 `AssertionError: anchor occurs 0/4 times`。
   两次都在 `finally` 里复原并核对了 sha256，**树未被污染**。
6. **收尾复跑时守卫突然 3 条红**，我一度以为代码回退了。**不是**：`tail` 报
   `No space left on device`。见第七节 —— **C: 盘被别人写满了**，不是本项造成的。
   盘恢复后同一条命令 **13 passed**。

---

## 七、磁盘纪律

- 全程工作区 **`E:\p28_work\`**（E: 盘）。`REMOTION_SCRATCH_DIR=E:/p28_work/bundle`，bundle 全落 E: 盘。
- **未写入 `studio/.remotion/bundle`**（收尾复查为空目录）；`studio/` 下无残留 `__probe*` 文件。
- `out/p13_probe/**` 与 `out/*.mp4` **只读**：`git status out/` 为空，`charts_demo.mp4` 未改动。
- 收尾删除 `E:\p28_work\`（含 before/after/probeA/probeB/snapshot/mutsnap/mutations 全部产物）。

### ⚠️ 但 **C: 盘在本项期间被写满到 0 字节可用** —— **不是本项造成的，需要指挥/用户处置**

收尾复跑时报 `No space left on device`，守卫因此假红 3 条。实测定位：

| 位置 | 大小 | 归属 |
|---|---|---|
| `%TEMP%\tmp.2F0Q9oojWC\data\ollama` | **20.2 G** | **别的任务**，非本项 |
| `%TEMP%\tmp.2F0Q9oojWC\data\vibevoice-test` | **18.8 G** | **别的任务**，非本项 |
| `%TEMP%\DiagOutputDir` | 7.9 G | **工单第四节明令不得动**，未动 |
| `%TEMP%\wsl-crashes` | 10.7 G | 非本项，未动 |
| `%TEMP%\trivy-*`（7 个） | 9.4 G | 非本项，未动 |
| **本项自己在 C: 的全部 footprint** | **< 100 MB**（`tsx-pc` 4.7 MB + `pytest-of-pc` 25.8 MB + 若干 puppeteer profile） | 本项 |

那 39 GB 的目录创建于 **14:30**，与我并行存在的另一个任务所有（内容是 ollama 模型与
vibevoice 会议音频测试数据，含 `meeting_140.m4a` / `create_meeting.sql`）。
**我没有删它** —— 那是别的任务的数据，删掉等于毁掉我不了解的工作。

**我只删了本项自己的两个临时目录**（`pytest-of-pc`、`tsx-pc`，合计约 30 MB，都是可再生的）。
随后那个并行任务自己清掉了目录，C: 恢复到 **40.2 GB 可用**，守卫随即 **13 passed**。

⚠️ **上报**：这台机器的 `%TEMP%` 有 **80.8 G / 37 万文件**，其中至少 **37 G** 是与本项目无关的
可再生/一次性数据（`trivy-*`、`wsl-crashes`、`tmp.*`）。**本项无权处置，请指挥或用户决定。**
本项目自己的历史教训（`still.mjs` 注释记的「125 个 render 堆到 58 GB 填满系统盘」）
说明这个盘是反复被同一类事故填满的，值得单独立一项。
  `out/` 下未新增任何文件。

---

## 八、本项**没有**做的事

- **没有动 `top`、`headroom`、`showValues` 的语义或任何视觉常数** —— 工单第四节明令，且 1.1 证明动了也无用。
- **没有动 B-2（末帧近黑）**：f01195 的 UNVERIFIABLE 照旧，是设计后果。
- **没有动 B-3（冻结 482 帧）**。
- **没有碰** `visual_qa.py` / `frame_baseline.py` / `render.mjs` / `docs/UPGRADE_PROGRESS.md` /
  `docs/UPGRADE_MASTER_PLAN.md` / `studio/public/jobs/**`。

### 5.1 `-rf` 原始输出（逐条）

**M0** — 把修复退回：`domainExtent = values`  →  **RED (5)**

```
FAILED ::test_no_volume_bar_is_drawn_outside_the_picture[showValues=false] - ...
FAILED ::test_no_volume_bar_is_drawn_outside_the_picture[showValues=true] - A...
FAILED ::test_no_volume_bar_is_drawn_above_the_frame_box[showValues=false] - ...
FAILED ::test_no_volume_bar_is_drawn_above_the_frame_box[showValues=true] - A...
FAILED ::test_a_large_baseline_that_would_have_pushed_the_bars_off_is_covered
5 failed, 8 passed in 9.76s
```

**M1** — **工单字面那条**：`top` 改回 18（无条件）  →  ****SURVIVED — 13 passed****

```
13 passed in 11.09s
```

**M2a** — 源码：让缺陷**只在 `showValues=true`** 时出现  →  **RED (2)**

```
FAILED ::test_no_volume_bar_is_drawn_outside_the_picture[showValues=true] - A...
FAILED ::test_no_volume_bar_is_drawn_above_the_frame_box[showValues=true] - A...
2 failed, 11 passed in 9.05s
```

**M2b** — M2a + 守卫裁成只测 `showValues=false`  →  **GREEN (9 passed) — proves the trimmed guard is blind**

```
9 passed in 6.49s
```

**M3** — 判据被阉：`assert True or not offenders`  →  **RED (1)**

```
FAILED ::test_no_assertion_in_this_file_is_neutered - AssertionError: assert ...
1 failed, 12 passed in 9.12s
```

**M3b** — 反向阉：`assert not offenders or True`  →  **RED (1)**

```
FAILED ::test_no_assertion_in_this_file_is_neutered - AssertionError: assert ...
1 failed, 12 passed in 9.15s
```

**M3c** — `assert not not offenders`  →  **RED (2) but INVALID — it neuters nothing**

```
FAILED ::test_no_volume_bar_is_drawn_outside_the_picture[showValues=false] - ...
FAILED ::test_no_volume_bar_is_drawn_outside_the_picture[showValues=true] - A...
2 failed, 11 passed in 8.91s
```
