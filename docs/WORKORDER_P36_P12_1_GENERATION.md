# 执行指令 — P12.1 BriefParser→ReferenceAnalyzer→StyleBible：先量它该生成什么

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> **本项是「生成侧」的第一次尝试** —— 下游校验与解析都已就绪，唯独中间这段没人写。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `20e69f6` + `6e8b3d5`（**工作树可能已有 P35 的提交**，请先 `git log --oneline -3` 确认） |
| 基线 | **先自己实测**（上次是 `637 passed, 4 skipped`，P35 之后可能更多） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，命令以 `cd E:/Minimax-H3 &&` 开头。

**开工前记录 sha256，收尾比对**：
- `pipeline/scene_graph.py`
- `studio/src/templates/finance-showcase/design/styleBible.tsx`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 上游为零，下游两处都已就绪

| 环节 | 状态 |
|---|---|
| **Brief → StyleBible（12.1，本项）** | **零实现** |
| **SceneGraph 校验** | `pipeline/scene_graph.py` **32 KB**，P11 起读 JSON Schema（`a55d03d`） |
| **StyleBible 解析** | `styleBible.tsx` **8 KB**，4.8 完成，接 `useDesign()` |

**⇒ 下游在等一个产出者。**

### 2. ⚠️ **它该生成的东西，九段从未被任何交付图谱用过**

`StyleBible` 的 **10 个键**：

```
palette  typography  spacing  radius  shadow  depthCue
cameraLanguage  motionLanguage  chartLanguage  audioLanguage
```

**指挥窗口实测：三份已交付图谱（`showcase_demo` / `charts_demo` /
`p29_new_renderer_showcase`）合起来只设过 1 个键** —— `typography`，1 次。

**⇒ 本项若照 schema 生成，会一次制造九段从未行使过的声明。**

⚠️ **而 P16 已逐键查过那七段在渲染侧有没有消费方**，结论见第二节。

### 3. ⚠️ 已知的两处陷阱

**(a) `chartLanguage` 与 `audioLanguage` 零消费**（P16 实测）——
**它们是「声明了但没人读」，与本系列修的「有人读但喂不进去」方向相反。**

**(b) `radius` / `shadow` / `depthCue` 直到 P26 才接通**
（`836f532`：它们被 `styleBible.tsx` 合并、被场景消费，但**不在 schema 里** ⇒
**永远拿不到图谱的值**）。**现在它们在 schema 里了，但三份图谱一个都没设过。**

### 4. 本项目对"照着 schema 生成"的态度

**P12 勘察（`a32f2f`）已裁定 Director Agent「零段值得建」**，
理由是**「若 Director Agent 照着 7 键 schema 自动生成 StyleBible，
默认就会生成大部分为哑声明」**。

**⇒ 本项与那一项是同一件事，只是范围更小。**
**⚠️ 请先回答：12.1 与 P12 勘察的结论矛盾吗？若不矛盾，差别在哪？**

---

## 二、你要交付的三件事

### 第 1 件事：**先回答"它该生成什么"**，再动手

⚠️ **本项最难的不是写代码，是决定生成侧的边界。**

**先查清 P16 那份记录**（`docs/P16_REFERENCE_BENCHMARK.md`）里七个键的逐键结论，
然后**给每个键一个裁定**：

| 裁定 | 条件 | 动作 |
|---|---|---|
| **A：可生成** | 有消费方、且**图谱设了它确实有效果** | 实现 + 守卫 |
| **B：不该生成** | 零消费方（`chartLanguage` / `audioLanguage`） | **记录为"生成侧也不产出"** |
| **C：缺判据** | 有消费方但**定不出该生成什么值** | 如实说，**别编一个默认值** |

⚠️ **C 是完全合法的。** 本项目已接受过九次「实测说不出想要的结果」。

**并回答第 4 节那个问题**：12.1 与 P12 的「零段值得建」是否矛盾。
**若你认为 12.1 同样不该建，那也是完整交付** —— **给出理由与依据。**

### 第 2 件事：实施你裁定的结果

**若裁定要生成**，实现要点：

- ⚠️ **它必须走真实链路**（Brief → 中间表示 → StyleBible 段 → 图谱），
  **不要做成"直接吐一个符合 schema 的字典"** ——
  **那会把本项变成一个 schema 校验器的换皮**；
- ⚠️ **产物必须能被 `scene_graph.py` 校验通过**（那是它的下游），
  **并被 `styleBible.tsx` 真的消费**（P26 那三个键是刚打通的）；
- ⚠️ **生成的值必须可解释** —— **若某个值只能靠默认值兜底，
  如实标注它是兜底而不是生成的**。**这是本项目反复栽跟头的地方**
  （`render.mjs` 静默忽略未知 flag、`visual_qa` 静默跳过缺失 props）。

### 第 3 件事：给"生成的东西真的被用"上一条守卫

**判读要求（本项目被骗九次）**：

- **必须真的跑一遍生成 → 校验 → 解析的链路并断言**，
  **不能**断言函数返回了一个 dict；
- ⚠️ **守卫必须能抓住「生成了但没人用」** ——
  **那正是 P12 勘察的核心担忧**。

**至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 让它生成一个零消费方的段（如 `chartLanguage`） | 守卫红 |
| 让它生成的值无法通过 `scene_graph.py` 校验 | 守卫红 |
| 让判据永远判"通过" | 守卫红 |

⚠️ **⚠️ 本项目最贵的一条**：**"红在错误的理由上"不算通过** ——
P35 的 M4 第一版红在 `NameError` 上（颜色对、理由错）。

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果**；**且要证明它不是死分支**。
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **红的理由必须对**（见上）。
4. **每条毒变异之后从快照复原，收尾核对 sha256。**
5. **⚠️ 高频复发**：先证明被测对象存在再测量；确认变异生效前不要宣称存活；
   **别让探针的异常变成判定**（P31/P34 各栽过一次：一对相同的 `KeyError` 被比较成 "INERT"）；
   CRLF 用字节计数验（**`p.write_text()` 在 Windows 上翻译行尾**）；
   路径分隔符；别把长跑命令管道进 `tail`；`tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD。
6. **py-3.10 有 cv2 但没有 pytest** —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`~`docs/P3*.md`
- `out/p13_probe/**` 与 `out/*.mp4` —— 只读；`DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要动 `scene_graph.py` 与 `styleBible.tsx`** —— **它们是下游，本项只该喂它们**
- **不要扩 schema**（十键已定，且 `.strict()` 已加）
- **不要动 P19–P35 的任何成果**
- **不要顺手做 12.2 / 16.x / 17.x**
- **⚠️ 若 P35 还在跑或刚提交，勿碰 `visual_qa.py` 与 `Chart.tsx`**

**本指令授权你修改**：新增 `pipeline/` 下的生成模块、相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **十个键逐个裁定 A/B/C + 依据**（最重要）
  - **12.1 与 P12「零段值得建」是否矛盾**（**若矛盾，说清差别**）
  - **全量测试数字**
  - **逐条变异结果**（贴 `-rf` 原始输出）
  - **两个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**同类未做**：**12.2**（`ScenePlanner→Storyboard→showcase_v1.json`）——
**上游 `scene_graph.py` 已就绪、在等产出者**，与本项同源。

**被外部条件卡住**：**16.x**（缺参考片）、**17.1**（无 H3 渲染器 + premium 无判据）。

**待你裁定**：**P27 B-2**（末帧近黑）、**P27 B-3**（冻结 8.03s）。

**已裁定不建**（**只等你决定是否正式关闭**）：
13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1 / 12.3 / 11.1。

**跨阶段剩**：1.3 / 10.2（标依赖、不合并、不重复建）。