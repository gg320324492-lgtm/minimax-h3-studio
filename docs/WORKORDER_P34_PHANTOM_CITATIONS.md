# 执行指令 — 四簇假注释/死引用全部修掉（B1 / A4+A6 / B3 / B4）

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 四簇是 P33 勘察（`32c3b9d`）列出的待裁定项，用户已裁定：**全部修掉**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `b497a43`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `632 passed, 4 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**（cv2 只装在 3.10）。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`** —— 它会污染 `test_visual_qa.py`。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，命令以 `cd E:/Minimax-H3 &&` 开头。
**⚠️ 磁盘**：**输出到 E: 盘**，跑完清理。

**开工前记录 sha256，收尾比对**：
- `studio/src/templates/finance-showcase/scenes/*.tsx`（**行数必须不变**，见第 3 件事）
- `studio/scripts/locked_fields.py`
- `studio/scripts/visual_qa.py` → 应为 `7e7d586a…`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 簇 B1（8 处）：**指向一个从未存在过的测试文件**

⚠️ **指挥窗口已复现**：`tests/test_design_system.py` **不在磁盘、`git log --all` 全历史无记录**。

**八个引用点**：`Brand.tsx` / `BrowserStack.tsx` / `BrowserWindow.tsx` / `Cards.tsx` /
`DataColumns.tsx` / `DataTable.tsx` / `KpiHero.tsx` / `Quote.tsx`。

**引用不是状态注记，是指令**（`Quote.tsx:5-7` 与 `Cards.tsx:5-7` 逐字相同）：

```tsx
// Fonts and scaling are NOT theme-scoped, so importing them is correct.
// Everything that IS theme-scoped (palette, type, spacing, shadow) must come
// from useDesign() — see tests/test_design_system.py.
```

**⇒ 前一位执行 agent 正确地没有只改一处** —— 改 1/8 会造成不一致，
**而它也不知道正确的替代是哪个**。

**⚠️ 指挥窗口已查到正确的替代**（`tests/test_showcase_schema_parity.py:283-300`）：

```python
def test_scenes_do_not_import_design_values_directly():
    """Scenes must read palette/type/motion through the style bible context.
    Fonts and the design-height scale stay a static import on purpose — they are
    not graph-overridable — so the check is for the design VALUES, not for any
    import from the tokens module."""
    design_values = ('PALETTE','TYPE','MOTION','SPACE','RADIUS','SHADOW','DEPTH')
```

**⇒ 那条规则的真实守卫是这个，而且它区分得比注释更精确**：
**"字体与缩放是刻意的静态 import，检查针对的是 design 值"** ——
**这正是那八处注释要传达的东西。**

**请核实这个判据，并用它改那八处**（**八处要一致**）。
⚠️ **若你发现更好的替代、或这个函数即将改名，请如实报告** —— **不要将就我给的答案。**

### 簇 A4 / A6：两处已过期的断言与行号

| # | 位置 | 断言 | 实际 |
|---|---|---|---|
| A4 | `locked_fields.py:26-29` | "**Two** things are locked: `type` … and `content.name`" | P31 后是**三**个：`type` / `name` / `tagline` |
| A6 | `locked_fields.py:10` | `content` 在 `showcase-v1.ts:100` | **:100 是 `rotateX`**；`content` 在 **:256** |

⚠️ **A4 是「活的少报」不是历史陈述** —— 它现在就在误导人。

### 簇 B3 / B4：两处死引用

| # | 位置 | 问题 |
|---|---|---|
| B3 | `locked_fields_brand_mutation.py:3` | Usage 指向 `E:/Minimax-H3/_p30_mutation_run.py` —— **该文件不存在也未被 git 跟踪** |
| B4 | `locked_fields_mutation.py` | **两个变异锚点已死**（P30 重写了 `diff_locked`）：`b_by_path = {p: v for _, _, p, _, v in iter_locked(before)}` 与 `emit(before, after, primary=True)` 在现行代码里**均不存在** |

⚠️ **B4 的好消息**：那个 harness 找不到锚点会**大声失败并返回 1**，不是静默失效。
**⚠️ 但那些变异实际上已不再运行** —— **账本把 P11 的结果列在「4 全杀」里，
而其中一条自 P30 起就没跑过了。**

---

## 二、你要交付的三件事

### 第 1 件事：修 B1 的八处，**八处一致**

⚠️ **判读要求**：

- **不要只把文件名换掉** —— 那样得到的是"八处一致地指向另一个可能也不对的地方"；
- **那八处注释要传达的信息是「字体/缩放可以静态 import，design 值不行」** ——
  **请确认新的引用确实守着这条**，而不只是"有个测试文件叫这名字"；
- **⚠️ 逐处核对那八处的措辞是否真的相同** —— 若有差异，**按各自的实际代码改**。

### 第 2 件事：修 A4 / A6 / B3 / B4

- **A4**：把"两样"改成当前真实的三个，并**说明为什么是这三个**；
- **A6**：核对行号后改（或改成不依赖行号的表述，**由你判断哪种更好**）；
- **B3**：Usage 指向的那个文件确实不存在 ⇒ 改成真实可跑的入口，**或删掉那条**；
- **B4**：⚠️ **两个锚点已死，harness 会大声失败** ——
  **请把它修到能真正运行**，**并如实说明修好后那两条变异的结果是什么**
  （**它们自 P30 起就没跑过，所以"当年杀掉"这个结论对它们已经不成立**）。

### 第 3 件事：给"注释引用必须落在代码上"上一条守卫

⚠️ **这是本项最有价值的交付物** —— **因为 B1 那八处从未失败过。**

**要求**：

1. **凡源码注释里出现的 `tests/xxx.py`（或任何文件路径）引用，必须在磁盘上存在**；
2. ⚠️ **不能只断言"字符串在文件里"** —— **那正是本项目被欺骗八次的形状**。
   **要真的解析路径、检查存在**；
3. ⚠️ **必须排除注释里合法的历史陈述** —— 例如
   「这个测试曾在 `tests/old.py`、已删除」**是合法的历史**，
   守卫不能把这类也判红。**请设计一个能区分"当前引用"与"历史引用"的判据**
   （**若你认为做不到，就如实说**，并说明为什么）。

**至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 把某处引用改成一个不存在的文件名 | 守卫红 |
| 删掉一处引用 | **守卫应当绿**（少引用不是问题）—— 请确认并说明 |
| 让判据永远判"通过" | 守卫红 |

⚠️ **⚠️ 行号引用这一族请一并考虑**（P33 的真正教训）：
`locked_fields.py:347` 用**行号**引用 `Brand.tsx`（`:93`、`:156-157`）。
**⇒ 若守卫只查文件路径、不查行号，那条失效形态仍然漏着。**
**请判断是否要一并覆盖，并说明代价。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果**；**且要证明它不是死分支**。
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
4. **每条毒变异之后从快照复原，收尾核对 sha256。**
5. **⚠️ ⚠️ 行数中性（P33 用一条 35 行的代价换来的）**：
   `locked_fields.py` 用**行号**引用 `Brand.tsx`。
   **⇒ 你若给 `Brand.tsx` 加行，那些引用会全部落进注释中间 ——
   仍然"能解析"、读起来像可信断言、没有任何东西失败。**
   **要么保持那八个文件的行数不变，要么同步更新 `locked_fields.py` 的行号引用。**
6. **⚠️ 高频复发**：先证明被测对象存在再测量；确认变异生效前不要宣称存活；
   CRLF 用字节计数验（**`p.write_text()` 在 Windows 上翻译行尾，P17 的 agent 污染了 1101 行**）；
   路径分隔符；别把长跑命令管道进 `tail`；`tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD；
   ⚠️ **`comment_blocks` 读不了 Python 的 `#`**（P33 踩过）—— 用 `tokenize`。
7. **py-3.10 有 cv2 但没有 pytest** —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`、`docs/P2*.md`、`docs/P3*.md`
- `out/p13_probe/**` 与 `out/*.mp4` —— 只读；`DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要动 `visual_qa.py` / `frame_baseline.py` / `render.mjs` 及 P19–P33 的成果**
  —— ⚠️ **注意：B2 那个失效在 `visual_qa.py:1155`，但上一份工单把它禁碰了；
  本项请把它一并修掉**（它只是一条注释的**行号**，不涉及判定逻辑）。
- **不要改品牌锁的两条裁定**（`{'logo','outro'}` 与 `('name','tagline')`）
- **不要给 11.1 的七个杠杆加锁**
- **不要改任何场景的渲染逻辑** —— 本项只改注释与变异锚点
- **不要顺手修 P27 的 B-2 / B-3**（设计后果，待裁定）

**本指令授权你修改**：那八个源文件的**注释**、`locked_fields.py` 的注释、
`visual_qa.py:1155` 的注释、两个 mutation harness 的锚点、相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **B1 你用什么判据定的替代**（⚠️ 若与我给的不同，说清理由）
  - **A4 / A6 / B3 各自改成了什么**
  - **⚠️ B4 修好后那两条变异的结果**（**"当年杀掉"对它们已不成立**）
  - **守卫能否区分「当前引用」与「历史引用」**；若不能，**为什么**
  - **行号引用那一族是否一并覆盖 + 代价**
  - **全量测试数字**
  - **逐条变异结果**（贴 `-rf` 原始输出）
  - **sha256 的比对**；**八个场景文件行数是否不变**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**P27 遗留（待裁定）**：**B-2** 末帧近黑、**B-3** 冻结
（`outro` 尾部实测约 124 帧 / 2.07s）。

**跨阶段剩**：1.3 / 10.2（标依赖、不合并、不重复建）。

**已裁定不要再讨论**：
P12 = 零段｜P13 = B+C｜P14 = B+C｜P15 = B｜P16 = 缺输入｜P17 = B｜P18 = B｜P19–P33 = 已处理