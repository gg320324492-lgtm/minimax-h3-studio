# 执行指令 — 修「反向剥离」：四段被合并、被消费、却永远喂不进去

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 这是 P12 勘察（`a32f47b`）发现的**最严重缺陷**，也是本项目至今最隐蔽的一类失效：
> **`safeParse` 返回 `success=true`，值被静默丢弃，而消费方一直在读它的默认值。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `0da3c89`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `346 passed, 2 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

**开工前记录 sha256，收尾比对**（这几对镜像刚被校准过）：
- `studio/src/schemas/showcase-v1.ts` → 应为 `653313f45b3257700ebbeaf41fb27d3adb93676222fe884c2df3e05470f0aeb6`
- `pipeline/schemas/showcase-v1.schema.json` → 应为 `ab19cda2df48dee62591495a4f14621ed12aca2096b783671e1b0e23a7e168fe`
- `studio/src/templates/finance-showcase/design/tokens.ts` → 应为 `698fb0f5089f526c930ed176ba44920ac5aed1a0e5fd40a9ead340518e7867c5`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺陷机制

`studio/src/templates/finance-showcase/design/styleBible.tsx` 合并了**九个**段：

```
:70  typography ← b.typography        ✅ 在 7 键 schema 里
:71  spacing    ← b.spacing           ✅
:72  radius     ← b.radius            ❌ 不在
:73  depth      ← b.depth             ❌ 不在
:74  motion     ← b.motionLanguage    ✅
:75  camera     ← b.cameraLanguage    ✅
:97  palette    ← section('palette')  ✅
:98  shadow     ← section('shadow')   ❌ 不在
:99  depthCue   ← section('depthCue') ❌ 不在
```

`StyleBibleSchema` 只声明 **7** 个键（`showcase-v1.ts`）：
`palette / typography / spacing / cameraLanguage / motionLanguage / chartLanguage / audioLanguage`

**`radius` / `depth` / `shadow` / `depthCue` 四段不在其中。**

### 2. 指挥窗口独立 node 探针实测（关键证据）

在 `studio/` 下用 `npx tsx` 跑真实 `ShowcaseSchema.safeParse`：

```
control (palette only):  success=true   keysAfter=['palette']
radius:                  success=true   keysAfter=[]
shadow:                  success=true   keysAfter=[]
depthCue:                success=true   keysAfter=[]
depth:                   success=true   keysAfter=[]
```

**`success=true` 而值被剥掉。** 没有任何报错、没有警告。

### 3. 这不是无害的：其中三段有真实场景消费方

指挥窗口刚测（按 `useDesign()` 解构计，**不是词频**）：

| 段 | 场景消费方 | 证据 |
|---|---|---|
| `RADIUS` | **有，且多处** | `BrowserStack.tsx:72/:102/:138` 解构，`:159` `RADIUS.window * s` |
| `SHADOW` | **有** | `BrowserStack.tsx:72/:102` 解构，`:293` `SHADOW.floating` |
| `DEPTH_CUE` | **有** | `BrowserStack.tsx:219` 解构，`:293` `depthCueAt(DEPTH_CUE, i)` |
| `DEPTH` | **零消费** | 场景目录里 `DEPTH` 零命中 |

**所以四段的处境并不相同，这是修法的分界线。**

### 4. 为什么 `success=true` 而不是报错

`StyleBibleSchema` 是 `z.object({...})`，**没有 `.strict()`**，
所以 zod 的默认行为是**剥掉未知键**而非拒绝。

注意 `showcase-v1.ts` 里 `SceneSchema` 和 `ShowcaseSchema` **都有 `.strict()`**，
而 `StyleBibleSchema` 没有 —— 这个不一致本身可能是有意的（注释说
"对象袋子保持开放，严格性施加在图谱自身的词汇表上"），**你不要擅自改它**。

---

## 二、你要交付的三件事

### 第 1 件事：**逐段裁定**，写进 `docs/STYLE_BIBLE_STRIPPED_SECTIONS.md`

对四段**各给一个裁定**，并说明依据。判据只有两条：

- **这一段有没有真实消费方**（第 1 节第 3 条已给出初判，你要独立复核）
- **让它可被图谱设置，是不是一个好的接口决定**

三档裁定：

| 裁定 | 含义 | 动作 |
|---|---|---|
| **A：接进 schema** | 有消费方 + 图谱应当能控制它 | 两侧镜像各加一段 |
| **B：删掉合并** | 无消费方，或图谱不该控制它 | 删 `styleBible.tsx` 的合并行 + 相应导出 |
| **C：现状 + 标注** | 有消费方但**有意**不让图谱控制 | 保留合并，注释写明「这是 tokens 的运行时合并，不是图谱词汇」 |

**我的初判是：`radius`/`shadow`/`depthCue` 倾向 A 或 C，`depth` 倾向 B——
但这是初判，不是裁定。你若有异议，用证据说服我，不要顺着。**

> **特别提醒 `depthCue`**：它刚在 6.8（`7a12d2f`）被扩展成 5 层并**实测有效果**。
> 它现在**永远只能拿到 `themes.ts` 的默认值** —— 也就是说 6.8 的修复
> 在图谱层面是**不可达**的。这两条记录之间的关系要讲清楚。

### 第 2 件事：实施你裁定的结果

按裁定执行。**若你裁定 A，必须两侧镜像同步加**，并处理：

- `StyleBibleSchema`（zod）的类型 —— `radius` 是 `Record<string, number>`、
  `depthCue` 是 `readonly string[]`、另两个是 `Record<string, string>`。
  **它们与现有 7 键的 `z.record(z.string(), z.unknown())` 不是同一种形状**，
  这个不对称本身要说明。
- JSON Schema 侧 `definitions/StyleBible` 同步。
- **`tests/test_showcase_schema_parity.py` 必须仍然绿** —— 那是两侧镜像的守卫。

**若你裁定 B，删之前必须确认零消费方**（给 grep），
且要检查 `studio/src` 里是否有别的地方读那些导出。

**不要做「A 和 B 都做」**，也不要做成「加了字段但仍然没人能设」。

### 第 3 件事：给「被静默剥掉」这件事上一条守卫

**这是本项最重要的交付物。** 当前 `success=true` + 静默丢弃这个形态，
**没有任何守卫能发现**。P12 刚加的守卫管的是「图谱里出现的键必须有消费方」，
管不到「schema 漏声明了一段，而有人正在读它」。

请加守卫断言：

> **`styleBible.tsx` 合并的每一个段，要么在 `StyleBibleSchema` 里声明，
>  要么被显式标注为「有意不让图谱控制」。**

**判读要求**（本项目反复栽跟头的地方）：

- **不能**落成 `assert 'radius' in schema_text` 这种文本存在性断言。
  必须**解析** `StyleBibleSchema` 的键集合，与 `styleBible.tsx` 合并的行做差集。
- 守卫**必须能红**。至少两条变异，各贴 `-rf` 原始输出：

| 变异 | 期望 |
|---|---|
| 从 `styleBible.tsx` 再加一段合并（模拟"合并了但没声明"） | 守卫红 |
| 从 schema 删掉一个已声明且被消费的键 | 守卫红 |

- 若某变异存活，判定"真漏洞"还是"无效变异"，两种都写进 commit。
  **不要造 contrived 输入去杀无效变异。**

**额外要求**：请在守卫的 docstring 里写明这个失效形态
（`success=true` + 静默剥掉 + 消费方读默认值）与 P11 `audio` 缺陷的关系
—— **两者方向相反**：P11 是"声明了但没人读"，本项是"有人读但喂不进去"。
把这个对照写清楚，它比守卫本身更有价值。

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
   **看到红的理由不对，先查现场再下结论。**
4. **每条毒变异之后从快照复原源文件，收尾核对三个 sha256。**
5. **行尾按文件实测**：`tokens.ts` / `themes.ts` / `showcase-v1.ts` 是 **LF**，
   `styleBible.tsx` / `BrowserStack.tsx` 是 **CRLF**。用 `read_bytes` 精确匹配写回。
6. **写长文本在字节层操作**；**不要在 bash 双引号里写带反引号的 Python 代码**
   —— 指挥窗口刚因此产出四个 0 字节垃圾文件。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— cv2 只装在 3.10，本项 `--ignore`
- **不要给 `StyleBibleSchema` 加 `.strict()`** —— 那是上游有意的设计，
  改了会让「图谱没设的键」从"忽略"变成"报错"，超出本项范围。
  **但若你认为它该改，写进报告，由指挥窗口裁定。**
- **不要改任何场景的构图**，不要改 `tokens.ts` 的值。

**本指令授权你修改**：`design/styleBible.tsx`、`schemas/showcase-v1.ts`、
`pipeline/schemas/showcase-v1.schema.json`、新增测试与文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（推送由指挥窗口裁定）
- 交付时报告：
  - **四段逐段裁定 + 依据**（最重要）
  - **`depthCue` 与 6.8 那条修复的关系**（6.8 的成果在图谱层是否可达）
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **三个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多** —— 前几轮的执行 agent 做到过这点，
  那是本项目最有价值的工作记录之一。

---

## 六、队列

**跨阶段**：1.3 / 10.2（VLM Critic provider 抽象；
**已裁定标依赖、不合并、不重复建** —— 仓库至今无 `take_critic.py`）、
**P13** Scene Cache / 增量构建（实测零实现；`render.mjs:57` 每次
`mkdtempSync` 建新 bundle，改一个 scene 要重跑全片）、
**P14** Render Worker / Fast Preview、**P15** SR 路由、**P16**–**P18**。

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** Repair Planner —— 仪器已建成（`chart_geometry.py` / `c6d7a5a`），
  修复器**故意未写**：已交付图表比值 **0.278**，无碰撞可修，
  而唯一能清碰撞的手段（缩短 labels）正是 11.2 禁掉的。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由
  "重新测量仍在碰撞"决定，而非计数器。
