# 执行指令 — `iter_locked` 只走 content：14 条锁规则里有 7 条在真实图谱上永远不触发

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
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`** —— 它会污染 `test_visual_qa.py`。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，命令以 `cd E:/Minimax-H3 &&` 开头。
**⚠️ 磁盘**：**输出到 E: 盘**，跑完清理。**C 盘刚清过（39.9 → 62.6 GB）**，
有 agent 就是被 C 盘 0 字节空闲打断的。

**开工前记录 sha256，收尾比对**：
- `studio/scripts/locked_fields.py`
- `studio/scripts/locked_fields_mutation.py`
- `studio/scripts/visual_qa.py` → 应为 `7e7d586a…`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺陷：`iter_locked` 只遍历 `content` 子树

`studio/scripts/locked_fields.py:222-234`：

```python
def iter_locked(graph):
    """... Walks the whole content subtree rather than only the top level..."""
    scenes = graph.get('scenes') or []
    for i, scene in enumerate(scenes):
        sid = str(scene.get('id', f'#{i}'))
        content = scene.get('content')          # ← 只从这里进
        if not isinstance(content, dict):
            continue
        for path, value in _walk(content, f'scenes[{i}].content'):
```

**⇒ 只有 `scene['content']` 里的东西能被锁到。**

### 2. 而 **11.1 的七个合法杠杆全部是 scene 的顶层键**

`durationInFrames` / `camera` / `motion` / `layout` / `style_bible` / `format` /
`transitionIn` / `transitionOut`

**⇒ 在 `SceneSchema` 里它们与 `content` 平级，不在 `content` 里面。**

### 3. ⚠️ 后果：**一条以杠杆命名的 `LockRule` 在真实图谱上永远不可能触发**

`locked_fields_mutation.py` 里既有的 `lock_a_legitimate_lever` 变异
就是这种形状 ⇒ **它测的东西在真实图谱上不存在** ⇒ **它是惰性变异**。

**⚠️ 而账本把它列在「4 全杀」里** —— **读者会以为存在一条行为证据链。**

### 4. ⚠️ 这不只是记账问题，它是一个真实的能力缺口

**当前 `iter_locked` 的形状是 P11 当时的设计选择**（11.2 的记录原话）：

> `content` 在 `showcase-v1.ts:100` 是 `z.record(z.string(), z.unknown())`，
> **每个场的每个字段都是 `unknown`，包括那些不得动的** ⇒ 没有类型边界可靠，
> **锁必须显式写下来，代价就是可能不完整**

**⇒ 11.2 当时就知道"可能不完整"，而现在我们知道了不完整在哪一块。**

⚠️ **但请注意：11.1 明确「不锁的是审计结论而不是口味」** ——
`durationInFrames` / `camera` / `motion` / `layout` / `style_bible` / `format` /
`transitionIn-Out` **正是 11.1 的合法杠杆**，
**它们该被「不被锁」而不是「锁不到」。**

⚠️ **这两者的区别是关键**：
- **现在**：它们在锁的**射程之外**，所以没人管；
- **应该**：它们在锁的**射程之内且被明确豁免**，所以"有没有人试图锁它"是个可问的问题。

**⇒ 本项的目标是把它们从「射程外」搬进「射程内 + 显式豁免」，
而不是让它们变成被锁的字段。**

---

## 二、你要交付的三件事

### 第 1 件事：**先判定方向**，再动手

⚠️ **三条路，请给裁定并说明依据**：

| 方向 | 做法 | 代价 |
|---|---|---|
| **A：`iter_locked` 也遍历 scene 顶层** | 让顶层键可被锁 | **然后必须给七个杠杆写显式豁免**，否则 `diff_locked` 会把它们锁死 —— **而那会让 11.1 的修复循环什么都做不了** |
| **B：保持射程，只把记账改对** | 承认它们锁不到，改文档与变异报告 | 能力缺口仍在 |
| **C：只改那条惰性变异** | 让 `lock_a_legitimate_lever` 变成真变异 | 缺口仍在 |

**我倾向 A**，因为它把"不被锁"变成一个**可断言的事实**而不是**一个巧合**。
**但这是设计判断，请你独立裁定。**

⚠️ **若判 A**：**豁免清单必须由代码表达、不能只写在注释里** ——
本项目吃过一次"注释承诺而代码没有"（`LOCKED_SCENE_TYPES` 活了几个月）。
**并要有守卫断言"豁免清单里的键确实不会被 emit"。**

### 第 2 件事：实施，并处理连带

⚠️ **若判 A，务必实测**：

- **11.1 的七个杠杆在 `diff_locked` 上仍然 0 违规**（**在顶层遍历打开之后**）——
  P31 刚在 `outro` 上验过一次，**别让它回退**；
- **14 条 `LOCK_RULES` 的既有行为不变** ——
  `by_kind` / `exercised` / `unexercised` 应当**不受影响**（**若变了，如实报告**）；
- **品牌锁（`iter_scene_locked`）不受影响** —— 它是独立通道。

### 第 3 件事：把那条惰性变异变成真的，并修账本的说法

⚠️ **本项的记账部分与代码同等重要** —— **账本现在是错的**。

1. **`lock_a_legitimate_lever` 改成真变异**
   （**若判 A**，它才可能变成真的；**若判 B/C**，请**如实把它标成 INERT**
   并说明它测的是什么）；
2. **⚠️ 账本由指挥窗口更新**（`docs/UPGRADE_PROGRESS.md` 是我的）——
   **你报告「账本该怎么改」，我来改**；
3. **守卫必须能红**。至少三条变异，各贴 `-rf` 原始输出：

| 变异 | 期望 |
|---|---|
| 从豁免清单里删掉一个 11.1 杠杆 | 守卫红（**它必须开始锁那个杠杆**） |
| 让顶层遍历停止 | 守卫红 |
| 让判据永远判"通过" | 守卫红 |

⚠️ **惰性变异要报 `INERT` 而不是 `SURVIVED`** ——
P31 的教训：**harness 拿两个相同的错误字符串比较、然后打印 `INERT`**，
**那是一个在"防假绿"上给出假裁定的 harness**。请确保 `run()` 拒绝比较错误输出。

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果**；**且要证明它不是死分支**
   （P30 的 `if False: return` 字节落盘、套件绿；P31 的探针别名 bug 污染全部测量）。
   **"先证明落地"是必要的但不充分。**
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
4. **每条毒变异之后从快照复原，收尾核对三个 sha256。**
5. **⚠️ 高频复发**：先证明被测对象存在再测量；**⚠️ 测试必须用 `{'scenes': [...]}` 形状**
   （指挥窗口验 P30 时传了裸 scene、`iter_scene_locked` 读 `graph['scenes']` ⇒ 测出"全部 0 条"）；
   在错误的尺度上测等于没测；确认变异生效前不要宣称存活；
   CRLF 用字节计数验（**`p.write_text()` 在 Windows 上翻译行尾，P17 的 agent 污染了 1101 行**）；
   路径分隔符；别把长跑命令管道进 `tail`；`tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD。
6. **py-3.10 有 cv2 但没有 pytest** —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`、`docs/P2*.md`
- **`out/p13_probe/**` 与 `out/*.mp4` —— 只读**（P27 的证据目录）
- `DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要动 `visual_qa.py` / `frame_baseline.py` / `render.mjs` 及 P19–P31 的成果**
- **不要给 11.1 的七个杠杆真的上锁** ——
  **⚠️ 锁了它们修复循环就什么都做不了**（11.2 原话）
- **不要改 `Brand.tsx`**、**不要改品牌锁的两条裁定**（`{'logo','outro'}` 与 `('name','tagline')`）
- **不要顺手修 P27 的 B-2 / B-3**（设计后果，待裁定）

**本指令授权你修改**：`studio/scripts/locked_fields.py`、
`studio/scripts/locked_fields_mutation.py`、相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **方向裁定 A/B/C + 依据**（最重要）
  - **11.1 七个杠杆的实测**（顶层遍历打开之后仍 0 违规）
  - **`by_kind` / `exercised` / `unexercised` 是否受影响**
  - **那条惰性变异现在测的是什么**
  - **账本该怎么改**（具体到哪一行、什么措辞）
  - **全量测试数字**
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活/惰性判定）
  - **三个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**P27 遗留（待裁定）**：**B-2** 末帧近黑、**B-3** 冻结
（`outro` 尾部实测约 124 帧 / 2.07s）。

**另一条待裁定的过期注释**：`Brand.tsx` 头部写着「the lock itself is unmodified」
—— **P30/P31 之后已过期**（可与本项同批修，或单独一项）。

**跨阶段剩**：1.3 / 10.2（标依赖、不合并、不重复建）。

**已裁定不要再讨论**：
P12 = 零段｜P13 = B+C｜P14 = B+C｜P15 = B｜P16 = 缺输入｜P17 = B｜P18 = B｜P19–P31 = 已处理