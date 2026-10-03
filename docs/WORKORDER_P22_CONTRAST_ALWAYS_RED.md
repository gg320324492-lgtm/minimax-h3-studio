# 执行指令 — 拆开 `contrast` 这道永久红的闸：主题缺陷被当成了逐帧门禁

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `22b246f`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `443 passed, 3 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

**⚠️ 网络**：本机代理时通时不通（推送前先测 `curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://github.com`）。
**但本项是提交但不推送。**

**开工前记录 sha256，收尾比对**：
- `studio/scripts/visual_qa.py`
- `studio/scripts/qa_layers.py`
- `studio/src/templates/finance-showcase/design/themes.ts`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺陷形状：一条与渲染无关的规则，被当作逐帧门禁

`visual_qa.py` 的 `rule_contrast()` —— **零参数**：

```python
def rule_contrast() -> list[Finding]:
    """WCAG ratios for every theme x background x role pair. 24 pairs.
    A lookup on palette constants, so it is exact — no threshold margin applies."""
```

**它只看 `THEMES`（`design/themes.ts` 的常量）**，**与渲染什么帧完全无关**。
P18 实测：**333 帧全部 FAIL** ⇒ **`--frame` 永远不可能 exit 0**。

**这不是强制，是噪声** —— 一条永远红的闸不能拦住任何东西，
只会让人学会忽略红色。

### 2. 指挥窗口实测：8 对失败**不是均匀分布的**

```
8/24 对低于 4.5:1:
   2.16  premium-light/inkFaint on bg          ← 最差
   2.20  premium-light/inkFaint on bgAlt
   2.83  premium-dark/inkFaint  on bg
   2.89  premium-dark/inkFaint  on bgAlt
   3.23  premium-light/accent   on bg
   3.64  premium-light/accent   on bgAlt
   3.71  premium-light/positive on bg
   4.18  premium-light/positive on bgAlt
```

**6/8 来自 `premium-light` 一个主题**；2/8 来自 dark 的 `inkFaint`。
**全部集中在三个角色上**：`inkFaint`（4 对）、`accent`（2 对）、`positive`（2 对）。

**⇒ 问题不是"对比度规则太严"，而是"某个主题的某几个角色不合格"。**

### 3. ⚠️ 而 `inkFaint` 低于 4.5:1 **可能是设计意图**

`inkFaint` 按命名就是**最淡的一档墨**。WCAG 的 4.5:1 是**给正文文字**的门槛；
一个专门用于装饰/次要信息的色阶低于它，**未必是缺陷**。

**请先查清**：`inkFaint` 在渲染源码里**实际用在哪**？
若是正文/数据数字 ⇒ 它是真的不合格；
若是分隔线/次要标签 ⇒ **规则问错了问题**。

⚠️ **注意一个判读陷阱**：本项目已因"同名诱饵"误报过惰性字段
（`focus` 匹配生命周期阶段名、`ease` 匹配内置表键、
`sizes`/`sizeBy`/`showArea`）。`inkFaint` 的消费方要**逐个确认**，不要只数词频。

### 4. 一条已确立的原则（`qa_report.py:11-12`）

```
a gate that cannot verify something must not report success — the P10 audit
found the duration check had never run on the one delivered props file for
exactly that reason.
```

**反向也成立**：**一条永远失败的闸同样是有害的** ——
它把"已知存在的主题缺陷"和"这一帧坏了"混成同一个红。
**本项要拆开这两件事。**

---

## 二、你要交付的三件事

### 第 1 件事：先分类，再决定

**先回答第 3 条**：`inkFaint` / `accent` / `positive` 在渲染源码里的**实际消费点**，
逐一给出（附 grep）。

然后**三档裁定**：

| 裁定 | 条件 | 动作 |
|---|---|---|
| **A：拆成两件事** | "主题合格性"（静态查表）与"这一帧的对比度"（需要像素）是两个问题 | 拆开：主题级结果**不再逐帧重复报**，逐帧那条要么实现要么诚实标 UNAVAILABLE |
| **B：改阈值** | 4.5:1 对某些角色不适用 | **⚠️ 最危险的选项** —— 见下方警告 |
| **C：现状 + 标注** | 它就该红，红是提醒 | **那么 `--frame` 的总闸必须知道** —— 见下方要求 |

⚠️ **B 的警告**：**不要为了让闸变绿而调低 `WCAG_TEXT`。**
那是把一个可测量的标准改成"让结果好看"。
**若判 B，必须给出 WCAG 适用范围的外部依据**，并说明为什么这条规则
只对某些角色适用 —— **不能是"调一下就不红了"**。
**本项目已因此类操作付出过代价**（`duplicate` 阈值错配、P19 的 `1.0`）。

**若裁定 A 或 C，请额外回答**：

> **`--frame` 的总闸（`visual_qa.py:855` `return 1 if hard or unver else 0`）
> 该怎么知道"这个红是已知的、不是这一帧的问题"？**

**这是本项的核心**。选项至少有：
- 主题级发现**不进逐帧报告**（单独一份）
- 或进报告但**不带 FAIL 判定**（如 `KNOWN` 之类第三种状态）
- 或总闸**显式豁免某几条规则**（并把豁免写进代码，不是配置）

**三档之外的答案（"拆开 + 新增真实逐帧检查"）是最好解，请优先考虑。**

### 第 2 件事：实施裁定

⚠️ **本项目最近四次的实际做法可参考**：

| 情况 | 本项目接受过的处置 |
|---|---|
| 仪器好、缺判据 | `collision` 至今 **UNAVAILABLE**（不编阈值） |
| 阈值错配、总体不分离 | `rule_duplicate` 改成问**它能问的问题**（同一帧，切口 0.0） |
| 声称的性质不存在 | 先修 docstring，再谈阈值 |
| 输入压根不通向渲染 | 改问**存在与否**（`graph_scene_renderable`） |

**请说明你的处置属于哪一类**，以及**为什么它是"说清真相"而不是"把红变绿"**。

### 第 3 件事：给"永久红的闸"上一条守卫

**判读要求（本项目被骗七次）**：

- **必须真的跑 `main(argv)` 并断言退出码/报告**，
  **不能**断言源码里出现 `WCAG_TEXT` 或某个数字 —— 那是文本存在性断言。
- 守卫要能回答一个具体问题：
  **"如果主题调色板明天修好了，这条闸会不会变绿？"**
  若答案是"不会"（因为它压根不看渲染），那守卫要把这个事实钉住。

**至少两条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 把 `rule_contrast` 的阈值改到不可能失败的值 | 守卫红（专抓"调阈值让它变绿"） |
| 让它仍然逐帧 FAIL 但换一种报告形式 | 按你的裁定决定，并说明为什么 |

**「变异存活」≠「变异无效」**：存活项判定"真漏洞"还是"无效变异"，
两种都写进 commit。**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
4. **每条毒变异之后从快照复原源文件，收尾核对三个 sha256。**
5. **⚠️ 三条高频复发**（本项目已见多次）：
   - **先证明被测对象存在，再测量** —— 指挥窗口与 P20 agent 各犯过一次
     （前者只 glob 到 4 张平铺 PNG 而帧序列在目录里；后者跑了 `out/` 里的快照副本，
     `ROOT` 解析到没有 `studio/` 的树）；
   - **写任何数字要么实测过、要么明确标注未测**（P18、P19 各返工一次）；
   - **在确认变异生效之前不要宣称它存活**（P21 agent 栽在这里，
     注入的变异产出 `NameError` 而非行为变化）。
6. **py-3.10 有 cv2 但没有 pytest** —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**（P20 的处理方式，**是本项目接受的做法**）。
7. **写完立刻验行尾**（`themes.ts` 的行尾**自己测**，不要相信任何人的断言）。
8. **测退出码不要用管道**（本项目已栽过多次）。
9. **不要在 bash 双引号里写带反引号的 Python 代码**；**用绝对路径而非 `/tmp`**。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要改 `themes.ts` 的调色板值** —— 即便你判定某些对比度不合格，
  **改色板是一个设计决定，超出本项范围**。**给建议，不实施。**
- **不要改 `WCAG_TEXT` 的值**，除非裁定 B 且**给出了 WCAG 适用范围的外部依据**
- **不要动 `unavailable_findings()` 的 4 条占位符**
- **不要动 P19 的 `SIGNATURE_EQUAL`、P20 的 `DUP_THRESHOLD`、P21 的 `graph_scene_renderable`**
- **不要顺手修 P18 剩下的两项**（`flicker` 缺失 / per-job 基线）

**本指令授权你修改**：`studio/scripts/visual_qa.py`、相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **`inkFaint`/`accent`/`positive` 的实际消费点**（最重要）
  - **裁定 A/B/C + 依据**；**总闸怎么知道"这个红是已知的"**
  - **你的处置属于哪一类**（"说清真相"而非"把红变绿"）
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **三个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染`
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**P18 遗留（本项不做）**：
`flicker` 是缺失的 Motion 规则（四层里唯一缺席的层成员）／
per-job 基线 + **任何偏离即拦**。

**跨阶段**：1.3 / 10.2（标依赖不合并不重复建）、
**P16**（`reference_analyze.py` 零实现）、
**P17**（Showcase Demo：**要求含 1–3 个 H3 cinematic shot**，而 `video`/`data-plane-3d`
在已交付 14 个场景里出现 **0 次**，且这两个类型**正是 P21 查出的 9 个无渲染器类型中的 2 个**
—— **若 P17 要含 H3 shot，那会是第一批渲染成 "not implemented in P4" 的内容**）。

**已裁定不要再讨论**：
P12 = 零段｜P13 = B+C｜P14 = B+C｜P15 = B｜P18 = B｜P19/P20/P21 = 已修

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** —— 仪器已建成，修复器**故意未写**：已交付图表比值 **0.278**，无碰撞可修。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由"重新测量仍在碰撞"决定。
