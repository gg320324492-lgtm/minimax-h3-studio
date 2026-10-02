# 执行指令 — 同一个问题有两把尺子三个数字：把 `signature_distance` 收到一处

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 这是 P19（`fa6cbb5`）记录但**明确超范围未修**的一条：
> `ceo_mindread_ep01/scripts/select_takes.py:90` 对同一比较用 **1.0** 而非 0.5 ⇒ **三个调用点持有三个数字**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `0045cb9`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `424 passed, 2 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**（cv2 只装在 3.10）。

**⚠️ 网络**：本机代理时通时不通。推送前先测
`curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://github.com`。
**但本项是提交但不推送。**

**开工前记录 sha256，收尾比对**：
- `studio/scripts/visual_qa.py`
- `studio/scripts/rank_takes.py`
- `studio/scripts/take_ranker.py`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 完整链条（三次 grep 逐层追出来的）

```
visual_qa.py:311    def signature(...)            ← 自己实现
visual_qa.py:331    def signature_distance(...)   ← 自己实现

rank_takes.py:32    from take_ranker import TakeMetrics, analyze, signature_distance
rank_takes.py:44    DUP_THRESHOLD = 0.5
rank_takes.py:68    if signature_distance(a._sig, b._sig) < DUP_THRESHOLD:

select_takes.py:45  import take_ranker as _RANKER
select_takes.py:90  if _RANKER.signature_distance(a._sig, b._sig) < 1.0:   ← 硬编码字面量
```

**三处调用，一个问题（"这两段是不是同一个东西"）：**
- `rank_takes.py:68` —— 用常量 `DUP_THRESHOLD = 0.5`
- `select_takes.py:90` —— 用**硬编码 `1.0`**，不引用任何常量
- `visual_qa.py` —— P19 刚改成 `SIGNATURE_EQUAL = 0.0`（**不同的问题**：同一帧判定）

### 2. ⚠️ 而**尺子有两把**

`rank_takes.py` 与 `select_takes.py` 都用 **`take_ranker` 的 `signature_distance`**；
`visual_qa.py` **自己又实现了一份**（`:311/:331`）。

**⇒ 两个问题混在一起，本项必须分开处理：**

| 子问题 | 性质 | 严重度 |
|---|---|---|
| **(a) `select_takes.py:90` 的硬编码 `1.0`** | 同一个问题、同一个常量，另一个调用点却写死字面量 | **高** —— 改阈值必漏 |
| **(b) `signature_distance` 有两份实现** | 两把尺子，**可能给出不同的答案** | **更高** —— 若已不同，那是错的；若相同，那是等着漂移的两份拷贝 |

**先测 (b)：两份实现现在是否逐位相同？**
若**不同** ⇒ 那就是真缺陷，且要给出**各自实测的差**。
若**相同** ⇒ 那仍是缺陷（两份拷贝迟早漂移），但修法不同。

### 3. P19 已确立的原则，本项必须继承

- **阈值必须由实测分布决定**，且**要写下分布**。
- **分布不足以支撑阈值就如实说"定不出"** —— `collision` 与 P19 的
  `rule_duplicate` 都是这个状态，**它们是被接受的**。
- **不得为了让规则变绿而编一个阈值。**

⚠️ **但本项与 P19 不同**：`rank_takes` / `select_takes` 量的是
**两次独立拍摄的整段签名**（P1 实测分布 `{0.000} u [34.5, 67.2]`），
**那个分布是存在的**。**请核实它现在是否仍然成立** ——
`select_takes` 用 1.0 而 `rank_takes` 用 0.5，**至少有一个不基于那份测量**。

### 4. 本项目记录在案的复发（本项目已被骗六次，第七次在 P19）

- **文本存在性断言**：`assert 'X' in source` 匹配到解释该 bug 的**注释**。
  **P19 的 agent 第一版守卫就犯了这个**，改用从 AST 读数字字面量。
- **假测量**：探针落在阈值内导致"什么都测不出"，读起来像"规则不看输入"。
- **在文档里断言会被自己测量推翻的数字**（P18、P19 各犯一次）。

---

## 二、你要交付的三件事

### 第 1 件事：先测两把尺子，再裁定

**独立复现第 1 条的链条**，然后回答：

> **`visual_qa.py` 与 `take_ranker` 的 `signature_distance` 现在逐位相同吗？**
> 相同 / 不同，**给可复现证据**。

**然后裁定 (a)**：`select_takes.py:90` 的 `1.0` 该怎么处理？

| 裁定 | 条件 | 动作 |
|---|---|---|
| **A：引用共享常量** | 0.5 有实测依据且 1.0 无 | 让 `select_takes.py` 引用 `DUP_THRESHOLD`，**不要自己判断哪个对** |
| **B：两处确实该不同** | 两处的问题不同（不同总体） | **给出依据**；并把两个数字各自的**实测分布**写下来 |
| **C：定不出** | 两份分布都不足以支撑 | **如实说定不出**，保持现状但**标注这是未决**，不要编 |

⚠️ **B 需要证据支撑，不能只凭"看起来不同"。**

### 第 2 件事：实施裁定，并处理那把重复的尺子

⚠️ **两把尺子的合并不在本项的最低要求内**，但请**至少给出结论**：

- 若逐位相同：**说清它们为什么相同、且给出防漂移的办法**
  （例如加一条守卫断言两者一致），**但不必强行合并** ——
  合并可能牵动 `ceo_mindread_ep01` 那条独立管线，超出本项范围。
- 若**不同**：**那是本项最重要的发现**，先报上来。

### 第 3 件事：给"同一个问题不许有两个数字"上一条守卫

**判读要求**：

- **必须真的调用两处代码并断言它们的判定一致**，
  **不能**断言源码里出现某个常量名或字面量 ——
  **本项目已被文本存在性断言骗过六次，第七次刚发生在 P19**。
- 若两处的**问题本身不同**（裁定 B），守卫必须**如实记录这个差异及依据**，
  **而不是强行判它们相等**。

**至少两条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 把 `select_takes.py:90` 的 `1.0` 改回一个别的数 | 守卫红 |
| 让两处引用同一个常量但**语义不同**（即裁定 B 的情形） | 守卫应**红**，并说明它发现的是"两个问题共用了一个数字" |

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
5. **⚠️ 语料要先证明存在再测量**（本项目测过 150 帧场景的**帧 120** ——
   80% 处、生命周期 exit 阶段、图表已退场，测出的"墨迹"全是背景噪声）。
   ⚠️ **本窗口刚犯过一次**：只 glob 到 4 张平铺 PNG，而帧序列在**目录**里 ——
   **测了不存在的东西**。
6. **写任何数字都要么实测过、要么明确标注未测**（P18、P19 各因此返工一次）。
7. **写完立刻验行尾** —— P18 的 `qa_layers.py` 曾被污染成 459 行 CRLF 而全仓裸 LF。
8. **测退出码不要用管道**（本窗口两次栽在这上面）。
9. **不要在 bash 双引号里写带反引号的 Python 代码**；**用绝对路径而非 `/tmp`**。
10. **`ceo_mindread_ep01` 是独立管线**（21894 文件 / 341 MB）——
    **若要 grep 它，注意别把整个目录当源码扫**，那条经验已写进 `locked_fields.py` 的注释。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录（含 `out/p13_probe/` 51 项）；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要改 `visual_qa.py` 的 `SIGNATURE_EQUAL = 0.0`** —— P19 刚定，
  它量的是**不同的问题**（同一帧 vs 两段独立素材）
- **不要合并两把尺子**（`visual_qa` 的与 `take_ranker` 的）——
  合并不在本项的最低要求内，**给结论即可**
- **不要动 `take_ranker.py` 的算法** —— 它是三条路径的共同上游
- **不要顺手修 P18 留下的其余四项**（`contrast` 永久失败 /
  `--props` 不检查交付物 / `flicker` 缺失 / 总计划措辞）

**本指令授权你修改**：`ceo_mindread_ep01/scripts/select_takes.py`、
`studio/scripts/rank_takes.py`、相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **两把 `signature_distance` 是否逐位相同 + 可复现证据**（最重要）
  - **`select_takes.py:90` 的裁定 A/B/C + 依据**；
    若定阈值，**附实测分布**；若裁定"定不出"，**如实说**
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **三个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**P18 遗留（本项不做，等裁定）**：
`contrast` 永久失败（主题级缺陷被当逐帧门禁）／
`--props` 路径不检查任何交付物（指挥窗口已实测复现）／
`flicker` 是缺失的 Motion 规则／
per-job 基线文件 + **任何偏离即拦**（P18 的最小设计）。

**跨阶段**：1.3 / 10.2（VLM Critic provider 抽象；标依赖不合并不重复建）、
**P16**（参考视频 Benchmark，`reference_analyze.py` 零实现）、
**P17**（Showcase Demo：45–60s 商业级 demo，**要求含 1–3 个 H3 cinematic shot** ——
而 `video` / `data-plane-3d` 在已交付 14 个场景里出现 **0 次**）。

**已裁定不要再讨论**：
P12 = 零段｜P13 = B + C｜P14 = B + C｜P15 = B｜P18 = B｜P19 = 已修

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** —— 仪器已建成（`chart_geometry.py` / `c6d7a5a`），修复器**故意未写**：
  已交付图表比值 **0.278**，无碰撞可修。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由
  "重新测量仍在碰撞"决定，而非计数器。
