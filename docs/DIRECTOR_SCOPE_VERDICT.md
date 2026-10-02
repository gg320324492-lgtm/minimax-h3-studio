# P12 Director Agent — 范围裁定：先证明哪一段值得建

> 执行 agent 交付。工单：`docs/WORKORDER_P12_DIRECTOR_BOUNDARY.md`，基线 `e71cb56`。
> 本文件是**测量记录**，不是放行/退回裁定。是否实现由指挥窗口与用户决定。
> **本项没有实现 Director Agent，一行生产代码都没有改。**

---

## 摘要（先看这一段）

1. **交付图谱实际只设了 1 个 `style_bible` 键，不是工单写的 4 个。**
   `pipeline/examples/showcase_demo.json` 只设 `typography`；另 3 个键
   （`palette` / `motionLanguage` / `cameraLanguage`）在 **`7bef0a8` 已被删掉**。
   工单的 "4 键" 数字来自 `studio/public/jobs/showcase_demo.json`——
   一个 **gitignore 的 staging 副本**（`.gitignore:26`）。详见 §4.1。

2. **7 键里 5 键有消费方，2 键是纯哑声明。**
   `chartLanguage` 与 `audioLanguage` 被两侧 schema 声明、被 resolver 零提及。
   Director 若照 schema 生成，**每次都会生成这 2 个没人读的键**。

3. **发现一处比工单所问更严重的反向缺陷（工单未预见）。**
   `styleBible.tsx` 合并了 `radius` / `shadow` / `depth` / `depthCue` **四段**，
   场景也确实消费了对应的 `useDesign()` 导出——**但这四个键不在 7 键 schema 里**，
   zod 在 parse 时把它们**静默剥掉**。这是"看起来接好了，却无法被喂"的哑声明，
   与 P11 的 `audio` 缺陷同构、方向相反。详见 §2.2。

4. **结论：五段里现在值得建的是 0 段。**
   不是保守，是逐段算出来的（§3.1）。**本项交付的是测量记录 + 一条已实测能红的守卫，
   不是 Director Agent。**

---

## 一、7 键逐键三态结论

判读方式不是文本存在性断言，而是一条**四段链**（实现见
`tests/style_bible_consumption.py`）：

```
图谱键 --[1. StyleBibleSchema 声明]--> 活过 zod parse
       --[2. resolveStyleBible 合并 b.<key>]--> 进入 StyleBible
       --[3. useDesign() 重新发布该字段]--> 进入场景可见范围
       --[4. 生产 .tsx 从 useDesign() 解构该导出]--> 驱动渲染决策
```

四段全成立才算 `reachable`。**任一段断开 = 哑声明。**

> 第 1 段是最容易被忘掉的、也最关键的一段：`StyleBibleSchema` 是
> **没有 `.strict()` 的开放 `z.object`**（`showcase-v1.ts:169-177`），
> 未声明的键被**剥掉而不是报错**。

### 1.1 逐键结论表

| 键 | 1 声明 | 2 resolver | 3 导出 | 4 场景消费 | 三态结论 |
|---|---|---|---|---|---|
| `palette` | ✅ | ✅ `s.palette` | ✅ `PALETTE` | ✅ 12 处 | **间接读（直接可达）** |
| `typography` | ✅ | ✅ `s.typography` | ✅ `TYPE` | ✅ 5 处 | **间接读（直接可达）** |
| `spacing` | ✅ | ✅ `s.spacing` | ✅ `SPACE` | ✅ 5 处 | **间接读（直接可达）** |
| `cameraLanguage` | ✅ | ✅ `b.cameraLanguage` | ✅ `camera` | ⚠️ **仅 1 处** | **间接读（真实但单点）** |
| `motionLanguage` | ✅ | ✅ `b.motionLanguage` | ✅ `MOTION` | ✅ 6 处 | **间接读（直接可达）** |
| `chartLanguage` | ✅ | ❌ **零提及** | — | — | **零消费** |
| `audioLanguage` | ✅ | ❌ **零提及** | — | — | **零消费** |

**没有一个键是"直接读 `b.<key>`"的**——全部走 `useDesign()` 间接层。
这正是工单第 4 条提醒的陷阱：`styleBible.tsx` 把整个 bible 展开导出，
零 grep 命中 ≠ 死字段。

### 1.2 每格的 grep（可复现）

检索范围**只取源码目录**（`pipeline/` + `studio/`）。全仓版会命中本文件自己与
`tests/`，那些是本项的产物与散文，不是消费方——把它们算进去会虚增命中数。

```bash
# 两个哑声明键，在源码目录穷举
grep -rn "chartLanguage\|audioLanguage" pipeline/ studio/ \
  --include=*.ts --include=*.tsx --include=*.py --include=*.json \
  | grep -v node_modules | grep -v 'studio/public/jobs'
```

实测输出（**穷举，共 4 行，全部是声明侧**）：

```
pipeline/schemas/showcase-v1.schema.json:256:        "chartLanguage": {
studio/src/schemas/showcase-v1.ts:175:  chartLanguage: z.record(z.string(), z.unknown()).optional(),
pipeline/schemas/showcase-v1.schema.json:259:        "audioLanguage": {
studio/src/schemas/showcase-v1.ts:176:  audioLanguage: z.record(z.string(), z.unknown()).optional(),
```

**→ 在全部生产源码里，这两键的命中只有 schema 声明本身。**
不是"没找到消费方"，是**穷举后确认零消费方**。

（若按全仓 `--include=*.md` 检索，还会命中 `docs/UPGRADE_PROGRESS.md:490`、
本工单与本文件——**全部是散文**，同样不构成消费方。
`UPGRADE_PROGRESS.md:490` 本身就写着「约束的是一个渲染路径从未读取的字段」。）

### 1.3 同名诱饵已排除（工单点名要求）

| 诱饵 | 命中情况 | 处置 |
|---|---|---|
| `focus` 匹配生命周期阶段名 | 本项 7 键不含 `focus`，但 `useDesign()` 导出里也没有 `focus` | 无 |
| `spacing` 匹配 CSS 属性 | 渲染源码里 `spacing` 共 13 处命中，**全部是散文注释**（`projection.check.ts:84` "spacing is the authored spacing"、`tokens.ts:242` 等），无一是读 `b.spacing` | 靠第 2 段链（`b.spacing`）判定，不靠词频 |
| `palette` 匹配 `PALETTE` 常量 | `PALETTE` 是 `tokens.ts:28` 的静态常量导出，`studio/src` 共 1187 处命中 | **靠第 3+4 段链判定**：必须经 `useDesign()` 解构才算数 |

**关键反例（本项实测踩到，值得记下）**：如果只看"词是否出现"，
`cameraLanguage` 会被判成有 **6 个**消费方——因为 `<CameraRig camera={scene.camera} .../>`
 prop** 与 `useDesign()` 导出的 `camera` **同名**。
真实消费方只有 **`CameraRig.tsx:149` 一处**：

```
common/CameraRig.tsx:149:  const {camera: cameraDefaults} = useDesign();
common/CameraRig.tsx:151:    camera?.perspective ? camera : {...camera, perspective: cameraDefaults.perspective},
```

所以第 4 段链**必须**匹配"从 `useDesign()` 解构"，而不是"词出现过"。
这是守卫第一版真实犯的错，已记进 `style_bible_consumption.py` 的注释里。

### 1.4 `cameraLanguage` 是"真实但单点"——必须单独点名

`cameraLanguage` 表面上 `reachable`，但它的唯一消费方只读了**一个子键**：

```
CameraRig.tsx:151   perspective: cameraDefaults.perspective
```

`camera` 字段的另一半 `durationSeconds`（`styleBible.tsx:76` 默认值来自
`MOTION.premiumCameraSeconds`）**全仓零消费**：

```bash
grep -rn "durationSeconds" studio/src pipeline --include=*.ts --include=*.tsx --include=*.py
```
```
common/primitives.tsx:25,37,45,97,100,108   ← 这些是 props，不是 bible
design/styleBible.tsx:33,76                 ← 声明与默认值
```

**→ 图谱可以设 `cameraLanguage.durationSeconds`，画面不会有任何变化。**
这是子键粒度的哑声明，与 §1.1 的键粒度哑声明是**不同**的一层，
且**目前没有任何守卫覆盖**（见 §5.3）。

---

## 二、五段链路逐段现状

`docs/UPGRADE_MASTER_PLAN.md:137`：
`Brief→StyleBible→Storyboard→SceneGraph→AssetPlan`

### 2.1 逐段表

| 段 | 现状 | 检索证据 |
|---|---|---|
| **Brief** | **零实现** | `grep -rn "brief\|Brief" --include=*.py pipeline/ studio/scripts/ tests/` → **0 命中** |
| **StyleBible** | **已存在（解析侧），生成侧零实现** | `styleBible.tsx` 90-102 行 `resolveStyleBible` 完整；但无任何生成器 |
| **Storyboard** | **零实现** | `grep -rn "storyboard\|Storyboard" --include=*.py ...` → **0 命中** |
| **SceneGraph** | **已存在** | `pipeline/scene_graph.py`（`load`/`schema`/`beat_aligned_durations`/`main`），`a55d03d` 刚改成读 JSON Schema |
| **AssetPlan** | **半成品（死头）** | `visual_qa.py::rule_missing_asset` 只剩 4 条硬编码 SFX 路径 |

补充检索（Python 侧，`pipeline/ studio/scripts/ tests/`）：

```
storyboard : 0      assetplan : 0      brief : 0
```

`director` 的命中需要**拆开数**才有意义（工单点名的同名诱饵，实测全中）：

```bash
grep -rno "director[a-z]*" --include=*.py pipeline/ studio/scripts/ tests/ \
  | awk -F: '{print $NF}' | sort | uniq -c
```
```
      1 director        ← 全仓唯一的真 director，是一句散文
      2 directories
     39 directory
```

```bash
grep -rnw "director" --include=*.py pipeline/ studio/scripts/ tests/
```
```
pipeline/shotspec.py:3:  A ShotSpec is what a director (human or agent) authors. It never contains
```

**40 处命中里，39 处是 `directory`、1 处是散文。零实现。**
（教训：这个诱饵连"数一遍 `director` 有多少命中"都骗得过——
必须按词形拆开数，`grep -c director` 给出的 40 极具误导性。）

`pipeline/` 实有模块只有 4 个：`shotspec.py` / `prompt_compiler.py` /
`scene_graph.py` / `migrate_shotspecs.py`——与指挥窗口实测一致。
**无 `take_critic.py`**（已裁定标依赖，不合并不重复建）。

### 2.2 顺带发现：resolver 里有 4 段**图谱永远喂不进去**

这是本项测出的、比工单所问更严重的一处：

| resolver 合并的段 | `StyleBibleSchema` 声明？ | 场景消费？ | 图谱能否送达 |
|---|---|---|---|
| `radius` | ❌ | ✅ `RADIUS` 4 处解构 | ❌ **zod 剥掉** |
| `shadow` | ❌ | ✅ `SHADOW` 5 处解构 | ❌ **zod 剥掉** |
| `depth` | ❌ | ✅ `DEPTH` 0 处 | ❌ **zod 剥掉** |
| `depthCue` | ❌ | ✅ `DEPTH_CUE` 1 处（`BrowserStack.tsx:293`） | ❌ **zod 剥掉** |

运行时实测（`npx tsx` 探针，非文本推断）：

```
parse ok: true
bible keys surviving parse: []
resolveStyleBible(RAW input)    RADIUS.card = 99   depthCue = ["A","B","C","D"]
resolveStyleBible(PARSED doc)   RADIUS.card = 20   depthCue = ["0 14px 40px rgba(0,0,0,0.40)", ...]
```

**raw 输入能改 `RADIUS.card=99`；经过 `ShowcaseSchema.parse` 后回到默认 `20`。**
`FinanceShowcaseWide.tsx:143` 走的正是 `parsed.data` 这一路，
所以生产路径上这四段**永远是主题默认值**。

**性质**：这是 P11 `audio` 缺陷**转 90°** 的镜像——不是"读了不可能发生的值"，
而是"读到了却不可能被喂进去的值"。图谱作者看不到任何错误，
渲染器看到的却是一个被填好的对象。**两端都不可见。**

**⚠️ 本项不修它**（工单第四节：不扩 schema、不改构图）。已写成断言
`test_the_resolver_merges_four_sections_no_graph_can_reach`，谁动它谁会看见。

---

## 三、结论与依据

### 3.1 哪一段**现在建了就有用**？

**0 段。**

这不是保守，是逐段算出来的：

- **Brief** — 零实现。但 Brief 的产物是什么？本项没测出任何消费方。
  建它 = 生成一份没人读的东西，正是工单要防的失败模式。
- **StyleBible** — **建了立刻产生哑声明**（见 §3.2）。
- **Storyboard** — 零实现，且零消费方证据。
- **SceneGraph** — **已经存在**。`scene_graph.py` 是校验侧，Director 该做的是
  生成侧；生成侧需要先有可生成的规范，而 §1 证明规范本身有问题。
- **AssetPlan** — **死头**。`rule_missing_asset` 只剩 4 条硬编码 SFX；
  它原先读的 `props.audio`/`audioEvents`/`narration` 渲染器一个都收不到
  （我复核了 `visual_qa.py::rule_missing_asset` 的 docstring 与实现，
  **已按 P11 收敛为只查 4 条硬编码**，见 §4.2）。
  **在图谱侧打通音频之前建 AssetPlan，等于给一个读不到东西的规则再加一层。**

### 3.2 哪一段建了会**立刻产生哑声明**？

**StyleBible 段——而且是 100% 会。**

照着 7 键 schema 自动生成，`chartLanguage` 与 `audioLanguage`
**必然**被生成（它们是声明的一部分），而这两键**没有任何消费方**。
`7bef0a8` 已经实测过一次这个失败：那份图谱声明了 **15 个键，
只有 1 个生效**。工单的"哑声明审计结论"在 §1 得到了第二次独立确认。

**更精确地说，哑声明有三层，粒度不同：**

| 层 | 数量 | 触发条件 |
|---|---|---|
| **键粒度** | 2 键（`chartLanguage`/`audioLanguage`） | 只要照 schema 生成就必然发生 |
| **段粒度** | 4 段（`radius`/`shadow`/`depth`/`depthCue`） | 只要图谱想改主题表面/景深，**改了必然无效** |
| **子键粒度** | 至少 `cameraLanguage.durationSeconds` | 该段只有 `perspective` 被读 |

**子键粒度是本项新识别的一层**，工单未提及，也**尚无守卫**——
现有守卫都是键粒度的。这是 Director Agent 设计的硬约束：
**"消费方已证明存在"必须做到子键粒度，否则生成的仍是哑声明。**

### 3.3 哪一段应当**等上游**？等什么？

| 段 | 等什么 | 判据 |
|---|---|---|
| **AssetPlan** | 等**音频在图谱里可达**。`audioLanguage` 要么被消费要么被删；顶层 `audio` 要么被 schema 声明并加消费方，要么维持不可达 | `audioLanguage` 目前与 6.7 查清的"顶层 `audio` 永久不可达"**同源**（工单已预警，实测确认：`ShowcaseSchema` 无 `audio`，`narration` 属另一个 schema） |
| **Storyboard** | 等**SceneGraph 生成侧规范**。`scene_graph.py` 是校验器；生成器要先知道"生成什么才不被校验拒绝" | 而这依赖 §1 的结论：规范里 2/7 键是哑的 |
| **Brief** | 等**下游任一段有可验证的输出契约**。没有消费方的上游段不值得建 | 本项未测出任何 Brief 消费方 |
| **StyleBible** | 等**消费方先补齐或键先删除**，再谈生成 | 见 §3.2 |

**一句话结论**：**Director Agent 现在不该建。**
五段里 3 段零实现且零消费方证据、1 段已存在、1 段是死头；
唯一"已存在"的那段（SceneGraph）恰好是**校验**侧，而它校验的规范里有哑声明。

**⚠️ 本项不修它**（工单第四节：不扩 schema、不改构图）。已写成断言

---

## 四、与工单实测事实的两处出入（如实记录）

### 4.1 "交付图谱设过 4 键" → 实测 **1 键**

| 来源 | `style_bible` 键 | 是否入库 |
|---|---|---|
| `pipeline/examples/showcase_demo.json` | **`typography`（仅 1 个）** | ✅ git 跟踪 |
| `studio/public/jobs/showcase_demo.json` | `cameraLanguage` `motionLanguage` `palette` `typography` | ❌ **gitignore（`.gitignore:26`）** |

查证：`git log -p -- pipeline/examples/showcase_demo.json` 显示
`7bef0a8 "P6.5-6.8: a light theme that is actually light, and a graph that is actually wired"`
**删除了那 3 个键**，commit message 原文：

> "The demo graph's style_bible declared 15 keys and exactly ONE took effect."

即：**工单说的"4 键"是 `7bef0a8` 之前的旧状态**，
而那 3 个键被删掉**正是因为它们是惰性的**。
`studio/public/jobs/` 下那份是**上次 staging 的残留副本**（gitignore 的 scratch），
**不是交付物**。

**这个出入有操作后果**：如果照"4 键"去设计 Director，
会以为 `palette`/`motionLanguage`/`cameraLanguage` 已有成功先例可循——
**而那三个"先例"恰恰是被判为无效而删掉的**。

### 4.2 "视觉 QA 仍读 3 个不可达字段" → 实测**已收敛**

工单 §1.2 说 `visual_qa.py` 的 `missing_asset` **仍在读**
`props.audio` / `audioEvents` / `narration`。实测：该函数已按 P11 收敛，
docstring 明写收敛理由，实现里 `declared` **仅剩 4 条硬编码 SFX**。
`tests/test_undeclared_field_reads.py:281` 有守卫锁住这一点。
**AssetPlan 是死头的结论不变**，但"仍在读"的描述已过期。

---

## 五、交付物

### 5.1 新增：`tests/style_bible_consumption.py`（只读辅助）

四段链的推导器，纯 Python + 正则，**不依赖 node**（沿用
`test_undeclared_field_reads.py` 的理由：需要 node 运行时才能失败的守卫价值更低）。

两个刻意的设计决定，都是被本项目自己的坑逼出来的：

1. **排除 `styleBible.tsx` 自身。** resolver **定义**了全部 9 个导出，
   所以它**命名**了全部 9 个；把它算作消费方会让每个键在"刚绑定"时就显示可达
   ——**守卫读自己的被测对象**。这是本文件第一版的真实 bug。
2. **消费方判定限定"从 `useDesign()` 解构"**，而不是"词出现过"。
   理由见 §1.3 的 `camera` 同名 prop 陷阱。

### 5.2 新增：`tests/test_style_bible_no_dumb_declarations.py`（12 个测试）

- 前提锚定：`StyleBibleSchema` 是开放的（非 `.strict()`）
- **反空转**：`useDesign()` 解构索引非空且含 `PALETTE`/`TYPE`/`MOTION`/`SPACE`
- 7 键逐键状态断言（含 2 个哑声明键的名字，**不只断言数量**）
- `resolver_sections_outside_the_schema()` 断言（§2.2 的四段）
- **主守卫**：交付图谱里每个 `style_bible` 键都必须有渲染侧消费方
- 3 个变异 + 1 个 node 运行时探针

### 5.3 已知未覆盖（留给裁决，不在本项授权内）

- **子键粒度哑声明**（§3.2 第三层）：守卫只到键粒度。
  `mergeSection` 会静默丢弃类型不匹配的子键，`cameraLanguage.durationSeconds`
  是已测得的实例。**加这一层需要扩守卫到子键，且要先定"值类型契约"。**
- **`radius`/`shadow`/`depth`/`depthCue` 四段不可达**（§2.2）：
  修法二选一——**声明它们**（扩 schema，工单明令禁止）或**删掉 resolver 里的合并**
  （会改主题行为）。**两者都不在本项授权内。**

---

## 六、第 2 件事：最小设计（**只设计，未实现**）

工单允许的结论之一是"没有任何一段现在值得建"。**实测结论正是如此**，
所以本节交付的是**"等上游"清单（§3.3）+ 一旦上游就位时的最小骨架**，
而不是某个现在就该建的模块。

### 6.1 一旦上游消费方就位，Director StyleBible 生成器的最小形态

**它必须是"消费方约束下的生成"，不是"schema 填充"。**
这是本项唯一的硬结论，也是 §3.2 的直接推论。

```python
# 建议路径（未创建）: pipeline/director/style_bible.py
def generate_style_bible(brief: dict, *, allowed: dict[str, set[str]]) -> dict:
    """只输出 `allowed` 证明存在消费方的键。

    输入
      brief:      上游 Brief 段产物（本项未测出消费方，暂定 {}）
      allowed:    键 -> 该键下**已被消费方读取的子键**集合，
                  由 style_bible_consumption 推导，不接受硬编码列表

    输出
      只含 `allowed` 覆盖的键；未覆盖的意图**不静默丢弃**，
      而是返回到 `unapplied` 里，由调用方决定是报错还是留档。

    返回类型
      {'style_bible': dict, 'unapplied': list[(path, reason)]}
    """
```

**三个不可协商的点：**

1. **消费方清单必须由 `tests/style_bible_consumption.py` 推导**，
   不接受手写。手写清单就是下一次惰性字段审计的起点。
2. **`unapplied` 必须显式返回**。静默丢弃 = 把哑声明换个地方生成。
3. **子键粒度必须带**（§3.2 第三层）。键粒度的 `allowed` 挡不住
   `cameraLanguage.durationSeconds`。

**消费哪些已有产物**（这三条是现成的）：

- `scene_graph.py::load` / `schema()` — 读 `showcase-v1`，拿到 scene 列表与类型
- `scene_graph.py::beat_aligned_durations` — 时长是 beat 对齐的，
  **不是自由值**；生成器若自造时长会与 §1.2 的 `41947f6` 撞上
- `shotspec.py::ShotSpec` / `validate_atomic` — 镜头文本的原子性校验

**守卫怎么写，且必须能红**（本项已交付三条实测有效的）：

| 变异 | 期望 | 实测 |
|---|---|---|
| 图谱加 `ghostKey` | 红 | ✅ 红 |
| 删掉渲染侧消费方 | 红 | ✅ 红（3 条） |
| 改 `useDesign()` 导出名 | 红 | ✅ 红 |

**尚未设计**：生成器产出后的**值类型校验**。
`mergeSection` 的类型守卫会静默丢弃类型不符的值——**这是"声明了但没生效"的
另一种形态，且比哑声明更难查**（因为键是对的、值被丢了）。
要设计它，需要先定 `typography` 等键的**值 schema**，那是扩 schema，需裁决。

---

## 七、变异记录（`-rf` 原始输出）

三次毒变异，每次**先 assert 变异落地**（本项目发生过两次"变异没落地却读了结果"），
每次从快照复原并核对 sha256。

### 变异 A：在图谱 `style_bible` 里加零消费键 `ghostKey`

落地断言：`b'"ghostKey"' in after` → `MUTATION LANDED at byte offset 3672`

```
E       AssertionError: a delivered graph declares a style_bible key with no render-side consumer:
E           showcase_demo.json sets style_bible.ghostKey -> no-declaration. The graph validates and renders unchanged.
E       assert not ['showcase_demo.json sets style_bible.ghostKey -> no-declaration. The graph validates and renders unchanged.']

E:\Minimax-H3\tests\test_style_bible_no_dumb_declarations.py:217: AssertionError
=========================== short test summary info ===========================
FAILED test_style_bible_no_dumb_declarations.py::test_no_delivered_graph_declares_a_key_nothing_reads
FAILED test_style_bible_no_dumb_declarations.py::test_the_one_key_the_demo_graph_sets_is_reachable
2 failed, 344 passed, 2 skipped in 46.39s
```

**红的理由已核对**：主守卫红在 `ghostKey -> no-declaration`（**对的理由**）；
第 2 条红在计数 pin（预期内，是 pin 在起作用）。
**无一条红在无关的几何/音频断言上。**

**存活判定**：无变异存活。两条红均属"真漏洞捕获"。

### 变异 B：删除渲染侧消费方（`CameraRig.tsx` 的 `useDesign()` 解构）

落地断言：`assert needle not in after` + 字节数差 49 → `MUTATION LANDED; removed 49 bytes`

```
E       AssertionError: assert 'resolver-bound-but-unused' == 'reachable'
E         
E         - reachable
E         + resolver-bound-but-unused
E:\Minimax-H3\tests\test_style_bible_no_dumb_declarations.py:272: AssertionError
=========================== short test summary info ===========================
FAILED test_style_bible_no_dumb_declarations.py::test_reachability_of_every_declared_key
FAILED test_style_bible_no_dumb_declarations.py::test_the_two_unconsumed_keys_are_dumb_declarations_today
FAILED test_style_bible_no_dumb_declarations.py::test_mutation_deleting_a_render_side_consumer_is_caught
3 failed, 343 passed, 2 skipped in 44.32s
```

**红的理由已逐条核对**（工单第三节第 3 条）：

```
E       AssertionError: {'audioLangua...achable', ...} == {'palette': '...achable', ...}
E       Differing items:
E         {'cameraLanguage': 'resolver-bound-but-unused'} != {'cameraLanguage': 'reachable'}
```

```
E       AssertionError: assert {'audioLangua...lver-binding'} == {'chartLangua...lver-binding'}
E         Left contains 1 more item:
E         {'cameraLanguage': 'resolver-bound-but-unused'}
```

**只有 `cameraLanguage` 一项变化，其余 6 键完全相同**——红的理由正确。

**存活判定**：无变异存活。

### 变异 C（追加）：改 `useDesign()` 导出名 `PALETTE` → `Color`

落地断言：`assert needle not in after` → `MUTATION LANDED.`

```
E       AssertionError: assert 'resolver-bound-but-unused' == 'reachable'
E         
E         - reachable
E         + resolver-bound-but-unused
1 failed in 0.05s
```

```
=========================== short test summary info ===========================
FAILED test_chart_baseline_is_read.py::test_baseline_inside_the_chart_moves_the_bars
FAILED test_chart_baseline_is_read.py::test_the_delivered_graphs_value_actually_reaches_the_mark
FAILED test_chart_baseline_is_read.py::test_baseline_at_the_content_level_does_nothing
FAILED test_depth_cue_layers.py::test_depth_cue_keeps_differentiating_past_the_third_window
FAILED test_style_bible_no_dumb_declarations.py::test_reachability_of_every_declared_key
FAILED test_style_bible_no_dumb_declarations.py::test_the_two_unconsumed_keys_are_dumb_declarations_today
FAILED test_style_bible_no_dumb_declarations.py::test_mutation_renaming_a_render_side_export_is_caught
7 failed, 339 passed, 2 skipped in 44.41s
```

**这一条同时证明了两件事**：新守卫红了（对的理由），
**且既有守卫 `test_chart_baseline_is_read` / `test_depth_cue_layers` 也红了**
——即本守卫不是唯一防线，与既有守卫**互补而非重叠**。

**存活判定**：无变异存活。

### 复原核对（三次之后）

```
698fb0f5089f526c930ed176ba44920ac5aed1a0e5fd40a9ead340518e7867c5 *tokens.ts
653313f45b3257700ebbeaf41fb27d3adb93676222fe884c2df3e05470f0aeb6 *showcase-v1.ts
ab19cda2df48dee62591495a4f14621ed12aca2096b783671e1b0e23a7e168fe *showcase-v1.schema.json
```

**三个工单指定 sha256 与开工时逐字节相同。**
另三个被变异过的文件（`styleBible.tsx` / `CameraRig.tsx` / `showcase_demo.json`）
与 `HEAD` blob 逐字节 `MATCH`。

### 测试数字

| 时点 | 结果 |
|---|---|
| 实测基线（改代码前） | `334 passed, 2 skipped in 46.47s` |
| 交付后（干净树） | **`346 passed, 2 skipped in 44.88s`**（+12 = 本项新增） |
