# P12 续:逐段裁定 —— 四段被合并、被消费、却喂不进去

> 2026-10-03。工单 `docs/WORKORDER_P12_INVERSE_STRIPPED_SECTIONS.md` 第一件事的交付。
> 勘察结论在 `a32f47b`,本文件只做**裁定**,不重复勘察。

## 零、失效形态(先讲清楚,因为两个方向的缺陷容易被混为一谈)

`StyleBibleSchema` 是**开放** `z.object`,没有 `.strict()`。zod 的默认行为是
**剥掉未知键**而不是拒绝。于是:

```
safeParse({radius: {...}})  ->  success = true
                              ->  解析结果里 radius 这个键不存在
```

**没有报错、没有警告、退出码 0。** 消费方拿到的是一个**结构完整**的
`StyleBible`,其中 `radius`/`shadow`/`depthCue` 全是 `tokens.ts` /
`themes.ts` 的默认值。

这是本项目至今最隐蔽的一类失效,因为它**两端都看起来正常**:

| 端 | 看到什么 | 实际 |
|---|---|---|
| 图谱作者 | `validate` 通过 | 他写的东西被删了 |
| 渲染器 | 拿到一个填满的对象 | 填的全是默认值 |

## 一、与 P11 `audio` 缺陷的方向对照(工单点名要求)

这两个缺陷**互为镜像**,必须分开记,否则会修错方向:

| | P11 `audioLanguage` | 本项(P12 续) |
|---|---|---|
| 方向 | **声明了,但没人读** | **有人读,但喂不进去** |
| 谁在撒谎 | 图谱作者 | 渲染器自己 |
| 症状 | 图谱写了 `audioLanguage`,胶片不变 | 图谱写了 `radius`,胶片不变 |
| 症状可见吗 | 可见(但难察觉) | **不可见**:解析成功、对象完整 |
| 修法 | 加消费方,或删声明 | 加声明,或删合并 |
| 守卫测哪一端 | 图谱 → 渲染(声明有没有人读) | 渲染 ← 图谱(合并有没有人喂) |

**它们可以同时发生,而且互不阻塞。** 一个键可以"被声明、被合并、被消费",
同时**声明和消费都在、唯独中间那一段喂不进去**——四段现在就是如此。
所以两条守卫必须都在:`test_style_bible_no_dumb_declarations.py` 管 P11 方向,
本项新增的守卫管 P12 方向。少任何一条,另一半缺陷就重新变成静默的。

## 二、消费方复核(**独立实测,不是引述工单**)

工单给的初判是按 `useDesign()` 解构计的。我复核了,并且**发现工单漏了三处**:

```
$ grep -rn "useDesign()" --include=*.tsx studio/src
```

| 段 | 工单列出 | **我复核后实际** | 差异 |
|---|---|---|---|
| `RADIUS` | `BrowserStack.tsx:159` | `BrowserStack.tsx:159` (`RADIUS.window * s`)<br>**`KpiHero.tsx:143` (`RADIUS.chip`)** | **工单漏 1 处** |
| `SHADOW` | `BrowserStack.tsx:293` | `BrowserStack.tsx:293` (`SHADOW.floating`)<br>**`DataColumns.tsx:142` / `:237` (`SHADOW.glowAccent`)** | **工单漏 2 处** |
| `DEPTH_CUE` | `BrowserStack.tsx:293` | `BrowserStack.tsx:293` (`depthCueAt(DEPTH_CUE, i)`) | 一致 |
| `DEPTH` | 零 | 零 | 一致 |

`DEPTH` 的零消费是**三重独立确认**的:

```
$ grep -rnE "\bDEPTH\b" --include=*.ts --include=*.tsx studio/src
  styleBible.tsx:3    (import)
  styleBible.tsx:73   (merge over b.depth)
  styleBible.tsx:173  (republish as useDesign().DEPTH)
  tokens.ts:116/123/127/147  (docstring + 定义)
  DEPTH.  -> 0 hits
```

四处全是**接线与定义**,没有一处是**读**。而 `DEPTH` 只被
`styleBible.tsx` 导入(全仓库唯一一处),所以删掉合并之后 `tokens.ts`
的表还在、还完整,只是不再对外发布。

**这三处遗漏不改变裁定方向,但改变论据强度**:前两段不是"一处弱消费",
而是跨两个场景的 5 处真实读取。工单的初判 A/C 二选一,在实测面前
A 的分量明显更重。

---

## 三、逐段裁定

### `radius` → **A:接进 schema**

**依据一:有真实消费方,且不止一处。** 5 处解构、2 处真实读取
(`BrowserStack.tsx:159`、`KpiHero.tsx:143`)。`RADIUS.window * s` 直接
决定窗口圆角,这是**看得见的构图差异**。

**依据二:同类已经声明了,这是不对称。** `radius` 的形状是
`Record<string, number>`,和**已声明的 `spacing`**(`Record<string, number>`)
**完全同型**。`spacing` 在 schema 里、`radius` 不在,而两者都是"图谱可调的
间距/圆角刻度"。同样的形状给两种待遇,没有原理支持。

**依据三:圆角是 brand 形状,是图谱该控制的。** 尖角 vs 圆角是设计语言,
不是一个主题的表面。`styleBible.tsx` 自己的注释也把 radius 归入
"does NOT vary by theme"那一档(`:61-68`),即**不变式**——而
`palette` 这种明确随主题走的都在 schema 里。一个更不该被图谱控制的
东西反而没进 schema,更不该被控制的东西却进了,这个方向是反的。

**反驳 C 的可能**:有人说"圆角应该由 brand 锁死"。但 `typography`
(字号/字重,同样是 brand)已经让图谱控制了(`numericDisplay` 是
`showcase_demo.json` 里唯一一个真正生效的声明)。锁死 brand 的先例
在这个仓库里不存在。

---

### `shadow` → **A:接进 schema**

**依据一:有真实消费方。** 3 处解构、3 处真实读取
(`BrowserStack.tsx:293`、`DataColumns.tsx:142`、`DataColumns.tsx:237`),
跨两个场景。

**依据二:它和 `palette` 是同一类东西,而 `palette` 在 schema 里。**
`shadow` 是**主题表面**(随 `premium-dark` / `premium-light` 走,
`themes.ts:117/:135` 两套值)。`palette` 同样随主题走,
`palette` 已经在 schema 里。**同一类东西给了两种待遇。**

`test_showcase_schema_parity.py::test_every_theme_carries_a_full_surface`
把这件事写成了断言:「一个主题要拥有 palette、shadow、depthCue 三样,
少一样就只换了一半」。既然主题必须同时拥有这三样,而图谱能改其中一样
(`palette`) 改不了另两样,那这个"主题表面"的接口就是**故意劈成两半**的,
而劈开的地方没有任何注释说明。

**依据三:反向合并是错的。** `shadow` 的默认值来自 `theme.shadow`,
合并逻辑 `mergeSection({...theme.shadow}, section('shadow'))`
**已经写好了**(`styleBible.tsx:98`),唯一缺的就是 schema 里那一个键。
零新增渲染逻辑,只差一个声明。

---

### `depthCue` → **A:接进 schema**(本项最关键的一处,见第四节)

**依据:6.8 的成果在图谱层不可达,这是一个尚未被记录的缺口。**

简述:`depthCue` 的形态是 `readonly string[]`,`mergeList` 已经实现
全有或全无的列表语义(`styleBible.tsx:37-40`,空数组/含非字符串则回退
默认值)。消费方 `BrowserStack.tsx:293` 的 `depthCueAt` 已经处理
空 ramp(`?? SHADOW.floating` 回退)。**两端的合并逻辑都在,只差 schema 的键。**

深度见第四节。

---

### `depth` → **B:删掉合并**(但**不删 tokens 表**)

**依据一:零消费方,三重确认**(见第二节)。零消费是硬事实,不是推断。

**依据二:它的输入在结构上不可能存在。** `depth` 只能来自 `b.depth`,
而 zod 保证 `b.depth` 恒为 `undefined`。`mergeSection(..., undefined)`
返回 `{...DEPTH}`——一次恒等的空操作。**这一行代码不可能改变任何输出。**

**依据三(决定性):`tokens.ts` 自己的注释已经指明了修法。**
`tokens.ts:141-145` 写着:

> Whether the graph SHOULD be able to reach it is a P6.8 decision,
> recorded with its reasoning in the commit that added this note.
> What is kept here is the measurement; what is NOT done is deleting the
> table, because removing a token is a larger call than recording one.

P6.8 当时**明确把删除这件事留空了**,理由是"删 token 是更大的决定"。
现在这个决定由本项来做,依据齐了(零消费 + 输入不可能存在 + 三年内
没有人要求它)。所以:**删掉图谱侧接线,保留 token 表。**

**依据四:留着它比删掉它更危险。** 一行恒等的空操作,读起来像
"深度平面可被图谱调整"。未来有人 `grep DEPTH` 看到四处命中,
会以为它已接线。删掉接线之后,`DEPTH` 只剩定义一处,
"未消费"变成一眼可见的事实。

**具体删什么**(工单 B 档说"删掉合并 + 相应导出",我按此执行并明确边界):

| 删 | 留 | 为什么 |
|---|---|---|
| `styleBible.tsx:73` 的 `depth:` 合并行 | `tokens.ts:147` 的 `DEPTH` 表 | token 表是资产,删它是更大的决定(P6.8 原文) |
| `StyleBible` 类型里的 `depth` 字段 | | 字段没有写入方,留着就是谎言 |
| `useDesign()` 里的 `DEPTH: s.depth` | | 零消费方,删掉零风险 |
| import 里的 `DEPTH` | | 删掉合并后成为悬空导入 |

**明确不做**:不改 `tokens.ts` 的任何**值**;不删 `DEPTH` 表;
不动 `test_showcase_schema_parity.py:292` 的 `design_values` 元组
(那里列的是**禁止场景直接 import 的名字**,与图谱能否设置无关,
删掉 `DEPTH` 只会让未来有人绕过 `useDesign()` 直接 import 而无人阻止)。

---

## 四、`depthCue` 与 6.8(`7a12d2f`)的关系 —— 本项最重要的记录

**6.8 做了什么。** `depthCue` 的 ramp 从 3 层扩展到 5 层。第 3 层原来是
终点,`BrowserStack` 把第 4 个及以后的窗口全部 clamp 到第 3 层的阴影:

```
w0 0 14px  40px   w1 0 30px  84px   w2 0 46px 132px
w3 0 46px 132px   w4 0 46px 132px   w5 0 46px 132px   <- 三个相同的字符串
```

4 层以上的堆叠在第 3 个窗口之后**完全没有深度差异**。6.8 用测量的
progression 拟合并外推到 5 层(alpha 每层 ×1.240,第 5 层到 0.95,
第 6 层需要 1.18 —— 不是颜色,所以 5 层是真实天花板),并写了
`design/depthCue.check.ts` 渲染真实场景验证。**这个修复是真的,有效的。**

**6.8 修的是哪一层。** 它修的是 **theme 层**:改的是 `themes.ts` 里的
`depthCue` 字面量。换一个主题换一套 ramp,这条路径是通的。

**6.8 没修哪一层。** 它**没有也无法**修 **graph 层**。因为:
```
graph.style_bible.depthCue
  -> StyleBibleSchema 不声明 depthCue
  -> zod 剥掉
  -> styleBible.tsx:99  section('depthCue') 恒为 undefined
  -> mergeList(theme.depthCue, undefined) == theme.depthCue
  -> BrowserStack 永远拿到 themes.ts 的字面量
```

**结论:6.8 的成果在图谱层完全不可达。** 一个想自定义深度线索的
Director,写什么都无效,而且**没有任何报错**。

**这个缺口为什么重要,而不只是"又一处哑声明"。** 因为 6.8 刚刚
**花了很大代价证明**这个 ramp 是有意义的(拟合、验证、天花板论证)。
一个投入了这么多成本、并且被写进 `depthCue.check.ts` 持续验证的东西,
却对图谱作者不存在——这正是 P4 那个缺陷("图谱声明的东西渲染器忽略")
的**完全反向的翻版**。P4 是"图谱能写、没人读";6.8 是"渲染器读了、
图谱写不了"。

**裁定 A 关闭的正是这个缺口**,而且成本为零:`mergeList` 的全有或全无
语义、`depthCueAt` 的空 ramp 回退、两端的类型,都已经写好了。
只差 `StyleBibleSchema` 里的三行。

---

## 五、本项改动的实际后果

| | 改前 | 改后 |
|---|---|---|
| `radius` | 恒为 `tokens.ts` 默认 | **图谱可设** |
| `shadow` | 恒为 `themes.ts` 默认 | **图谱可设** |
| `depthCue` | 恒为 `themes.ts` 默认 | **图谱可设** |
| `depth` | 恒为 `tokens.ts` 默认(空操作) | **接线删除**,零消费的事实一眼可见 |
| 图谱写这四段时的反馈 | 静默无效 | `radius`/`shadow`/`depthCue` **生效**;`depth` 由守卫拦下 |

**注意 `depth` 的变化**:改前图谱写 `depth` 是静默无效;改后
`StyleBibleSchema` 依然不声明它,所以**依然静默无效**,但新增的守卫
会在合并侧把它报出来(见 `tests/test_style_bible_merges_only_declared.py`)。
守卫管的是**代码里的合并**,不是**图谱里的声明**——图谱侧写 `depth`
仍然不会报错,这是开放 schema 的固有性质,本项不改(工单第四节明令
不得加 `.strict()`)。

## 六、未决 / 提请指挥窗口裁定

1. **`StyleBibleSchema` 是否该加 `.strict()`。** 工单明令本项不加,我也同意
   不加。理由补一条:加了之后,现有图谱里任何写 `depth` 的文档会**从
   静默无效变成硬报错**,这是破坏性变更,应该由一个专门的迁移来做,
   而且要先修好 6.8/本项的缺口再收口。**但我认为方向是对的**——开放
   schema 正是这个缺陷家族的温床(`success=true` + 静默剥掉)。建议
   排入后续项。
2. **`chartLanguage` / `audioLanguage`(P11 方向)本项未动。** 它们是
   "声明了没人读",与本项方向相反,修法不同(加消费方或删声明),
   且不在本项授权范围内。它们的状态由
   `test_style_bible_no_dumb_declarations.py` 记录在案。