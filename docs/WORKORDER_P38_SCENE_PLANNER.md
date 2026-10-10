# 执行指令 — P12.2 ScenePlanner→Storyboard→showcase_v1.json：接上刚建好的生成侧

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **P36（`8bd4666`）刚刚建好上游**，本项是它的下游。**接缝很窄，先看清再动手。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `a9038d9`（已推送） |
| 基线 | **先自己实测**（P36 报告 658 passed / 4 skipped） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**（会污染 `test_visual_qa.py`；本项目已有 agent 因此产生过 4 条假失败）。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，命令以 `cd E:/Minimax-H3 &&` 开头。

**⚠️ 工作树里有不属于本线的东西**：`studio/src/water-renewal/`（12 个文件）、
`studio/bin/render-water.mjs`、`studio/tsconfig.water.json`、`studio/package.json` 与
`pnpm-lock.yaml` 的改动、`.cache/`。
**⚠️ 那不是本项的、也不是你的 —— 不要碰、不要提交、也不要为了让它变绿而改守卫。**
⚠️ **注意**：它当前让 `test_p4_9_ledger_numbers_resolve` 变红（其中用了 `330`），**那是既有的**。

**开工前记录 sha256，收尾比对**：
- `pipeline/director/style_bible.py`
- `pipeline/scene_graph.py`
- `studio/src/templates/finance-showcase/design/styleBible.tsx`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 上游（P36，`8bd4666`）已经存在并**已经对齐下游**

`pipeline/director/style_bible.py:21` 的模块说明原话：

> "returns a document that **`scene_graph.load()` accepts**."

**⇒ P36 已经把「产出物能被 `scene_graph.load()` 接受」当作约束了。**

十键裁定：**1 A（`depthCue`）/ 2 B / 7 C**，`EMITS = frozenset({'depthCue'})`，
**拒绝清单是返回值的一部分（`unapplied`）、不是日志行**。

⚠️ **它声明的弱点你要知道**：对一部标准片子，
**推导出的 ramp 等于 `premium-dark` 主题默认值**（因为那条推导延续的正是从该默认值测出的序列）
⇒ **「渲染与生成相符」在生成器什么都不产出时同样成立**。
**⇒ 任何断言"生成的东西真的被用"的测试，都必须先排除这个兜底。**

### 2. 下游两处都已就绪

| 环节 | 状态 |
|---|---|
| **Storyboard → showcase_v1.json（12.2，本项）** | **零实现** |
| **图谱校验** | `pipeline/scene_graph.py`，P11 起读 JSON Schema（`a55d03d`），`SCHEMA_PATH` 在 `:140` |
| **StyleBible 解析** | `styleBible.tsx`，4.8 完成，接 `useDesign()` |

**⇒ 本项要补的是「从 Brief/意图 到 一张可被校验的图谱」这一段。**

### 3. ⚠️ 十种 scene 类型的可画性差别很大

- **13 个有渲染器**（P26 实测，`SCENE_RENDERERS`）；
- **9 个显式标记为不渲染**（P26 决策表 `UNRENDERED_SCENE_TYPES`）：
  `video` / `data-plane-3d` —— **且 P17 已裁定无 H3 渲染器**。

⚠️ **Planner 若按 22 种类型挑，会挑到渲染不出东西的类型。**

### 4. 已交付图谱的规模（供 Planner 定尺寸）

指挥窗口实测：`showcase_demo` 4 scenes / 801 帧；`charts_demo` 10 scenes / 1950 帧；
`p29_new_renderer_showcase` 7 scenes / 1120 帧。
**⇒ 场景数在 4–10 之间，没有先例可抄，Planner 得自己定规则并说明依据。**

---

## 二、你要交付的三件事

### 第 1 件事：**先判定 Planner 该规划什么**，再动手

⚠️ **本项最容易变成「生成一堆没人验证的东西」。** 请先回答：

**(a) 它规划的场景类型该从哪来？**
**⚠️ 不要按 `SceneType` 的 22 种挑** —— **其中 9 种会渲染成 `MissingScene`**。
**给出你的选择规则，并说明如何避开那 9 种。**

**(b) 每个场景的时长与节奏由什么决定？**
⚠️ **已交付图谱的时长各不相同**（801 / 1950 / 1120 帧），
**而参考片 P37 实测 beat ≈ 120.19 BPM**。**你的规则基于什么？**
**若定不出判据，**如实说**（**C 是合法结论**）。

**(c) Storyboard 这一层是必需品还是空转？**
⚠️ **若 Storyboard 只是 Planner 的中间数据结构、不产生可验证的产物**，
**那它就是一层装饰** —— **请如实判定，并说明它带来了什么。**
**本项目已接受过九次「实测说不出想要的结果」。**

### 第 2 件事：实施你裁定的结果

⚠️ **若裁定要建**，实现要点：

- **产物必须能被 `scene_graph.py` 真校验通过**（不是"看起来对"）；
- ⚠️ **它必须与 P36 的生成器协作，而不是各写一套** ——
  **⚠️ 本项目吃过一次：P21 时两个调用点持有同一个常数、只有一个读它**；
- ⚠️ **storyboard 的每个字段都要有消费方** ——
  **本项目的核心病灶就是"声明了但没人用"**（`generative` 死了一个字段、
  `LOCKED_SCENE_TYPES` 死了几个月、`chartLanguage` 至今零消费方）。

### 第 3 件事：给"Planner 的产物真的能被校验"上一条守卫

**判读要求（本项目被骗十次）**：

- **必须真的跑 `scene_graph.load()`（或等价的校验入口）并断言它通过**，
  **不能**断言返回了一个 dict；
- ⚠️ **必须能抓「产出的图谱里有渲染不出来的东西」** ——
  **那正是 (a) 的失效形态**，也是 P26 那九条决策表存在的原因。

**至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 让 Planner 挑一个 `UNRENDERED_SCENE_TYPES` 里的类型 | 守卫红 |
| 让它产出的图谱过不了 `scene_graph.py` 校验 | 守卫红 |
| 让判据永远判"通过" | 守卫红 |

⚠️ **"红在错误的理由上"不算通过**（P35 的 M4 第一版红在 `NameError` 上；
P36 的第二条红在 `SyntaxError` 且 pytest 在收集阶段就中止）。
⚠️ **别让探针的异常变成判定**（P31/P34/P36 各栽过一次）。

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果**；**且要证明它不是死分支**
   （P36 的教训：`tuple(str(x) for x in strings)` 是恒等、落盘了但行为没变）。
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **每条毒变异之后从快照复原，收尾核对三个 sha256。**
4. **⚠️ 高频复发**：先证明被测对象存在再测量；**在错误的尺度上测等于没测**；
   写数字要么实测要么标注未测；确认变异生效前不要宣称存活；
   CRLF 用字节计数验（**`p.write_text()` 在 Windows 上翻译行尾**）；
   路径分隔符；别把长跑命令管道进 `tail`；`tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD。
5. **py-3.10 有 cv2 但没有 pytest** —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**。

---

## 四、不要动的东西

- **⚠️ `studio/src/water-renewal/`、`studio/bin/render-water.mjs`、`
  studio/tsconfig.water.json`、`studio/package.json`、`pnpm-lock.yaml`、`.cache/`**
  —— **不是本线的、不要碰、不要提交、不要为了让它变绿而改守卫**
- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`~`docs/P3*.md`
- `out/p13_probe/**` 与 `out/*.mp4` —— 只读；`DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要改 `scene_graph.py`** —— **它是下游，本项只该产出它能接受的图谱**
- **不要改 P36 的生成器与其十键裁定**（`EMITS = {'depthCue'}`、九个拒绝理由）
- **不要扩 schema**、**不要改任何场景组件**、**不要改 `themes.ts`**
- **不要动 P19–P37 的任何成果**
- **⚠️ 不要实现 H3 渲染器**（P17 裁定 B）

**本指令授权你修改**：`pipeline/` 下的新模块、相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（**只 stage 你自己的文件** —— 本工作树里还有别人的未提交内容）
- 交付时报告：
  - **(a)(b)(c) 三个问题各自的答案**（最重要）
  - **若裁定不建：理由与依据**
  - **全量测试数字**
  - **逐条变异结果**（贴 `-rf` 原始输出）
  - **三个 sha256 的比对**
  - **磁盘纪律**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **⚠️ `git add` 请用显式路径**，不要用 `-A` 或 `.` ——
  **本工作树里有不属于你的未跟踪内容**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**同类未做**：**11.3** `MAX_REPAIR_ROUNDS=3`（形状待改：轮次应由"重新测量仍在碰撞"决定）。
**⚠️ 但它依赖 11.1，而 11.1 的解锁条件是"真出现一个接近碰撞的图表"（当前比值 0.278）** ——
**不建议现在动。**

**待你裁定**：**P27 B-2**（末帧近黑）、**P27 B-3**（冻结 8.03s）。

**已裁定不建**（只等你决定是否正式关闭）：
13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1 / 12.3 / 11.1。

**跨阶段剩**：1.3 / 10.2（标依赖、不合并、不重复建）。