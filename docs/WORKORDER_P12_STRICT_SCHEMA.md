# 执行指令 — 给 `StyleBibleSchema` 加 `.strict()`：把「静默剥离」这一族从根上关掉

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `80d2021`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `355 passed, 2 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

**开工前记录 sha256，收尾比对**：
- `studio/src/schemas/showcase-v1.ts`
- `pipeline/schemas/showcase-v1.schema.json`
- `studio/src/templates/finance-showcase/design/styleBible.tsx`
- `studio/src/templates/finance-showcase/design/tokens.ts`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 上一项刚闭合的缺陷

`836f532` 修掉了「合并了但未声明 → `success=true` 静默剥掉」：
`radius` / `shadow` / `depthCue` 三段已接进 schema，`depth` 按裁定删掉合并。
守卫 `tests/test_style_bible_merges_only_declared.py` 双向把关。

### 2. **但根没动：`StyleBibleSchema` 仍然没有 `.strict()`**

`studio/src/schemas/showcase-v1.ts` 里：

- `SceneSchema` **有** `.strict()`
- `ShowcaseSchema` **有** `.strict()`
- **`StyleBibleSchema` 没有** → zod 默认**剥掉未知键**而非拒绝

**这正是上一项那个失效形态的温床**：只要 schema 是开放的，
「合并了一段 → 图谱设了它 → 被静默剥掉 → 消费方读默认值」这条链随时可以再次发生，
而上一项的守卫只能抓「合并了但未声明」，**抓不到「声明了但又被某个中间层剥掉」**。

### 3. 上一项 agent 提请裁定，并说这是破坏性变更 —— **指挥窗口实测推翻了这一点**

它的原话是：加 `.strict()`「会把现有写 `depth` 的图谱从静默无效变成硬报错，属破坏性变更」。

**指挥窗口实测（19 份图谱全扫）**：

```
scanned graphs: 19
undeclared keys that would become hard errors: (零)
```

`pipeline/**` 与 `studio/public/**` 全部 JSON 里，
**没有任何一处 `style_bible` 含未声明键**。
**所以加 `.strict()` 今天不会破坏任何现存图谱。**

**但"今天不破坏"不等于"永远不破坏"** —— 这正是 `.strict()` 的价值：
把「静默失效」提前到**编写时**变成一次明确的报错。
请在文档里把这个区别写清楚，而不是只说"没有现存破坏"。

---

## 二、你要交付的三件事

### 第 1 件事：先复核，再动手

**独立复现第 3 条那个测量**（不要采信我的数字），并把范围查全：

- `pipeline/**` 与 `studio/public/**` 的**全部** JSON
- `tests/**` 里的**测试夹具**图谱（这些最容易在加 `.strict()` 后转红）
- `studio/bin/` 的渲染示例 / `pipeline/examples/`

若你发现任何一处会转红的，**停下并上报**，不要自行决定它的命运。

### 第 2 件事：加 `.strict()`，两侧镜像同步

**zod 侧**：`StyleBibleSchema` 加 `.strict()`。

**JSON Schema 侧**：`definitions/StyleBible` 加 `"additionalProperties": false`。

⚠️ **两侧镜像必须同时改** —— `tests/test_showcase_schema_parity.py` 是守卫，
它会红。而本项目有过一次教训：**Python `jsonschema` 不解析 `$ref`，
用错工具会得到相反的结论**（上一轮指挥窗口实测踩过）。
验证编译请用 **Ajv 并加载该文件自己声明的 dialect**
（`showcase-v1.schema.json` 声明的是 draft-07）。

**同时要处理的不对称**：现有 7 键全是 `z.record(z.string(), z.unknown()).optional()`，
而新加的 `depthCue` 是 `z.array(z.string()).optional()`。
**`.strict()` 只管顶层键，不管 record 内部** —— 所以
「`radius` 里有 `card` 就合法」这件事不受影响。
请确认这一点，并在文档里写明 `.strict()` 关掉了什么、**没**关掉什么。

### 第 3 件事：给「开放 schema 会静默剥离」上一条守卫

**这是本项最重要的交付物。** 上一项的守卫抓「合并了但未声明」，
**抓不到「schema 是开放的，于是某个未声明键悄悄消失」**。

请加守卫断言：

> **`StyleBibleSchema` 是严格的** —— 喂一个未声明的键必须**报错**，
> 而不是 `success=true` 且键消失。

**判读要求**：

- 必须**真的调 `safeParse`** 并断言返回值，**不能**断言源码里出现 `.strict()` 字符串
  —— 那是文本存在性断言，本项目已被骗过五次
  （`mkdtemp` 匹配到解释 bug 的注释 / `rmSync` 被预先存在的调用满足 /
  两个词构成的说明删掉后仍通过 / `'depth' not in schema_text` 被 `depthCue` 子串触发 /
  P12 守卫第一版读了自己的被测对象）。
- **同时断言"报错时给出的是有用的信息"**（能指认是哪个键），
  否则作者只知道"schema 错了"，不知道错在哪。

**至少两条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 从 `StyleBibleSchema` 去掉 `.strict()` | 守卫红 |
| 给 `StyleBibleSchema` 加 `.passthrough()`（另一种"接受未知键"） | 守卫红 |

第二条特别重要：**`.passthrough()` 和不加 `.strict()` 都会让未知键存活，
但形态不同**（一个保留、一个剥掉）—— 守卫必须能同时抓住这两个变体。
若它只抓得住一个，如实报出来。

**docstring 里要写明这个失效家族的全貌**：
P11 `audio`（声明了但没人读）、`836f532` 的四段（有人读但喂不进去）、
本项要关的根（schema 开放 → 静默剥离 → 两者都会发生）。
**三者是同一个温床的三种病。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
   **看到红的理由不对，先查现场再下结论。**
4. **每条毒变异之后从快照复原源文件，收尾核对四个 sha256。**
5. **行尾按文件实测**：上一项实测 `showcase-v1.ts` 是 **CRLF**（339 CRLF / 0 裸 LF），
   `tokens.ts` / `themes.ts` 是 LF，`styleBible.tsx` / `BrowserStack.tsx` 是 CRLF。
   **不要相信任何人的行尾断言，包括本工单的** —— 自己测一遍。
6. **写长文本在字节层操作**；**不要在 bash 双引号里写带反引号的 Python 代码**
   —— 指挥窗口刚因此产出四个 0 字节垃圾文件。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— cv2 只装在 3.10，本项 `--ignore`
- **不要给 `SceneSchema` / `ShowcaseSchema` 改任何东西** —— 它们已有 `.strict()`
- **不要碰 `chartLanguage` / `audioLanguage`** —— 它们是 P11 方向（声明了但没人读），
  修法不同（删声明还是接线消费方），不在本项范围
- **不要改任何场景构图**，不要改 `tokens.ts` 的值

**本指令授权你修改**：`schemas/showcase-v1.ts`、
`pipeline/schemas/showcase-v1.schema.json`、新增测试与文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（推送由指挥窗口裁定）
- 交付时报告：
  - **第 1 条那个测量的独立复现结果 + 你的查全范围**
  - **`.strict()` 关掉了什么、没关掉什么**
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **四个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**跨阶段**：1.3 / 10.2（VLM Critic provider 抽象；
**已裁定标依赖、不合并、不重复建** —— 仓库至今无 `take_critic.py`）、
**P13** Scene Cache / 增量构建（实测零实现；`render.mjs:57` 每次
`mkdtempSync` 建新 bundle —— 该文件注释记录过一次严重事故：
**bundle 从不删除，118 个副本把 C: TEMP 填到 46 GB**；
且 `bin/` 下**没有 scene 级渲染入口**，13.2 连入口都不存在）、
**P14** Render Worker / Fast Preview、**P15** SR 路由、**P16**–**P18**。

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** Repair Planner —— 仪器已建成（`chart_geometry.py` / `c6d7a5a`），
  修复器**故意未写**：已交付图表比值 **0.278**，无碰撞可修。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由
  "重新测量仍在碰撞"决定，而非计数器。
