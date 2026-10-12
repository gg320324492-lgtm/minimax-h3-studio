# 执行指令 — P52：`rule_font_size` 量了画面，判决却只看调用者传进来的数字

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **本项有一个先例可抄（P22），也有一个陷阱要避开（P48 记的"量了但测错东西"）。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `eeb7d39`（已推送） |
| 基线 | **⚠️⚠️ 本机全量套件测不出稳定数字。** 三次连跑得到三个不同失败集合，<br>而每个失败文件单跑都绿。**⇒ 你报的每个数字都要注明：是否并发、是否清过探针。**<br>**开工前先自己测一次当基线**，不要沿用工单里的任何数字。 |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**（GBK 控制台把 `—` 显示成替换字符）。
**读非 ASCII 用字节判断，别信控制台。**

**⚠️ Shell 状态在两次工具调用之间不保持**。**全程用绝对路径**。
**⚠️ `git add` 用显式路径**，不要用 `-A` 或 `.`。
**⚠️ 目前没有别的 agent 在跑，但请假设可能有**，用独立的 scratch 目录。

**开工前记录 sha256，收尾比对**：
- `studio/scripts/visual_qa.py`
- `tests/test_p22_contrast_is_not_a_per_frame_gate.py`
- `tests/test_p48_reaccept.py`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺陷：**仪器是真的，判决不看它**

`studio/scripts/visual_qa.py:644-676`：

```python
def rule_font_size(a, declared_px=None, scale=1.0) -> Finding:
    m, trusted, _ = model_mask(a)
    …
    median = float(np.median(bands))          # ← 真的量了画面
    if declared_px is None:
        return Finding(..., UNVERIFIABLE, …)
    ratio = median / declared_px             # ← median 只进了这里
    absolute_short = declared_px < MIN_TYPE_PX   # ← 判决只看 declared_px
    verdict = FAIL if absolute_short else PASS
```

**⇒ `median` 不参与判决**，只进了 `ratio` 与 message。

**实测（P48 报、指挥窗口复核）：同一帧传 `--declared-px 20` → PASS，
传 `--declared-px 5` → FAIL。与画面上是什么无关。**

### 2. ⚠️ 它只跑在 `--frame` 路径上

`visual_qa.py:1367`（`run_on_frame`）与 `:1544`。
**`--props` 路径不经它。** 它的调用面很窄：

| 调用点 | 情况 |
|---|---|
| `run_on_frame` ← `--frame` 路径 | 唯一入口 |
| `test_p22_contrast_is_not_a_per_frame_gate.py:103` | ⚠️ **传 `--declared-px 20`，但注意力全在 `contrast` 上** |

**⇒ P22 那条测试里 `font_size` 是陪跑的** —— 它的 `20` 只是为了
让 `font_size` 不 UNVERIFIABLE（`20 >= MIN_TYPE_PX` ⇒ PASS）。
**⚠️ 请核实这条判断，并说明改动它会不会破坏 P22 的本意。**

### 3. ⚠️ 先例：P22 已经修过同一形状的 `contrast`

账本记着 P22 把 `contrast` 从"逐帧门"里拿掉，**理由是仪器与判据口径不同**。
**⇒ 本项应当沿用 P22 的先例：把判据换成"画面自身的读数"。**

⚠️ **但请先读 P22 的文档确认那个先例具体是什么形状**
（`docs/P22_CONTRAST_ALWAYS_RED.md`（指挥窗口已核实存在；若你找到更完整的以你为准）），**不要凭我这句话照抄**。

### 4. ⚠️ 陷阱：`declared_px` **不是**没用，它是有功能的

⚠️ **不要因为它"不参与判决"就断言它该被删。**
它承载的是**声明值与实测值之比**（`ratio = median / declared_px`）——
**那是一个有意义的量**：它回答「图谱声明 20px，画面上的字实际多少高」。

⚠️ **本项真正的问题是「判决用了错的量」，不是「这个量不该存在」。**
⚠️ **而且要小心**：若把判决改成只看 `median`，就会丢掉
**「声明得太小」这一类缺陷** —— 而那正是 docstring 里写的
*"chart value labels are declared `20 * s`, which is 11.25px at s=0.5625"* 那条。
**⚠️ 请明确回答：改完之后，「声明值过小」这条缺陷还能不能被抓到？抓不到就是回归。**

---

## 二、你要交付的东西

### 第 1 件事：**先判定判据该怎么写，再写代码**

⚠️ **这一步是本项的全部难点。** 请给出判据，并说明**它为什么可判定**
（有仪器 / 有期望值 / 有正类）。

⚠️ **至少要考虑这三条路，并说明你选哪条、为什么**：

| | 做法 | 代价 / 风险 |
|---|---|---|
| **A** | 判决改成只看**实测** `median`（低于绝对可读下限就 FAIL） | ⚠️ **丢掉"声明过小"这一类** |
| **B** | `median` **与** `declared_px` **都**进判决，但**各司其职** | 需要说清两者如何分工、如何避免重演"参数劫持" |
| **C** | 你认为还有更好的形状 | 请论证 |

⚠️ **⚠️ 判读要求（本项目被骗过十一次）**：
- **不能只是把 `absolute_short` 换成 `median < MIN_TYPE_PX`** ——
  **那只是把"被 `--declared-px` 劫持"换成"被测量噪声劫持"**。
  ⚠️ **请证明你的判据不会被一个离群帧劫持**（例如只有一行大字的帧）；
- **必须有正类与负类**：什么样的帧该 FAIL、什么样的该 PASS？
  ⚠️ **如果你找不到能区分这两者的判据，如实说**，**那是合法交付**
  （本项目已接受过十三次「实测说不出想要的结果」）。

### 第 2 件事：**实施，并核实 P22 那条测试**

⚠️ **改动 `visual_qa.py` 后，`test_p22_...` 会怎样？**
**若它变红，说明什么？** 请判断那些红**是不是对的**。
⚠️ **不要为了让它绿而弱化断言** —— 若它该红，就改断言并说清理由。

### 第 3 件事：**给"判决不看画面"上一条守卫**

⚠️ **⚠️ 本项的守卫必须能抓住的是「判决与画面脱钩」，不是「某个数变了」。**

- **必须真的跑它并断言行为**，不能断言源码里有 `declared_px` 或某个常量名；
- ⚠️ **至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| **同一帧、只改 `--declared-px`，让判决跟着变** | **守卫红**（这是本项的缺陷形态） |
| **同一帧、只改画面内容（字号），让判决不变** | **守卫红**（专抓"判决不看画面"） |
| 让判据永远判"通过" | 守卫红 |

⚠️ **"红在错误的理由上"不算通过**（P35 红在 `NameError`、P36 红在 `SyntaxError`）。
⚠️ **别让探针的异常变成判定**（P31/P34/P36 各栽过一次）。
⚠️ **每条毒变异后从字节快照复原，收尾核对 sha256。**

---

## 三、验证协议

1. **测量前先证明被测对象存在**（先造出该 PASS 的帧与该 FAIL 的帧，
   **别在写代码前就假定它们存在**）；
2. **贴原始输出**，不贴结论句；
3. ⚠️ **五条高频复发**：先证明被测对象存在再测量；**在错误的尺度上测等于没测**；
   **外推等于没测**；**写数字要么实测要么标注未测**；**CRLF 用字节计数验**
   ⚠️ **`visual_qa.py` 的行尾请先测再动**；
4. ⚠️ **磁盘**：输出到 **E 盘**，`TMPDIR` 指 E 盘、`--public-dir` 指空目录
   （否则每个 bundle 复制 **773 MB** 的 `studio/public`）。**跑完清理。**
   ⚠️ **`studio/.remotion/water-renewal-bundle`（1.5 GB）不是你的，别删。**
   ⚠️ **⚠️ 指挥窗口上一轮忘了清自己 8 MB 的探针残留，
   而失败的 `test_a_finished_render_leaves_no_bundle_directory_behind` 恰恰是查残留的。
   **别成为下一个。**
5. ⚠️ **不要与别的进程并发渲染** —— 本项若要造帧会用到渲染。
6. ⚠️ `tests/test_markdown_text_is_intact.py` 守着全仓 markdown 的 U+FFFD。
7. ⚠️ py-3.10 有 cv2 但没有 pytest —— 需要 cv2 就写进普通函数用 3.10 驱动，
   3.12 里 **skip 而不是撒谎**。

---

## 四、不要动的东西

- `docs/UPGRADE_PROGRESS.md` —— **账本由指挥窗口统一更新**
- ⚠️ **`docs/P48_REACCEPTANCE.md` —— 只读。** 它的 §四.1 描述的是**修复前**的状态
  （P49 修了相机静止），指挥窗口会在账本侧统一标注，**你不要改**。
- ⚠️ **`out/charts_demo.mp4`（P27 证据目录）—— 只读，不覆盖**
- ⚠️ **`out/p45_vlm/**`、`out/p48_reaccept/**` —— 只读。**
  ⚠️ **`p45_control_render.py` 把输出路径硬编码在 `out/p45_vlm/` —— 别原样跑它。**
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`~`docs/P51*.md` —— 只读
- `DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- ⚠️ **不要动 `tests/test_p42*`、`test_p46*`、`test_p27*`、`test_p49*`、
  `test_chart_type_defaults_are_real.py`、`tests/tautology_criterion.py`** ——
  **P50/P51/P49 的成果，守卫的守卫刚建好，别碰。**
- **不要动 P19–P51 的任何成果**、不要改 `studio/src/**`（`visual_qa.py` 除外）
- **⚠️ 不要把任何帧/图复制进仓库**

**本指令授权你修改**：`studio/scripts/visual_qa.py`（**仅限 `rule_font_size` 与其调用处**）、
相关测试、新增文档。
⚠️ **`visual_qa.py` 里有 13 条规则与大量已验收的逻辑 —— 只动 `rule_font_size`。**

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（**只 stage 你自己的文件**）
- 交付时报告：
  - **判据选了 A / B / C + 理由**
  - **为什么它可判定**（仪器 / 期望值 / 正类，各是什么）
  - **假阳性与假阴性会是什么**
  - **⚠️ 改完之后「声明值过小」这条缺陷还能不能被抓到**（抓不到就是回归）
  - **你的判据为什么不会被离群帧劫持**
  - **P22 那条测试的处置 + 那些红是不是对的**
  - **三条变异的 `-rf` 原始输出**
  - **全量测试数字 + 是否并发 + 是否清过探针**
  - **三个 sha256 比对**
  - **磁盘纪律**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**；用**字节层快照**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列（供你了解上下文，不必处理）

- **待派**：`c05_bubble` 的 `chart.sizes` 惰性字段 ——
  机制已查清：`types.tsx:404` 是 `series.sizes ?? series.values`，
  **有回退**，而图谱把 `sizes` 放在 `chart` 顶层 ⇒ **回退接管，
  气泡半径用的是 values**。⚠️ **它与本项同族但更难**：
  **不是判据问题，是「一个真实的意图被一个回退值静默替换」，
  而回退让画面看起来完全正常。**
- **P49 登记未修**：`camera.focus`、`bible.camera.durationSeconds` **零读者**
  （⚠️ P49 明确没顺手补消费方，因为**补消费方等于造新的哑声明**）。
- **P43 `data-plane-3d`** —— 判 C。**`video`** —— 等外部素材。
- **P16 / P17** —— 卡在 "premium" 无判据。
- **已裁定关闭**：11.1 / 12.2 / 12.3 / 13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1。