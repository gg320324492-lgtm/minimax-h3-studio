# 执行指令 — 把品牌锁接上：它现在是一个只有注释、没有规则的常量

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `0c00893`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `561 passed, 4 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**（cv2 只装在 3.10）。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`** —— 它会污染 `test_visual_qa.py`。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，依赖仓库根的命令以 `cd E:/Minimax-H3 &&` 开头。

**⚠️ 磁盘**：**输出到 E: 盘**，跑完清理。**C 盘刚清过（39.9 → 62.6 GB）**，
有 agent 就是被 C 盘 0 字节空闲打断的。

**开工前记录 sha256，收尾比对**：
- `studio/scripts/locked_fields.py`
- `studio/scripts/visual_qa.py` → 应为 `7e7d586a…`
- `studio/scripts/frame_baseline.py` → 应为 `91e3463c…`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 那把锁的现状：**常量有、注释有、规则没有、读者没有**

`studio/scripts/locked_fields.py:99-100`：

```python
# Scene types that carry brand meaning and must survive a repair.
LOCKED_SCENE_TYPES: frozenset[str] = frozenset({'logo'})
```

**指挥窗口独立复现**：

```
改 logo 的品牌名            → diff_locked 报 0 条违规
把 logo 场景改道成 bar-chart → diff_locked 报 0 条违规     ← 这正是这把锁存在的目的
coverage_report([含 logo 的图谱]).by_kind.brand == []
```

**全仓检索 `LOCKED_SCENE_TYPES`：只有声明处、注释（`Brand.tsx:15/17`）、三处测试断言**
（`test_locked_fields.py:184`、`test_locked_fields_wiring.py:323/:327`）
—— **零生产代码读它**。

⚠️ **比"没有读者"更彻底**：读 `diff_locked` 的实现，**它根本没有读 `LOCKED_SCENE_TYPES`**
⇒ **不是"规则写了但没接线"，是规则本身就不存在**。

### 2. 它与另两类锁的区别（本项的设计要点）

`LOCK_RULES` 有 14 条，3 种 kind：**fact 9 / copy 4 / identity 1**。
它们锁的是**字段**（`values` / `labels` / `headline` …），
机制是 `_RULE_BY_KEY` 按 key 匹配。

而 `logo` 是**场景类型**，不是 content 字段 —— **`content` 是开放袋子，
每个字段都是 `unknown`，没有类型边界可依赖**（11.2 的记录原话）。

**⇒ 这两类锁的机制天然不同，参数 11.2 已经写明了**：

> 为什么不走字段规则：**为什么是显式路径而不是类型**：
> `content` 是 `z.record(z.string(), z.unknown())`，
> **每个场的每个字段都是 `unknown`，包括那些不得动的** ⇒ 没有类型边界可靠，
> **锁必须显式写下来，代价就是可能不完整** —— 所以 `LOCK_RULES` 导出且在测试里数掉，
> `coverage_report()` 直接打印交付图谱真正命中的部分。

### 3. ⚠️ `11.2` 声称的东西已被 P26 部分推翻

账本 11.2 写：「**品牌那一类不走字段规则**：`logo` 是**场景类型**而非 content 字段，
所以锁的是类型本身」—— **但锁类型这件事从未实现。**

而 **P26 文档写**「P26 给了 `logo` 渲染器之后，锁就可证伪了」——
**实测仍然不可证伪**（`by_kind.brand == []`）。

### 4. 三个问题需要你判定，而它们是**产品判断**

⚠️ **本项最难的不是写代码，是决定"品牌锁定"意味着什么。**

| 问题 | 为什么必须先答 |
|---|---|
| **(a) 锁什么？** | 锁 `type` 不变？锁 `content.name`？还是锁整段 content？ |
| **(b) 锁到多严？** | `identity` 那类锁"整个标签被删"；品牌锁是否也要禁"改名"？ |
| **(c) 修好之后，`by_kind.brand` 该显示什么？** | 现在是 `[]`。修好后应该非空 —— **但那会让 `unexercised` 之类的既有断言变化**，请说明影响 |

**我对 (a) 的初判（不是裁定）**：锁 `type`（场景不能被改道）
**加上** `content.name`（品牌名不能被改）—— **但 `content` 是开放袋子，
所以必须显式列出要锁的键名，这正是 11.2 说的"代价"**。

**⚠️ 请独立判断，不要采信我的初判。**

---

## 二、你要交付的三件事

### 第 1 件事：**先答 (a)(b)(c)，再写规则**

**给一个明确裁定**，并说明依据。

⚠️ **⚠️ 若你认为"这不该由我决定"** ——
**那就如实说，并把问题写清楚交给指挥与用户**，
**同时给出 2–3 个可选方案 + 各自的代价**。
**不要自己拍一个然后往下做。**
**本项目已接受过七次"实测说不出想要的结果"**（`collision` / `rule_duplicate` /
`rule_contrast_frame` / `flicker` / P12 零段 / P16 十二维 / P17）。

### 第 2 件事：实施你裁定的结果

**若裁定要接线**，实现要点：

- **它必须走 `diff_locked` 的现有返回路径**（`LockedField` / `kind`），
  **不要另起一套机制** —— **⚠️ 本项目吃过一次：P12 的 P21 那次，
  两个调用点持有同一个常数、另一个却硬编码字面量，改阈值必漏**；
- **`kind` 用什么？** 现有三种是 fact / copy / identity。
  **品牌属于哪一种，还是需要第四种？** —— **若需要第四种，
  请说明它对 `by_kind` 计数、`coverage_report()` 与既有守卫的影响**；
- ⚠️ **`unexercised` 会被改动** —— 现在 `by_kind.brand == []`，
  接上规则后它在含 `logo` 的图谱上会命中。**请把影响写清**。

**若裁定不接线**（例如认为产品意图未明）：

- **把那一行注释改成说真话** ——
  **⚠️ 当前的注释「Scene types that carry brand meaning and must survive a
  repair」是一个承诺，而承诺没有兑现。这是本项目最核心的那类失效。**
- **并把"要接线需要先定什么"写进同一处**。

### 第 3 件事：给"品牌锁真的会拦"上一条守卫

⚠️ **本项的守卫是这次交付的核心，比代码更重要** ——
**因为这把锁已经"绿着"很久了。**

**判读要求（本项目被骗七次）**：

- **必须真的调用 `diff_locked` 并断言它的返回值**，不能断言源码里出现
  `LOCKED_SCENE_TYPES` 这个名字。
  ⚠️ **已有三条测试就是断言那个常量的值**（`test_locked_fields.py:184` 等）
  —— **它们会一直绿，而锁一直不生效**。**本项的守卫必须断言行为，不是断言常量。**
- 守卫要能回答：**"如果明天有人把品牌规则从 `diff_locked` 里删掉，会怎样？"**
  **答案必须是红。**

**至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 把品牌规则从 `diff_locked` 里摘掉（模拟今天的状态） | 守卫红 |
| 让规则永远不 emit（`if False:`） | 守卫红 |
| 让规则对所有场景类型都 emit | 守卫红（专抓"过度锁"——那会把 11.1 的合法杠杆也锁死） |

⚠️ **第三条特别重要**：11.2 明确「**不锁的是审计结论而不是口味**」——
`durationInFrames` / `camera` / `motion` / `layout` / `style_bible` / `format` /
`transitionIn/Out` **正是 11.1 点名的杠杆，锁了它们修复循环就什么都做不了**。
**守卫必须同时断言这些杠杆仍然放行**，否则一把"总是锁"的锁也能让上面的变异红。

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** → **注入后先 assert 变异在文件里。**
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
   ⚠️ **指挥窗口刚犯过一次**：第一次注入破坏了语法，守卫报 `SyntaxError` —— 那不算数。
4. **每条毒变异之后从快照复原，收尾核对三个 sha256。**
5. **⚠️ 高频复发**：先证明被测对象存在再测量；在错误的尺度上测等于没测；
   写数字要么实测要么标注未测；确认变异生效前不要宣称存活
   （P21/P22/P24 均产出过 `NameError`）；CRLF 用字节计数验
   （**`p.write_text()` 在 Windows 上翻译行尾，P17 的 agent 污染了 1101 行**）；
   路径分隔符（P17 的 `startswith('out/')` 在 Windows 上漏掉整个 `out/`）；
   别把长跑命令管道进 `tail`；`tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD。
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
- **不要动 `visual_qa.py` / `frame_baseline.py` / `render.mjs` 及 P19–P29 的成果**
- **不要动 11.2 那 14 条 `LOCK_RULES`** —— **它们都实测在工作**
  （`unexercised` 与 `by_kind` 都有真实命中）
- **不要给 `durationInFrames` / `camera` / `motion` / `layout` / `style_bible` /
  `format` / `transitionIn/Out` 加锁** —— **那是 11.1 的合法杠杆**，
  **⚠️ 锁了它们修复循环就什么都做不了。守卫必须断言它们仍然放行。**
- **不要改 `Brand.tsx` 的实现**（本项是锁，不是渲染器）
- **不要顺手修 B-2 / B-3**（设计后果，待裁定）

**本指令授权你修改**：`studio/scripts/locked_fields.py`、
相关测试（**含那三条只断言常量的旧守卫——但请按下面第 3 件事的方式改，不要直接删**）、
新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **(a)(b)(c) 三个问题的裁定 + 依据**（最重要）
  - **若你认为不该由 agent 决定**：说清楚，并给出 2–3 个方案与代价
  - **`unexercised` / `by_kind` 的影响**
  - **⚠️ 11.1 的七个合法杠杆在修复后是否仍然放行**（给实测）
  - **全量测试数字**
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **三个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**P27 遗留（本项不做，待裁定）**：**B-2** 末帧近黑、
**B-3** 冻结（`outro` 尾部实测约 124 帧 / 2.07s，与 B-3 同形状）。

**其他提请裁定（未决）**：
`test_the_probe_set_is_what_this_file_claims` 的硬编码 `36`／
`showcase-v1.ts:290` 注释称 `_note` 只存在于一份图谱（现有两份）／
`"+0.0pt"` 渲染成绿色正增长。

**跨阶段剩**：1.3 / 10.2（标依赖、不合并、不重复建）。

**已裁定不要再讨论**：
P12 = 零段｜P13 = B+C｜P14 = B+C｜P15 = B｜P16 = 缺输入｜P17 = B｜P18 = B｜P19–P29 = 已处理