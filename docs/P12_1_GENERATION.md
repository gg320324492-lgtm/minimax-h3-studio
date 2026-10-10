# P12.1 — Brief → StyleBible：十个键逐个裁定，以及只生成一个键的理由

> 执行 agent 交付。工单 `docs/WORKORDER_P36_P12_1_GENERATION.md`，基线 `20e69f6`。
> 本文件是**裁定与测量记录**，不是放行决定。
> 产物：`pipeline/director/`（生成侧）、`tests/test_p12_1_depth_cue_generation.py`（守卫）、
> `studio/scripts/p12_1_depth_cue_probe.ts`（真实渲染探针）。

---

## 摘要（先看这一段）

1. **十键裁定：1 个 A、2 个 B、7 个 C。** 实现的是 `depthCue` 一个键。
2. **与 P12「Director 零段值得建」不矛盾** —— 差别有两条，都写在第三节。
3. **本项发现 `themes.ts` 的一处不精确**：它声称 ramp 是「拟合而非挑选，
   没有一个数字是凭品味定的」，但用它给出的常数**重算不出它自己存的 10 个 blur
   中的 4 个**（差 1px）。详见第六节。这是本项的副产品，**未修**。
4. ⚠️ **一个必须说清的弱点**：在标准场景下，生成出来的 ramp **恰好等于**
   `premium-dark` 的主题默认值（因为推导就是在延续那条实测曲线）。
   所以「渲染结果等于生成值」这句话，**单靠它自己证明不了通道是通的** ——
   守卫里为此单独立了一条反空转测试，见第七节。

---

## 一、裁定标准与十键逐个结论

判据（工单第1件事）：**A** = 有消费方，**且**有可解释的推导规则；
**B** = 零消费方；**C** = 有消费方，但**定不出该生成什么值**。

> **消费方不是查出来的，是跑出来的。** `tests/style_bible_consumption.py` 的
> 四段链（声明 → resolver 合并 → `useDesign()` 重发布 → 生产 `.tsx` 解构）
> 实测结果，8 个键 `reachable`、2 个键 `no-resolver-binding`。

| # | 键 | 裁定 | 消费方（实测） | 为什么是这个裁定 |
|---|---|---|---|---|
| 1 | `palette` | **C** | 22 处 `PALETTE` | 有消费方，**无推导**。值是品牌 hex；P16 已裁定色彩维度**无仪器可判**（参考片不在本机）。我生成的任何 hex 都是**编的**，不是生成的。 |
| 2 | `typography` | **C** | 12 处 `TYPE` | 有消费方，且是**唯一被真实图谱设过的键**，但那一个值（`tracking: -0.055em`，默认 `-0.04em`）是**人工判断**，不是某条曲线的延续。**没有可延续的东西。** |
| 3 | `spacing` | **C** | 12 处 `SPACE` | 有消费方，但生成它会**对抗一条不变量**：8×斐波那契刻度，由 `tests/test_space_scale.py` 钉住；且 `xs`/`xxl`/`hero` 三级已被实测为**死级**。生成器发的是没人读的数，还违反规矩。 |
| 4 | `radius` | **C** | 10 处 `RADIUS` | 有消费方，但四个值是**形状惯用法**不是刻度：`chip: 999` 是「胶囊」技巧，不是某一级。没有可延续的序列。 |
| 5 | `shadow` | **C** | 8 处 `SHADOW` | 有消费方；四个具名角色（`near`/`medium`/`floating`/`glowAccent`）是**主题表面**，不是曲线。没有任何规则把意图映射到它们。 |
| 6 | **`depthCue`** | **A** | `BrowserStack.tsx:293` 经 `depthCueAt` | **全仓唯一一个有实测推导规则的键**：P6.8 拟合出 `y` 等差、`blur = k·y`、`alpha` 等比，并撞到一个**真实天花板**（第5层 alpha 0.95，第6层需 1.18，不是颜色）。**长度由图谱真实的窗口数决定**，且超出即拒绝。 |
| 7 | `cameraLanguage` | **C** | 仅 `CameraRig.tsx:149` | 有消费方，但**只读一个子键**（`cameraDefaults.perspective`）。`durationSeconds` 声明了、合并了、**无人读** —— 生成它等于在**子键粒度**上重演 P12 识别出的缺陷，而那一层**至今无守卫**。且没有任何规则把意图映射成一个透视数值。 |
| 8 | `motionLanguage` | **C** | 15 处 `MOTION` | 有消费方，但 `mergeSection` 是**带类型检查的浅合并**，而它的值表是**嵌套对象**。**实测**：图谱设 `motionLanguage.profiles.premium` 之后只剩 `premium`，另外三个 profile 被**替换**而非合并，`profileOf` 随后静默回落。生成一个嵌套 motion 段 = 生成一个能**删掉另外三个**的值。 |
| 9 | `chartLanguage` | **B** | **零** | 四段链实测停在 `no-resolver-binding`：schema 声明了，resolver 零提及，场景零读取。**穷举确认**，不是「没找到」。 |
| 10 | `audioLanguage` | **B** | **零** | 同上。⚠️ 注意它与 P11/P12 的 `radius`/`shadow`/`depthCue` **方向相反**：那些是「有人读但喂不进去」，这两个是「**没人读**」。 |

**A 的判据为什么不是「有消费方就行」**：`palette` 有 22 个消费方，
`spacing` 有 12 个，`motionLanguage` 有 15 个 —— 它们全都**没有**进入 A。
差别在于：**只有 `depthCue` 的值可以由一条规则从输入推出来。**

---

## 二、C 占多数，这件事本身是结果不是失败

七个 C 里，五个的判据是同一个形状：**消费方是真的，推导规则不存在。**

这不是「没来得及想」，而是本仓库的现状决定的：

- `design/tokens.ts` 与 `design/themes.ts` 里的值是**一次人工设计**的成果，
  它们的来历在 P16 里已经被追到底 —— 「人眼看片 + 抽帧目检 + 手工调 token」，
  **没有留下任何可复用的测量**（`docs/P16_REFERENCE_BENCHMARK.md` §2）。
- 唯一留下拟合过程的是 `depthCue`，因为 6.8 是**先测量、后修复**的，
  并且把拟合常数、拟合方法和天花板论证都写进了 `themes.ts` 的注释。

⇒ **能生成 = 那条曲线当初是被测出来的。**
没被测出来的东西，生成器就只能编，而编出来的东西本项目已经拒绝过九次了。

---

## 三、与 P12「Director Agent 零段值得建」是否矛盾？

**不矛盾。** P12 的裁定（`docs/DIRECTOR_SCOPE_VERDICT.md` §3.1）是对的，
本项在它之下工作。两处差别：

### 差别一：范围

| | P12 勘察 | 本项 |
|---|---|---|
| 对象 | Director Agent（`Brief→StyleBible→Storyboard→SceneGraph→AssetPlan` 五段） | 只有 `Brief→StyleBible` 一段 |
| 生成面 | 照 7 键 schema **逐键生成** | **一个键**，其余九键显式拒绝并写明理由 |

P12 §3.2 说得很直白：照 7 键 schema 自动生成，**`chartLanguage` 与
`audioLanguage` 必然被生成，而这两键零消费方** —— 「哑声明率 100%」。
本项的生成器**结构上不可能**走到那个失败：`EMITS = {'depthCue'}` 是
一个单元素集合，另外九个键走的是 `REFUSED` 分支，**每个都带理由**，
并且拒绝结果是 `GeneratedGraph.unapplied` 的**一部分**（返回值，不是日志）。

### 差别二：多了一条 P12  ruling 时不存在的判据

P12 裁定「五段里值得建的是 0 段」，其判据是**有没有消费方**。
本项加了一条：**值能不能被推导出来**。

在 P12 的判据下，`depthCue` 与 `palette` 同样是「reachable」；
是本项的第二个判据把它们分开了 —— `palette` 没有规则，`depthCue` 有。

⇒ **P12 的结论没有被推翻，而是被细化了一层。**
它说「五段都别急着建」，本项说「其中一段的两个键里，有一个现在可以建，
另外九个键要等到各自有了测量」。

---

## 四、生成侧长什么样（不是 schema 校验器的换皮）

```
Brief（无 style_bible）
  project / format / scenes[].content.windows
        │
        ▼  _browser_stack_windows()      ← 只有 browser-stack 场景参与计数
   最大堆叠窗口数 N
        │
        ▼  plan_depth(theme, N)          ← 中间表示 DepthPlan
   layers = min(N, ceiling)             ← 唯一真正被「推导」的数
   ramp   = MEASURED_RAMPS[theme][:layers]
   refusals = 当 N > ceiling 时记录被拒的那一层与它需要的 alpha
        │
        ▼  generate_graph() 组装
   showcase-v1 文档 { version, project, format, scenes, style_bible: { depthCue } }
        │
        ▼  scene_graph.load()            ← 真实校验器，真实 JSON Schema
   GeneratedGraph{ graph, plan, unapplied }
```

**为什么这不是换皮**：给它 3 个窗口 → 3 层；给它 9 个窗口 → 5 层 **加一条拒绝**。
一个「直接吐符合 schema 的字典」的函数做不到这两件事里的任何一件，
因为窗口数根本不在它的输入里。

---

## 五、`depthCue` 的值：哪些是**实测携带**，哪些是**推导**

工单要求「若某个值只能靠默认值兜底，如实标注它是兜底而不是生成的」。
这里没有兜底，但**必须区分两类值**：

| | 内容 | 性质 |
|---|---|---|
| **携带** | 10 个 CSS 字符串本身 | **实测值**，逐字取自 `themes.ts`（P6.8 于 2026-10-03 测得）。生成器**不计算**它们，只是按窗口数取前缀。 |
| **推导** | `layers = min(N, ceiling)` | **唯一被推导的数**。它是本片图谱知道、而 ramp 不知道的那个数。 |
| **拒绝** | `N > ceiling` 时的 `refusals` | 记录被拒的层号与它会需要的 alpha（1.18） |

守卫 `test_the_carried_ramps_still_equal_the_theme_that_measured_them`
把携带的那份钉在 `themes.ts` 上 —— 主题一旦重新拟合，守卫立刻红，
而不是让生成器悄悄继续发旧数字。

---

## 六、⚠️ 顺带查出：`themes.ts` 有一处不精确（本项未修）

`themes.ts` 的注释说：

> The extension is the ramp's OWN progression, fitted rather than picked …
> **no number here was chosen by taste.**

并给出常数（dark: `k=2.849`, ratio `1.240`, y 步长 `16`；
light: `k=2.671`, ratio `1.357`, y 步长 `12`）。

**实测：这些常数拟合得不错，但重算不出它自己存的值。**
用 `blur = round(k * y)` 代入存储的 `y`：

| 主题 | 5 个 blur | 命中 |
|---|---|---|
| dark | 40✓ 84✗(85) 132✗(131) 177✓ 222✓ | 3/5 |
| light | 22✗(21) 48✓ 80✓ 112✓ 144✓ | 4/5 |

**10 个里 6 个命中，4 个差 1px** —— 因为字符串是拟合之后**手工取整**的，
而不是由公式生成的。

**这不是缺陷，也不是指控。** 它说明的是：那条 ramp 的来历是
「拟合 + 手工取整」，不是「一条公式」。**因此生成器必须携带它，不能重算它** ——
重算会发出与它声称遵循的那个文件不一致的数字。这正是第五节那个设计的由来。

**本项不修 `themes.ts`**（工单第四节：不动 P19–P35 成果、不扩 schema）。
是否把那四个值对齐到公式、或改注释措辞，**留给指挥窗口裁定**。

---

## 七、守卫：怎么保证「生成了真的被用」

`tests/test_p12_1_depth_cue_generation.py`，14 项。

### 7.1 主链路是真的

```
generate_graph() → scene_graph.load() → ShowcaseSchema.parse()
                → resolveStyleBible() → renderToStaticMarkup(BrowserStack)
                → 读回每个窗口的 box-shadow
```

探针 `studio/scripts/p12_1_depth_cue_probe.ts` 走**真实**的 zod（`.strict()` 在身）、
真实的 merge、真实的场景，**读 React 输出的 HTML**，不重算 clamp
（理由与 `design/depthCue.check.ts` 相同：重算等于拿缺陷的副本去测缺陷本身）。

实测一次 6 窗口生成图：

```json
{ "parse_ok": true, "bible_keys_surviving_parse": ["depthCue"],
  "window_count": 6, "distinct_shadows": 5,
  "shadows": ["0 14px 40px …0.40", "0 30px 84px …0.50", "0 46px 132px …0.62",
              "0 62px 177px …0.77", "0 78px 222px …0.95",
              "0 78px 222px rgba(0,0,0,0.95)"] }      ← 第6个窗口 clamp 到第5层
```

**最后一行就是天花板在屏幕上显形**，也正是生成器拒绝编造第 6 层的原因。

### 7.2 ⚠️ 反空转测试（单独一条，因为它最容易骗人）

**生成出来的 ramp 在标准场景下等于主题默认值。** 于是
「渲染的阴影 == 生成的值」这句话，**在生成器什么都不发、主题默认值应答时也一样成立**。

`test_a_depth_cue_that_is_not_the_theme_default_changes_the_render` 就是堵这个洞的：
它往图谱上放一条**任何主题都没有的** ramp，要求渲染结果随之改变。
一旦这条成立，其余断言才是在读图谱而不是读兜底。

### 7.3 「生成了但没人用」的 catcher

`unused_declared_keys()` 逐键走 P12 的四段链，判定每个被生成的键是否有消费方。
它**先用一个已知死键自证有牙**（`chartLanguage` 必须被报出来），
再判生成器的输出必须干净 —— 否则这条断言可以靠「永远说通过」空转。

判据**不是手写清单**，是 `style_bible_consumption.reachability()` 现算的
（P12 §6.1 明令：手写清单就是下一次惰性字段审计的起点）。

---

## 八、变异记录（含本项自己栽的三次）

三条毒变异，全部**先断言落地再读结果**，`finally` 复原并逐字节核对 sha256。
`-rf` 原始输出见交付报告。

| 变异 | 期望 | 实测 | 红的理由 |
|---|---|---|---|
| 让生成器发一个零消费方的段（`chartLanguage`） | 守卫红 | ✅ **5 red** | `assert ['chartLanguage'] == []` —— 正是「生成了但没人用」 |
| 让生成的值过不了 `scene_graph` 校验（`depthCue` 发数字） | 守卫红 | ✅ **4 red** | `scene_graph.ShowcaseError: style_bible.depthCue[0]: must be string, got int 0` —— **真实校验器**拒绝 |
| 让判据永远判「通过」（`reachability()` 恒返回 reachable） | 守卫红 | ✅ **5 red** | 「`unused_declared_keys` 接受了一个无 resolver 绑定的键」 |

### 8.1 ⚠️ 本项在变异上栽的三次，全部记下

**第一次：字节落地了，行为没变。** 第一版「让生成的值无法通过校验」的变异是
把 `ramp=MEASURED_RAMPS[theme][:layers]` 改成 `tuple(str(x) for x in ...)`。
它**确实写进了磁盘**（断言过），但对字符串取 `str()` 是恒等运算 ——
生成物逐字节相同，套件**全绿**。

⇒ **「变异落地」不等于「变异改变了行为」。** 本项目此前的纪律只要求前者；
这一次证明还需要后者，否则会拿一个空变异的结果当结论。
（守恒地说：这一次套件绿是**对的** —— 守卫没有在检测文本变化。）

**第二次：红在错误的理由上。** 重做的变异写成 `ramp=(', '.join(...),)`
—— 少了赋值号，整个模块 **SyntaxError**，pytest 在**收集阶段**就中断，
1 error。这与 P35 的 M4 第一版（红在 `NameError` 上）**是同一类错误**。
修法：变异之后立刻 `py_compile`，**先证明它是个能跑的 Python 文件**，再看红。

**第三次：探针异常变成了判定。** 数字变异下，
`test_no_generated_layer_carries_an_alpha...` 死于 **`TypeError`**
（对 `int` 做正则匹配），而不是一句干净的断言 ——
**这正是 P31/P34 各栽过的那一次**。已修：先断言 `isinstance(cue, str)`，
再取 alpha，失败时把值打进消息里。

### 8.2 ⚠️ 另一次：守卫自己的判据一度是「副本」

`unused_declared_keys` 第一版写的是 `from style_bible_consumption import reachability`，
而「判据永远通过」那条变异 monkeypatch 的是**模块属性**。
两者不是同一个引用，于是那条变异**打不动它**（测试假绿）。
这是 **P16 §8.4 记录过的同一个坑**：自检测调用的是自己那份副本。
改成经模块查找（`style_bible_consumption.reachability(...)`）后，
该变异才真正生效 —— 上表第三行是改完之后才测的。

> 这四次里，**有两次是我自己的测试写错了**（第二次、第三次），
> 一次是变异本身选错了（第一次），一次是判据接线错了（8.2）。
> 没有一次是守卫生得太松。

---

## 九、已知未覆盖 / 留给裁定

1. **子键粒度哑声明**（`cameraLanguage.durationSeconds` 零消费）
   —— P12 §5.3 已记录，**至今无守卫**。本项因为拒绝生成该键而**不受影响**，
   但若将来有人加消费方，生成器需要跟着扩 `allowed`。
2. **`motionLanguage` 的浅合并删除效应**（第六节实测）
   —— 一个图谱就能删掉另外三个 profile 且无报错。**本项未修，未加守卫**。
3. **生成器只服务 `browser-stack`**：其它场景类型不消费深度线索，
   所以一部没有 `browser-stack` 的片子，本生成器**不产出 `style_bible`**。
   这是正确的，但意味着「每部片子都有一个 style_bible」目前**不成立**。
4. **标准场景下生成值 == 主题默认值**（第七节 2）——
   本项生成器的**非平凡贡献**只有两条：按窗口数**定长度**、**拒绝**越过天花板。
   这一点必须对任何读这份记录的人说清楚，否则会高估它。

---

## 十、账本

`docs/UPGRADE_PROGRESS.md` **未修改**（工单第四节：账本由指挥窗口统一更新）。
本项请账本考虑：把 12.1 记为「**十键裁定完成，生成 1 键，其余 9 键带理由拒绝**」，
而不是「生成器已建成」—— 后者会让人以为 `palette` 之类也有产出。