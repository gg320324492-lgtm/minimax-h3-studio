# 执行指令 — P12 Director Agent：先证明哪一段值得建

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 本指令**不是**"去实现 Director Agent"。它先要回答一个问题，答案可能是"不建"。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `e71cb56`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `334 passed, 2 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

**开工前记录这些 sha256，收尾比对**（6.7/6.8 刚动过，别把它们弄脏）：
- `studio/src/templates/finance-showcase/design/tokens.ts` → 应为 `698fb0f5…`
- `studio/src/schemas/showcase-v1.ts` → 应为 `653313f4…`
- `pipeline/schemas/showcase-v1.schema.json` → 应为 `ab19cda2…`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. P12 完全没有实现

`docs/UPGRADE_MASTER_PLAN.md:137`：

```
| P12 | Director Agent | Brief→StyleBible→Storyboard→SceneGraph→AssetPlan | Agent 不直接改 TSX |
```

- 全仓检索 `director` / `storyboard` / `assetplan`：**零个实现文件**
- `pipeline/` 只有 4 个模块：`shotspec.py` / `prompt_compiler.py` / `scene_graph.py` / `migrate_shotspecs.py`
- **没有 `take_critic.py`**（那属于 1.3/10.2，已裁定标依赖不合并不重复建）

### 2. 五段链路里，有一段已经存在，有一段是死头

`scene_graph.py` 已经存在且**上轮刚把它改成读 JSON Schema**（`a55d03d`）。
它对应链路里的 **SceneGraph** 段（校验侧）。

**AssetPlan 段是死头**：`visual_qa.py` 的 `missing_asset` 规则
仍在读 `props.audio` / `props.audioEvents` / `props.narration` 三个字段，
而**渲染器一个都收不到**（`narration` 属于另一个 schema）。
所以它目前实际只能核对四条硬编码 SFX 路径。

### 3. StyleBible：schema 声明 7 键，交付图谱只设过 4 键

| 检查 | 结果 |
|---|---|
| JSON Schema `definitions/StyleBible.properties` | **7 个键** |
| zod `StyleBibleSchema`（`showcase-v1.ts`） | **同样 7 个键**，全为 `z.record()` 开放袋子 |
| 两侧是否一致 | **一致**（无镜像漂移） |
| 交付图谱实际设过的键 | **只有 4 个**：`typography`(3) / `palette`(2) / `motionLanguage`(2) / `cameraLanguage`(2) |

**7 个键全部是开放的（无 `additionalProperties: false`）**，所以设 0 个也合法。

**`spacing` / `chartLanguage` / `audioLanguage` 三键：schema 允许、零图谱使用。**
其中 `audioLanguage` 尤其可疑——它与 6.7 刚查清的"顶层 `audio` 永久不可达"同源。

### 4. 三个键在渲染侧有没有真消费方 —— **这是本项的核心判据**

指挥窗口**尚未**逐键测量。**你要测。**

对 7 个键各给出：**渲染源码里有没有代码读它**。

注意本项目的判读陷阱：
- 断言"某键没被读"必须给出 grep 并**排除同名诱饵**
  （`focus` 会匹配生命周期阶段名、`spacing` 会匹配 CSS 属性、
  `palette` 会匹配 `PALETTE` 常量）
- **零命中 ≠ 死字段**：`styleBible.tsx` 会把整个 bible 展开导出
  （`DEPTH: s.depth` / `SPACING: …` 之类），**间接消费**要走 `useDesign()`
  才能发现。本项目已因此把 `sizes`/`sizeBy`/`showArea` 误报成惰性。

**逐键给出三态结论**：直接读 / 间接读（经 `useDesign()` 或展开）/ 零消费。
**每一态都要附可复现的 grep。**

---

## 二、你要交付的三件事

### 第 1 件事：产出 `docs/DIRECTOR_SCOPE_VERDICT.md`

一份测量记录，包含：

1. **7 键逐键三态表**（第 1 节第 4 条），每格附 grep。
2. **五段链路逐段现状**：Brief / StyleBible / Storyboard / SceneGraph / AssetPlan，
   每段标注"已存在 / 半成品 / 零实现"，附检索证据。
3. **结论与依据**，必须回答：

   > 在已测得的消费方事实下，Director Agent 的哪一段**现在建了就有用**？
   > 哪一段建了会**立刻产生哑声明**（声明了但没人读）？
   > 哪一段应当**等上游**（并说明等什么）？

**这一条比任何代码都重要。** 本项目已经因为"照着 schema 生成"造出一批
没人消费的字段（惰性字段审计的结论）。Director Agent 若照着 7 键 schema
自动生成 StyleBible，**默认就会生成 11 个键里的大部分为哑声明**。

### 第 2 件事：给"建哪一段"的最小设计（**只设计，不实现**）

对你判定为"值得现在建"的那一段，给出最小可用设计：
- 模块路径、函数签名、输入输出
- **它消费哪些已有产物**（`scene_graph.py` / `shotspec.py` / `prompt_compiler.py`）
- **它如何避免制造哑声明**（这是硬要求，给出具体机制，
  例如"只允许输出消费方已证明存在的键"，或"输出后由某条检查拒绝未消费键"）
- **守卫怎么写，且必须能红**

**不要实现它。** 是否实现由指挥窗口与用户裁定。

> 除非你判定**没有任何一段现在值得建**——那也是合法结论，
> 交付物就是那份记录加上"等上游"的清单，同样要有证据。

### 第 3 件事：给"哑声明"上一条通用守卫（**本项一定做**）

`StyleBible` 的 7 个键是开放的，所以**任何未被消费的键都能悄悄存在**，
且没有任何守卫会发现。这是与已交付图谱里那批惰性字段**同构**的问题。

请加一条守卫，断言：

> **图谱里 `style_bible` 出现的每一个键，都必须至少有一个渲染侧消费方。**

- 已知当前只有 4 个键出现，所以这条守卫应当**绿**。
- 若某键将来零消费，它必须**红**。

**这条守卫的红必须是行为性的**：消费方的判定要用检索/推导得出，
不要落成 `assert 'palette' in src` 这种文本存在性断言——
**本项目已被这类断言骗过三次**（`mkdtemp` 匹配到解释 bug 的注释、
`rmSync` 被预先存在的调用满足、两个词构成的说明删掉后仍通过）。

**至少做这两个变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 在某图谱的 `style_bible` 里加一个零消费键（如 `ghostKey: {...}`） | 守卫红 |
| 把某个键的渲染侧消费方改名/删除 | 守卫红 |

**若某变异存活**，判定它是"真漏洞"还是"无效变异"，两种都写进 commit。
**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
   上一轮指挥窗口误判过一次：前一个形态的污染没清，导致两条变异红在
   无关的几何断言上，看着像"形态没被抓住"。
   **看到红的理由不对，先查现场再下结论。**
4. **每条毒变异之后从快照复原源文件，收尾核对三个 sha256。**
5. **行尾按文件实测**：`tokens.ts` / `themes.ts` 是 **LF**，
   `styleBible.tsx` / `BrowserStack.tsx` 是 **CRLF**。
   指挥窗口上一份工单写反了，被执行 agent 纠正。用 `read_bytes` 精确匹配写回。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— cv2 只装在 3.10，本项 `--ignore`
- **不要扩 schema。** 本项不实现 Director Agent，
  所以不需要任何新字段。若你认为需要，先写进设计，由指挥窗口裁定。
- **不要改任何场景的构图。** 那会改变已交付画面，超出"测量与守卫"范畴。

**本指令授权你修改**：新增 `docs/DIRECTOR_SCOPE_VERDICT.md`、
新增测试文件、以及为守卫所必需的**只读**辅助代码。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（推送由指挥窗口裁定）
- 交付时报告：
  - **7 键逐键三态结论 + 各自 grep**
  - **五段链路逐段现状**
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **三个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **写长文本在字节层操作**；**不要在 bash 双引号里写带反引号的 Python 代码**
  —— 指挥窗口刚因此产出四个 0 字节垃圾文件（shell 把反引号当命令替换）

---

## 六、队列

**跨阶段**：1.3 / 10.2（VLM Critic provider 抽象；
**已裁定标依赖、不合并、不重复建** —— 仓库至今无 `take_critic.py`）、
**P13** Scene Cache / 增量构建（`job_state.json` + hash 缓存，
"改一个 scene 不重跑全片"）、**P14** Render Worker / Fast Preview、
**P15** SR 路由、**P16**、**P17**、**P18**。

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** Repair Planner —— 仪器已建成（`chart_geometry.py` / `c6d7a5a`），
  修复器**故意未写**：已交付图表比值 **0.278**，无碰撞可修，
  而唯一能清碰撞的手段（缩短 labels）正是 11.2 禁掉的。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由
  "重新测量仍在碰撞"决定，而非计数器。
