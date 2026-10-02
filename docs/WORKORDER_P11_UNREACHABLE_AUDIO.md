# 执行指令 — 修复「静默失效」：不可达的 audio 与骗人的 motion.ease

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 本指令处理惰性字段审计里**最贵的两条**——它们不是"死字段"，是**误导性文档**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `9002573` |
| 基线 | `261 passed, 2 skipped` |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

`tokens.ts` sha256 应为 `6a89a5b4537794187e0ac2d8a0add9c7a0dc07a6135c337d4a225b9381bd9c3c`。

---

## 一、缺陷一：顶层 `audio` 永久不可达（**静默渲染静音**）

### 机制（指挥窗口已运行时验证，不是推断）

`studio/src/templates/finance-showcase/FinanceShowcaseWide.tsx:99` 读顶层字段并在 `:135` 渲染音频：

```tsx
const audio = (doc as unknown as { audio?: { src: string; volume?: number } }).audio;
...
{audio ? <Audio src={staticFile(audio.src)} volume={audio.volume ?? 0.9} /> : null}
```

**但 `ShowcaseSchema`（`studio/src/schemas/showcase-v1.ts:105-116`）从未声明 `audio`**，
且该 `z.object(...)` 没有 `.passthrough()`。运行时实测：

```
parse success: true
keys after parse: version,project,format,bpm,scenes
audio survived?: false
```

**zod 剥掉未知键 → `doc.audio` 恒为 undefined → 那个 `<Audio>` 分支永久不可达。**
今天谁写一份带 `"audio": {"src": "audio/bgm.m4a"}` 的图谱，会
**渲染静音、且 `safeParse` 返回 success**。没有任何报错。

### 三个已量的事实（决定修法）

1. **没有任何被跟踪的图谱设置顶层 `audio`**（指挥窗口遍历 `git ls-files` 下的 props/job/graph 类 JSON，零命中）。
2. **Python 侧不生成它**：`grep -rn "'audio'" pipeline/ studio/scripts/` 无生成点；
   `pipeline/schemas/showcase-v1.schema.json` 也**未声明** `audio`。
3. **但 QA 在检查它**：`studio/scripts/visual_qa.py:566` 的 `missing_asset` 规则读
   `props.get('audio')`、`props.get('audioEvents')`、`props.get('narration')`
   三个字段来核对资产是否存在 —— **这三个字段渲染器一个都收不到**
   （`narration` 属于另一个 schema `report-data.schema.json`，
   `audioEvents` 虽在 `showcase-v1.ts:101` 声明但**渲染源码零读取**）。

**所以 `missing_asset` 目前实际只能核对那四条硬编码 SFX 路径。**

### 你要做的（先判断，再动手）

**先判断这个音频分支应当存在还是应当删除**，并把判断依据写进代码注释。两种修法都可行：

- **接线**：在 `ShowcaseSchema` 声明 `audio`（z.object，src 必填 / volume 可选），
  让 `<Audio>` 真正可达。代价：新增一条 schema 字段 + 一条 parity 约束。
- **删除**：删掉那个不可达分支，因为没有任何生产者会生成它。
  代价：`visual_qa.py` 仍会检查 `props.audio`（无害但要一并清理或注释说明）。

**判断依据至少要覆盖**：有没有管线会生成它（实测：无）、
有没有图谱依赖它（实测：无）、QA 规则是不是在检查一个不可能存在的字段（实测：是）。

**不要两条都做**，也不要做成"声明了但仍然没人用"——那只是把一个静默失效
换成另一个静默失效。

---

## 二、缺陷二：`motion.ease` 在交付图谱里被设置，但渲染器从不读它

### 机制

- `showcase-v1.ts:64` 声明 `ease: z.string().optional()`
- **交付图谱主动设置它**：`pipeline/examples/showcase_demo.json` **2 次**、
  `studio/public/jobs/showcase_demo.json` **3 次**
- **渲染源码零读取图谱的 `motion.ease`**：`grep -rnE "motion\??\.ease|motion\[['\"]ease"`
  在 `studio/src/` 下**零命中**
- `common/primitives.tsx:183` 把 bezier **硬编码**：
  `cubicBezierEase(0.16, 1, 0.3, 1)`
- `design/tokens.ts:155-158` 的 `MOTION.profiles` 表里虽有 `ease` 键，
  但那是**内置默认值**，不是图谱的输入

**也就是说**：作者读那份交付图谱，有充分理由相信 `expo-out` 正在塑造那两个场景。它没有。**

### 你要做的（二选一，同样先判断再动手）

- **接线**：让渲染路径真正读 `motion.ease`（注意 `ease` 当前声明为 `z.string()`，
  而实际 bezier 是四个数字——**类型可能需要改**，改之前先确认调用点期望什么形状）。
- **清理**：从交付图谱里删掉那些设置，让图谱不再声称它有效。
  **注意 `studio/public/jobs/` 是 gitignore 的 staging 副本，不要动它**；
  只改 `pipeline/examples/showcase_demo.json`。

同样：**不要两条都做**，也不要接线成"读了但忽略"。

---

## 三、验证要求

### 1. 每处修改都要有守卫，且守卫要能失败

- 若接线 `audio`：加一条守卫证明**带顶层 `audio` 的图谱能通过 schema 且 `audio` 存活**。
  该守卫必须能红——把 schema 里 `audio` 删掉，它必须红。
- 若删除分支：加一条守卫证明**不存在读取未声明字段的代码**
  （否则删了分支，别处又写一遍同样的 `as unknown as`）。
- 无论哪种：加一条守卫覆盖 `motion.ease` 的选择，
  并证明它**不是"读了但忽略"**。

### 2. 变异测试

每条守卫做变异，**记录结果**。至少：

| 变异（以接线 audio 为例） | 期望 |
|---|---|
| 从 schema 删掉 `audio` 声明 | 守卫红 |
| 给 `audio` 加回 `.passthrough()` 之外的逃逸 | 守卫红 |

若你选择的是删除分支，把上表换成对应的变异。

**「变异存活」≠「变异无效」**：存活项要判定是真漏洞还是方向上无效的变异，
两种都写进 commit。**不要造 contrived 输入去杀无效变异。**

### 3. 必须用可证伪的证据

本指令的每条主张都附了 grep/运行时输出。你的结论也要附同样的东西。
**特别地**：断言"某字段没被读"时，要给出 grep 并注意同名诱饵
（`focus` 会匹配生命周期阶段名、`ease` 会匹配内置表键）——
本项目已因此把 `sizes`/`sizeBy`/`showArea` 误报成惰性。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `out/` 下任何证据目录；`DiagOutputDir`
- `studio/src/templates/finance-showcase/design/tokens.ts`
  —— 本轮 `SPACE.lg` 曾被测试污染过，保持只读

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 贴 `-rf` 原始输出，不贴结论句
- 交付时报告：**全量测试数字**、**逐条变异结果（含存活判定）**、
  **你对两处修法的判断及依据**、**`tokens.ts` sha256 比对**
- 有未提交工作时不要用 `git checkout -- <file>` 清污染（本项目已因此丢过一次工作）

---

## 六、队列

本项之后：

- **惰性字段的其余四条**（`scene.notes`、`scene.audioEvents`、`scene.transitionOut`、
  `camera.focus`）—— 交付图谱都没设，属 schema 里的空承诺，**可先记账不动**。
- **`content.chart.baseline`** —— 特殊：作者在 `content.baseline` 设了它才生效，
  而 `content.chart.baseline` 被静默丢弃；`charts_demo` c08 两处都设了。
  属于"同名字段放错层"的陷阱，值得单独一条。
- **`visual_qa.py` 的 `missing_asset` 规则** —— 它检查三个渲染器收不到的字段，
  与缺陷一同理清（你的修法会决定它要不要一并调整）。
- **P11 11.1 / 11.3** —— 解锁条件见 `docs/WORKORDER_P11_11_2_SURVIVORS.md` 第六节。
