# 执行指令 — P18 四层门禁：先数清现在有几层，再决定要不要"四层"

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 本指令**不是**"去实现四层门禁"。它先要回答一个问题，答案可能是"现在只有两层"。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `60f8d0c`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `395 passed, 2 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

**⚠️ 网络**：本机代理（`127.0.0.1:7897`）**时通时不通**。
推送前先测 `curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://github.com`
（000 = 绕过代理，200 = 走代理）。**但本项是提交但不推送。**

**开工前记录 sha256，收尾比对**：
- `studio/scripts/visual_qa.py`
- `studio/scripts/qa_report.py`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. P18 从未实现

`docs/UPGRADE_MASTER_PLAN.md`：

```
| P18 | 最终 QA（四类） | Technical / Layout / Motion / Visual 四层门禁 | 全过 |
```

账本 18.1 空行。**"四层"这四个字从未被定义过** —— 哪条规则属哪层，
没有一处写过。

### 2. `visual_qa.py` 有 11 条规则，但它们**不在同一层**

指挥窗口实测（`grep "^def rule_"`）：

| 规则 | 输入 | 它实际上属于哪一层 |
|---|---|---|
| `rule_safe_area` | `np.ndarray` | Layout |
| `rule_clipping` | `np.ndarray` | Layout |
| `rule_font_size` | `np.ndarray` | Layout |
| `rule_contrast` | **无参** | Visual（静态查 palette） |
| `rule_black_frame` | `np.ndarray` | Technical |
| `rule_freeze` | **两个路径** | Motion |
| `rule_duplicate` | **两个路径** | Technical |
| `rule_blur` | `np.ndarray` | Technical |
| `rule_aspect` | 尺寸元组 | Technical |
| `rule_missing_asset` | **props 字典** | Technical |
| `rule_duplicate_check_props` | **路径** | Technical（刚接上，`6e86b46`） |

**三种输入形态**（像素数组 / 文件对 / 图谱）混在十一个函数里。
**Motion 层只有一条规则**（`rule_freeze`）—— 而它需要两个路径，
也就是**需要渲染两帧**，是全套里最贵的一条。

### 3. 另有一套口径不同的门禁

`studio/scripts/qa_report.py` 管**容器 / 时长 / 响度**，其表头第 17 行：

```
Exit 1 on any FAIL, and on any UNVERIFIABLE.
```

且它记录了一条本项目的重要教训（同文件第 11-12 行）：

> a gate that cannot verify something must not report success — the P10 audit
> found the duration check had never run on the one delivered props file for
> exactly that reason.

⚠️ **注意它管的是 `report-pipeline` 渲染**（另一条管线），
**不是 `visual_qa.py` 管的 showcase 渲染**。
**两套门禁的适用对象不同，请先查清它们各自服务于什么，不要合并。**

### 4. 「三态而非两态」已是本项目既定原则

`PASS` / `FAIL` / `UNVERIFIABLE`，且 **UNVERIFIABLE 退出非零**
（`6e86b46` 已把 `visual_qa.py` 对齐到这个原则）。
**新门禁必须继承这条**，不能退回"查不了就当过"。

---

## 二、你要交付的三件事

### 第 1 件事：把"四层"落到具体规则上

**这是本项的核心。** 产出一张**每条规则都有归属**的表：

| 层 | 判据是什么 |
|---|---|
| **Technical** | 产物/资产层面：能不能读、对不对得上（黑帧、重复帧、模糊、宽高比、资产缺失、容器、时长、响度） |
| **Layout** | 画面几何层面：安全区、裁切、字号（元素是否放得下、可不可读） |
| **Motion** | 时间维度层面：动没动、动得对不对（冻结检测、时长比例） |
| **Visual** | 审美/一致性层面：对比度、模糊、风格一致性 |

**要求**：

- **每条规则必须归到恰好一层**，且**给出归类的理由**。
- 若发现**某层只有 0–1 条规则**，**如实写出来** —— 这正是本项要暴露的事实。
- 若某条规则**归不进任何一层**（例如 `rule_missing_asset`），**说明它为什么特殊**。
- ⚠️ **不要为了凑成"四层"而硬分。** 若实测只有两层有实质规则，
  **那就是结论，不是失败**。

### 第 2 件事：判定"四层门禁"该怎么建

必须回答：

> 现在这套 QA **离"四层门禁"差什么**？差的是**规则本身**、
> **层的划分**，还是**"全过才算过"这个总闸**？

三档：**A 值得建**（给最小设计，不实现）／**B 不值得建**（记录理由与真正的缺口在哪）／
**C 拆开**（逐条给结论）。

**B 和 C 完全合法。** 本项目已接受 P12「零段值得建」、P13/P14「B+C」、P15「B」。
**不要为了交差而建。**

⚠️ **特别注意**：**"全过才算过"这个总闸现在很可能不存在** ——
`visual_qa.py` 目前是"报告所有发现"，**不是"任一失败就拦住"**。
请实测这一点，并说明总闸与"报告"的差别在本项目里是否成立
（想想 P15 那个 `generative`：**QA 报告逐字节相同、退出码相同** ——
它能拦住什么？）。

### 第 3 件事：给"层归属"上一条守卫

守卫必须落在**可测行为**上：

- **断言当前真实归属**，不是理想归属。
- **每条规则只能属于一层** —— 若某条被归到两层，守卫必须红
  （这是"分类必须穷尽且互斥"的性质）。
- **不能**用文本存在性断言来判定"某规则属于某层" ——
  本项目已被这类断言骗过**六次**，最近三次是：
  ① `assert 'mkdtemp' in source` 匹配到解释该 bug 的**注释**；
  ② `assert 'depth' not in schema_text` 被 `depthCue` 的**子串**触发；
  ③ 删掉检查后 `Unknown flag` 仍留在**修复说明的注释里**。

**至少两条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 把某条规则改归到另一层 | 守卫红 |
| 让一条规则同时属于两层 | 守卫红 |

**若某变异存活**，判定"真漏洞"还是"无效变异"，两种都写进 commit。
**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
4. **每条毒变异之后从快照复原源文件，收尾核对两个 sha256。**
5. **⚠️ 磁盘纪律**：`studio/bin/render.mjs:45-47` 记录过
   **118 个 bundle 把 C: 盘 TEMP 填到 46 GB**。
   **本项大概率不需要渲染** —— `out/p13_probe/` 里已有 51 个产物可用。
   若确实要渲，输出到 **E: 盘**，跑完清理，收尾报告写明造了什么、删了什么。
6. **测退出码不要用管道**（本窗口用 `| tail` 读到 `tail` 的、差点误判）。
7. **写长文本在字节层操作**；**不要在 bash 双引号里写带反引号的 Python 代码**
   —— 指挥窗口刚因此产出四个 0 字节垃圾文件。
8. **行尾按文件实测**，不要相信任何人的断言包括本工单的。
9. **`/tmp` 在 bash 与 Python 中解析不同**（`C:\Users\pc\AppData\Local\Temp`）——
   用绝对路径。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录（含 `out/p13_probe/` 51 个文件）；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— cv2 只装在 3.10，本项 `--ignore`
- **不要实现四层门禁、不要改任何规则的判定逻辑** —— 结论未裁定，实施越界
- **不要合并 `visual_qa.py` 与 `qa_report.py`** —— 它们服务于**不同管线**，
  先查清各自服务什么（工单第 3 条）
- **不要改那两条钉住现状的守卫**（`tests/test_p13_scene_cache_facts.py`）——
  若你的改动会让它们红，先读、确认钉的是现状，再决定

**本指令授权你修改**：新增文档、新增测试文件。
**除守卫所需的最小改动外，不要改生产代码。**

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **每条规则的层归属表 + 归类理由**（最重要）
  - **哪几层是空的或只有一条规则**
  - **"全过才算过"这个总闸现在存不存在 + 实测**
  - **建不建的判定 + 真正的缺口在哪**
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **两个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**跨阶段**：1.3 / 10.2（VLM Critic provider 抽象；
**已裁定标依赖、不合并、不重复建** —— 仓库至今无 `take_critic.py`）、
**P16**（参考视频 Benchmark，`reference_analyze.py` 零实现）、
**P17**（Showcase Demo：45–60s 商业级 demo，**含 1–3 个 H3 cinematic shot** —— 
⚠️ 这与 P15 的结论直接相关：**`video` / `data-plane-3d` 在已交付 14 个场景里出现 0 次**，
**若 P17 要含 H3 shot，那是第一个**）。

**已裁定不要再讨论**：
- P12 = 零段值得建｜P13 = B + C｜P14 = B + C｜P15 = B
- 「入口静默通过」一族确认**无第三处**（`render.mjs` / `still.mjs` 与四个 `argparse` 脚本
  都拒绝未知 flag；`check_contract.py` 不接受任何参数）

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** —— 仪器已建成（`chart_geometry.py` / `c6d7a5a`），修复器**故意未写**：
  已交付图表比值 **0.278**，无碰撞可修。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由
  "重新测量仍在碰撞"决定，而非计数器。
