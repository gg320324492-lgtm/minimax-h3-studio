# 执行指令 — P54：`c05_bubble` 声明了 `chart.sizes`，而渲染器只读 `series[].sizes`

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **本项的隐蔽之处：修好它会让一个已验收的画面变化。请正面处理这一点。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | 指挥窗口派工时的 `main`（⚠️ **本仓有别的会话在提交**，见第四节） |
| 基线 | **⚠️ 本机全量套件测不出稳定数字** —— 三次连跑三个不同失败集合，<br>而每个失败文件单跑都绿。**开工前自己测一次，并注明是否并发、是否清过探针。** |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**。**读非 ASCII 用字节判断，别信控制台。**

**⚠️ Shell 状态在两次工具调用之间不保持**。**全程用绝对路径**。
**⚠️ `git add` 用显式路径**，不要用 `-A` 或 `.`。

**开工前记录 sha256，收尾比对**：
- `studio/src/templates/finance-showcase/charts/types.tsx`
- `studio/src/templates/finance-showcase/charts/Chart.tsx`
- `pipeline/examples/charts_demo.json`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺陷：图谱声明的 `sizes` 从未到达渲染器

**图谱**（`pipeline/examples/charts_demo.json`，`c05_bubble`）：

```json
"chart": {
  "type": "bubble",
  "values": [12, 28, 45, 66, 88, 100],
  "sizes":  [8, 22, 40, 61, 79, 95],
  …
}
```

**渲染通路**（`studio/src/templates/finance-showcase/charts/Chart.tsx:238`）：

```tsx
<Bubble series={{values: spec.series?.[0]?.values ?? values,
                 sizes: spec.series?.[0]?.sizes}} … />
```

**⇒ 它只读 `spec.series[0].sizes`。而 `c05_bubble` 的 `chart` 里没有 `series` 键**
⇒ `sizes: undefined`
⇒ `types.tsx:404` 的 **`const sizes = series.sizes ?? series.values;`**
⇒ **回退到 `values`** ⇒ **气泡半径用的是 `values`，不是 `sizes`。**

### 2. ⚠️ 为什么这个缺陷特别难抓

**回退让画面看起来完全正常** —— 气泡确实有大有小（用 `values` 排的）。
**⇒ 任何存在性检查都是绿的。** 它不是"选项惰性"，**它是"一个真实的意图被一个回退值静默替换"**。

**实测（P48 报、指挥窗口复核）**：改 `chart.sizes` ⇒ **0 px**；
改 `chart.values[0]` ⇒ **1226 px**。

### 3. ⚠️ `series[].sizes` 是一条**完整、可用、已被文档化**的通路

`Chart.tsx:29` 的类型：`series?: {name?: string; values: number[]; sizes?: number[]}[]`
`Chart.tsx:137`：`sizes: s.sizes ? numArray(s.sizes) : undefined`

**⇒ 图谱若把 `sizes` 写在 `chart.series[0].sizes`，它会生效。**

### 4. ⚠️⚠️ **全仓没有第二张气泡图谱可对照**

指挥窗口查了三张 tracked 图谱：
**`showcase_demo.json` 与 `p29_new_renderer_showcase.json` 都没有气泡场景。**
**⇒ `chart.sizes` 这个位置全仓只此一处，而 `series[].sizes` 有明确的渲染通路。**

**⚠️ 这意味着：没有"正确写法的先例"可抄。**
**⇒ 你必须先判定是「图谱用错了位置」还是「渲染器少读了一个位置」，**
**而且要论证，不能靠"看起来更合理"。**

### 5. ⚠️⚠️ **修好之后，`c05_bubble` 的画面会变 —— 而 P27 验收过旧画面**

`chart.sizes = [8,22,40,61,79,95]` 与 `chart.values = [12,28,45,66,88,100]`
**长度相同、值全不同** ⇒ 修好之后**半径的相对大小关系会变**。

**⇒ P27（`docs/P27_VISUAL_ACCEPTANCE.md`）验收的是用 `values` 的那版。**
**⚠️ 这是本项最需要正面处理的一点：**
**"修好"不是"变得和 P27 一样"，而是"变成作者本来想要的"。**
**⇒ 请明确回答：修好之后，那个画面还是不是一件好作品？**
**（若它变得不好看，那说明图谱的 `sizes` 值本身有问题，
而那也是一个值得报告的发现。）**

---

## 二、你要交付的东西

### 第 1 件事：**先判定，再动手**

⚠️ **这是本项的核心。** 请回答并论证：

**(a) 哪个位置是"这个字段的合法位置"？**

| | 位置 | 现状 |
|---|---|---|
| **A** | `chart.series[0].sizes` | **渲染器认它**（`Chart.tsx:137` / `:238`），类型里有 |
| **B** | `chart.sizes`（顶层） | **只有 `c05_bubble` 一处用它，无任何读者** |

**⇒ 若判 A：改图谱（把 `sizes` 移到 `series[0]`），说明为什么图谱当初那样写。**
**⇒ 若判 B：改渲染器接受两个位置 —— ⚠️ 请说明这是否等于造了「第二个真相来源」，
以及两个位置同时存在时谁赢。**

⚠️ **⚠️ 特别注意**：`chart.sizes` 与 `chart.values` **在图谱里是两个并列的顶层键**，
**而 `series[].sizes` 与 `series[].values` 是并列的一对** ——
**⇒ 从"作者想画什么"的形状看，图谱现在写的是「一组值 + 一组半径」，
那个形状对应的是 `chart.sizes` 与 `chart.values` 并列，
而渲染器要的是 `series[0].sizes` 与 `series[0].values` 并列。**
**请判断这个形状差异说明了什么 —— 它可能说明是图谱笔误，也可能说明渲染器该更宽容。**

**(b) `values` 与 `sizes` 的语义分别是什么？**

⚠️ `sizeBy: 'value'` 意味着**"气泡半径正比于这个字段的值"**。
**⇒ 若 `sizes` 才是半径编码，而 `values` 是 y 值，那 `sizeBy` 指哪个？**
**⇒ `sizeBy` 有 `value` 与 `none` 两个取值 —— 它的名字说的"value"是哪一个 value？**
**⚠️ 这个问题不回答清楚，修了也可能是错的。**

### 第 2 件事：**实施**

⚠️ **三条硬要求**：

1. **改完之后 `sizes` 必须真的到达渲染器** —— **用像素证明**
   （⚠️ **用仓库仪器 `ab_field.frame_ink()`，别用临时阈值** ——
   指挥窗口刚用临时阈值报出过不可比的数）；
2. **不许用"让画面动起来/看起来对"代替"让声明到达"**；
3. **⚠️ 图谱改了之后 `c05_bubble` 的画面会变** ——
   **请把改前改后的画面都渲出来并报告**（**旧的和新的**），
   **并回答 §一.5 那个问题：新的画面还是不是一件好作品。**

### 第 3 件事：**给"图谱声明的字段必须到达渲染器"上一条守卫**

⚠️ **⚠️ 这条守卫的难点是：它不能只抓 `sizes`。**
**`chart.sizes` 只是本项的实例，而这一类缺陷是"任何图谱声明的字段都可能落空"。**

⚠️ **⚠️ 但请小心别造一台误报机**：
- **不是每个图谱字段都有渲染器消费者** ——
  ⚠️ **P43 已经证明 `data-plane-3d` 那类"声明了但没有渲染器"是合法决策**，
  **所以守卫不能要求"每个字段都被读了"**；
- ⚠️ **一个窄而有意义的性质是什么？** 请给出你的判据，
  **并说明它为什么不会误报**；
- ⚠️ **⚠️ P47 已经建过一条同族守卫**
  （`tests/test_chart_type_defaults_are_real.py`，问"这个类型的默认该画什么"），
  **⚠️ 请先读它，判断你的守卫是它的补充还是重复。**
  **若重复，请说明为什么不复用。**

**至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| **把 `sizes` 挪回顶层（还原缺陷）** | 守卫红 |
| **让渲染器忽略 `sizes`（另一种落空方式）** | 守卫红 |
| 让判据永远判"通过" | 守卫红 |

⚠️ **"红在错误的理由上"不算通过**。⚠️ **别让探针的异常变成判定**（P31/P34/P36 各栽过一次）。
⚠️ **每条毒变异后从字节快照复原，收尾核对 sha256。**

---

## 三、验证协议

1. **测量前先证明被测对象存在**（先证明"改 `sizes` 会动画面"这件事在修好之后为真）；
2. **贴原始输出**，不贴结论句；
3. ⚠️ **五条高频复发**：先证明被测对象存在再测量；**在错误的尺度上测等于没测**；
   **外推等于没测**；**写数字要么实测要么标注未测**；**CRLF 用字节计数验**
   ⚠️ **`types.tsx` 与 `Chart.tsx` 是纯 CRLF，动之前先测行尾**；
4. ⚠️ **磁盘**：输出到 **E 盘**，`TMPDIR` 指 E 盘、`--public-dir` 指空目录
   （否则每个 bundle 复制 **773 MB** 的 `studio/public`）。**跑完清理。**
   ⚠️ **`studio/.remotion/water-renewal-bundle`（1.5 GB）不是你的，别删。**
   ⚠️ **⚠️ 指挥窗口上一轮忘了清自己 8 MB 的探针残留，
   而失败的 `test_a_finished_render_leaves_no_bundle_directory_behind` 恰恰是查残留的。别成为下一个。**
5. ⚠️ **不要与别的进程并发渲染** —— 已有三个 agent 因此制造过假红。
6. ⚠️ `tests/test_markdown_text_is_intact.py` 守着全仓 markdown 的 U+FFFD。
7. ⚠️ py-3.10 有 cv2 但没有 pytest —— 需要 cv2 就写进普通函数用 3.10 驱动。

---

## 四、不要动的东西

- `docs/UPGRADE_PROGRESS.md` —— **账本由指挥窗口统一更新**
- ⚠️⚠️ **本仓有别的会话在提交，而且工作树里有不属于本项的在制工作**：
  ```
   M studio/src/Root.tsx
  ?? intro_video/
  ?? from_e_root/
   M studio/src/Root.tsx
   M tests/test_p48_reaccept.py   <- 本项自己的半成品（测试已翻转，渲染器与图谱还没改完）
  ?? studio/public/audio/intro/
  ?? studio/src/templates/model-intro/
  ```
  **⚠️ 那不是你的，不要碰、不要提交、不要为了让它变绿而改它。**
  **⚠️ 提交前先 `git status` 看一眼 —— 别的会话可能已经提交过了。**
- ⚠️ **`studio/scripts/qa_layers.py`、`tests/test_p40_docstring_counts_match_code.py`**
  —— **P53 正在改，不要碰**
- ⚠️ **`tests/test_p42*`、`test_p46*`、`test_p27*`、`test_p49*`、`test_p50*`、`test_p51*`、
  `tests/tautology_criterion.py`** —— **别碰**
- ⚠️ **`tests/test_chart_type_defaults_are_real.py`（P47 建的）—— 优先复用，别改；
  若你确需改它，先在报告里说明为什么。**
- `out/charts_demo.mp4`（P27 证据目录）、`out/p45_vlm/**`、`out/p48_reaccept/**` —— 只读
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`~`docs/P53*.md` —— 只读
- `DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要动 P19–P53 的任何成果**、不要改 `themes.ts`、
  不要动 `charts/options.ts`（P47 的 `TYPE_DEFAULT_ROWS` 刚落地）
- **⚠️ 不要把任何帧/图复制进仓库**

**本指令授权你修改**：`pipeline/examples/charts_demo.json`、
`studio/src/templates/finance-showcase/charts/types.tsx`、
`studio/src/templates/finance-showcase/charts/Chart.tsx`、
相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（**只 stage 你自己的文件**）
- 交付时报告：
  - **(a) 哪个位置是合法位置 + 论证**（最重要）
  - **那个形状差异（`chart.sizes` 与 `chart.values` 并列 vs `series[0]` 并列）说明了什么**
  - **(b) `values` 与 `sizes` 的语义，`sizeBy` 指哪个**
  - **改完之后的像素证据**（改 `sizes` 动多少 px）
  - **⚠️ 改前改后的画面各是什么样 + 新的还是不是一件好作品**
  - **守卫判据 + 它为什么不会误报 + 与 P47 那条守卫是补充还是重复**
  - **三条变异的 `-rf`**
  - **全量测试数字 + 是否并发 + 是否清过探针**
  - **三个 sha256 比对**
  - **磁盘纪律**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**；用**字节层快照**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列（供你了解上下文，不必处理）

- **并行跑**：**P53** 在还 `qa_layers.py` 的一笔已知债 + 修 `font_size` 的状态陈述
  （**不同文件，无冲突**）。
- **P49 登记未修**：`camera.focus`、`bible.camera.durationSeconds` **零读者**。
- **P43 `data-plane-3d`** —— 判 C。**`video`** —— 等外部素材。
- **P16 / P17** —— 卡在 "premium" 无判据。
- **已裁定关闭**：11.1 / 12.2 / 12.3 / 13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1。