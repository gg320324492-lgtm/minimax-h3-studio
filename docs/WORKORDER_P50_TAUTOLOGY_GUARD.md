# 执行指令 — P50：一条守卫，专为抓「被阉割的断言」而写，却在同文件里放过了一条

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **本项的严重性高于它守的任何东西：守卫本身失效了。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `0f89de0`（已推送） |
| 基线 | **`757 passed, 4 skipped`**（⚠️ 实测为准） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**（GBK 控制台把 `—` 显示成替换字符）。

**⚠️ Shell 状态在两次工具调用之间不保持**。**全程用绝对路径**。
**⚠️ `git add` 用显式路径**。

**开工前记录 sha256，收尾比对**：
- `tests/test_p42_fade_is_not_a_freeze.py`（⚠️ 文件名已由指挥窗口核实）

---

## 一、指挥窗口已核实的缺陷

### 1. 那条恒真断言

```python
# :328
assert c10['durationInFrames'] in durations[:-1] or True
```

**`X or True` 恒为真。这条断言什么都不检查。**

### 2. 那条本该抓住它的守卫，看不见它

`test_p42` 里的元守卫（约 `:479-505`），docstring 原话：

> *「Every mutation harness in this project died of a variant of neutering an
> `assert X, (msg)` into `assert True or (msg)`, which keeps the message and
> the line and survives review.」*

它的实现：

```python
def _is_true(node) -> bool:
    return isinstance(node, ast.Constant) and node.value is True

...
if isinstance(node.test, ast.BoolOp) and isinstance(node.test.op, ast.Or):
    if _is_true(node.test.values[0]):          # <-- 只看第一项
        offenders.append((node.lineno, 'assert True or ...'))
```

**⇒ 它只检查 `values[0]`。** 于是：

- `assert True or X` → **抓到**（`values[0]` 是 True）
- `assert X or True` → **放过**（`values[0]` 是 X）

**⇒ 而 `:328` 正是后者，在同一个文件里。**

**⚠️ 指挥窗口已独立核实**：`grep "or True"` 在 `tests/test_p42_fade_is_not_a_freeze.py` 只命中 `:328` 一处。

### 3. 为什么这一条特别严重

docstring 说这个失效形态**杀死了本项目每一个变异工具链**。而这条守卫
**是为终结那个形态而写的**，它却**只覆盖了布尔表达式的一半**。

⚠️ **它是一台「检查器」，检查的是别的检查器有没有失效 —— 而它自己失效了，
且是在它自己那个文件里、被它自己的作者写下的那条上。**

---

## 二、你要交付的东西

### 第 1 件事：**先回答 —— `assert X or True` 该不该存在**

⚠️ **`X or True` 有两种可能，处理方式不同：**

| | 情况 | 该怎么办 |
|---|---|---|
| **I** | **笔误 / 变异残留** —— 作者本意是 `assert X` | **改成 `assert X`**，并说明它应当断言什么 |
| **II** | **刻意写的** —— 有理由让它恒真（例如「先占位」） | **⚠️ 那它就不该是一条 `assert`。** 说清理由；**恒真的断言是噪声，它会让读者以为这里有检查** |

⚠️ **⚠️ 不要为了让它绿就删掉它。**
**若你认为它本意有独立价值 → 改判据、保留断言（P39 的先例）。**
**若你认为它没有价值 → 删，但要说清理由（P39 的先例）。**
**本项目拒绝过很多次「把红变绿」。**

⚠️ **并且请判断**：`durations[:-1]` 那个表达式**若去掉 `or True`，它会通过吗？**
**请实测** —— 若它会红，那说明有人是**故意**用 `or True` 把它压绿的，
**那是一个更严重的发现（一条被静默禁用的检查）**，请单独报告。

### 第 2 件事：**修元守卫，让它覆盖布尔表达式的两侧**

⚠️ **这是本项的核心。**

- 现在只查 `values[0]`。**请让它查整个布尔表达式**：
  **只要 `or` 的任意一项恒真，整条断言就恒真** ⇒ 应当被抓到；
- ⚠️ **但要小心**：`assert a or b` 里 `b` 是合法条件是**正常的**。
  **只有当某一项是字面 `True`（或等价恒真）时才是缺陷。**
  **请说明你的判据为什么不会误报**；
- ⚠️ **请一并考虑其他恒真形状**，并说明哪些你**故意不覆盖**、为什么：
  `assert True`、`assert True or X`、`assert X or True`、`assert not False`、
  `assert 1`、`assert x == x`、`assert X or not X`（排中律）。

⚠️ **⚠️ 不要试图覆盖全部逻辑恒真 —— 那是停机问题，会造出一台误报机。**
**挑一个窄而有意义的性质**，并**在 docstring 里写清它不覆盖什么**
（P47 的守卫这么做过，是好范例）。

### 第 3 件事：**给这条元守卫本身上一道变异**

⚠️ **守卫的守卫。** 请证明：**若把元守卫改回只查 `values[0]`，会有测试变红。**

⚠️ **本项目最核心的失效形态就是「守卫永远不红」。**
**请你造出那个红，并贴 `-rf` 原始输出。**

**至少三条变异**：

| 变异 | 期望 |
|---|---|
| 在某个测试里插入 `assert X or True` | 元守卫红 |
| 把元守卫改回只查 `values[0]` | **守卫的守卫**红 |
| 让判据永远判"通过" | 红 |

⚠️ **"红在错误的理由上"不算通过**（P35 红在 `NameError`、P36 红在 `SyntaxError`）。
⚠️ **别让探针的异常变成判定**（P31/P34/P36 各栽过一次）。
⚠️ **每条毒变异后从字节快照复原，收尾核对 sha256。**

---

## 三、验证协议

1. **测量前先证明被测对象存在**（先确认那条断言真的恒真，别只读代码）；
2. **贴原始输出**，不贴结论句；
3. ⚠️ **五条高频复发**：先证明被测对象存在再测量；**在错误的尺度上测等于没测**；
   **外推等于没测**；**写数字要么实测要么标注未测**；**CRLF 用字节计数验**。
   ⚠️ **报「全场 X」之前先证明你量的确实是全场** ——
   **指挥窗口本轮把单格当整块，报出过「18 格同色」的伪影。**
4. **⚠️ 磁盘**：本项基本不渲染。**若你渲染，输出到 E 盘**，跑完清理。
   ⚠️ **`studio/.remotion/water-renewal-bundle`（1.5 GB）不是你的，别删。**
5. ⚠️ **不要与别的进程并发渲染** —— **本项会与 P49 并行跑，请用独立 scratch 目录。**
6. ⚠️ `tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD。
7. ⚠️ py-3.10 有 cv2 但没有 pytest。

---

## 四、不要动的东西

- `docs/UPGRADE_PROGRESS.md` —— **账本由指挥窗口统一更新**
- ⚠️ **`pipeline/examples/charts_demo.json` —— P49 正在改它，本项不要碰**
- ⚠️ **`studio/src/templates/finance-showcase/common/CameraRig.tsx` —— P49 的，不要碰**
- `out/charts_demo.mp4`、`out/p45_vlm/**`、`out/p48_reaccept/**` —— 只读
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`~`docs/P48*.md` —— 只读
- `DiagOutputDir` —— **禁止触碰**
- `studio/scripts/**` —— 本项不需要
- **不要动 P19–P48 的任何成果**、不要改 `studio/src/**`
- **⚠️ 不要把任何帧/图复制进仓库**

**本指令授权你修改**：`tests/test_p42_fade_is_not_a_freeze.py`（**那条断言与那条元守卫**）、相关测试、新增文档。
⚠️ **`test_p42*.py` 里除这两处之外的内容不要动** —— 它有 P42/P47 已经验收过的东西。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（**只 stage 你自己的文件**）
- 交付时报告：
  - **`assert X or True` 是情况 I 还是 II + 理由**（最重要）
  - **去掉 `or True` 之后它会通过吗（实测）** —— 若会红，那是**被静默禁用的检查**，单独报告
  - **元守卫的新判据 + 它故意不覆盖什么**
  - **守卫的守卫**：那条变异贴 `-rf`
  - **三条变异结果**
  - **全量测试数字**
  - **sha256 比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**；用**字节层快照**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列（供你了解上下文，不必处理）

- **并行跑**：**P49** 在修全片每场景 1.13 秒的静止（**不同文件，无冲突**）。
- **待办**：`c05_bubble` 的 `chart.sizes` 惰性字段、`rule_font_size` 的判定与画面无关。
- **P43 `data-plane-3d`** —— 判 C。**`video`** —— 等素材。
- **P16 / P17** —— 卡在 "premium" 无判据。
- **已裁定关闭**：11.1 / 12.2 / 12.3 / 13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1。