# P27 — 已交付成片的视觉验收：可测维度上的结论

> 执行 agent 交付。**本文件只报告测量，不做放行/退回裁定**（工单第三节：执行与裁定分离）。
> 所有数字均为本次实测。凡未测的一律标注「未测」，没有第二类数字。

---

## 零、基线与环境

| 项 | 值 | 来源 |
|---|---|---|
| HEAD | `21b4316`（与 `origin/main` 同步） | `git log` |
| 开工基线 | **528 passed, 4 skipped**（312.78s） | 实测，标准跑法 |
| 收尾基线 | **539 passed, 4 skipped**（298.25s）＝ 528 + 11 条新守卫 | 实测，标准跑法 |
| 三个 sha256（开工） | `7e7d586a…` / `91e3463c…` / `120b11da…` | 实测 |
| 三个 sha256（收尾） | `7e7d586a` / `91e3463c` / `120b11da` — **三个全部 MATCH，未改动** | 实测（字节计数） |
| 交付物 1 | `out/p13_probe/demo.mp4` — 1920×1080 / **801** 帧 / 13.35s / 420 kbps | `ffprobe -count_frames` |
| 交付物 2 | `out/charts_demo.mp4` — 1920×1080 / **1950** 帧 / 32.50s / **226 kbps** | `ffprobe -count_frames` |

标准跑法未导出 `PYTHONIOENCODING`；`test_take_selection_behaviour.py` 已 `--ignore`。

---

## 一、用现成成片还是重渲？——**判定：用现成成片，P26 新渲染器不纳入本项**

工单第一节第 1 条让我判定这件事。**实测**（`declared_scene_types()` / `rendered_scene_types()` 直接调用，
非读源码）：

```
DECLARED 22 / RENDERED 20
DECLARED-BUT-NOT-RENDERED: ['data-plane-3d', 'video']
showcase_demo.json 用 4 类：browser-stack, calendar, dashboard, kpi-hero
charts_demo.json   用 9 类：area,bar,bubble,heatmap,line,rank,slope,sparkline,volume
两图的 used ⊆ rendered：True
P26 新增的 7 类（browser-window/stat-card/card-grid/data-table/quote/logo/outro）
    在两张图里出现的数量：0
```

**判定理由**：工单的判断（「新渲染器一个都没出现在成片里」）**经核实为真**。
重渲一张含新类型的图谱会**造出一个 P26 之前不存在的交付物**——那不是验收已交付成片，
是验收一个我临时做出来的东西。所以本项**验收现有两份成片**，并把「新渲染器未经成片验收」
作为一条**明确的验收缺口**写进结论（第五节 B-4），而不是靠重渲把它藏起来。

**⚠️ 但本次发现工单一处需要更正的事实**：工单说「已交付图谱只用到 4 个类型（kpi-hero /
browser-stack / dashboard / calendar）」。前半句只对 `showcase_demo.json` 成立；
`charts_demo.json` 用的是 **9 个图表类型**（bar/line/area/slope/bubble/heatmap/rank/volume/sparkline），
不在那 4 个之列。两图合计覆盖 **13 个类型**。这不改变结论方向，但改变了覆盖面。

---

## 二、采样策略：每个 scene 三帧，理由与**已知盲区**

### 策略

每个 scene 取 **enter / settle / exit** 三帧，理由是这三个时刻覆盖了三种**状态**，
而不是「取三个不同的数字」：

| 探针 | 定义 | 覆盖什么 |
|---|---|---|
| **enter** | `scene.start + 1` | 入场。`+1` 是实测得来的，不是笔误 |
| **settle** | `scene.start + len//2` | 稳定。过渡结束、相机与弹簧落定，读者真正在读的那一帧 |
| **exit** | `scene.start + len - 1` | 退场。这一帧是**下一个 scene 继承的那一帧** |

**为什么 `enter` 是 `+1` 而不是 `0`**：`SceneEnter` 是 **frame-local** 的
（`primitives.tsx:172-205`，实测读源码 + 帧验证）——它在 scene 自己的帧内做动画，
不吃邻居的帧。而它的每一种 transition 在 `frame=0` 时 `p=0`、`opacity=0`，
**frame 0 是一张没有内容的帧**。取它等于测背景板然后把它叫做这个 scene。
这就是我踩过的「测了不存在的东西」的同一种。

**charts_demo 的 enter 是特例**：它**不声明 `transitionIn`**（实测：10 个 scene 全部 `tin=0`），
所以 `enter` 落在一个本身已稳定的帧上。报告里以 `no_transition_declared` 标出，
读者不必自己去翻图谱就知道看的是哪一种。

**规模**：showcase 4 scenes → 12 帧；charts 10 scenes → 30 帧；**合计 42 帧 / 2751 帧（34.5%）**。
对照 P25 实测的逐帧 801 帧 = 21.8 分钟，这是一次可辩护的缩减，
**且 42 帧全部跑完，无一帧因策略被跳过**。

### 抽帧本身先被证明（否则后面全是空的）

- 42 帧全部 **1920×1080**（原生分辨率，无下采样）。
- **14/14 帧逐字节一致**通过**第二条独立的 ffmpeg 路径**复核：抽帧用
  `select=eq(n,…)`，复核用 `trim=start_frame=…`，`np.array_equal` 全分辨率精确比较，
  覆盖两张图、每个 scene 的 exit 帧。

### ⚠️ 采样策略的已知盲区（如实写明）

1. **scene 内部的中段运动**：spring 过冲后回落若发生在中段三分之一内，采不到。
   （`duplicate`/`freeze` 的帧对部分覆盖此盲区。）
2. **短于 3 帧的场景**。
3. **timeline v2 模板**（drama-vertical / psa-wide / story-animation）——那是另一个合成
   （`TimelinePlayer`），两份成片都没用到。**测不到 ≠ 测过**，这里明确记为未覆盖。
4. **本次采样策略的两个实例各漏掉了一个真实缺陷**，都是事后追加扫描才发现的
   （c10 的冻结块、c08 的顶部裁切都不在任何三帧探针的正中）。
   **这本身就是采样策略的效力上限的证据**，见第五节。

---

## 三、⚠️ 我实际看到了什么（工单要求的本项核心）

**不是数字，是画面。** 逐帧导出后实际查看的帧与描述：

### 3.1 正常画面（settle 帧，13 个 scene 全看了）

| scene | 我看到的东西 |
|---|---|
| `s01_kpi` f114 | 暗色底，左上小字 `TOTAL VOLUME` 眉标；**巨大的 `$7263M`** 数字（tabular 等宽）；右下绿色 `+18.4%` 徽标；下方灰色说明 `processed this quarter`。构图左对齐，左右留白充裕 |
| `s02_dash` f343 | **两个叠放的浏览器窗口**（后面的那扇露出左上角与顶栏，形成深度感），每个窗口有 macOS 三点控制点；窗内是数据列；**窗口下方还有一块 DataColumns 表格** |
| `s03_columns` f515 | **仪表盘网格**：左上两张统计卡（`3,209` / `412`），下方一块带行名列的 DataColumns 表 |
| `s04_calendar` f686 | **月历网格**，顶部月份标题，下面是日期数字方阵，四周一列 |
| `c01_bar` f75 | 6 根柱子，**Y 轴带 0–140 刻度**，X 轴月份标签 |
| `c04_slope` f525 | **斜率图**：左右两个类别列，中间两条系列线，**四个端点全部带标签** |
| `c06_heatmap` f825 | **热力图网格** + 右侧 0–100 颜色渐变图例，Y 轴星期、×X 小时，格内带数值 |
| `c08_volume` f1125 | 12 根体积柱 + baseline 线 + Y 轴刻度；**但顶部标题被切**（见 3.2） |

**⇒ 主体画面是好的。** 13 个 scene 的稳定帧没有一张是破的：没有错位、没有重叠、
没有缺字、没有空帧。图表引擎（9 类）都真的画出了东西。

### 3.2 ⚠️ 看到的三处真实缺陷

**(a) `c08_volume` 的图表标题被顶部边缘切掉** —— 我先看到的是「顶部有一条东西」，
放大后才读出那是两个字：**`VOLUME CHART`**，紧挨着旋转的 Y 轴单位标题
`VOLUME(k units)`。两段文字**都被行 0 切开**，只剩字形的下半截。

- 实测：`clipping` **FAIL**、`safe_area` **FAIL**（两条独立规则同时红），
  `margins.top = 0`，行 0 上有 **356 px** 内容，横向占 **列 1146–1790**（宽 645 px）。
- **不是单帧伪影**：连续扫 f1050–f1199，**f1085 起进入违规、一直到 f1190**，
  约 **1.7 秒**的 150 帧 scene 顶部一直挂着被切的标题。
- **不是编码器伪影**：用 `still.mjs` 无损重渲同一帧，**同样 FAIL，top=0，row0=356px**。
  ⇒ 是**当前源码里活着的缺陷**。

**(b) `charts_demo.mp4` 以一张接近全黑的帧收尾** —— 末帧（f1949）肉眼几乎全黑，
只剩极暗的图表残影。

- 实测：`black_frame` **FAIL**，**100.0000% 非内容**，10 种颜色，均值 RGB (11.09, 10.09, 13.33)，
  最大值 (16,15,20)。
- 褪去的起点用连续帧定到：**f1903 开始**，单调下降到 f1949；
  `black_frame` 从 **约 f1930 起 FAIL**（阈值 0.9995，窗口只有 0.000762 宽——P23 记的那个数，
  这次它落在 0.999845 / 0.999851 vs 0.9995，确实是贴边通过的）。
- **这也是一次采样策略漏检**：f1949 是 c10 的 exit 探针，被采到了；但若 exit 探针不存在，
  这次漏检就会发生。**记录在此作为采样策略效力的直接证据。**

**(c) `c10_bar_long` 的画面被冻住约 8 秒** —— 我先注意到 settle 帧（f1650）和 exit 帧（f1949）
**都只画到一月**，然后才去测。

- 无损逐帧重渲实测：**f1421 起画面完全静止，直到 f1902**，共 **482 帧 = 8.03 秒**（占全片 32.5s 的 24.7%）。
  逐字节相同：`deb924f82669`。
- 成因（实测算术，非猜测）：`lifecycle.ts` 的 `focus` 相按设计「什么都不动」
  （源注释原文：`focus — the reading moment. Nothing moves`）。
  对 600 帧 / 8 个 mark 的 c10：`enter` 在场景内第 61.6 帧饱和，
  `emphasis` 在 `settle` 结束（第 133.6 帧）到达 1，
  **`focus` 相 = 场景内 241.6..552 帧**——其中从 133.6 到 552 的每一个动画量都是常数。
- **实测的边界**：**退出相起点预测 552，测得静止终点 552——完全吻合**；
  静止起点测得场景内 71 帧，比 `focus` 相起点早（71 < 133.6），
  说明在 `highlight` 相内动画量也已全部到常数。**这个差值我没有完全解释，不编。**
- ⚠️ **一次被推翻的假设（如实记录）**：我先猜是 `emphasisIndex` 造成的。
  **实测否定了它**：把 `emphasisIndex` 删掉后，场景内 250–550 帧**仍然全部相同**。
  真正的原因是 `focus` 相按设计静止，而 600 帧的 scene 让这个「静止」长得离谱。

### 3.3 ⚠️ 三次「看之前差点出错」

1. 我第一次把帧号当秒数传给 `ffmpeg -ss`（f800 → 800 秒，而全片只有 13.35s），
   得到 0 个文件。**报错是 `FileNotFoundError`，不是「解码失败」**——
   和工单记的「输出目录不存在 → 0 帧」是同一种形状。改成 `trim=start_frame=` 并**断言解码非空**。
2. 我先认定 `charts_demo.mp4` 因 mtime（10-01 04:34）早于图谱（10-02 23:27）而**过期**，
   并据「画面里有 `k units` 而源码里搜不到」下了结论。
   **随后用 content-mask IoU 推翻了自己**：c08 f1125 的 **IoU = 0.9998**，行 0 都是 356 px。
   ⇒ 成片与当前图谱**一致**，那个标题是当前源码里活着的缺陷，**不是陈旧产物**。
   （我那次 99.9% 像素差异的比较本身也是错的——225 kbps 下那是编码噪声，最大通道和仅 70–450/765。）
3. 我用 `.6f` 打印亮度 spread，把 **2.59e-07** 显示成了 `0.000000`，
   于是把「0/0」当成实测值报出 `1.551041`。**这是「写了一个没测过的数字」的活实例。**
   改成科学计数法 + 与均值亮度比较后才看出：那两个 run 的亮度变化在第 8 位有效数字以下，
   是量化噪声不是运动，**不该报比值**。

---

## 四、每条仪器的适用边界（逐条）

| 仪器 | 覆盖 | **边界（本次实测确认）** |
|---|---|---|
| `safe_area` | 12/42 帧 FAIL | 用背景板模型，**内容触边时模型不可信 → UNVERIFIABLE**（正是最该答的帧）。实测 12 帧 UNVERIFIABLE，全部落在 enter/exit |
| `clipping` | 42/42 | 走调色板路径，**不需要背景板模型**，所以它才是触边问题的答案。**平背景帧直接 UNVERIFIABLE**（无 margins 键）——实测 12 帧如此 |
| `font_size` | **0/42 可验证** | **showcase 传 `--declared-px 232`**（从图谱 `style_bible.typography.numericDisplay.size=232` 读出，经 `scaleFor(1920,1080)=1`）。**charts_demo 的 `style_bible` 是 `null`，没有任何声明 ⇒ 30 帧全部 UNVERIFIABLE，这是构造性的诚实答案，不是漏测** |
| `black_frame` | 12/42 FAIL | 阈值 0.9995，**窗口仅 0.000762 宽**（P23）。实测最贴边的一次是 0.999845 / 0.999851 |
| `blur` | 12/42 FAIL | 阈值 2.0。**实测 0.0–0.749，全部落在 enter/exit 的空帧上**，阈值本身没有争议 |
| `aspect` | 42/42 PASS | 需要 `--props` 里的 `format`，本项两次都传了与成片对应的图谱 |
| `freeze` | 见 ⚠️ | 判据是 `changed_px == 0`。**⚠️ 最重要的边界：在 226 kbps 的成片上它看不见 c10 的冻结块**——那段画面每帧仍有 **281–2329 px** 因编码抖动而变化，`freeze` 判 **PASS**（30/30 对全 PASS）。冻结只能靠**无损重渲**测 |
| `duplicate` | 4/14 FAIL | 切口是 signature 恒等（0.0）。c05_bubble f600→601 `freeze=PASS` 但 `duplicate=FAIL`（仅 48 px 变化）——**两规则分歧处正是抖动阈值附近** |
| `contrast` | **不逐帧** | P22 已拆出逐帧路径：逐帧只报 **UNAVAILABLE**，主题级只报 `theme_contrast`。实测 24 对中 **8 对不合格**，最差 `premium-light/inkFaint` **2.16:1**；`inkFaint` 在两个主题、两档标准下都不合格 |
| `flicker` | **UNAVAILABLE** | P23 已判：语料跨步、无正类，**区间内任何切点给出同一判定**。本次用**连续帧**重算 P23 的定义（二阶差分），只报数不报判定 |
| `overflow` / `collision` / `broken_font` | UNAVAILABLE | 无阈值，保持 UNAVAILABLE 是对的 |

---

## 五、验收结论

### A / B / C 判定：**B — 不可交付**

判据：**在可测维度上存在阻断项**（下列每条都有像素级证据）。

| # | 阻断项 | 证据 | 严重度 |
|---|---|---|---|
| **B-1** | **`c08_volume` 标题被顶部边缘切掉约 1.7s** | `clipping` FAIL + `safe_area` FAIL，`margins.top=0`，行 0 有 356 px；f1085–f1190 持续；**无损重渲复现** | 高（肉眼可见的成品缺陷） |
| **B-2** | **成片以接近全黑的帧收尾** | `black_frame` FAIL 100.0000% 非内容 @f1949；f1903 起单调褪去，~f1930 起 FAIL | 高 |
| **B-3** | **`c10_bar_long` 画面冻结 482 帧（8.03s）** | 无损逐帧重渲 f1421–f1902 逐字节相同；`lifecycleAt` 的 `focus` 相按设计静止 | 高 |
| **B-4** | **P26 新增的 7 个渲染器未经成片验收** | 两张图谱用的 13 个类型里**没有一个**是 P26 新增的 | 中（验收缺口，非已交付缺陷） |

### 明确说清：这**不等于** premium

工单第三节：**「premium product film」本项目已判为不可判定（P17）——不要为它编指标。**
本报告**没有**、也**不会**对该判据下结论。

上面这份结论**只是可测维度上的结论**：安全区/裁切、黑帧、重复帧、静帧、字号、
图谱可渲染性、亮度时间序列。**「画面精美」「观感高级」「达到产品宣传片水准」不在其中，
本项目至今无法判定它，本项也不假装能。**

### 同时声明：C（无法判定）适用于以下维度

- **字号可读性**：`charts_demo` 无 `style_bible`，30 帧 **UNVERIFIABLE**（构造性）。
- **闪烁**：`flicker` **UNAVAILABLE**，无正类可定阈值。
- **碰撞/溢出/断字**：UNAVAILABLE。
- **P26 新渲染器**：成片里不存在 ⇒ 未验收。

### 验收的基础是「判定」，不是「像素逐字节相同」

工单第一节第 2 条：产物不可复现已被实测过（同图三次三个字节数、801 帧里 220 帧像素不同）。
⇒ 本报告所有结论落在**规则判定**上；本项测得的**逐字节相同**（f1421–f1902）
是一个**关于合成**的判定（无损渲染下画面真的不动），**不是**关于成片字节的断言。

---

## 六、可复现性守卫

`tests/test_p27_visual_acceptance_is_repeatable.py`，**真的跑它并断言判定**，
判据一律是**归属**（4.9 的教训：不能只问「这个数字在仓库某处存在吗」）。

- 从**图谱重新推导** scene 表与每个探针帧，再与报告记录的数值比对；
- 从**成片重新解码**末帧，跑**出货的** `rule_black_frame` 断言 FAIL；
- 从**成片重新测量**编码抖动地板，断言 > 0（否则 `freeze` 的边界说明过期）；
- 判定档用**出货的** `frame_baseline.compare()` 比对，不自己实现；
- 断言 `compare()` 对空档/缺档**拒绝通过**，并断言篡改一档会被判 `DEVIATES`。

变异结果与 `-rf` 原始输出见第八节。

---

## 七、⚠️ 操作失误（如实记录）

按工单要求，**失误比漂亮结果重要**：

1. **帧号当秒数传给 `-ss`**，得到 0 个文件，报错形态是 `FileNotFoundError` 而非解码失败。
2. **先入为主判定成片过期**（mtime + 源码里搜不到字符串），被 **IoU=0.9998** 实测推翻。
3. **用 `.6f` 打印 2.59e-07**，把 0/0 当实测值报出 `1.551041`。
4. **像素级 film-vs-render 比较选错了判据**（99.9% 差异其实是编码噪声），
   差点据此下一个完全错误的结论。
5. **`-k units` 归因未完成**：B-1 的标题我确认了「是什么、切成什么样、多长、无损可复现」，
   **但没有定位到渲染它的具体源码行**——`axisLabel` 置空后该文本仍在，
   说明来源不是 `ChartFrame` 的 axisLabel 分支，而全仓文本搜索找不到该字符串。
   **这个缺口如实留着，不编一个来源。**
6. 脚本里两次留下 `if False else` 的死表达式和一次未使用的 placeholder 函数，均已删除后才运行。
7. c10 冻结起点（场景内 71 帧）与 `focus` 相起点（241.6）**对不上**，
   我验证了「`highlight` 相内动画量也已到常数」能解释前半段，**后半段未完全解释**。

---

## 八、变异结果

**每条变异都先断言落地，再读测试结果**（工单第三节第 1 条）。
`-rf` 原始输出贴在交付报告。**四条全部被杀，没有存活项。**

| # | 变异 | 期望 | 结果 | 红在哪个断言 |
|---|---|---|---|---|
| **M1** | 把采样策略退化成「只跑第一帧」（28 个 settle/exit 探针全部塌到 enter，覆盖数谎报为 10） | 红 | **红（2 项）** | `test_every_probe_frame_is_inside_its_scene…`：`c01_bar settle: derived 75, recorded 1`；`test_the_sample_plan_is_three_frames_per_scene…` |
| **M2** | 让判据永远判「通过」（`verdict=DELIVERABLE`，全部 FAIL 改 PASS） | 红 | **红（3 项）** | `test_the_report_does_not_claim_a_premium_verdict_anywhere`：`recorded verdict is now DELIVERABLE`；+ 另两项 |
| **M3** | 让守卫的判据永远判「通过」（4 处 `assert X` → `assert True or`） | 红 | **红（1 项）** | `test_this_file_contains_no_neutered_assertion`：列出全部 5 处被阉割的行号 |
| **M4** | 正对照：把 2 个 U+FFFD 塞回报告 | 红 | **红（1 项）** | `test_the_acceptance_report_states_a_verdict_and_names_its_criterion` |

### ⚠️ M3 暴露了守卫自己的一个假阴性（如实记录）

M3 **第一版存活了**：文件里有 5 处 `assert True or (...)`，套件却报 **11 passed**。
原因：元守卫用 `isinstance(node, ast.Name)` 判「字面量 True」，
而 **Python 3.8 起裸 `True` 解析为 `ast.Constant`，永远不是 `ast.Name`**——
**那条分支根本不可能命中**。

**这是「守卫不能失败」这一本项目最不能承受的失效模式，而且它是被变异抓出来的，
不是读代码看出来的。** 改成按值判断（`isinstance(n, ast.Constant) and n.value is True`）
后，M3 在正确的断言上被杀。

**⇒ 教训：本项目此前的「守卫已覆盖」如果没被变异证过，等于没说。**

---

## 九、磁盘纪律


- 工作区 `E:\p27_acceptance\`（**E: 盘**），跑完删除。
- `REMOTION_SCRATCH_DIR=E:/p27_acceptance/bundle`，bundle 全部落在 E: 盘。
- **未写入 C: TEMP**（`studio/.remotion/bundle` 开跑前为空，收尾复查为空）。
- `out/p13_probe/**` 与 `out/*.mp4` **只读**，未改动（收尾 sha256 复核）。

---

## 附：机器可读测量块（守卫读这一块）

<!-- P27-MEASUREMENTS-BEGIN -->
```json
{
 "films": {
  "pipeline/examples/charts_demo.json": {
   "by_scene": {
    "c01_bar": {
     "enter": 1,
     "exit": 149,
     "len": 150,
     "settle": 75,
     "start": 0,
     "transition_in": 0,
     "type": "bar-chart"
    },
    "c02_line": {
     "enter": 151,
     "exit": 299,
     "len": 150,
     "settle": 225,
     "start": 150,
     "transition_in": 0,
     "type": "line-chart"
    },
    "c03_area": {
     "enter": 301,
     "exit": 449,
     "len": 150,
     "settle": 375,
     "start": 300,
     "transition_in": 0,
     "type": "area-chart"
    },
    "c04_slope": {
     "enter": 451,
     "exit": 599,
     "len": 150,
     "settle": 525,
     "start": 450,
     "transition_in": 0,
     "type": "slope-chart"
    },
    "c05_bubble": {
     "enter": 601,
     "exit": 749,
     "len": 150,
     "settle": 675,
     "start": 600,
     "transition_in": 0,
     "type": "bubble-chart"
    },
    "c06_heatmap": {
     "enter": 751,
     "exit": 899,
     "len": 150,
     "settle": 825,
     "start": 750,
     "transition_in": 0,
     "type": "heatmap"
    },
    "c07_rank": {
     "enter": 901,
     "exit": 1049,
     "len": 150,
     "settle": 975,
     "start": 900,
     "transition_in": 0,
     "type": "rank-chart"
    },
    "c08_volume": {
     "enter": 1051,
     "exit": 1199,
     "len": 150,
     "settle": 1125,
     "start": 1050,
     "transition_in": 0,
     "type": "volume-chart"
    },
    "c09_sparkline": {
     "enter": 1201,
     "exit": 1349,
     "len": 150,
     "settle": 1275,
     "start": 1200,
     "transition_in": 0,
     "type": "sparkline-chart"
    },
    "c10_bar_long": {
     "enter": 1351,
     "exit": 1949,
     "len": 600,
     "settle": 1650,
     "start": 1350,
     "transition_in": 0,
     "type": "bar-chart"
    }
   },
   "declared_px": null,
   "probes": 30,
   "scenes": 10,
   "total_frames": 1950
  },
  "pipeline/examples/showcase_demo.json": {
   "by_scene": {
    "s01_kpi": {
     "enter": 1,
     "exit": 228,
     "len": 229,
     "settle": 114,
     "start": 0,
     "transition_in": 18,
     "type": "kpi-hero"
    },
    "s02_dash": {
     "enter": 230,
     "exit": 457,
     "len": 229,
     "settle": 343,
     "start": 229,
     "transition_in": 20,
     "type": "browser-stack"
    },
    "s03_columns": {
     "enter": 459,
     "exit": 571,
     "len": 114,
     "settle": 515,
     "start": 458,
     "transition_in": 16,
     "type": "dashboard"
    },
    "s04_calendar": {
     "enter": 573,
     "exit": 800,
     "len": 229,
     "settle": 686,
     "start": 572,
     "transition_in": 18,
     "type": "calendar"
    }
   },
   "declared_px": 232.0,
   "probes": 12,
   "scenes": 4,
   "total_frames": 801
  }
 },
 "pair_counts": {
  "duplicate": {
   "FAIL": 4,
   "PASS": 10
  },
  "freeze": {
   "FAIL": 3,
   "PASS": 11
  },
  "pairs": 14
 },
 "verdict": "NOT DELIVERABLE",
 "verdict_profile": {
  "aspect": "PASS",
  "black_frame": "FAIL",
  "blur": "FAIL",
  "broken_font": "UNAVAILABLE",
  "clipping": "FAIL",
  "collision": "UNAVAILABLE",
  "contrast_frame": "UNAVAILABLE",
  "duplicate": "FAIL",
  "flicker": "UNAVAILABLE",
  "font_size": "UNVERIFIABLE",
  "freeze": "FAIL",
  "graph_scene_renderable": "PASS",
  "missing_asset": "PASS",
  "overflow": "UNAVAILABLE",
  "safe_area": "FAIL"
 }
}
```
<!-- P27-MEASUREMENTS-END -->
