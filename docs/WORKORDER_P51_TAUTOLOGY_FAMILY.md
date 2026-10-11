# 执行指令 — P51：三处同形的恒真判据，**先测清覆盖面再决定合不合并**

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **本项的第一个问题不是"怎么合并"，是"该不该合并"。指挥窗口已查明它们互有独有覆盖。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `7e38898`（已推送） |
| 基线 | **`757 passed, 4 skipped`**（⚠️ 本机并发下测不出稳定数字，见第五节） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**（GBK 控制台把 `—` 显示成替换字符）。
**读非 ASCII 用字节判断，别信控制台。**

**⚠️ Shell 状态在两次工具调用之间不保持**。**全程用绝对路径**。
**⚠️ `git add` 用显式路径**，不要用 `-A` 或 `.`。
**⚠️ 本项会与 P49 并行跑，请用你独立的 scratch 目录，不要动它正在改的文件。**

**开工前记录 sha256，收尾比对**：
- `tests/test_p42_fade_is_not_a_freeze.py`
- `tests/test_p46_probe_instruments.py`
- `tests/test_visual_qa.py`
- `tests/test_locked_fields_wiring.py`
- `tests/test_p27_visual_acceptance_is_repeatable.py`

---

## 一、指挥窗口已核实的事实（本指令建立在此之上，不是引述）

### 1. 四份判据，各不相同 —— **且互有独有覆盖**

| 文件 | 判据 | 抓 `A or True` | 抓嵌套 `or`（`and` 下一层） | 抓 `A == A` |
|---|---|---|---|---|
| `test_locked_fields_wiring.py` | `is_tautology()` | ✅ | ❌ | ✅ |
| `test_p42_fade_is_not_a_freeze.py`（P50 刚建） | `_tautology_offenders()` | ✅ | ✅ **（`ast.walk`）** | ❌ |
| `test_p27_visual_acceptance_is_repeatable.py:587` | P27 原始那条 | ❌ **只查 `values[0]`** | ❌ | ❌ |
| `test_p46_probe_instruments.py` | ？**请自己查** | ？ | ？ | ？ |

⚠️ **指挥窗口已实测：前两份都不是对方的超集。**
**⇒ "合并成一份"不是显然该做的事。**

### 2. ⚠️⚠️ 那份"已经写对的"判据，其文件明确**拒绝**造守卫的守卫

`test_locked_fields_wiring.py` 的 docstring 原话：

> *"...level of infinite regress and is deliberately **NOT** built here. The project
> has a track record in the direction that needs it (**a test rewriting its own
> source: six silent CRLF patch failures**, and one **`git checkout -- <file>` that
> discarded uncommitted work**)."*

**⇒ 而 P50 恰恰造了一个** —— 办法是把判据抽成接收 `tree` 的纯函数，
让它的测试传**夹具树**而不是自己的源码。

⚠️ **这不是"谁对谁错"，是两个不同的风险取舍，你必须先说清你站在哪一边。**

### 3. 两条**活的**恒真断言（P50 报出，指挥窗口逐字核实）

```python
# tests/test_p46_probe_instruments.py:229
assert chart.unavailable(tmp_path / 'nope.png', transport=lambda *a: {}) is None or True

# tests/test_visual_qa.py:771
assert raw.decode('utf-8').isprintable() or True   # decodable is the assertion
```

⚠️ **`:771` 那条作者是知情的** —— 注释写着 *"decodable is the assertion"*，
**而他写的判据（`isprintable()`，而 JSON 里有换行 ⇒ 必假）会让它红，
于是加了 `or True` 把它压绿。**

**⇒ 这不是"忘了写检查"，是"写了检查、发现它会红、然后把它变成永远绿"。**

### 4. ⚠️ 一个指挥窗口已经犯过、你别重犯的错误

复验 P50 时，指挥窗口**为了独立复验它那条守卫，在同一个文件上做了毒变异**，
而那个窗口正好压在那位 agent 的 commit 上 ⇒ 它 commit 后核对 sha256 时看到的是
指挥窗口留下的毒。**它花了很长时间排查 git 线索才排除掉所有 git 解释，
最后猜错了原因。**

**⇒ 若你也在别人正在收尾的文件上做变异，先确认对方是否还在动它。**
**⚠️ 更根本的：你应当尽量避免在共享仓库里对别人正在编辑的文件做字节级改写。**

---

## 二、你要交付的东西

### 第 1 件事：**先测量覆盖面，再决定合并与否**

⚠️ **不要一上来就合并。** 请先做一张**实测的**覆盖表：

**构造一个形状空间**（至少 12–15 个），每个形状标注：
- 它是不是真的恒真/无意义；
- **四份判据各自会不会标记它**。

⚠️ **形状空间至少包含**（可增）：
`assert True` / `assert True or X` / `assert X or True` / `assert X or Y or True` /
`assert (X or True) and Y` / `assert X == X` / `assert not False` / `assert 1` /
`assert X and False` / `assert X or not X` / `assert f() == f()` /
`assert X is None or True` / 合法的 `assert a or b` / 合法的 `assert X == Y` /
`assert X > 0 or True`

⚠️ **⚠️ 这就是「先证明被测对象存在」在本项的形态** ——
**你先得有一张可信的"什么是缺陷"表，才谈得上测判据。**

**⇒ 然后回答**：
1. **四份判据里，哪些是彼此的真子集？**（贴实测矩阵）
2. **合并成一份，会丢掉谁独有的覆盖？**（若会，说明合并要补什么）
3. **⚠️ 合并会让另外两个文件的测试变红 —— 那些红里，有多少是真的缺陷？**
   **请逐条说清，不要笼统说"会红"。**

### 第 2 件事：**处理那两条活的恒真断言**

对每一条，先回答工单 P50 问过、而你必须**再问一次**的那个问题：

**它是哪种情况？**

| | 情况 | 怎么办 |
|---|---|---|
| **I** | 笔误 / 变异残留 | 改成真断言 |
| **II** | 刻意恒真（有意占位） | ⚠️ 那它不该是一条 `assert`，说清理由 |
| **III** | **断言本身有意义，只是判据写错了** | **改判据，保留断言** |

⚠️ **P50 在 `:328` 上遇到的正是第三种**：`durations[:-1]` 乍看像写错了，
**而 `c10` 恰是末位，切片去掉的正是它自己** ⇒ 断言含义是
「c10 的时长等于某个**别的**场景的时长」=「不再是异类」，正是 B-3 的核心主张。
**⇒ 若按笔误删掉整行，就会连同 B-3 的核心断言一起丢掉。**

**⚠️ 你的两条里，`:771` 的注释已经说了它的意图是 "decodable" ——
请判断正确判据是什么（`raw.decode('utf-8')` 成功就是可解码，
而上一行 `:769` 已经 `json.loads` 过一次了 —— **⚠️ 那意味着"可解码"已经被断言过了，
所以这条断言可能是完全冗余的**，请核实并说明）。**

### 第 3 件事：**给"判据本身"上一条守卫**

⚠️ **⚠️ 但先回答这个问题：这条守卫该不该存在？**

**`test_locked_fields_wiring.py` 明确拒绝了它**，理由是
*"a test rewriting its own source: six silent CRLF patch failures,
and one `git checkout --` that discarded uncommitted work"*。

**⇒ 三个选项，请选一个并给理由：**

- **A. 建**，用 P50 的办法（判据抽成接收 `tree` 的纯函数，测试传夹具树，
  **不读自己的源码**）—— **这样能绕开那份 docstring 担心的风险吗？请论证**；
- **B. 不建**，采纳 `test_locked_fields_wiring.py` 的立场 ——
  **⚠️ 但那份 docstring 同时写着**：
  > *「**Weakening the checks above leaves the suite fully green.
  > "The guard is still there" is not the same claim as "the guard works".**」*

  **⚠️ 也就是说它自己承认"守卫还在"不等于"守卫在工作"。** **那这个风险由谁承担？**
- **C. 别的** —— 你若有第四条路，说清。

⚠️ **⚠️ 不要为了省事选 B。** **B 意味着本项目承认"判据可以被静默收窄，
而没有任何东西会发现"** —— **而本项的起因恰恰是有人收窄了它。**

**若判 A，至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 把判据改回只查 `values[0]`（P50 的缺陷形态） | 守卫红 |
| 在某个测试里插入 `assert X or True` | 元守卫红 |
| 让判据永远返回"无违规" | 守卫红 |

⚠️ **"红在错误的理由上"不算通过**。⚠️ **别让探针的异常变成判定**。
⚠️ **每条毒变异后从字节快照复原，收尾核对 sha256。**

---

## 三、验证协议

1. **测量前先证明被测对象存在**（§二.1 那张形状空间表就是本项的"存在性证明"）；
2. **贴原始输出**，不贴结论句；
3. ⚠️ **五条高频复发**：先证明被测对象存在再测量；**在错误的尺度上测等于没测**；
   **外推等于没测**；**写数字要么实测要么标注未测**；**CRLF 用字节计数验**
   ⚠️ **这批文件里有纯 CRLF 的，动之前先测行尾**；
4. ⚠️ **磁盘**：本项基本不渲染。**若你渲染，输出到 E 盘**，跑完清理。
   ⚠️ **`studio/.remotion/water-renewal-bundle`（1.5 GB）不是你的，别删。**
5. ⚠️ **不要与别的进程并发渲染** —— 已有三个 agent 因此制造过假红。
   **并注明你报的测试数字是否在并发下取得。**
6. ⚠️ `tests/test_markdown_text_is_intact.py` 守着全仓 markdown 的 U+FFFD。
7. ⚠️ py-3.10 有 cv2 但没有 pytest —— 需要 cv2 就写进普通函数用 3.10 驱动，
   3.12 里 **skip 而不是撒谎**。

---

## 四、不要动的东西

- `docs/UPGRADE_PROGRESS.md` —— **账本由指挥窗口统一更新**
- ⚠️ **`pipeline/examples/charts_demo.json`、`studio/src/**`、`tests/test_p49_camera_move_is_not_a_freeze.py`**
  —— **P49 正在改，不要碰**
- ⚠️ **`tests/test_p42_fade_is_not_a_freeze.py`** —— ⚠️ **指挥窗口刚在它上面做过毒变异，
  压在了那位 agent 的 commit 上**（已恢复，sha256 `0e2b3171…`）。
  **⚠️ 若你要动它，先 `git status` 与 `git log` 确认无人正在编辑，并在报告里说明你为什么需要动它。**
  **优先改那两条活的恒真断言所在的其他文件。**
- `out/charts_demo.mp4`、`out/p45_vlm/**`、`out/p48_reaccept/**` —— 只读
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`~`docs/P50*.md` —— 只读
  （⚠️ `docs/P48_REACCEPTANCE.md` 的过时处**已由账本侧标注**，你不要改）
- `DiagOutputDir` —— **禁止触碰**
- **不要动 P19–P50 的任何成果**、不要改 `studio/**`

**本指令授权你修改**：`tests/test_p46_probe_instruments.py`、
`tests/test_visual_qa.py`、`tests/test_p27_visual_acceptance_is_repeatable.py`、
`test_locked_fields_wiring.py`、必要时**新增**一个共享判据模块、相关测试、新增文档。
⚠️ **`test_locked_fields_wiring.py` 改动前先说明为什么必须改** —— 它有已验收的内容。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（**只 stage 你自己的文件**）
- 交付时报告：
  - **那张实测覆盖矩阵**（形状 × 四份判据），**贴原始输出**
  - **哪些判据互为真子集、合并会丢什么**
  - **合并会让哪些测试变红、其中多少是真缺陷**（逐条）
  - **两条活的恒真断言各是 I / II / III**
  - **⚠️ `:771` 是否完全冗余**（`:769` 已经 `json.loads` 过了）
  - **守卫该不该建：选 A / B / C + 理由**
  - **若选 A：那三条变异的 `-rf`**
  - **全量测试数字 + 是否并发取得**
  - **五个 sha256 比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**；用**字节层快照**
  （⚠️ `test_locked_fields_wiring.py` 的 docstring 明确记着
  *"one `git checkout --` that discarded uncommitted work"*）
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列（供你了解上下文，不必处理）

- **并行跑**：**P49** 在修全片每场景 1.13 秒的静止（`charts_demo.json` + `CameraRig.tsx`）。
- **待派**：`c05_bubble` 的 `chart.sizes` 惰性字段（回退值静默替换真实意图）、
  `rule_font_size` 的判定被 `--declared-px` 劫持（仪器是真的，判据不看画面）。
- **P50** —— 元守卫的洞已闭（`6fc9b82`）。**本项是它的续。**
- **P43 `data-plane-3d`** —— 判 C。**`video`** —— 等外部素材。
- **P16 / P17** —— 卡在 "premium" 无判据。
- **已裁定关闭**：11.1 / 12.2 / 12.3 / 13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1。