# 执行指令 — `Brand.tsx` 的头注释是一份假账：它说「锁未被改动」，而锁已被接线两次

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `aa509c4`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `617 passed, 4 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**（cv2 只装在 3.10）。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，命令以 `cd E:/Minimax-H3 &&` 开头。
**⚠️ 磁盘**：**输出到 E: 盘**，跑完清理。

**开工前记录 sha256，收尾比对**：
- `studio/src/templates/finance-showcase/scenes/Brand.tsx`
- `studio/scripts/locked_fields.py`
- `studio/scripts/visual_qa.py` → 应为 `7e7d586a…`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 那段注释的原话（`Brand.tsx:12-30`）

```tsx
/**
 * ── THE `logo` TYPE AND `LOCKED_SCENE_TYPES` ─────────────────────────────
 *
 * `studio/scripts/locked_fields.py` carries `LOCKED_SCENE_TYPES = frozenset(
 * {'logo'})`, and its comment says why: "`logo` is a scene TYPE in
 * showcase-v1.ts:36, so the brand mark is a scene, not a field. Locking the
 * type is what stops a repair from rerouting it to a chart to make it fit."
 *
 * WHAT THAT LOCK ACTUALLY WAS. Until P26 it guarded a type that had NO renderer:
 * ... Registering a renderer gives the lock an artefact.
 * The lock itself is untouched; `tests/test_locked_fields.py` still pins it.
 */
```

### 2. ⚠️ **最后两句现在都不成立**

| 注释说 | 实际 |
|---|---|
| `LOCKED_SCENE_TYPES = frozenset({'logo'})` | **P31 已改成 `frozenset({'logo', 'outro'})`** |
| "The lock itself is untouched" | **P30 接线了品牌规则（`iter_scene_locked`）**；**P31 又纳入 outro 与 tagline** |
| "`tests/test_locked_fields.py` still pins it" | **P30 把那条守卫从断言常量改成了断言行为** —— agent 明确报告「M1 红里含**两条被改写的旧守卫**，**证明它们不再是常量 pin**」 |

**⇒ 这不是"过期"，这是本项目最核心的那类失效：一段注释在描述一件早已不成立的事，
而读它的人会以为那是现状。**

**⚠️ 注意**：P26 写这段注释时**它是对的**（那时锁确实没被接线、守卫确实钉的是常量）。
**所以本项不是"谁写错了"，而是"记录没有随裁定更新"** —— 这与 4.9 那两次假账同源。

### 3. ⚠️ 与本项目另一条教训的对照

`LOCKED_SCENE_TYPES` 在 `locked_fields.py:99` 的注释写：

> `# Scene types that carry brand meaning and must survive a repair.`

**那是同一个承诺的另一个副本** —— 而那一个**在 P30 之前也是假的**
（`diff_locked` 根本没读它）。

**⇒ 同一个失效有两个副本。** **请核实是否还有第三个。**

---

## 二、你要交付的三件事

### 第 1 件事：把这段注释改成说真话

⚠️ **不是删掉，是改成现在为真**。

**新注释该说清**（措辞自定，但事实必须对）：

1. **`LOCKED_SCENE_TYPES` 现在是什么**（`{'logo', 'outro'}`）；
2. **品牌锁现在真的接在 `diff_locked` 上**（P30 走的 `iter_scene_locked`，
   **并说清它与 `LOCK_RULES` 是两套机制、为什么** ——
   `LOCK_RULES` 按 key 匹配**每个场景**的 content，而 content 是开放袋子，
   **所以品牌锁必须按场景类型限定**）；
3. **`BRAND_CONTENT_KEYS` 现在是 `('name', 'tagline')`**（P31 裁定）；
4. **P26 那段推理仍然成立、但已经不是全部** ——
   "注册渲染器给了锁一个可证伪的物件"是 P26 的贡献，**保留它**，
   但**后面必须接上 P30/P31 做了什么**；
5. ⚠️ **`tagline` 的对称锁与渲染器契约的关系**（若你认为值得写）：
   `Brand.tsx:95` 条件渲染 ⇒ **缺失是合法状态**，
   而锁仍然对称 —— **"那个三元式说的是画什么，不是谁可以写这个字段"**。

### 第 2 件事：**扫一遍还有没有同类**

⚠️ **本项的真正价值不是改一段注释，是知道这类注释还有多少。**

请检索：**全仓的源码注释里，有哪些在描述 `LOCKED_SCENE_TYPES` / 品牌锁 / P30 / P31 的状态？**
逐条判断**是否仍然为真**。

⚠️ **判读要求**：

- **不要只 grep 关键词** —— **本项目被文本存在性断言骗过八次**。
  要读**那句话在断言什么**，然后**去代码里核对那个断言**；
- **⚠️ 特别注意 `locked_fields.py` 自己的注释** —— 那是同一个承诺的另一个副本；
- **若发现第三处同类假注释，如实报告**，并**说明它是否影响代码行为**
  （注释不影响行为，但**读注释做决定的人会栽**）。

### 第 3 件事：给"注释不撒谎"上一条守卫

⚠️ **这是本项最有价值的交付物** ——
**因为这段注释已经骗过人一次了**（P26 写时为真，P30/P31 之后变假）。

**判读要求（本项目被骗八次）**：

- **守卫必须真的读注释并核对它断言的事实**，**不能**只是断言"某个字符串在文件里"。
  ⚠️ **那恰恰是本项目最常见的失效**：断言文本存在。
- **⚠️ 判据要从代码里推导**（例如：`LOCKED_SCENE_TYPES` 的实际值 →
  注释里声称的值是否一致），**不能**把两个常量都写死在测试里。

**至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 把 `LOCKED_SCENE_TYPES` 改成三个类型，**注释不动** | 守卫红 |
| 把注释里的类型名改错 | 守卫红 |
| 让判据永远判"通过" | 守卫红 |

⚠️ **变异一是本项的核心** —— **那正是这次发生的事**：
裁定改了、注释没改。**守卫必须能抓住它。**

⚠️ **不要试图守卫全仓所有注释** —— 那会有海量误报
（时间戳、历史记录、"这个 bug 曾发生在…"都是合法的历史陈述）。
**请挑一个窄而有意义的性质**，
例如「**凡提到 `LOCKED_SCENE_TYPES` 当前值的注释，必须与代码一致**」。

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果**；**且要证明它不是死分支**。
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
4. **每条毒变异之后从快照复原，收尾核对三个 sha256。**
5. **⚠️ 高频复发**：先证明被测对象存在再测量；**测试必须用 `{'scenes': [...]}` 形状**
   （若本项涉及图谱）；确认变异生效前不要宣称存活（P21/P22/P24 均产出过 `NameError`）；
   CRLF 用字节计数验（**`p.write_text()` 在 Windows 上翻译行尾，P17 的 agent 污染了 1101 行**）；
   路径分隔符；别把长跑命令管道进 `tail`；`tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`、`docs/P2*.md`
- `out/p13_probe/**` 与 `out/*.mp4` —— 只读；`DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要动 `visual_qa.py` / `frame_baseline.py` / `render.mjs` 及 P19–P31 的成果**
- **不要动品牌锁的两条裁定**（`{'logo','outro'}` 与 `('name','tagline')`）
- **⚠️ 不要改 `Brand.tsx` 的渲染逻辑** —— **只改注释**
- **⚠️ `locked_fields.py` 的注释若要改，只改注释** ——
  **⚠️ P32 正在同时改那个文件**（顶层遍历射程），**你若也改会冲突**。
  **请只报告「它有哪些注释已过期」，由指挥窗口统一裁定要不要改、什么时候改。**

**本指令授权你修改**：`studio/src/templates/finance-showcase/scenes/Brand.tsx` 的注释、
相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **还有没有同类假注释**（最重要，**逐条给判断与证据**）
  - **注释改写后的要点**
  - **全量测试数字**
  - **逐条变异结果**（贴 `-rf` 原始输出）
  - **三个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**另一条同类（本项不要做）**：`showcase-v1.ts:290` 的注释称 `_note`
"exists on exactly ONE graph" —— **现有两份**（P29 已确认，**待修**）。

**P27 遗留（待裁定）**：**B-2** 末帧近黑、**B-3** 冻结。

**P32 并行进行中**：`iter_locked` 只走 `content` 而 11.1 杠杆是 scene 顶层键
⇒ 以杠杆命名的 `LockRule` 在真实图谱上永远不可能触发，
**而账本把它列在「4 全杀」里**。**⚠️ 那也是一处"记录未随裁定更新"。**

**跨阶段剩**：1.3 / 10.2（标依赖、不合并、不重复建）。