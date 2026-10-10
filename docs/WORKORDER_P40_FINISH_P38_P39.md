# 执行指令 — 收尾 P38 与 P39：两项的半成品都在仓库里，未提交

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **前一个 Claude 进程结束时，两个 agent 都还在跑。它们的产出保住了，但没有提交。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `a9038d9`（已推送） |
| 基线 | **先自己实测**（见第一节第 3 条：**当前有 1 条已知红**） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，命令以 `cd E:/Minimax-H3 &&` 开头。

**⚠️⚠️ 工作树里有大量不属于本线的未提交内容**：

```
 M studio/package.json
 M studio/pnpm-lock.yaml
?? .cache/
?? studio/bin/render-water.mjs
?? studio/src/water-renewal/        （12 个文件）
?? studio/tsconfig.water.json
```

**那不是你的、不是 P38/P39 的 —— 不要碰、不要提交、不要为了让它变绿而改它。**
**⚠️ `git add` 必须用显式路径，绝不要用 `-A` 或 `.`** ——
**P36 的六个文件就是被并发 agent 的 `git commit` 卷走的。**

---

## 一、现状：两个半成品都在，都没提交

### 1. P38（P12.2 ScenePlanner）：**裁定已完成，记录文档已写，未提交**

`docs/P12_2_SCENE_PLANNER.md`（**393 行**，未跟踪）。
**它没建任何模块** —— 因为它的裁定是 **C：不建**。

**它的三个答案**（摘要原话）：

| 问题 | 答案 |
|---|---|
| **(a) 场景类型不该由 Planner 挑** | brief 里的场景**已经带类型**，`generate_graph` 逐字节原样带进图谱（`is` 判定 `True`）。而"挑不出渲染不出来的类型"这条规则**已经存在且已经会红** —— **P21 的 `rule_graph_scene_renderable`**，本项端到端跑过 |
| **(b) 时长判据不存在，且能证明不存在** | 唯一被提名的仪器 `beat_aligned_durations` **对任何输入都返回空**（构造性证明 + 2 万次随机图谱穷举 + 1 帧/4999 帧极端输入）。**而三张交付图谱在渲染器真正使用的时间线上漂移 12.9–13.9 帧** —— **仪器说"没问题"，片子不在这条线上** |
| **(c) Storyboard 是恒等映射** | 实测 `generated.graph['scenes'] IS brief['scenes']` —— **它要的输入就是它的输出** |

### 2. ⚠️ 它纠正了指挥窗口工单的一处前提，**而且它是对的**

工单（及 `visual_qa.py:1051-1054` 的 docstring）都写「22 声明 / 13 渲染 / **9 落空**」。
**它实测：22 声明 / 20 渲染 / 2 落空**（`video`、`data-plane-3d`）。

**原因**：`a7f02b8`（P29）验收了七个新渲染器
（`browser-window`/`stat-card`/`card-grid`/`data-table`/`quote`/`logo`/`outro`）。

**⇒ 按「避开那 9 种」写的 Planner 会去避开 7 种现在渲染正常的类型，
而真正渲染不出来的那 2 种一个都没提到。**
**⇒ 唯一经得起时间的规则是集合差，不是名单**：
`renderable = SceneType ∩ SCENE_RENDERERS`。

**它的守卫 `test_the_unrendered_set_is_the_two_generative_types_not_nine` 钉住这个数字**，
**它一变动就红，并要求重新测量而不是放宽断言。**

### 3. P39（守卫判据）：**改动已完成，未提交**

`tests/test_p4_9_ledger_numbers_resolve.py`：**`381 insertions / 46 deletions`**。

**它做的事**（从 diff 可见）：

- **把两种判据统一到一种**：文件里新增了 `## ONE CRITERION PER QUESTION (P39)` 一节，
  开头是「This file used to carry TWO ways to say "this number is not real", and they…」；
- **判据改为「数字是它被引用的那个字段的值」** —— 每个断言指名拥有该字段的文件，
  resolver 在**那个文件的那个字段**上核对（`layout.<field> ?? N` 默认 / `"<field>": N` 图谱键 /
  **未加引号的 `<field>: N` TS 对象键（P39 新增）** / `<field> = N` 赋值）；
- **每次读取都剥注释**（因为属主文件的散文里会提到代码没用到的值）；
- **它还订正了文件头部那句已失效的话**：原文说「`330` appears nowhere」，
  **现在明确标注了"它停止为真，而那正是缺陷本身，不是事实"**。

**⚠️ 当前那条红**：
`test_the_two_numbers_4_9_invented_still_exist_nowhere` —— **P39 要修的正是它**。

### 4. 当前基线的三条红，各自的归属

```
FAILED test_p4_9_ledger_numbers_resolve.py::test_the_two_numbers_...  ← P39 修的就是它
FAILED test_markdown_text_is_intact.py                                ← 已在 5a754d2 修掉（现在应当绿）
FAILED test_p14_render_entry_points.py                                ← GBK 控制台假象，源码零 U+FFFD
```

**请先自己实测确认**。

---

## 二、你要交付的三件事

### 第 1 件事：**收尾 P39**（先做这条，它更窄）

1. **跑全量，确认那条红转绿**；
2. **跑工单要求的三条变异**（前一位 agent 未必跑完）：

| 变异 | 期望 |
|---|---|
| 把后半段改回裸数字扫描 | 守卫红 |
| 给 resolver 加一个恒真的旁路 | 守卫红 |
| 让判据永远判"通过" | 守卫红 |

3. **回答工单原问的第 2 件事**（前一位 agent 未必答）：**这份文件里有几种判据？
   有没有第三种与前两种都不一致的？**
4. **提交**（**只 stage 这一个文件**）。

⚠️ **P39 的工单在 `docs/WORKORDER_P39_GUARD_CRITERION.md`，请读它。**

### 第 2 件事：**收尾 P38**

1. **核实它那三个答案是否成立**（**不要采信自述**）：
   - (a) `rule_graph_scene_renderable` 是否**真的**已经覆盖"挑不出渲染不出来的类型"？
     **端到端跑一次确认**；
   - (b) `beat_aligned_durations` 是否**真的**对任何输入都返回空？
     **这是它的核心论据，请独立复现**；
   - (c) `generated.graph['scenes'] IS brief['scenes']` 是否成立？
2. **核实它对「9 种 → 2 种」的纠正**（**自己数，不要采信**）：
   `SceneType` 声明数、`SCENE_RENDERERS` 键数、`UNRENDERED_SCENE_TYPES` 键数。
   ⚠️ **若属实，请一并订正 `visual_qa.py:1051-1054` 那段 docstring** ——
   **它现在写着过期数字**，而**那段 docstring 正是我工单里那个错数字的来源**。
3. **跑它那条守卫的变异**（它可能没跑完）：
   **把 `UNRENDERED_SCENE_TYPES` 改成一个类型 → 守卫必须红**。
4. **提交**（**只 stage 它的文件**）。

### 第 3 件事：给「文档里的数字」上一条守卫

⚠️ **本项真正的价值在这里。**

**本项暴露的失效是**：`visual_qa.py` 的 docstring 写「9 落空」，
**而实测是 2** —— **那段 docstring 成了一个过期数字的来源，
指挥窗口照着它写了工单，工单又把错误的规则传给下一个 agent。**

**⇒ 请设计一条守卫**，断言**源码 docstring 里引用的那些集合大小，与代码实际的集合大小一致**。

⚠️ **判读要求（本项目被骗十次）**：

- **必须真的从代码里算出那个数字再与 docstring 比对**，
  **不能**把两边都写死在测试里；
- **⚠️ 不要试图守卫全仓所有数字** —— 那会有海量误报
  （时间戳、行号、历史记录都是合法的）。**挑一个窄而有意义的性质**；
- **若你认为做不到，如实说并说明为什么**。

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果**；**且要证明它不是死分支**。
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **⚠️ "红在错误的理由上"不算通过** ——
   P35 的 M4 红在 `NameError`；P36 的第二条红在 `SyntaxError` 且 pytest 在收集阶段就中止。
4. **⚠️ 别让探针的异常变成判定** —— P31/P34/P36 各栽过一次
   （一对相同的 `KeyError` 被比较成 "INERT"）。
5. **每条毒变异之后从快照复原，收尾核对 sha256。**
6. **⚠️ 高频复发**：先证明被测对象存在再测量；
   **在错误的尺度上测等于没测**；写数字要么实测要么标注未测；
   CRLF 用字节计数验（**`p.write_text()` 在 Windows 上翻译行尾**）；
   路径分隔符；别把长跑命令管道进 `tail`；
   `tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD。
7. **py-3.10 有 cv2 但没有 pytest** —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**。

---

## 四、不要动的东西

- **⚠️ `studio/src/water-renewal/**`、`studio/bin/render-water.mjs`、
  `studio/tsconfig.water.json`、`studio/package.json`、`pnpm-lock.yaml`、`.cache/`**
  —— **不是本线的、不要碰、不要提交、不要为了让它变绿而改它**
- `studio/public/jobs/**` —— **只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`~`docs/P3*.md`
- `out/p13_probe/**` 与 `out/*.mp4` —— 只读；`DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要改 `DataColumns.tsx` / `BrowserStack.tsx`**（P39 只改断言方式）
- **不要改 `scene_graph.py` 与 P36 的生成器**
- **不要动 P19–P37 的任何成果**
- **⚠️ `visual_qa.py` 只授权你改 `:1051-1054` 那段 docstring 的数字**（若核实为过期）

**本指令授权你修改**：`tests/test_p4_9_ledger_numbers_resolve.py`、
`docs/P12_2_SCENE_PLANNER.md`、新增测试与文档、
`visual_qa.py:1051-1054` 的 docstring 数字。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（**只 stage 你自己的文件**）
- 交付时报告：
  - **P38 三个答案的独立复核结果**（**尤其 (b) 那个构造性证明**）
  - **「9 种 → 2 种」你自己数出来的数字**
  - **P39 的判据有几种、三条变异结果**
  - **第 3 件事的守卫方案**
  - **全量测试数字**（实测基线 + 改完后）
  - **sha256 比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **⚠️ `git add` 用显式路径**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**待你裁定**：**P27 B-2**（末帧近黑）、**P27 B-3**（冻结 8.03s）。

**已裁定不建**（只等你决定是否正式关闭）：
13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1 / 12.3 / **11.1** / **12.2（本项 P38 的裁定 C）**。

⚠️ **11.3 仍然不动** —— 指挥窗口刚实测：
`charts_demo` 的最差标签比值 **0.2775**（与账本记的 0.278 一致），
**离碰撞（1.0）差三倍多，没有可修的东西。**

**跨阶段剩**：1.3 / 10.2（标依赖、不合并、不重复建）。