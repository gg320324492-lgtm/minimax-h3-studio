# 执行指令 — 把 `outro` 纳入品牌锁（用户已裁定）

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `1f60f62`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `591 passed, 4 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**（cv2 只装在 3.10）。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`** —— 它会污染 `test_visual_qa.py`。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，命令以 `cd E:/Minimax-H3 &&` 开头。
**⚠️ 磁盘**：**输出到 E: 盘**，跑完清理。**C 盘刚清过（39.9 → 62.6 GB）**，
有 agent 就是被 C 盘 0 字节空闲打断的。

**开工前记录 sha256，收尾比对**：
- `studio/scripts/locked_fields.py`
- `studio/scripts/visual_qa.py` → 应为 `7e7d586a…`
- `studio/scripts/frame_baseline.py` → 应为 `91e3463c…`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 用户已裁定：**`outro` 纳入品牌锁**

P30 交付时把这条列为「故意没决定」的第一项，提请裁定。**用户说：纳入。**

### 2. 纳入的依据（指挥窗口已从源码核实）

`studio/src/templates/finance-showcase/scenes/Brand.tsx`：

```tsx
:115  export const Logo  ... const name = c.name ...     const tagline = c.tagline ...
:147  export const Outro ... const cta/sub               const name = c.name ...     const tagline = c.tagline ...
```

**`Outro:155-156` 读的正是 `c.name` 与 `c.tagline`** —— 与 `Logo` **完全相同的两个键**，
只是额外渲染 `cta` / `sub`。

**⇒ 它渲染的是同一个字标。纳入是对的。**

### 3. ⚠️ 一处必须一并处理的连带：**`outro` 已经在交付图谱里**

`pipeline/graphs/p29_new_renderer_showcase.json` 的 `p29_outro` 场景：

```json
{"name": "MERIDIAN", "tagline": "financial infrastructure", "cta": "..."}
```

**与同图谱的 `p29_logo` 是同一个字标。**

**⇒ 纳入之后，「改 outro 的字标」会从「0 条违规」变成「1 条违规」。**
**这是本项的目的，但请确认没有任何既有流程依赖它可以改。**

⚠️ **重点查**：`p29` 图谱是 P29 的验收语料，**若它被某条测试当作"可自由修改"的样本**，
纳入后会红。**请查清并如实报告，不要为了让套件绿而放宽锁。**

### 4. `LOCKED_SCENE_TYPES` 当前的值

`studio/scripts/locked_fields.py`：

```python
LOCKED_SCENE_TYPES: frozenset[str] = frozenset({'logo'})
```

**改成 `frozenset({'logo', 'outro'})`。** ⚠️ **注意它现在是单元素所以没加逗号** ——
**改成两元素时要写 `frozenset({'logo', 'outro'})`，别漏逗号。**

### 5. ⚠️ P30 已确立的两条原则

**(a) `name` 不能进 `LOCK_RULES`** —— 那张表按 key 匹配**每一个场景**的 content，
而 `content` 是开放袋子 ⇒ **会把未来某个场景的非品牌 `name` 也锁上**。
**品牌锁必须继续走那条按场景类型限定的独立通道**（`iter_scene_locked`）。

**(b) `BRAND_CONTENT_KEYS: tuple[str, ...] = ('name',)`** ——
**`tagline` 仍未纳入**（P30 已列为待裁定第二项，**用户没有裁定它**）。
**⇒ 本项不要顺手加 `tagline`。**

---

## 二、你要交付的三件事

### 第 1 件事：改 `LOCKED_SCENE_TYPES`，并查清连带影响

⚠️ **这是本项的全部实质改动** —— 它可能只有一行。**不要把它做成更多。**

**改之前必须查清**（第 3 节第 3 条已给线索）：

1. **有没有测试把 `outro` 当作"可自由修改"的样本？**
2. **有没有既有图谱的 `outro` 场景带 `name` 且被某处改动？**
   （指挥窗口已查：P29 的 `p29_outro` 带 `name`，**请确认没有测试在改它**）
3. **`coverage_report()` 的输出会怎么变？** ——
   `by_kind['brand']` 与 `scene_locks` 段应当反映两个类型了。

**若查出任一会红，如实报告，不要为了让套件绿而回退裁定。**

### 第 2 件事：把那条"故意没决定"的记录改成"已决定"

⚠️ **P30 特意把那两条决定写进源码并用测试钉住，**"这样它们不能被悄悄删掉"**。
**你裁定了一条，就要相应更新那条记录** —— 否则源码里会同时留着
"没决定"和"已纳入"两处互相矛盾的话。

⚠️ **`tagline` 那条保持"未决定"**（用户没裁定），**但请确认它的记录仍然准确**。

### 第 3 件事：给"`outro` 确实被锁"上一条守卫

⚠️ **本项最容易被做成"改了个常量、什么都没验"** ——
P30 的整条教训就是这个。**所以守卫是核心交付物。**

**判读要求（本项目被骗八次）**：

- **必须真的调用 `diff_locked` 并断言返回值**，
  **不能**断言 `LOCKED_SCENE_TYPES` 含有 `'outro'`。
  ⚠️ **P30 之前就有三条测试断言那个常量的值** —— 它们绿着而锁不生效。
  ⚠️ **⚠️ 指挥窗口在验 P30 时自己就栽过**：传了裸 scene 而不是整份图谱，
  `iter_scene_locked` 读的是 `graph['scenes']` ⇒ **测出"全部 0 条"**。
  **⇒ 你的测试必须用 `{'scenes': [...]}` 这个形状**，并**先证明那个形状是对的**
  （例如断言 `Logo` 场景在同样形状下确实被锁）。

**至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 从 `LOCKED_SCENE_TYPES` 删掉 `'outro'` | 守卫红 |
| 整个品牌通道摘掉（M1 的形状） | 守卫红 |
| **让品牌锁对所有场景类型都 emit**（过度锁） | 守卫红 |

⚠️ **第三条是 P30 已验证过的**（当时 `65 passed` —— **所有"锁拦不拦得住"的测试
在它过度锁定时仍然全绿**）。**本项要保持那条性质。**

⚠️ **另外请断言 11.1 的合法杠杆在 `outro` 场景上仍然放行** ——
P30 已在 `logo` 上验过一次，**`outro` 是新纳入的，没验过**：
`durationInFrames` / `camera` / `motion` / `layout` / `style_bible` /
`transitionIn-Out` / `format`。

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** → **注入后先 assert 变异在文件里。**
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
   ⚠️ **⚠️ 惰性变异要报 `INERT` 而不是 `SURVIVED`** ——
   P30 的教训：`if False: return` **字节落盘、套件绿**，
   **"先证明落地"是必要的但不充分**。请加行为探针。
4. **每条毒变异之后从快照复原，收尾核对三个 sha256。**
5. **⚠️ 高频复发**：先证明被测对象存在再测量；在错误的尺度上测等于没测；
   写数字要么实测要么标注未测；确认变异生效前不要宣称存活（P21/P22/P24 均产出过
   `NameError`）；CRLF 用字节计数验（**`p.write_text()` 在 Windows 上翻译行尾，
   P17 的 agent 污染了 1101 行**）；路径分隔符；别把长跑命令管道进 `tail`；
   `tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD。
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
- **不要动 `visual_qa.py` / `frame_baseline.py` / `render.mjs` 及 P19–P30 的成果**
- **不要把 `name` 挪进 `LOCK_RULES`**（见第一节第 5 条 (a)）
- **不要顺手把 `tagline` 加进 `BRAND_CONTENT_KEYS`** —— **用户没有裁定它**
- **不要给 11.1 的合法杠杆加锁**
- **不要改 `Brand.tsx`** —— 只改锁的适用范围，不改渲染器
- **不要顺手修 P27 的 B-2 / B-3**（设计后果，待裁定）

**本指令授权你修改**：`studio/scripts/locked_fields.py`、相关测试、
以及把 P30 那条"故意没决定"的记录改成"已决定"。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **有没有测试把 `outro` 当作可自由修改的样本**（最重要）
  - **`coverage_report()` 输出的变化**
  - **11.1 的合法杠杆在 `outro` 场景上是否仍放行**（给实测）
  - **全量测试数字**
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活/惰性判定）
  - **三个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**仍未裁定（用户未表态，本项不要做）**：
**`content.tagline` 是否纳入品牌锁**。

**P27 遗留（待裁定）**：**B-2** 末帧近黑、**B-3** 冻结
（`outro` 尾部实测约 124 帧 / 2.07s）。

**P30 遗留（待裁定）**：
- **`iter_locked` 只走 `content`，而 11.1 的杠杆都是 scene 顶层键** ⇒
  **以杠杆命名的 `LockRule` 在真实图谱上永远不可能触发**，
  `locked_fields_mutation.py` 里的 `lock_a_legitimate_lever` 是**惰性变异**，
  **而账本把它列在「4 全杀」里**；
- `Brand.tsx` 头部注释已过期（写着「锁本身未被改动」）。

**跨阶段剩**：1.3 / 10.2（标依赖、不合并、不重复建）。

**已裁定不要再讨论**：
P12 = 零段｜P13 = B+C｜P14 = B+C｜P15 = B｜P16 = 缺输入｜P17 = B｜P18 = B｜P19–P30 = 已处理