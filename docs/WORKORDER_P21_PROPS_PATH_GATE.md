# 执行指令 — 补上 `--props` 路径上真正检查交付物的东西

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 这是 P18 未决项 3。**指挥窗口已实测复现**（非引述）：把图谱里每一个字符串毒化，
> QA 报告**逐字节相同**、退出码相同（0），且**干净图谱也是 0**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `03527c9`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `431 passed, 3 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**（cv2 只装在 3.10）。

**⚠️ 网络**：本机代理时通时不通（推送前先测 `curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://github.com`）。
**但本项是提交但不推送。**

**开工前记录 sha256，收尾比对**：
- `studio/scripts/visual_qa.py`
- `studio/scripts/qa_layers.py`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺陷：`--props` 路径检查不到任何交付物

`visual_qa.py:865` —— props 路径上唯一的真实规则是 `rule_missing_asset(props)`。
加上 `unavailable_findings()` 里的 4 条占位，**5 条 findings 里 4 条是 UNAVAILABLE 占位符**。

**指挥窗口实测**（本轮亲手跑，不是采信自述）：

```
把 showcase_demo.json 里每一个字符串毒化成 "POISONED_…"
（含 4 个 scene 的全部内容）：
  报告：IDENTICAL —— 逐字节相同
  退出码：0（干净图谱也是 0）
```

**这条路径既不拦错误、也不拦正确，是完全的装饰。**

### 2. 原因不是疏忽，是它诚实放弃了三个不可能的字段后**没有补上任何替代**

`rule_missing_asset` 的 docstring（`:616-632`）原样：

```
WHICH FIELDS ARE READ, AND WHY THAT LIST IS SHORT (P11 defect 1).
This rule used to read `props['audio']`, `props['audioEvents']` and
`props['narration']`. Of those, the renderer can receive NONE from a
showcase-v1 graph, and that was not an oversight in this function — it was
this function checking for something structurally impossible:
  * audio       — NOT declared by ShowcaseSchema, no .passthrough(), zod strips it
  * narration   — declared by a DIFFERENT schema (report-data), never in showcase
  * audioEvents — declared at showcase-v1.ts:101 as SCENE-level, zero renderer reads
```

**所以清单短是对的。** 问题在于**删掉三个不可能的之后，没有补上任何一个可能的**，
于是这条规则在 showcase 图谱上**必然无话可说**。

### 3. ⚠️ 而现在**有**可检查的字段了 —— 这是本项成立的前提

P12 与 `836f532` 之后，`radius` / `shadow` / `depthCue` 三段**已接进 schema**
（`StyleBibleSchema` 现 10 键，`.strict()`）。

**请核实：这三段里有没有「图谱声明了某个路径，而磁盘上没有」这一类可做的检查？**
若有 —— 那就是一条真实的、能拦住东西的 props 规则。

⚠️ **但请先确认它真的是缺陷**：也许 `missing_asset` 就该只管资产（音频/图片文件），
而样式段本就不该走"文件存在性"检查。**若你判定不该加，**如实说**，那也是合法结论** ——
但要给出依据，并且回答"那 `--props` 路径上还有什么应该被检查"。

### 4. 参考：`duplicate` 是另一条 props 无关但能拦住东西的规则

`rule_duplicate`（P19 已修）现在问的是"这两个文件是不是同一帧"，切口精确 `0.0`。
它**读产物**（两个 PNG），所以 `--frame-pair` 路径上的绿灯是有内容的。

**对比**：一个入口会检查、另一个不会 —— 这正是本项要问的。

---

## 二、你要交付的三件事

### 第 1 件事：先判定"该不该有检查"，再决定加什么

**先回答第 3 条那个问题**，并给出三档：

| 裁定 | 条件 | 动作 |
|---|---|---|
| **A：应该有** | 存在一类可做的 props 检查 | 给最小实现 + 守卫 |
| **B：不该有** | `--props` 的语义本就是"校验资产存在性"，样式段不该走这条路 | **如实说**，并回答"那这条路径上什么应该被检查" |
| **C：部分** | 例如某些段该查、某些不该 | **逐段给结论** |

**不要为了"让 `--props` 变绿"而加一条实际拦不住东西的规则。**
本项目刚刚接受过一个反面教训：`collision` 规则至今 UNAVAILABLE，
因为**仪器是好的、缺的是判据** —— 那比"有规则但没意义"诚实。

### 第 2 件事：实施裁定

若裁定 A：

- **明确它检查的是什么**，以及**为什么那个失败意味着产物错了**
- **必须有真东西可查** —— 若查出来永远是 PASS，那它就是新的装饰
- **给出它能拦住什么的一个具体实例**（用毒化的图谱实测）

若裁定 B 或 C：**如实写**，并把"那这条路径上什么应该被检查"作为**问题**记下来，
**不要自行扩范围**。

⚠️ **不要改 `unavailable_findings()`** —— 那 4 条是**诚实的占位符**
（"仪器没建"），它们是这个项目里被接受的状态。

### 第 3 件事：给"这条路径能不能拦住东西"上一条守卫

**判读要求（本项目被骗七次）**：

- **必须真的跑 `main(argv)` 并断言报告变了 / 退出码变了**，
  **不能**断言源码里出现某个字段名 —— 那是文本存在性断言。
- 守卫要能回答一个具体问题：
  **"把图谱改成坏的，这条路径会不会报出来？"**
- 若裁定 B（不该有检查），守卫必须**如实钉住"这条路径拦不住东西"这个事实**，
  **而不是制造一个假的通过条件**。

**至少两条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 让新加的规则无条件返回 PASS | 守卫红 |
| 让新加的规则无条件返回 FAIL | 守卫红（这条专抓"永远失败"的实现） |

**「变异存活」≠「变异无效」**：存活项判定"真漏洞"还是"无效变异"，
两种都写进 commit。**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
4. **每条毒变异之后从快照复原源文件，收尾核对两个 sha256。**
5. **⚠️ 语料要先证明存在再测量**（本窗口与上一轮 agent 各犯过一次：
   指挥窗口只 glob 到 4 张平铺 PNG，而帧序列在**目录**里；
   agent 跑的是 `out/` 里的快照副本，`ROOT` 解析到了没有 `studio/` 的树）。
6. **写任何数字要么实测过、要么明确标注未测**（P18、P19 各因此返工）。
7. **⚠️ py-3.10 有 cv2 但没有 pytest** —— 若你的测量需要 cv2，
   写进普通函数并用 3.10 脚本驱动，在 3.12 套件里 **skip 而不是撒谎**
   （P20 的处理方式，**是本项目接受的做法**）。
8. **写完立刻验行尾**。**测退出码不要用管道**（本项目已栽过多次）。
9. **不要在 bash 双引号里写带反引号的 Python 代码**；**用绝对路径而非 `/tmp`**。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要改 `unavailable_findings()` 的 4 条占位符**
- **不要动 `rule_duplicate_check_props`**（`6e86b46` 刚接上的）
- **不要动 P19 的 `SIGNATURE_EQUAL = 0.0`**、**P20 的 `DUP_THRESHOLD = 0.5`**
- **不要扩 schema** —— 本项不加字段
- **不要顺手修 P18 留下的其余三项**（`contrast` 永久失败 / `flicker` 缺失 / per-job 基线）

**本指令授权你修改**：`studio/scripts/visual_qa.py`、相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **裁定 A/B/C + 依据**（最重要）
  - **若裁定 A：它能拦住什么 + 一个具体实测实例**
  - **若裁定 B：那这条路径上什么应该被检查**
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **两个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**P18 遗留（本项不做，等裁定）**：
`contrast` 永久失败（`rule_contrast()` 零参数、333 帧全 FAIL，主题级缺陷被当逐帧门禁）／
`flicker` 是缺失的 Motion 规则（四层里唯一缺席的层成员）／
per-job 基线 + **任何偏离即拦**（P18 的最小设计）。

**跨阶段**：1.3 / 10.2（标依赖不合并不重复建）、
**P16**（`reference_analyze.py` 零实现）、
**P17**（Showcase Demo：**要求含 1–3 个 H3 cinematic shot**，而 `video`/`data-plane-3d`
在已交付 14 个场景里出现 **0 次** —— P17 会是第一个）。

**已裁定不要再讨论**：
P12 = 零段｜P13 = B+C｜P14 = B+C｜P15 = B｜P18 = B｜P19 = 已修｜P20 = 已修

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** —— 仪器已建成，修复器**故意未写**：已交付图表比值 **0.278**，无碰撞可修。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由"重新测量仍在碰撞"决定。
