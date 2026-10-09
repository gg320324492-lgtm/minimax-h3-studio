# 执行指令 — 补齐 9 个无渲染器的场景类型（先分清哪几个是"能做的"）

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 本指令**不是**"把 9 个全做了"。`video` / `data-plane-3d` **要 H3，P17 已裁定 B**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `291f847`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `522 passed, 4 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**（cv2 只装在 3.10）。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`** —— 它会污染 `test_visual_qa.py`（该文件按 GBK 解码子进程输出而红）。

**⚠️ 磁盘**：`render.mjs:43-47` 记录过 **118 个 bundle 把 C: 盘 TEMP 填到 46 GB**。
**输出到 E: 盘，跑完清理，收尾报告写明造了什么、删了什么。**

**开工前记录 sha256，收尾比对**：
- `studio/scripts/visual_qa.py` → 应为 `7e7d586a…`
- `studio/scripts/frame_baseline.py` → 应为 `91e3463c…`
- `studio/bin/render.mjs` → 应为 `120b11da…`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺口的确切形状

`SceneType`（`showcase-v1.ts`）声明 **22 个**，`SCENE_RENDERERS`
（`FinanceShowcaseWide.tsx:75-93`）注册 **13 个** ⇒ **9 个落在中间**：

```
video  browser-window  stat-card  card-grid  data-table
quote  data-plane-3d   logo       outro
```

它们走 `MissingScene`（`:95`），**渲染出类型名加上 "not implemented in P4"**。

### 2. ⚠️ 但账本 3.2 曾被当作**完成**

```
| ~~3.2~~ | 20 种 scene 类型注册 | — | video/kpi-hero/browser-window/.../outro |
```

**「注册」被当成了「能渲染」。** 这正是 P21 抓出这个缺口的来源。

### 3. **9 个不是同一类东西 —— 先分类再动手**

| 类型 | 需要什么 | 能不能做 |
|---|---|---|
| `video` | **H3（MiniMax 生成）** | ❌ **P17 已裁定 B：无 H3 渲染器** |
| `data-plane-3d` | **H3** | ❌ 同上 |
| `browser-window` | 程序化（`browser-stack` 已有，**单窗口版本**） | ✅ 可能 |
| `stat-card` | 程序化 | ✅ |
| `card-grid` | 程序化 | ✅ |
| `data-table` | 程序化（**`DataColumns` 已有柱状，表格是另一种**） | ✅ |
| `quote` | 程序化（大字引言） | ✅ |
| `logo` | 程序化 | ✅ **且有特殊性，见下** |
| `outro` | 程序化（收尾） | ✅ |

**⇒ 7 个可做、2 个不可做。** 请**独立复核**这个分类，不要采信我的表。

### 4. ⚠️ `logo` 有特殊性，要单独看

`studio/scripts/locked_fields.py` 的 `LOCKED_SCENE_TYPES = frozenset({'logo'})` ——
**品牌锁的对象是 `logo` 这个类型本身**（11.2 的记录：`logo` 是**场景类型**而非 content 字段，
所以锁的是类型）。

**⇒ 锁防的是一个还没有渲染器的类型。** 请核实这一点，并在交付里说明。

### 5. ⚠️ 本项最可能被误做的两件事

1. **把 9 个都做了**（包括需要 H3 的两个）—— 那会产出两个渲染不出真东西的假渲染器；
2. **做得像"能跑"但没有内容** —— 本项目已记录过这类：
   `9.3` 的「只立规格，不接线」、`collision` 的「仪器好但缺判据」。
   **一个渲染器如果只是把 `content` 原样打印出来，它就不是渲染器。**

---

## 二、你要交付的三件事

### 第 1 件事：**先给 7 个（或更少）逐个裁定**

对 9 个**各给一个裁定**：

| 裁定 | 条件 | 动作 |
|---|---|---|
| **A：做** | 纯程序化、有真实设计、**能定义"渲染对了"是什么样** | 实现 + 守卫 + **渲染取证** |
| **B：不做（缺输入）** | 需要 H3 或外部素材 | **如实说**，别做假渲染器 |
| **C：不做（缺设计）** | 没有可依据的视觉规格，做了就是编 | **如实说** |

⚠️ **C 是完全合法的**。本项目已接受过 P12「零段」、P13/P14「B+C」、P15「B」、
P16「12 维全 B」、P17「B」。**不要为了凑数而做。**

⚠️ **若你判 C，请说明"要做它需要什么"** —— 是缺参考片（P16 已确认找不到）、
缺设计稿，还是缺某个既有组件的复用。

### 第 2 件事：实现你判 A 的那些

**每个都有三条硬要求**：

1. **有真实设计** —— 不是把 `content` 打印出来。
   **可参考已交付的四个**（`KpiHero` / `BrowserStack` / `DataColumns` / `CalendarGrid`）
   的做法：它们都从 `useDesign()` 取 token、用 `MOTION` 的 spring、走 `CameraRig`。
2. **渲染取证** —— **必须真渲一次**（`still.mjs` 单帧通常够用），
   证明它出的**不是 `MissingScene` 那个占位符**。
   ⚠️ 本项目最贵的教训：**"改进的声明"必须由渲染兑现，不是由源码兑现**
   （`UPGRADE_MASTER_PLAN.md:97`）。**4.9 两次假账就是这么来的。**
3. **守卫** —— 见第 3 件事。

⚠️ **不要动已有的 13 个渲染器**，除非你要复用它们的组件（`browser-window` 可能复用
`BrowserStack` 的单窗口部分）。

### 第 3 件事：把"缺渲染器"这件事本身钉住

⚠️ **现在已经有守卫抓这个了**：P21 的 `graph_scene_renderable` 会在图谱用到无渲染器类型时 FAIL。
**不要重复造它。** 你要加的是**另一条**：

> **`SceneType` 声明的每一个类型，要么有渲染器，要么被显式标记为"有意不做"。**

**判读要求（本项目被骗七次，最近一次就在 4.9）**：

- **必须真的读 `SCENE_RENDERERS` 的键集合并与 `SceneType` 做差集**，
  不能只断言"源码里出现某类型名"。
  ⚠️ **4.9 的 agent 第一版守卫就栽在这**：它的判据是"数字在仓库某处存在"，
  **被"删掉 520"击穿而存活**（`520` 也出现在别的夹具里）。
  它据此改成**归属**判据 —— 照这个思路做。
- **断言"某物存在"时排除注释** —— `render.mjs:141` 的注释里写着 `qa_final.py`，P17 因此栽过。
- **守卫必须能红**。至少三条变异，各贴 `-rf` 原始输出：

| 变异 | 期望 |
|---|---|
| 让一个已做的渲染器名字从 `SCENE_RENDERERS` 消失 | 守卫红 |
| 在 `SceneType` 里新增一个类型（两边都不动） | 守卫红（它没渲染器也没被标记） |
| 让判据永远判"通过" | 守卫红（专抓空转） |

**「变异存活」≠「变异无效」**：存活项判定"真漏洞"还是"无效变异"，
两种都写进 commit。**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** → **注入后先 assert 变异在文件里。**
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
   ⚠️ **指挥窗口刚犯过一次**：第一次注入破坏了语法，守卫报 `SyntaxError` —— **那不算数**。
4. **每条毒变异之后从快照复原源文件，收尾核对三个 sha256。**
5. **⚠️ 十条高频复发**（本项目已见多次，**指挥窗口本人也栽过**）：
   - **先证明被测对象存在，再测量**（指挥窗口刚栽：`ffmpeg` 解码时输出目录不存在，
     产出 0 帧、0.085s，差点读成"解码几乎免费"；P13 还测过 150 帧场景的**帧 120**，
     那时图表已退场，测出的"墨迹"全是背景噪声）；
   - **在错误的尺度上测量等于没测**（P13 的 480×270 下采样，差异被平均掉）；
   - **`visual_qa.py` 的 `--declared-px` 必须与图谱声明一致** ——
     指挥窗口刚栽过：给 480×270 的帧配 1080p 图谱，得到一个**自己制造的 FAIL**；
   - **写任何数字要么实测过、要么明确标注未测**（P18/P19/P23 各返工）；
   - **在确认变异生效之前不要宣称它存活**（P21/P22/P24 各栽过一次，均产出 `NameError`）；
   - **CRLF 污染**（**P17 的 agent 用 `p.write_text()` 污染了 1101 行**；
     **`grep -c $'\r$'` 会给出整文件 CRLF 的假读数**）——
     **用 `read_bytes`/`write_bytes`**；
   - **路径分隔符**（P17 的 `startswith('out/')` 在 Windows 上漏掉了整个 `out/`）；
   - **别把长跑命令管道进 `tail`**（指挥窗口与 P21 agent 各栽过一次）；
   - **`PYTHONIOENCODING=utf-8` 会污染 `test_visual_qa.py`**；
   - **`tests/test_markdown_text_is_intact.py` 守着全仓 markdown 的 U+FFFD**。
6. **py-3.10 有 cv2 但没有 pytest** —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**（P20 的处理方式，**是本项目接受的做法**）。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`、`docs/P2*.md`
- `out/**` —— **只读**；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要动 `visual_qa.py` / `frame_baseline.py` / `render.mjs`**
- **不要动 P19–P25 的任何成果**（`SIGNATURE_EQUAL` / `DUP_THRESHOLD` /
  `graph_scene_renderable` / `theme_contrast` / `contrast_frame` / `flicker` / `frame_baseline`）
- **不要动已交付的 13 个渲染器**（除非为复用而抽取公共部分，那要说明）
- **不要改 `GENERATIVE_SCENE_TYPES`**（`showcase-v1.ts:87-90`）
- **不要改 `FinanceShowcaseWide.tsx` 的 `resolved.map` 那一行** ——
  P15 记录了 `generative` 信号死在类型边界上，那是**待裁定**的线索，不是本项该动的
- **不要为了让某个类型"有渲染器"而做空壳**

**本指令授权你修改**：`studio/src/templates/finance-showcase/scenes/**`、
`FinanceShowcaseWide.tsx` 的 `SCENE_RENDERERS` 表、相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **9 个类型逐个裁定 A/B/C + 依据**（最重要）
  - **每个判 A 的渲染取证**（非 `MissingScene` 的证据）
  - **`logo` 与 `LOCKED_SCENE_TYPES` 的关系**
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **三个 sha256 的比对**
  - **磁盘纪律**：造了什么、删了什么
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**本项之后**：
- **已交付成片的视觉验收**（用 `visual_qa` + 人眼看成片）—— 队列里的第二项
- **P16 = 缺输入**（参考片找不到，原始任务书未持久化）
- **P17 = 缺 H3 渲染器**，且 premium 无判据
- **P11 11.1 / 11.3** —— 等"真出现一个接近碰撞的图表"（当前比值 0.278）
- **1.3 / 10.2** —— 标依赖、不合并、不重复建

**已裁定不要再讨论**：
P12 = 零段｜P13 = B+C｜P14 = B+C｜P15 = B｜P17 = B｜P18 = B｜P19–P25 = 已处理
