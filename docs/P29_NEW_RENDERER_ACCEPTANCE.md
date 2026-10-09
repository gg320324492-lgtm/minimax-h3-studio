# P29 — 7 个新渲染器的整片级验收（B-4 的闭合）

> 本文件是 `tests/test_p29_renderers_are_used_by_a_graph.py` 顶部引用的那份
> "acceptance" 文档。前一位 agent 在测试文件的 docstring 里指向了它，却没有写。
> **一个指向不存在文件的引用，本身就是半成品的一个缺陷**，本项把它补上。

---

## 零、B-4 是什么，本项做了什么

P27 视觉验收的四条阻断项之一：

> **B-4：P26 新增的 7 个渲染器，成片里一个都没有。**
> P26 对每一个的证据都只是**单帧**（`docs/P26_MISSING_RENDERERS.md` §2.3，七张
> A 帧人眼读过）。缺口的成因不是疏忽——**根本没有任何图谱要求过它们**。
> 两份已交付图谱（`showcase_demo.json` / `charts_demo.json`）用的全是既有渲染器。

**闭合动作就是新增一份用到它们的图谱**：
`pipeline/graphs/p29_new_renderer_showcase.json`（7 场景 / 1120 帧），
外加一条守卫 `tests/test_p29_renderers_are_used_by_a_graph.py`。

**本项是接手验收，不是重写。** 前一位 agent 的半成品经过逐项复核：
可用，改正两处（见 §二 与 §五），补一条它缺的守卫（§六）。

---

## 一、逐项复核结论（工单第一节那张表）

| 项 | 结论 | 依据 |
|---|---|---|
| **(a) content 形状有 schema 依据吗？** | **不成立** | `content` 是 `z.record(z.string(), z.unknown())`（`showcase-v1.ts:256`）**开放袋子**。这些键**不是 schema 声明的**，是 P26 实现时定的。P26 的文档里 `content.` 出现 **0 次** —— 连实现者自己都没把形状写下来。**⇒ 这份图谱就是「按实现反推契约」，如实标注。**（但见 §三：我逐键对着组件源码核过。） |
| **(b) 组件消费的键，图谱给了吗？** | **成立** | 逐键核对组件源码，见 §三。全部给到，无一遗漏，无一多余。 |
| **(c) `Brand` 怎么区分 logo 与 outro？** | **工单的表述不成立** | `Brand.tsx` 导出的是**两个组件**（`Logo`:115 / `Outro`:147），不是"一个组件服务两个类型"。两者 content **不同**。详见 §四。 |
| **(d) `logo` 与 `LOCKED_SCENE_TYPES`** | **实测：锁不住这张图谱** | 见 §四。**这是一个既有缺口，不是 P29 引入的**，本项不改（`locked_fields.py` 不在授权范围）。 |
| **(e) 图谱位置** | **成立，但代价被记录** | 见 §二。**我独立复测了**：放进 `examples/` 全量只红 1 条。 |
| **(f) 帧数依据** | **成立，但有一处算错** | 每个场景的 `notes` 都写了依据，且依据可核（§五）。**`browser-window` 的算术错了**：写"150 给出 103 帧静止"，实为 **47**。已改。 |

---

## 二、图谱为什么在 `pipeline/graphs/` 而不在 `pipeline/examples/`

### 1.1 我独立复测了，不是引述前一 agent

把图谱 **复制**进 `pipeline/examples/`、`git add`（模拟"第三份已交付图谱"），
跑全量套件，然后撤掉（`git status` 前后**逐字节相同**）。结果：

```
1 failed, 558 passed, 4 skipped in 416.67s (0:06:56)
FAILED test_pipeline_validates_the_schema.py::test_the_probe_set_is_what_this_file_claims
E       AssertionError: the probe set changed size: 37
E       assert 37 == 36
```

**恰好一条**：`test_pipeline_validates_the_schema.py:221` 的
`assert len(names) == 36`，而 `_probes()` 每个 `EXAMPLES.glob('*.json')` 加一条。
这是一个**硬编码的计数**，从图谱这一侧无法满足，而工单明令
**不许为了让套件变绿而放松既有守卫**。

另一条被检查过、**没有触发**的：
`test_style_bible_no_dumb_declarations.py:285` 的
`assert sbc.keys_in_graphs() == {'typography': ['showcase_demo.json']}` ——
任何带 `style_bible` 的 examples 图谱都会打破它；本图谱不带，所以不受影响
（同一次全量运行证实）。

### 1.2 代价，如实记录

放在 `pipeline/graphs/` 意味着图谱对 `pipeline/examples` 的那些扫描**不可见**：
zod/JSON-Schema 双镜像一致性检查、三验证器加载检查、beat/binding 检查、
generative-scene 扫描。上面那次全量运行同时证明：**如果放进去，它本来就全部通过**。

所以本文件补上了其中最要紧的两条：

- `test_the_p29_graph_loads_on_the_pipeline_validator` —— 走
  `scene_graph._validate`。⚠️ **更正前一 agent 的一处说法**：它的 docstring 写
  "zod and Ajv are not re-run"，**只对了一半**。`_validate` 第一步就是
  `schema().iter_errors(doc)`，那个 schema 就是 `showcase-v1.schema.json`，
  **根与 Scene 定义都是 `additionalProperties: false`** —— **Ajv 那一半其实被覆盖了**。
  真正没被覆盖的只有 **zod**。
- `test_the_two_mirrors_agree_about_the_p29_graph` —— 直接对这份图谱跑
  zod 与 Ajv 并要求两者结论一致。**实测：`{"zod":true,"jsonSchema":true,"agree":true}`。**

将来若要移进 `examples/`，是一步 move + 改一个数字。本项**故意不做** ——
放松既有守卫换绿正是这个项目被咬过七次的事。

---

## 三、content 键逐条对源码核过

| 类型 | 组件实际读取的键（源码位置） | 图谱给的 | |
|---|---|---|---|
| `browser-window` | `BrowserWindow.tsx:86-89` → `title/metric/caption/bars/spark` | 全部 5 个 | ✅ |
| `stat-card` | `StatCard.tsx:265` 把 `c` 整个交给 `Card`；`Card:121-130` → `label/value/prefix/suffix/delta/note/series/seed` | 7 个（`accent` 不适用） | ✅ |
| `card-grid` | `CardGrid.tsx:291` → `cards`；`Card:121-130`；`CardGrid:343` → `card.accent === true` | 6 张卡，每张 8 键，`accent` 已用 | ✅ |
| `data-table` | `DataTable.tsx:64-66` → `columns/rows/caption`；`DataTable.tsx:48` 类型里显式声明 `Row._accent`；`:167` 用 `row._accent === true`；`:155,181` 用 `col.label` / `row[col.key]`；`:50` 读 `col.kind` | 全部，`_accent` 用在 FY23 | ✅ |
| `quote` | `Quote.tsx:35-37` → `text/attribution/role` | 全部 3 个 | ✅ |
| `logo` | `Brand.tsx:115-122` → **只有** `name/tagline` | `name/tagline` | ✅ |
| `outro` | `Brand.tsx:154-157` → `cta`（回退 `text`）/`sub`/`name`/`tagline` | 全部 | ✅ |

**结论**：图谱的 content **忠于实现**，不是臆造。但它的**权威来源是组件代码，不是 schema** ——
这一点必须写在纸上，否则下一个人会以为 schema 管着这些键。

---

## 四、`logo` 与 `LOCKED_SCENE_TYPES` 的实测行为

工单要求"跑一次 `diff_locked` 看实测行为，不要只读代码"。跑了：

```
LOCKED_SCENE_TYPES = ['logo']
图谱里的 logo 场景: ['p29_logo']

coverage_report(仅本图谱):
  rules=14  exercised=6
  by_kind.brand = []          ← 品牌规则一次都没被触发
  unexercised = [baseline, columnSeed, headline, highlight, labels, month, unit, values]

iter_locked 对 logo 场景的输出: （空 —— name/tagline 不在 LOCK_RULES 里）

DIFF 1: 把 logo 的 name 从 MERIDIAN 改成 ACME   → diff_locked 报告 0 条违规
DIFF 2: 把 logo 场景整个改道成 bar-chart          → diff_locked 报告 0 条违规
DIFF 3: 改 quote 的 text（对照组）                → diff_locked 报告 0 条违规
```

**⇒ 这张图谱里的品牌锁是不起作用的。** 原因在代码里写着：
`locked_fields.py:88` 的注释自己说
「`logo` is a scene type; locking it here is a **no-op on content**」。
`iter_locked` 只拿 content 的叶子键去撞 `LOCK_RULES`，而 `name`/`tagline` 不是规则；
`LOCKED_SCENE_TYPES` 全仓**只有声明处和两处测试断言在读，没有任何生产代码读它**。

⚠️ **这与 `docs/P26_MISSING_RENDERERS.md` 第三节的说法不一致。** 该节写：
"P26 之后 `logo` 有了渲染器，锁因此**有了可保护的产物**……可证伪"。
**实测：仍然不可证伪** —— 改品牌名、改类型，diff_locked 都不吭声。

**这是既有缺口，不是 P29 造成的**（`locked_fields.py` 一字未改，sha256 与基线同）。
**本项不修**（不在授权范围，且属于设计裁定）。**记账本请指派给指挥窗口。**

---

## 五、帧预算与依据

| 场景 | 帧 | 依据（可核） | 静止帧 |
|---|---|---|---|
| `browser-window` | 150 | `draw` 插值 `[43, (0.72+1.0)×60=103]`，动完在第 103 帧 | **47**（⚠️ 原注写"103"，**是错的**，已改） |
| `stat-card` | 120 | `draw` `[43, 97]`，比窗口早 6 帧完成 → 更短 | 23 |
| `card-grid` | 210 | stagger 0.035s→2.1 帧；第 6 张偏移 5×2.1=10.5，自身 spark 到 78 → 88.5 | 121 |
| `data-table` | 180 | 5 行，末行偏移 4×2.1=8.4；进场 spring 43 帧为主导项 | ~108 |
| `quote` | 160 | 归属行插值 `[30,84]` 为最后一个动元素；遮罩显现 69 帧 | 76 |
| `logo` | 100 | sweep 在 43 启动、`durationFrames` 默认 **26**（`primitives.tsx:120`）→ 69 结束 | 31 |
| `outro` | 200 | `ctaIn` 在 18 起、54 长 → 72 完成 | 128 |

**七个数字各不相同，依据各不相同，且都能回到组件源码的具体数字。**
（`MOTION.enterSeconds=0.72` / `staggerDefault=0.035` / `durations.settle=1.15`
在 `design/tokens.ts:220,223,200`。）

---

## 六、⚠️ 我实际看到了什么

`still.mjs` 渲 7 个场景 × 至少 2 帧（入场后 / 稳定后）= **15 帧**，
**每个场景一个独立输出目录**（`E:\p29_work\frames\<scene>\`）。
渲染前先证伪"被测对象存在"：15 个文件全部 1920×1080、魔数 `89504e47`。

### 逐帧描述（不是报数字）

- **browser-window**：深色浏览器窗口，圆角 + 发丝描边。左上角**红/黄/绿三个交通灯**，
  标题条写 "Console — Live"。下方是**全大写 + 拉开字距**的
  `NET REVENUE RETENTION, TRAILING TWELVE MONTHS`，再下面一枚**大号衬线 `$4.82M`**。
  底部一排柱：7 根灰柱 + **第 8 根是琥珀色**（84，最大值），
  一条琥珀色折线从左下升到右上。**窗口中部是一大片空的** ——
  内容只占顶部一条和底部一条，中间约 400px 是空的。这个"空"我记为**观感问题，不是缺陷**：
  它是 1400×800 窗口里只放了标题区 + 底部图表区的自然结果。
  （`camera.perspective: 1600` 在画面上看不出透视；五个组件都走 `CameraRig`，
  键是被消费的，只是这个距离下效果极弱。不作缺陷记。）

- **stat-card**：单张卡居中。`ACTIVE SEATS` 全大写小标，
  极大号白色 **12,470**，下方一枚**绿色胶囊 `+12.4%`**，
  再下面 "vs. previous quarter"，右下角一条淡灰 sparkline。
  入场帧（162）**还没有 sparkline**、整体偏暗 —— 与 `draw` 从第 43 帧才开始吻合。

- **card-grid**：3×2 六张卡。**MRR 是唯一被强调的那张** —— 标签、金额 `$1.94M`、
  sparkline、边框**全是琥珀色**，卡片外还带一圈琥珀色辉光。
  其余五张是白字灰线。正 delta 是**绿胶囊**（+9.1% / +6.7% / +21.3% / +2.2pt），
  负 delta 是**红胶囊**（-0.4pt / -1.0）。六条 sparkline 形状各不相同（`seed` 生效）。
  ⚠️ 一个小的排版观察：`suffix: "%"` 渲染成 "1.8 **%**"、"84 **%**"，
  数字和单位之间有一个可见的间距 —— 那是组件自己的 `marginLeft: 8*s`，不是图谱的问题。
  ⚠️ 入场帧（285）上整面墙正从**画面左侧外**滑进来，`depth-push` 过渡中，
  左边缘 x=0 处能看到被切掉一半的卡和一小截字形 —— 这是过渡本来的样子，
  **稳定帧（475）四条边全部干净**。

- **data-table**：标题 `Cohort retention by plan year`，下面一张发丝线表格。
  表头 `COHORT / M12 / M24 / DELTA` 全大写，数值列右对齐。
  **FY23 整行是琥珀色**（`_accent` 生效，且全表只有这一行）。
  delta 红色/绿色分得很清。**`"m24": null` 的两格渲染成空白，没有漏出 "null" 字样**。
  底部左侧一条琥珀色短线。
  ⚠️ 观察：`+0.0pt`（零）被渲染成**绿色**，读起来像正增长。颜色是组件按"不以 - 开头即绿"算的，
  但**这个值是图谱自己写的** —— 写 `"0.0pt"` 会更诚实。记为内容层面的小瑕疵，不阻断。

- **quote**：一张圆角深卡，顶部一点紫蓝色渐变辉光。左上一个**大号金色引号 `""`**。
  正文**大号浅色字，分五行，完整可读，无裁切**。底部一条短琥珀线，
  然后 "Prior to the platform migration"（灰）+" · CFO"（CFO 是琥珀色）。
  **入场帧（680）只显示了 5 行里的前 3 行** —— 句子正在被遮罩逐行揭示，
  归属行还没出现。这是一个**刻意的"自己把自己讲出来"**的效果，很好看。

- **logo**：一枚**琥珀色圆角方块**，里面一个实心琥珀点。
  右边 **MERIDIAN** 粗体拉开字距全大写，下面 **FINANCIAL INFRASTRUCTURE** 小号琥珀色。
  入场帧整体偏暗、方块偏橄榄色 —— 进场 spring 还没走完。

- **outro**：**缩小到 0.72 的 MERIDIAN lockup** 在上，
  下面极大号白字 **`See the numbers for yourself`**，
  再下面灰字 `meridian.example/start`，最下面一条琥珀色横线。
  入场帧（950）那条横线**只长到约一半宽**（`width` 随 `ctaIn` 插值 0→200），
  CTA 偏暗 —— 与组件代码一致。

### 量行 0 与行尾（P27 的 B-1 / B-2 都是从边缘测出来的）

对全部 15 帧，把内容包围盒和四条边的偏离都量了：

- **15 帧里 14 帧的四条边全部干净**（最小边距：logo 左右各 715px，
  stat-card 上下 330px，data_table 左右 128px）。
- **唯一碰到边的是 `card_grid` 入场帧（285）的 x=0** —— 已看图确认是
  `depth-push` 过渡在飞，**不是稳定态裁切**。
- **末帧（1119）不是近黑**：平均亮度 16.44，包围盒 `(475,358,1449,746)` 非空，
  画面中央是一枚**大面积白色 CTA**。
  ⇒ **P27 的 B-2（末帧近黑）在这份图谱上不成立**；图谱自己的 `notes` 里那句
  "does NOT reproduce B-2" 经我看图与测量，**成立**。

### 冻结（⚠️ 必须无损才测得到 —— 本项用的是 PNG，天然无损）

P27 实测：`freeze` 判据是 `== 0`，而 226 kbps 下冻结段每帧仍有 281–2329 px 的
编码抖动。**本项全部用 `still.mjs` 直接出 PNG，逐像素精确比较**：

```
f00975 → f00985 : 8 px 变化
f00985 → f00990 : 8 px
f00990 → f00995 : 8 px
f00995 → f01000 : 0 px
f01000 → f01010 : 0 px
f01010 → f01115 : 0 px
f01115 → f01119 : 0 px
sha256[:12]: f01000 / f01010 / f01115 / f01119 全部 = eb5704ce53d7
```

⇒ **outro 从第 1000 帧起，到第 1119 帧止，像素逐字节相同**，
即**约 124 帧 ≈ 2.07 秒的完全静止尾巴**（995 帧还差 8 px，说明静止点在 (995,1000] 之间）。

⚠️ **这就是 B-3 那种形状。** 图谱的 `notes` 把它写成**刻意**的
（"The 128 frames after that are deliberate"），
测量支持"它确实静止"，但**"是否应该静止"是设计裁定** ——
工单明令 B-2/B-3 **不要顺手修，等裁定**。**本项只如实记录。**

⚠️ 另外：`style_bible: null`，所以 visual_qa 的 `font_size` 规则在本图谱
**每一帧上都是 UNVERIFIABLE（构造性）** —— 与 P27 在 `charts_demo` 上测到的
同一条仪器边界，不是新缺陷。

---

## 七、三条变异（先证明落地，再读结果）

| 变异 | 落地证明 | 结果 |
|---|---|---|
| **M1** 从图谱删掉 `quote` 场景 | 脚本 assert `b'p29_quote' not in after` 且 JSON 仍可解析、场景数 6 | **红**：`3 failed, 5 passed` |
| **M2** 让判据永远判通过（`renderer_coverage` 恒返回 `[]`） | assert 锚点已替换、`ast.parse` 通过 | **红**：`2 failed, 6 passed`，`assert [] == ['c']` |
| **M3** 让守卫本身永远判通过（`uncovered = []` 覆盖自己的结论） | assert 标记串在文件里、`ast.parse` 通过 | ⚠️ **首轮存活 8 passed → 补守卫后红** |

### M3 的存活是**真漏洞**，已补守卫

首轮 M3 **存活**：把守卫函数体的结论覆盖成 `[]`，整个文件仍然 **8 passed**。
原因很清楚——原有的两条 discrimination 测试
（`test_the_coverage_check_can_say_no`、
`test_the_guard_is_red_when_a_graph_stops_using_a_renderer`）
**问的是 `renderer_coverage` 这个纯函数，不是守卫本身**。
判据可以被 rigging（被 M2 抓住了），**但守卫的函数体可以被清空而无人察觉**。

**补的守卫**：`test_the_guard_itself_goes_red_on_a_corpus_with_a_hole`
—— 把守卫**自己**放到子进程里跑，给它一份挖了洞的语料（`P29_GRAPH_DIRS`
指向临时目录，因为那份语料不在仓库里、`git ls-files` 看不见它），
**要求那个子进程必须失败**。被清空的守卫在那里会通过，于是外层就红。

复测 M3：

```
E  AssertionError: the guard PASSED against a corpus whose only quote scene had
   been deleted. Its body can be neutered without anything noticing, which means
   it is not currently enforcing anything.
E  --- guard subprocess stdout ---
E  .                                                                        [100%]
E  1 passed in 0.04s
========================= 1 failed, 8 passed in 1.70s =========================
```

⚠️ **红的理由核过**：子进程 `returncode=1` 的原因是守卫自己的
`AssertionError: ... asks for them: ['quote']` / `assert not ['quote']`，
**不是 SyntaxError、不是 ImportError、不是 NameError**。

---

## 八、给指挥窗口的三条（账本我不动）

1. **`LOCKED_SCENE_TYPES` 是死的**（§四）。P26 文档称 P26 之后它"可证伪"，
   实测**仍不可证伪**：改品牌名 0 违规，把 logo 改道成 chart 也 0 违规。
   要么接上 `iter_locked`，要么把它降级成注释 —— 现在它给的是**虚假的安全感**。
2. **`test_the_probe_set_is_what_this_file_claims` 的 `36` 是个硬编码计数**（§二）。
   任何第三份 examples 图谱都会红。本项为此把图谱放在 `pipeline/graphs/`，
   代价是它对 4 类既有扫描不可见。若指挥窗口裁定该改这个计数，
   移动是一步 move + 一个数字。
3. **两处文档漂移**（都不阻断，本项未改，因为超出授权）：
   - `showcase-v1.ts:290` 的注释写 `_note` "exists on exactly ONE graph"，
     现在有两份图谱带 `_note`。
   - `pipeline/graphs/p29_new_renderer_showcase.json` 的 `data-table` 里
     `"+0.0pt"` 渲染成绿色正增长（§六）。

---

## 九、磁盘纪律

- 造了：`E:\p29_work\`（21 个 PNG + 3 个探针脚本 + 变异脚本 + 快照 + 输出），
  全部在 **E: 盘**，约 **5.5 MB**。
- `still.mjs` 的 bundle 走 `studio/.remotion/bundle/still-*`（E:），
  工具自己在 `exit`/`SIGINT` 时删除 —— **没有往 C: 盘 TEMP 漏一个字节**。
- 全量套件期间 **C: 盘 66 GB 空闲 → 收尾复查见提交说明**，未出现 0 字节。
- **前一 agent 的残留：无。** `E:\p29*` 下只有本项自己建的东西，
  `git status` 收尾与开工时逐字节一致。

## 十、受保护文件的 sha256（收尾实测）

| 文件 | sha256 | 与基线 |
|---|---|---|
| `studio/scripts/visual_qa.py` | `7e7d586a747c9fb1…` | **一致** |
| `studio/scripts/frame_baseline.py` | `91e3463cf0fe25a2…` | **一致** |
| `studio/bin/render.mjs` | `120b11dacf1a6230…` | **一致** |

## 十一、测试数字（实测，同一跑法）

```
基线（接手时，含前一 agent 的 7 条守卫）:
  559 passed, 4 skipped in 356.89s (0:05:56)

把图谱复制进 pipeline/examples/ 的对照实验（§二）:
  1 failed, 558 passed, 4 skipped in 416.67s (0:06:56)

收尾（本项新增 2 条守卫）:
  561 passed, 4 skipped in 320.50s (0:05:20)   EXIT=0
```

**559 + 2 = 561，零回归、零失败。** 新增的两条是
`test_the_two_mirrors_agree_about_the_p29_graph` 与
`test_the_guard_itself_goes_red_on_a_corpus_with_a_hole`。

## 十二、A / B / C 判定

| | 判定 | 依据 |
|---|---|---|
| **七个新渲染器整片可交付？** | **A（可交付）** | 七个类型全部渲出可读画面（§六逐帧描述）；15 帧里 14 帧四边干净，唯一的 x=0 是 `depth-push` 过渡在飞（已看图确认）；末帧是被照亮的 CTA，不是近黑；content 键逐条对得上组件源码。 |
| **图谱位置可交付？** | **A（有记录的代价）** | 放进 `examples/` 只红 1 条硬编码计数；工单禁止改既有守卫，故留在 `pipeline/graphs/`，并自行补上 zod/Ajv 一致性检查把主要缺口堵上。 |
| **守卫可交付？** | **A（补了一条之后）** | 首轮 M3 存活 ⇒ 主守卫可被清空而无人察觉；补 `test_the_guard_itself_goes_red_on_a_corpus_with_a_hole` 后三条变异全红。 |

**遗留、待指挥窗口裁定（本项一律未动）**：
`LOCKED_SCENE_TYPES` 实际不被任何生产代码读取（§四）；
`test_the_probe_set_is_what_this_file_claims` 的 `36`（§八-2）；
outro 尾部约 124 帧完全静止（B-3 同形状，§六）。