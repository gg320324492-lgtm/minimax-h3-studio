# 执行指令 — 接手 P29：半成品已在仓库，你要判断的是「能不能用」，不是重写

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **前一位执行 agent 被中断了，它的半成品已在仓库里（已 `git add`、未提交）。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `7950166`（已推送，与 `origin/main` 同步） |
| 基线 | **实测 `559 passed, 4 skipped`**（含前一 agent 的 7 条新守卫，已绿） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**（cv2 只装在 3.10）。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`** —— 它会污染 `test_visual_qa.py`。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 前一位 agent 死在这上面。
**全程用绝对路径**，依赖仓库根的命令以 `cd E:/Minimax-H3 &&` 开头。

**⚠️ 磁盘**：**C 盘刚清过（39.9 → 62.6 GB）**，前一位 agent 就是被 C 盘 0 字节空闲打断的。
**输出到 E: 盘**，跑完清理，收尾报告写明造了什么、删了什么。
`render.mjs:43-47` 记录过 **118 个 bundle 把 C: 盘 TEMP 填到 46 GB**。

**开工前记录 sha256，收尾比对**：
- `studio/scripts/visual_qa.py` → 应为 `7e7d586a…`
- `studio/scripts/frame_baseline.py` → 应为 `91e3463c…`
- `studio/bin/render.mjs` → 应为 `120b11da…`

---

## 一、现状：前一 agent 留下的东西

### 1. 已存在、已 `git add`、**未提交**

| 文件 | 状态 |
|---|---|
| `pipeline/graphs/p29_new_renderer_showcase.json` | **已 add** |
| `tests/test_p29_renderers_are_used_by_a_graph.py` | **已 add** |

**指挥窗口已实测**：加进这两份之后全量套件 **559 passed, 4 skipped**
（基线 552 + 7 条新守卫），**零回归**。

**⇒ 半成品没破坏任何东西。**

### 2. 图谱的实际内容（指挥窗口已复核）

**7 个场景、1120 帧，帧数各不相同**（符合工单要求的"不要照抄一个数字给七个"）：

| scene | type | 帧数 |
|---|---|---|
| `p29_browser_window` | `browser-window` | 150 |
| `p29_stat_card` | `stat-card` | 120 |
| `p29_card_grid` | `card-grid` | 210 |
| `p29_data_table` | `data-table` | 180 |
| `p29_quote` | `quote` | 160 |
| `p29_logo` | `logo` | 100 |
| `p29_outro` | `outro` | 200 |

### 3. 守卫已有的三条测试

```
test_every_renderer_is_used_by_a_tracked_graph      ← 主断言
test_the_corpus_is_not_vacuous                      ← 防空转/空语料
test_the_p29_graph_actually_uses_the_seven_renderers ← 抓图谱本身被删
```

⚠️ **"绿"不等于"有效"** —— **它们全部通过过**，而 B-4 当时是开着的。

### 4. ⚠️ 一件必须你判断的事：图谱放在了 `pipeline/graphs/`，不是 `pipeline/examples/`

**⇒ 请核实这是否正确**：

- 有没有既有守卫扫 `pipeline/examples/*.json` —— **若有，你这份图谱它们根本扫不到**，
  **新守卫可能正建立在一个没人检查的位置上**；
- `pipeline/graphs/` 这个目录是**先前就有的**还是前一 agent 新建的？
  **若新建，账本上有没有它的来历？**

---

## 二、你要交付的三件事

### 第 1 件事：**判断半成品能不能用**（先判断，后动手）

**逐项复核，任何一项不成立就修或替换，并说明理由**：

| 要复核的 | 怎么查 |
|---|---|
| **(a) content 形状有 schema 依据吗？** | `content` 是 `z.record(z.string(), z.unknown())` **开放袋子** ⇒ **任何形状都合法**。**若这些键是 P26 实现时自己定的，那这份图谱就是「按实现反推契约」—— 如实标注** |
| **(b) 七个组件消费的键，图谱真的给了吗？** | 组件契约（指挥窗口从代码 grep）：`BrowserWindow`→`title/metric/caption/bars/spark`；`Cards`（stat-card 与 card-grid 共用）→`cards/label/value/prefix/suffix/delta/note/series/seed`；`DataTable`→`columns/rows/caption`；`Quote`→`text/role/attribution`；`Brand`（**一个组件服务 `logo` 与 `outro` 两个类型**）→`name/tagline/sub/cta/text` |
| **(c) `Brand` 怎么区分 `logo` 与 `outro`？** 两者要的 content 相同吗？ | 读 `Brand.tsx` |
| **(d) `logo` 与 `LOCKED_SCENE_TYPES` 的行为** | `locked_fields.py` 的品牌锁对象是 `logo` 这个类型本身。**跑一次 `diff_locked` 看实测行为**，不要只读代码 |
| **(e) 图谱位置** | 见第一节第 4 条 |
| **(f) 帧数依据** | 100–210 各不相同，**但依据是什么？** 前一 agent 未必写下来 |

⚠️ **不要采信前一 agent 的任何设计决定** —— 它**没有留下任何说明文档**
（`docs/` 下没有 P29 的记录），**所以它的理由你无从查证，只能重判**。

### 第 2 件事：**渲染取证 + 描述画面**（前一 agent 完全没做）

⚠️ **验收标准是「看画面」，不是看数字** —— P27 的结论有价值，
是因为它**逐帧描述了画面**（`$7263M` 的 tabular 字、右下绿色徽标、
两个叠放的浏览器窗口形成深度感…）。**你必须做同样的事。**

**必须做**：

1. **`still.mjs` 渲每个场景至少 2 帧**（入场后、稳定后）；
2. **⚠️ 每个场景一个独立输出目录** —— 文件名相同会互相覆盖
   （**指挥窗口栽过四次**）；
3. **量行 0 与行尾** —— P27 的 B-1 与 B-2 都是从边缘测出来的；
4. **描述你看到了什么**；
5. **给 A/B/C 判定**（可交付 / 不可交付 / 无法判定）。

⚠️ **P27 实测出的三条仪器边界，本项要避开**：

- **`freeze` 看不见冻结** —— 226 kbps 下冻结段每帧仍有 **281–2329 px 编码抖动**，
  而判据是 `== 0` ⇒ **必须无损渲染**才测得到；
- **`font_size` 在 `style_bible: null` 的图谱上全 UNVERIFIABLE**（**构造性**）；
- **`black_frame` 的窗口只有 0.000762 宽**，而 **P27 的 B-2 就是末帧近黑** ——
  **若你的图谱也以近黑帧收尾，那是 P27 记录的同一种情况，如实记，不要当新缺陷**。

⚠️ **其他判读陷阱**：`ffmpeg -c:v copy` 配 PNG 输出产出**全损坏**帧（用 `-vsync 0`）；
`--declared-px` 必须与图谱声明一致，否则**自造一个 FAIL**；先证明被测对象存在再测量。

### 第 3 件事：**三条变异的 `-rf` 原始输出**

主断言已有，但**变异没跑过**（前一 agent 被中断在渲染取证之前，
而工单要求每条变异**先证明落地再读结果**）。

| 变异 | 期望 |
|---|---|
| 从图谱里删掉一个用到新渲染器的 scene | 守卫红 |
| 让判据永远判"通过" | 守卫红 |
| 让守卫的判据永远判"通过" | 守卫红（专抓空转） |

⚠️ **本项目被骗七次**，最常见的两个形状：

- **文本存在性断言** —— `assert 'quote' in src` 会匹配到**解释该修复的注释**。
  ⚠️ `render.mjs:141` 的注释里写着 `qa_final.py`，P17 因此栽过；
  ⚠️ 4.9 的 agent 第一版守卫的判据是"数字在仓库某处存在"，
  **被"删掉 520"击穿而存活**（520 也在别的夹具里）；
- **从被守卫对象派生** —— P18 抓到过：守卫从 `LAYER_OF` 派生分层，
  于是"把 blur 换个类"这个变异**首轮存活 16 passed**。
  ⚠️ **判据必须真的解析图谱并与 `SCENE_RENDERERS` 的键做覆盖计算。**

**「变异存活」≠「变异无效」**：存活项判定"真漏洞"还是"无效变异"，
两种都写进 commit。**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果**（注入后先 assert 变异在文件里）。
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
   ⚠️ **指挥窗口刚犯过一次**：第一次注入破坏了语法，守卫报 `SyntaxError` —— 那不算数。
4. **每条毒变异之后从快照复原，收尾核对三个 sha256。**
5. **⚠️ 高频复发**：先证明被测对象存在再测量；在错误的尺度上测等于没测；
   写数字要么实测要么标注未测；确认变异生效前不要宣称存活（P21/P22/P24 均产出过
   `NameError`）；CRLF 用字节计数验（**`p.write_text()` 在 Windows 上翻译行尾，
   P17 的 agent 污染了 1101 行**）；路径分隔符（P17 的 `startswith('out/')`
   在 Windows 上漏掉整个 `out/`）；别把长跑命令管道进 `tail`；
   `tests/test_markdown_text_is_intact.py` 守着全仓 markdown 的 U+FFFD。
6. **py-3.10 有 cv2 但没有 pytest** —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**（P20 的处理方式，**是本项目接受的做法**）。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`、`docs/P2*.md`
- **`out/p13_probe/**` 与 `out/*.mp4` —— 只读**（P27 的证据目录）
- `DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要动 `visual_qa.py` / `frame_baseline.py` / `render.mjs` 及 P19–P28 的成果**
- **不要动七个新渲染器的实现** —— 本项是**验收**
- **不要改既有那两份图谱**（`showcase_demo.json` / `charts_demo.json`）——
  **新增，不要篡改**
- **不要顺手修 B-2（末帧近黑）或 B-3（冻结 482 帧）** —— **设计后果，待裁定**
- **⚠️ 若前一 agent 在 `E:/p29*` 之类留了临时目录，清理并说明**

**本指令授权你修改**：`pipeline/graphs/p29_new_renderer_showcase.json`、
`tests/test_p29_renderers_are_used_by_a_graph.py`、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **半成品的逐项复核结论**（第一节那张表，每格"成立/不成立 + 理由"）
  - **⚠️ 你实际看到了什么**（描述画面，**不要只报数字**）
  - **A/B/C 判定 + 依据**
  - **三条变异的 `-rf` 原始输出**
  - **全量测试数字**
  - **三个 sha256 的比对**
  - **磁盘纪律**：造了什么、删了什么，**以及前一 agent 的残留**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**P27 的其余两条阻断项（本项不做，等裁定）**：
- **B-2** 成片以近全黑帧收尾（**可能是有意的收尾设计**）；
- **B-3** `c10_bar_long` 冻结 482 帧（`focus` 段按设计静止 + 600 帧 scene）。

**B-1 已由 P28 修复**（真因是柱子画到画幅外，**不是标题被切**）。

**跨阶段剩**：1.3 / 10.2（标依赖、不合并、不重复建）。

**已裁定不要再讨论**：
P12 = 零段｜P13 = B+C｜P14 = B+C｜P15 = B｜P16 = 缺输入｜P17 = B｜P18 = B｜P19–P28 = 已处理