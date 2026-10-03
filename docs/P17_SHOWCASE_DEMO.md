# P17 — Showcase Demo：能不能做出来，以及做出来会被什么拦住

> 结论 **B**，含 **C** 的一半。下面每一个数字都是本次实测，不是引述。
> 配套守卫：`tests/test_p17_showcase_demo_verdict.py`（本次新增 16 项，现 **17 项**）。
>
> ⚠️ **2026-10-03 修订（P25 之后）**：第③条判定已被 P25（`ad23a6c`）改写，
> 详见 **第 3.5 节**与 **第五节**。**第①、②条不变**（无 H3 渲染器、
> premium 不可判定），它们没有被 P25 推翻。

---

## 零、一句话结论

**P17 现在做不出来**，因为「含 1–3 个 H3 cinematic shot」没有任何东西可以渲染
（H3 渲染器不存在）；而如果有人**绕过**这一条去交付，
**时长 / 分辨率 / 帧率 / "premium" 四条里没有一条能拦住他** ——
这不是"判据偏松"，是**判据不存在**。

工单问的那个问题，答案是：

> **「如果有人今天就交付一份 demo，它会被什么判定拦住？」**
> → **只有 H3 shot 那一条会拦住。其余全部拦不住。**

**⚠️ 这一句在 2026-10-03 之后要加一个限定**：
**H3 那一条现在不止"手动跑得到"，它已经接进了渲染路径**
（`--gate-props`，默认关，见 3.5）——
**但时长 / 分辨率 / 帧率 / "premium" 四条仍然一条都拦不住，
逐帧那一层也仍然一条都拦不住。**

---

## 一、H3 cinematic shot 现在能不能有：**不能**（实测）

### 1.1 渲染器不存在

对 `studio/src/**` 全树扫 `H3` / `h3_`（`.ts`/`.tsx`），**共 2 处命中，没有一处是渲染器**：

| 位置 | 内容 | 是渲染器吗 |
|---|---|---|
| `schemas/showcase-v1.ts:86` | `/** Scenes that need H3 rather than the Remotion motion engine. */` | 否，**是注释** |
| `templates/Phase0Probe.tsx:33` | `Remotion × MiniMax-H3` | 否，**是标题字符串** |

> ⚠️ 这两处正是本项目栽过的那个坑的形状：`render.mjs` 里
> `'Unknown flag' in source` 一直匹配着**解释该修复的那条注释**。
> 所以本项没有用"源码里有 H3 字样"当证据，而是用下面的运行期证据。

### 1.2 两个 generative 类型��会渲染成占位符

- `SceneType`（`showcase-v1.ts:60-84`）声明 **22** 个类型；
- `SCENE_RENDERERS`（`FinanceShowcaseWide.tsx:75-93`）登记 **13** 个；
- 差集 **9** 个 → 全部落到 `MissingScene`（`:95-112`），渲染出
  **"not implemented in P4"**。
- `GENERATIVE_SCENE_TYPES`（`:87-90`）= `{video, data-plane-3d}`，
  **两个都在那 9 个里面**。

Python 镜像 `pipeline/scene_graph.py:179` 的 `GENERATIVE_TYPES` 是同一对
（`test_the_two_mirrors_agree_on_the_generative_set` 每次跑都核对两侧一致）。

### 1.3 运行期实测（不是源码阅读）

把已交付的 `showcase_demo.json` 四个场景**全部**改成 `type: "video"`，
送进 `visual_qa.py --props`：

```
[FAIL        ] graph_scene_renderable  value=4
               4 scene(s), 13 of 22 declared scene types have a renderer;
               4 scene(s) have NO renderer and will render the MissingScene
               placeholder ("not implemented in P4"): scenes[0]=video, ...
6 findings: 1 FAIL, 0 UNVERIFIABLE, 4 UNAVAILABLE
EXIT=1
```

**⇒ 这是 P17 唯一真正会被拦住的条款。** 并且它拦住的形态很特别：
它拦住的是**占位符帧**，不是"画质不够"——
一份含 1–3 个 H3 shot 的 demo，会成片地把那几段���染成
**"video / not implemented in P4"** 这几个字。

### 1.4 P15 那条"差一行"的线索：至今没改，且比记录的更彻底

`tests/test_generative_signal_has_no_consumer.py`（P15）已经钉住"`generative` 无消费者"。
本次实测**确认它至今没改**，并把边界说得更准：

- `generative` 在 `showcase-v1.ts:373` 被算出，在 `:316` 被声明；
- 对**整个 `studio/src`** 扫 `generative` —— **只有那两行**，
  **零消费者**。
- P15 说"信号死在 `resolved.map` 那一行"；
  **实测是信号从没进过 `SceneRenderer`，而 `SceneRenderer` 的 prop 类型是 `{scene: Scene}`**，
  `SceneSchema` 是 `.strict()` 且没有该键。

**⇒ 那正是 H3 渲染器该待的地方，本项按工单要求没动它。**

---

## 二、时长 45–60s：**差 12.5 秒，且这是唯一"能用现有能力补上"的缺口**

### 2.1 已交付两份图谱（实测复现，与指挥窗口一致）

| 图谱 | 场景数 | 总帧数 | 规格 | 时长 |
|---|---|---|---|---|
| `pipeline/examples/charts_demo.json` | 10 | 1950 | 1920×1080@60 | **32.5s** |
| `pipeline/examples/showcase_demo.json` | 4 | 801 | 1920×1080@60 | **13.35s** |

**规格（16:9 / 1080p / 60fps）已达标；最长的离 45s 下限差 12.5 秒���**

> ⚠️ **一处需要纠正的读数**（本项自己踩到并修正）：
> 全仓扫描时**出现过 65.00s 的条目** —— 那是**同样的 1950 帧跑在 30fps**，
> 不是更长的内容。**声明"最长 32.5s"时必须限定 60fps**，
> 否则会拿一个 fps 探针冒充成片。（第一次扫描时我的 `out/` 过滤没生效 ——
> Windows 反斜杠路径不匹配 `startswith('out/')` —— 把 `out/**` 的探针也算进来了。
> 已修正为归一化路径后重扫。）

按 60fps 限定，**全仓被 git 跟踪的、带 `scenes`+`format` 的图谱只有 4 个**
（另两个是 `studio/public/jobs/**` 的 staging 副本，只读，不算数）。
**最长 = 32.5s。**

### 2.2 加长是纯算术，不是能力缺口

实测构造 2700 帧（4 × 675）@60fps = **45.0s**，全部用**有渲染器**的类型：

```
[PASS] graph_scene_renderable  value=0
6 findings: 0 FAIL, 0 UNVERIFIABLE, 4 UNAVAILABLE
EXIT=0
```

schema 侧也没有上限：`Scene.durationInFrames` 是
`{"type": "integer", "minimum": 1}`，**无 `maximum`，无总时长约束**。

**⇒ 「45–60s」是 AUTHORABLE 的。今天就能写出来。**
**⇒ 它不是 P17 的阻塞项，缺的只是编排（多写/加长几个场景）。**

**但** —— 它**���样不会被任何东西拦住**（见第三节）。

---

## 三、⚠️ 最危险的一条：另外三条判据**根本不存在**

### 3.1 实测：`visual_qa.py --props` 对时长和分辨率**完全无感**

三个图谱，同一条命令，**退出码全是 0，全 PASS**：

| 图谱 | 时长 | 规格 | `graph_scene_renderable` | 退出码 |
|---|---|---|---|---|
| 单场景 60 帧 | **1.0s** | 1920×1080@60 | PASS | **0** |
| 单场景 18000 帧 | **300.0s** | 1920×1080@60 | PASS | **0** |
| 单场景 60 帧 | 1.0s | **640×480@24** | PASS | **0** |

**一份 1 秒的片子、一份 5 分钟的片子、一份手机分辨率的片子，
在这道门上和一份合规片子毫无区别。**

（`test_p8_format_scale.py` 钉的是"模板**读** format 读得对不对"，
**不是**"片子**有**没有这个 format"—— 两回事，前者已过，后者无人过。）

### 3.2 实测（**2026-10-03 前**）：这道门**没有被任何生产路径调用**

工单问"如果有人今天交付会被什么拦住"。我把这个问题反过来做了一遍 ——
**不是去读 `pipeline_manifest.yaml` 的 `enforced: false` 注释，
而是把全仓扫了一遍并断言结果**：

- 对 `tests/`、`out/`、`node_modules/` 之外的 `.py`/`.mjs`/`.sh`/`.json`/`.yaml`
  扫 `visual_qa`——**生产代码里零调用点**。
- **`studio/bin/render.mjs` —— 所有渲染必经的那个文件 —— 里没有任何 QA 调用。**

`pipeline_manifest.yaml:198-204` 用仓库自己的话说：
**「质量门禁（当前全部无自动执行 —— P0 接线）」/ `enforced: false`**，
并把 `qa_report.py` 标为**「零调用方」**。实测与这句话一致。

> ⚠️ **本小节的两条结论在 P25 之后都不再成立**，改写见 3.5。
> 保留原文是为了让"它曾经成立过"这件事留在纸上 ——
> 本项目记录的是**判断何时改变**，不是只记录最后的结论。

### 3.3 ⚠️ "premium product film"：**不可判定，不给它编指标**

**总计划对 P17 的成功判据是「明显达到 premium product film」。**
本项目**没有任何可测量判据**对应这句话：

- `visual_qa.py` 的 4 个 `UNAVAILABLE` 里，有 3 个正是这类"仪器在、判据缺"的：
  `collision`（**阈值从未设定**，已交付图表实测 0.278）、
  `flicker`（跨步 + 无正类，P23 实测）、
  `contrast_frame`（**像素里没有前景/背景角色**，无法双峰，P22 实测）。
- **`premium` 是这五个里最糟的一个**：前面四个至少有仪器、有语料；
  premium 连仪器都没有 —— 没有语料（没有"premium 成片"对照组），
  没有正类，没有负类。

**⇒ 明确记录：这一条不可判定。**
本项目已经接受过**五次**「实测说不出想要的结果」
（collision / rule_duplicate / rule_contrast_frame / flicker / per-job 基线）。
**这是第六次，且是唯一一次连测量对象都不存在的。**
**本项没有为它编任何指标。**

### 3.4 「达标」由什么判定 —— 本项的正面回答

即便绕开 H3，一条 45–60s 的片子交上来，今天能判定它的只有：
**`graph_scene_renderable`（有没有渲染器）+ `missing_asset`（资产在不在）**，
**而且这两个都得有人手动跑、并且手动读退出码。**

**所以「商业级 demo 达标」这件事，本质上目前是一个人的一次手动判断，
不是一个可复现、可回归、可交付的判定。**
P13 已实测「产物不可复现」，P24 进一步实测
**同一次渲染的两次运行之间 801 帧里有 220 帧像素不同** ——
**在一个不可复现的产物上，"premium" 更无从谈起。**

### 3.5 ⚠️ 第③条判定已被 P25 改写（2026-10-03）

**这一节是本次修订的核心。** P25（`ad23a6c`）把 3.2 断言为真的事实改掉了，
所以第③条判定必须跟着改，**否则这份文档就在说一件不再为真的事**。

**改后的第③条判定，一句话：**

> **props 级门禁已可接进渲染路径（`--gate-props`，默认关闭）；
> 逐帧门禁未接，且按现有仪器不应接。**
> 时长 / 分辨率 / 帧率 / "premium" 四条**仍然一条都拦不住**，
> 与 P25 之前完全一样。

| 层 | P25 之前 | P25 之后 | 依据 |
|---|---|---|---|
| `graph_scene_renderable` / `missing_asset` | 手动跑才拦得住 | **渲染路径里能拦（默认关）** | `--gate-props` |
| 时长 45–60s | 拦不住 | **仍拦不住** | 未测（`--props` 对 1s / 300s 均 EXIT=0，见 3.1） |
| 分辨率 / 帧率 | 拦不住 | **仍拦不住** | 同上 |
| "premium product film" | **不可判定** | **仍不可判定** | P25 未碰；第②条**不变** |
| 逐帧层（黑帧 / 模糊 / 安全区 / 裁切） | 拦不住 | **仍拦不住，且接了会更糟** | 见下 |

#### 3.5.1 为什么说"已接进渲染路径"

P25 实测（同机同 commit，数字逐条列在 `docs/P25_QA_IN_RENDER_PATH.md`）：

| 事件 | 实测 |
|---|---|
| 被拒图谱 + `--gate-props` | **0.41 s** 退出，非零，**一个 mp4 都不留** |
| 正常图谱 + `--gate-props` | **0.20 s**（渲染的 **1%**），随后 exit 0、mp4 产出 |
| 关掉 flag（默认路径） | 行为与 P25 之前完全一致 |

**⚠️ 默认关，这是一个必须一起记下的事实。**
`--props` 也吃非图谱的 timeline / report props，
那类会被 `graph_scene_renderable` 报 UNVERIFIABLE 而非零退出（`6e86b46` 立的规矩），
**默认开会让每一个非 showcase 渲染都红，红的原因与片子无关**。
⇒ **"能接"和"默认开着"是两回事，本文档只认前者。**

#### 3.5.2 为什么逐帧门禁"不应接"（这是钉住的裁定，不是"还没做"）

| 事实 | 实测 |
|---|---|
| 全片 801 帧逐帧 `run_on_frame` | **801/801 帧退出码非零，能过的帧 0** |
| 这些红里有多少来自这次渲染 | **0 条**。801 `aspect` + 801 `font_size` UNVERIFIABLE 是**调用方没传 `--props` / `--declared-px`**；P25 实测补上两个参数后**同一帧 exit 0** |
| 50 `black_frame` / 60 `blur` FAIL | 集中在 scene 之间的**纯色过渡帧**；`black_frame` 阈值窗口只有 **0.000762** 宽，**分不出"刻意的转场空帧"和"渲染卡死的空帧"** |
| 成本 | **21.5–21.8 min / 次**，整片渲染 19.6–22.5 s ⇒ **57–69 倍** |
| 瓶颈 | **不是解码**（全片解码 1.324 s），是 `rule_black_frame` 的 `np.unique`（1.18 s / 帧） |

**⇒ 接了 = 每一次渲染都红，红的原因 100% 来自仪器没建、0% 来自片子。**
**这正是 P22 修掉的"永久红的闸"，只是入口从 `--frame` 换成了 `render.mjs`。**

**⚠️ 什么情况下这条判定要重新裁定**（写明，以免它变成一条
"永不失效因此毫无意义"的守卫）：
成本出在 `rule_black_frame` 里那个**精确计数 `distinct_colours`** 上，
**不在任何一条判定上**。
等哪天把它从"精确计数"改成"超过 N 就是 flat"，
逐帧闸的成本会掉一个数量级 —— **那时以 P25 的这份实测为依据重新裁定。**

#### 3.5.3 这一条改写**没有**推翻什么

- **第①条（H3 cinematic shot 不能有）不变** —— P25 一行没改
  `FinanceShowcaseWide.tsx`，也没给 `video` / `data-plane-3d` 注册渲染器。
- **第②条（"premium" 不可判定）不变** —— P25 没有为它编任何指标。
- **3.1（`--props` 对 1s / 300s / 640×480@24 全 EXIT=0）不变** ——
  这是**本次未重测**的，来自 P17 原测；P25 只改了渲染路径的接线，
  没有改 `visual_qa.py`（sha256 一字未变，见 `docs/P25_QA_IN_RENDER_PATH.md` 第 5 节）。
- **`pipeline_manifest.yaml` 的 `enforced: false` 仍然成立**，
  它指的是 `qa_report.py` / `check_contract.py` 那两个**零调用方**的工具，
  不是 props 闸；守卫 `test_the_manifest_says_the_gates_are_not_enforced` 仍在跑、仍绿。

---

## 四、裁定

### **B（不能建）**，其中时长一条是 **C（拆开）** 的可建半

| 要求 | 判定 | 依据 |
|---|---|---|
| 16:9 / 1920×1080 / 60fps | ✅ **已达** | 实测两份图谱均 1920×1080@60 |
| 45–60s | ⚠️ **可建但差 12.5s**，且无判据 | 实测 32.5s 最长；45.0s 图谱实测 EXIT=0；schema 无上限 |
| **1–3 个 H3 cinematic shot** | ❌ **不能建（硬缺口）** | 实测无 H3 渲染器；两 generative 类型实测 EXIT=1 / "not implemented in P4" |
| **"明显达到 premium product film"** | 🚫 **不可判定** | 无判据、无仪器、无正负类；**未编造指标**（P25 未推翻） |
| （隐含）**判据存在** | ❌ **不存在** | 实测 `--props` 对 1s/300s/640×480@24 均 EXIT=0；**⚠️ P25 已把这一格的"零调用"改掉**：props 闸现接在渲染路径上（默认关），但**时长/规格/premium 三条依然一条都拦不住** |
| （P25 新增）**props 门禁接线** | ✅ **已接**（默认关） | `--gate-props`，红 0.41 s / 绿 0.20 s，被拒图谱不留 mp4（3.5.1） |
| （P25 新增）**逐帧门禁** | 🚫 **不应接** | 801/801 帧全红且红不来自渲染；21.5–21.8 min = 渲染的 57–69×（3.5.2） |

**⚠️ 裁定仍然是 B，理由没有被 P25 削弱。**
P25 让 H3 那一条从"手动跑才拦得住"变成"渲染路径里拦得住（默认关）"，
**它没有让 P17 变得可建**：H3 渲染器仍然不存在，
而时长 / 规格 / premium 三条的"拦不住"与 P17 实测时**逐字相同**。

**选 B 而不是 C 的理由**：C 会说"时长可建，H3 不可建，拆开做"。
但**时长那一条的"可建"是有条件的** ——
按第三节，它今天既不被拦、也没有判据，**做出来也无法被判定为"达标"**。
把一个**无法被判定为达标**的 45s demo 单独交付，
交付的不是"P17 的一半"，是**一个没有验收标准的文件**。
**⇒ 拆开没有意义，整条要求不成立。**

### 要建它需要什么、按什么顺序

**前置（P0，缺了后面都白做）：**

1. ~~**接线**：`render.mjs` 在渲染后调用 `visual_qa.py --props`，
   **并 gate 在退出码上**。~~ ✅ **P25 已完成**（`--gate-props`，默认关）。
   —— 原判据里"渲染**后**"这一处**没有照做，也不需要照做**：
   P25 接在 bundle **之前**，于是"QA 红了片子已经产出"这个问题不存在了
   （被拒的图谱一个 mp4 都不留）。
   **仍未做、仍是缺口的**是 3.1 那三格：**时长 / 分辨率 / 帧率仍然无判据**。
   （`pipeline_manifest.yaml:198` 当年标的 `P0 接线` 已由 P25 结清。）
2. **时长/规格判据**：为「45–60s / 1920×1080@60」写**带阈值**的规则。
   这一条**可以有阈值**（与 premium 不同）：45–60s 是计���里写死的数字，
   `durationInFrames` 又有 `minimum: 1` 的现成下界语境，
   **这是"计划给了数、仪器给了测量"**，不是要发明判据。

**H3（真正的硬缺口，按依赖顺序）：**

3. **决定 H3 是什么**：仓库里**没有** H3 客户端、没有 provider 抽象、
   没有 `take_critic.py`（工单第六节：已裁定标依赖、不合并、不重复建）。
   ⇒ **这不是"接线"，是"从零建一条新链路"**，工作量不在 P17 之内。
4. **让 `generative` 有一个消费者**：改 `FinanceShowcaseWide.tsx` 的
   `resolved.map`，把**带 `generative` 的 `r`** 传下去，
   并让 `SceneRenderer` 能按该位分派。
   ⇒ **P15 已记录该线索，本项按工单要求未改**（待裁定）。
5. **`MissingScene` 的处置**：在 `video` / `data-plane-3d` 有渲染器之前，
   **这两个类型应该被 schema 拒绝**，而不是渲染成 "not implemented in P4"。
   `graph_scene_renderable` 已经在报，但**没人叫它**（回到第 1 条）。

**"premium"：**

6. **不要动它，直到有对照组。** 需要的是**一份公认达标的 premium 成片语料**
   加上**一个能把它和不合格样本分开的统计量**。
   在此之前，任何"premium 判据"都是编的��
   **这一条建议单独开一项，且明确允许它得出"仍然不可判定"。**

---

## 五、守卫：真的跑了，并断言了判定

`tests/test_p17_showcase_demo_verdict.py`，**原 16 项，现 17 项**（P25 后新增 1 项）。

**没有一条断言"源码里有 `premium`"或"某个数字出现了"。**
每一条能力断言都走 `vqa.main(argv)`，读**返回值**和**打印的报告**。

### 5.1 它回答的那个问题

```
tests/test_p17_showcase_demo_verdict.py::test_a_graph_asking_for_a_generative_scene_is_blocked
tests/test_p17_showcase_demo_verdict.py::test_every_generative_type_is_gated_not_only_video
tests/test_p17_showcase_demo_verdict.py::test_a_demo_that_is_one_h3_shot_among_many_is_still_blocked
```
**⇒ 会被拦住的（实测 EXIT≠0）**，且报告必须点名 `scenes[3]=video` 这种可操作的定位。

```
tests/test_p17_showcase_demo_verdict.py::test_a_one_second_film_passes_the_graph_gate
tests/test_p17_showcase_demo_verdict.py::test_a_five_minute_film_passes_the_graph_gate
tests/test_p17_showcase_demo_verdict.py::test_a_640x480_at_24fps_film_passes_the_graph_gate
```
**⇒ 拦不住的（实测 EXIT==0）** —— 这几条是**钉住"时长 / 规格 / premium 拦不住"这个事实**，
正是工单要求的那个答案。**P25 没有推翻它们，也没有碰它们。**

### 5.1.1 ⚠️ 2026-10-03：两条守卫被**重写**，不是被删掉

```
tests/test_p17_showcase_demo_verdict.py::test_the_only_production_caller_of_the_showcase_gate_is_the_render_path
tests/test_p17_showcase_demo_verdict.py::test_the_render_entry_point_calls_the_props_gate_in_code_not_in_a_comment
```
**它们原来断言的是相反的事**（生产路径零调用点 / `render.mjs` 零 QA 调用），
P25 把那两个事实改掉了，它们因此转红 —— **那是正确的行为**。
按 P14 的先例**就地改写**，不改写成"什么都行"：

| 原断言 | 现断言 |
|---|---|
| `unexpected == []`（零调用方） | `production_callers == ['studio/bin/render.mjs']` —— **恰好一个，且只能是渲染路径** |
| `QA_NAME.findall(code) == []` | `QA_NAME.findall(code) == ['visual_qa']` **且**闸命令里带 `--props` **且**闸被真的 `spawn` 了 |

**第三条新守卫**：

```
tests/test_p17_showcase_demo_verdict.py::test_the_frame_gate_is_not_wired_and_must_not_be
```
**⇒ 钉住"逐帧门禁不应接"这个裁定**，而不是让它作为一条没人注意的空白留着
（理由见 3.5.2：801/801 全红且红不来自渲染；成本 57–69 倍）。
它带**校准**：一条合不上的 sweep 会永远报零，所以测试里断言
"一段真实的整片帧闸代码能被这套标记认出来"。

### 5.2 变异（每条都先 assert 变异落地，再跑 pytest）

| # | 变异 | 期望 | 结果 |
|---|---|---|---|
| **M1** | `visual_qa.py` 的 `gaps` 恒为 `[]`（门不再拦占位符） | 红 | ✅ **被杀**，3 项 |
| **M2** | 同规则**恒返回 PASS**（永远通过） | 红 | ✅ **被杀**，3 项 |
| **M3** | 给 `data-plane-3d` 登记一个渲染器（假装 H3 缺口被本地填了） | 红 | ✅ **被杀**，2 项 |
| **M4** | 给 `Scene.durationInFrames` 加 `maximum: 3600` | 红 | ✅ **被杀**，1 项 |

**4/4 存活变异全部被杀，无无效变异。**
**M1/M2 红的理由正确**：红在 `assert 'PASS' == 'FAIL'`（判定本身），
不是红在别的断言上。

**原始 `-rf` 输出**（各变异后从快照复原，收尾 sha256 全部核对一致）：

**M1**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_a_graph_asking_for_a_generative_scene_is_blocked
FAILED tests/test_p17_showcase_demo_verdict.py::test_every_generative_type_is_gated_not_only_video
FAILED tests/test_p17_showcase_demo_verdict.py::test_a_demo_that_is_one_h3_shot_among_many_is_still_blocked
3 failed, 13 passed in 3.82s
```
```
E       assert 'PASS' == 'FAIL'
E       - FAIL
E       + PASS
tests\test_p17_showcase_demo_verdict.py:205: AssertionError
```

**M2**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_a_graph_asking_for_a_generative_scene_is_blocked
FAILED tests/test_p17_showcase_demo_verdict.py::test_every_generative_type_is_gated_not_only_video
FAILED tests/test_p17_showcase_demo_verdict.py::test_a_demo_that_is_one_h3_shot_among_many_is_still_blocked
3 failed, 13 passed in 3.85s
```
```
E       AssertionError:   [PASS        ] missing_asset   value=0
E       assert 'PASS' == 'FAIL'
tests\test_p17_showcase_demo_verdict.py:162: AssertionError
E       AssertionError: generative type 'data-plane-3d' was not gated:
E       assert 'PASS' == 'FAIL'
tests\test_p17_showcase_demo_verdict.py:184: AssertionError
```

**M3**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_every_generative_type_is_gated_not_only_video
FAILED tests/test_p17_showcase_demo_verdict.py::test_no_h3_renderer_exists_in_the_render_source
2 failed, 14 passed in 3.91s
```
```
E           AssertionError: generative type 'data-plane-3d' was not gated:
tests\test_p17_showcase_demo_verdict.py:184: AssertionError
E           AssertionError: SCENE_RENDERERS now routes ['data-plane-3d'] — a generative type has a Remotion renderer. Re-measure before claiming P17 cannot be built.
tests\test_p17_showcase_demo_verdict.py:531: AssertionError
```

**M4**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_the_schema_places_no_upper_bound_on_scene_duration
1 failed, 15 passed in 4.52s
```
```
E       AssertionError: Scene.durationInFrames now has a maximum: {'type': 'integer', 'minimum': 1, 'maximum': 3600}. The finding that duration is unconstrained has changed and this file must be re-measured.
tests\test_p17_showcase_demo_verdict.py:283: AssertionError
```

**复原核对（sha256，四个源文件全部一致）**
```
7e7d586a747c9fb13eb5b23628156e19649b1d696fa85fbff281207416d35ded  studio/scripts/visual_qa.py
e426a88febd9dd5ee6138381c2638f0f94b2abaea83678e42efcf845e1a36ed4  studio/src/templates/finance-showcase/FinanceShowcaseWide.tsx
812506600494bbaac9b9a4c237a8eb8c4a19060d91b648ac48d7ade844ee6acf  pipeline/schemas/showcase-v1.schema.json
fd7e6927b8af11ecc4aabc7b412ac5a73cc0dac74007a0c6593efe5206140d21  pipeline_manifest.yaml
```

### 5.3 变异（2026-10-03，为 5.1.1 那三条新判定而做）

**协议同 5.2：先 `MUTATION LANDED = True` + sha 读回，再读 pytest。**

| # | 变异 | 落地证明 | 期望 | 结果 |
|---|---|---|---|---|
| **M1** | 移除 props 闸接线：`if (argv.includes('--gate-props'))` → `if (false)`，且闸命令里的 `--props` → `--nope` | `LANDED=True`，`120b11da…` → `fe0ad9f9…` | 红 | ✅ **被杀**，1 项（**且这一项是本项目被骗九次里最典型的一种**） |
| **M2** | 把整片逐帧闸**接上**（新增 `--frame-gate`：ffmpeg 解码成帧 → 逐帧 `visual_qa.py --frame` → 非零即 `exit 1`），并登记进 `BOOL_FLAGS` | `LANDED=True`，`120b11da…` → `50610508…` | 红 | ✅ **被杀**，2 项 |

**M1 的原始 `-rf` 输出**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_the_render_entry_point_calls_the_props_gate_in_code_not_in_a_comment
1 failed, 16 passed in 6.93s
```
```
E       AssertionError: the command render.mjs builds no longer runs the gate on the props
E       path. `--props` occurring elsewhere in the file does not count — it is also an
E       argument of the spawn. The props path is the only one that can judge a scene
E       graph before any pixels exist; without it the file carries a name and no decision.
E       assert False
E        +  where False = _gate_command_judges_the_props("...
tests\test_p17_showcase_demo_verdict.py:620: AssertionError
```

**M2 的原始 `-rf` 输出**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_the_render_entry_point_calls_the_props_gate_in_code_not_in_a_comment
FAILED tests/test_p17_showcase_demo_verdict.py::test_the_frame_gate_is_not_wired_and_must_not_be
2 failed, 15 passed in 6.85s
```
```
E       AssertionError: a whole-film frame gate is now WIRED into a production path: studio/bin/render.mjs
E       Measured on the delivered 801-frame render, all 801 frames exit non-zero and none
E       of those reds come from the render (801 aspect + 801 font_size UNVERIFIABLE for want
E       of --props/--declared-px), and the cost is 21.5-21.8 min against a 19.6-22.5 s render.
E       If that has changed, re-measure before unpinning this.
E       assert ['studio/bin/render.mjs'] == []
E         Left contains one more item: 'studio/bin/render.mjs'
E         Use -v to get more diff
tests\test_p17_showcase_demo_verdict.py:694: AssertionError
```

**⚠️ M1 为什么值得单独记：** **它第一次跑时是绿的。**
第一版重写只问"`render.mjs` 里有没有 `visual_qa` 和 `--props`"，于是
- 死掉的 `if (false) { … }` 块**仍然在文件里**，
- `--props` **仍然**作为 `spawnSync` 的实参出现在那一块里，
- 于是"命名即通过"的守卫在**接线已经被拆掉**的情况下报了绿。

加上 `const runGates =` 之后**它仍然是绿的** ——
直到断言改成**闸命令本身**（`GATE_COMMAND` 捕获那个模板字符串）才被杀。
**⇒ 文本共现不是守卫；被判定的必须是那个被构造出来、并且被执行的东西。**
这与 P25 的 M3（"名字在、标记在、stdout 里 QA GATE 也在"，
文本断言全绿、被真跑一次杀掉）是同一个失败形状的第二次出现。

**⚠️ M2 的红在一处别的地方**：它同时触发了
`test_the_render_entry_point_calls_the_props_gate_in_code_not_in_a_comment`，
红在 `FRAME_PATH` 那条断言上（`render.mjs 出现了 --frame`）。
**承重的是 `test_the_frame_gate_is_not_wired_and_must_not_be`** ——
它红在 `offenders == []`，即"逐帧闸被接上了"这个判定本身。

### 5.4 ⚠️ 一个**真漏洞**，以及为什么它不能靠再加一条正则修掉

**这是指挥窗口在复验时注入并实测存活的：**

```
注入: 把 render.mjs 第 160 行的
  const gate = spawnSync(pyArgs[0], [...pyArgs.slice(1), qaScript,
改写成
  if (false) { const gate = spawnSync(pyArgs[0], [...pyArgs.slice(1), qaScript,
结果: 17 passed（存活）
```

**根因（本项自己也写错过一次的那个洞的下一层）**：5.3 那条守卫里的
`RUN_GATES` / `_gate_command_judges_the_props` / `LIVE_GATE`
**全是正则匹配文本**，而 `if (false) { … spawnSync(…) }` 在文本上
三者**全部满足**：它定义了就 spawn 了，只是被死代码包住。

**⇒ 死代码在文本上和活代码没有区别。再加一条正则只会把洞换一层。**
本文件的 docstring 早就写着「a command that is built and never executed is
not a gate」——**现在要判的是"被构建了、在死代码里执行"**。

**修法不是正则，是一个动态观测**：`tests/_p17b_reach.mjs`。

```
它做的事：把 render.mjs 自己的顶层代码放进一个 vm 沙箱跑一遍，
        spawnSync 换成记录器，fs 和 Remotion 渲染器换成桩，
        然后报告它**实际上**有没有 spawn 过闸。
        ESM 的 import 改写成 require 打到桩上；
        import.meta 和 await 各做一次机械替换（await 全部在闸之后）。
        任何没配桩的 import 会直接抛错，而不是安静地回答"不可达"。
```

| 形态 | 观测结果 |
|---|---|
| 真实接线 | `qaSpawnCount: 1`，argv 里带 `--props` |
| 不传 `--gate-props` | `qaSpawnCount: 0`（P25 的"默认关"也成了被观测的事实） |
| **spawn 被 `if (false) { }` 包住** | **`qaSpawnCount: 0`** |

**为什么是动态的**：死代码**spawn 不出任何东西**。
这条性质与源码长什么样无关，所以"再加一种写法"骗不过它。

**为什么不用 Node 自己的 parser**：Node 不在没有 acorn 的情况下把
parser 暴露给用户代码，而本仓库没有、也不该为了一个测试去依赖 acorn。
**⇒ 记录在案，不要重试。**

**⚠️ 两次失败的做法也记录在案**（都在探测器的注释里）：
① 先写了一个**手写词法分析器**放在 Python 测试里 —— 它吞掉了每一个模板字面量
及其之后的全部内容，而且**丢掉了 `runGates()` 那唯一一次真实调用**
（它在 `${…}` 洞里）；② 先写了个**"死分支正则"** ——
先撞上 `render.mjs` 里 `if (0)` 那行**在注释里**，
改完之后又因为**先删后并**把行结构粘在一起，让一句英文读成了 `import p from ...`，
最后干脆把注释里的 `import` 单词也扫了进来。
**三条都记下来了，因为"再加一条正则"正是这个坑的形状本身。**

### 5.5 新判据的两条变异（证明它不是空转）

| # | 变异 | 落地证明 | 期望 | 结果 |
|---|---|---|---|---|
| **M3** | **指挥窗口那个变异**：spawn 被移进 `if (false) { … }`（补一个 `let gate = {status:0…}` 让文件仍可解析） | `LANDED=True`，`120b11da…` → `97ede5e3…` | 红 | ✅ **被杀**，2 项 |
| **M5** | **真调用被移除**：spawn 整段改名成 `Object.assign({status:0…}, {…})`，**`runGates` / `--props` / `QA GATE` / `spawnSync` 这个词全部留下** | `LANDED=True`，`120b11da…` → `edcd2900…`；`node --check` 通过 | 红 | ✅ **被杀**，2 项 |

**M3 的原始 `-rf` 输出**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_the_render_entry_point_calls_the_props_gate_in_code_not_in_a_comment
FAILED tests/test_p17_showcase_demo_verdict.py::test_the_probe_observes_the_real_render_path
2 failed, 18 passed in 27.04s
```
```
E       AssertionError: render.mjs ran its own top-level code with --gate-props on its command
E       line and spawned no QA gate. The gate is defined, the command is built, the spawn is
E       spelled out — and it does not run. That is what dead code looks like, and no amount of
E       text matching can see it (measured: wrapping the spawn in `if (false) { ... }` was green
E       on every text-based version of this assertion).
E       assert 0 >= 1
tests\test_p17_showcase_demo_verdict.py:732: AssertionError
```

**M5 的原始 `-rf` 输出**
```
FAILED tests/test_p17_showcase_demo_verdict.py::test_the_render_entry_point_calls_the_props_gate_in_code_not_in_a_comment
FAILED tests/test_p17_showcase_demo_verdict.py::test_the_probe_observes_the_real_render_path
2 failed, 18 passed in 26.83s
```
```
E               AssertionError: with --gate-props on the command line, render.mjs spawned no QA
E               gate: []
E               assert 0 >= 1
tests\test_p17_showcase_demo_verdict.py:795: AssertionError
```

**M5 这条尤其关键**：它把 `spawnSync` 这个**词**留在 import 里、
留在注释里，`runGates`、`--props`、`QA GATE` 一个不少 ——
**所有基于文本的断言全部照常通过**，而闸实际上已经不再跑了。
**新判据红在 `assert 0 >= 1`（一个数上），不是红在任何文本匹配上。**

**⚠️ 一条变异"存活"及其判定**（按规矩记，不造 contrived 输入去杀它）：
**M4** —— 只把 `console.log(\`… ${runGates()}\`)` 里的那次 `runGates()` 调用去掉，
**整个文件 20 passed**。
**判定：无毒变异。** 它并没有删掉闸，只是让工具**不再打印**闸命令；
闸在下一行照常 spawn。**这条守卫守的是"闸跑没跑"，不是"某处有没有出现
`runGates` 这个名字"** —— 这正是它该有的性质。
M5 才是"真调用被移除"，它被杀。

---

## 六、本项的失误（如实记录）

1. **守卫的第一版数注释当调用点。**
   `render.mjs:141` 的**注释**里出现了 `qa_final.py`
   （解释为什么传 `--pixelfmt yuv420p`），我的第一版 sweep 直接命中它并报红，
   `test_the_render_entry_point_calls_no_qa_gate` 因此**第一次是红的**。
   **这正是本项目记录过的 `render.mjs` 'Unknown flag' 坑的形状。**
   已改成"先剥注释再扫"，并加 `test_the_comment_stripper_separates_a_call_from_a_mention`
   把这个错误本身钉住。

2. **第一版 sweep 的范围过宽，产生了 11 个"offender"。**
   逐个查证后，**诚实的只有两类**：`third_lantern` / `liaozhai_demo` 的
   `qa_final.py` 确实被自己的 `run_post_chain.sh:133` 调用
   （`"$PY" scripts/qa_final.py`，实测），其余是注释。
   ⇒ **"仓库里什么都没有 gate"是假的，我没有这样断言。**
   守卫改成只声称**可核实的那一条**：**没有任何生产路径运行能判定 showcase 图谱的那道门**。

3. **`out/` 过滤第一次失效**，把 `out/**` 的 fps 探针算进"最长的图谱"，
   一度得出"最长 65s"。原因：Windows 反斜杠路径不匹配 `startswith('out/')`。
   已改为 `os.path.normpath` 归一化后重扫（**同一条数据，两个不同结论**，
   记在这里以免下次又被它骗一次）。

4. **两处自己写错的断言**：`schema['$defs']`（该镜像是 draft-07，用
   `definitions`）、以及一个指向不存在目录的占位 fixture。
   都在首次运行时暴露并已修。

### 6.1 2026-10-03（P25 之后改写第③条时）的失误

5. **⚠️ 第一版重写的守卫在 M1 下是绿的 —— 而 M1 正是"拆掉接线"那条变异。**
   详见 5.3：**死掉的 `if (false)` 块仍在文件里，`--props` 仍是它的 spawn 实参**，
   于是"名字共现"的守卫在接线已被拆掉时报了绿。**我第一次读到 `17 passed`
   时以为 M1 被杀错了人，又回去重跑才确认它本来就该绿。**
   这条与 P25 的 M3 是同一个失败形状的第二次出现。
   修法是把断言从"两个词在文件里"改成"**闸命令里带 `--props` 且闸被执行**"。

6. **帧闸 sweep 的第一版校准样本漏了解码那一步**，
   于是 `decode` 标记匹配不上校准样本，测试第一次跑就是红的。
   **是校准自己抓住了不一致**，不是测试主体的断言。
   ⇒ 已把校准样本补成一段真实的整片帧闸（ffmpeg → 逐帧 `--frame` → 非零即退）。

7. **文本通道在本次编辑里造出 4 处 U+FFFD**（中文被通道弄坏）。
   全部定位并修复 —— **本文件开工前已有 5 处 U+FFFD（P17 原始那次编辑留下的），
   本次未扩大它们，也未新增**，下面的计数写的是**收尾实测值**，
   而非"全部为 0"（`docs/P25_QA_IN_RENDER_PATH.md` 修过一轮全仓 FFFD，
   `docs/P17_SHOWCASE_DEMO.md` 的这 5 处不在那一轮的文件清单里）。

### 6.2 2026-10-03 修那个真漏洞时的失误

8. **⚠️ 我先试了两个错的东西当"修法"，都不该那么写。**
   ① **手写 JS 词法分析器**（放在 Python 测试里）：它吞掉了每一个模板字面量
   及其之后的全部内容，**并且丢掉了 `runGates()` 那唯一一次真实调用**
   ——那一次调用在 `` `${runGates()}` `` 的洞里，而我为了不让 `}` 破坏
   花括号配平**把模板文本全涂白了**，于是洞里的代码也没了。
   ② **"断言文件里不出现 `if (false)`"**：这条**在干净文件上就是错的** ——
   实测 `render.mjs` 的**注释里**就有一行 `if (0)`，第一版标记把它数成了死分支。
   ⇒ 两者都已删除，换成 `tests/_p17b_reach.mjs` 的**动态观测**。
   **写下来是因为它们正是"再加一条正则"这个动作的两种形状。**

9. **探测器自己也错了六次**，全部记在 `tests/_p17b_reach.mjs` 的注释里，
   其中两次值得在这里点出来：
   - **`String.replace` 的回调拿到的是 `(match, p1…pn, offset, whole)`，
     没有 groups 数组。** 我把整个 `match` 当 groups 传进去，
     于是"模块 id"读成了 `p` —— 看起来像 import 匹配写错了，
     实际是回调参数用错了。**连续两次卡在这里。**
   - **`spawnSync(cmd, [...spread], opts)` 到达记录器时，`args[1]` 是一个数组**。
     我用 `String()` 把它拍平成一个逗号串，于是 `includes('--props')`
     在**干净文件上**返回 false —— **探测器一度在正确的代码上报"闸没有传
     `--props`"**。**一个只会说"否"的探测器比没有更坏**，这条与 5.4 里
     "探测不了不许读成不可达"是同一条规矩。

10. **⚠️ 我用 Python 打补丁把 `tests/test_p17_showcase_demo_verdict.py`
    整个文件变成了 CRLF（1101 个 CR，HEAD 是 0）。**
    `p.write_text()` 在 Windows 上默认翻转行尾，而我没有显式 `newline=''`。
    **P23 栽在 `grep -c` 上、P22 栽在 Edit 上，这次栽在我自己的脚本上。**
    收尾用**字节计数**核对（不是 `grep`）：`CR=0 / LF=1101`，已修回 LF。
    **⚠️ 而且它是在全量套件跑完之后才发现的** —— 也就是说那次
    `506 passed` 是在一个 CRLF 文件上跑出来的。修完 LF 后**重跑了全量**，
    数字见下。

11. **M4 存活，我判定它无毒，没有为了杀它造 contrived 输入。**
    理由写在 5.5：它删的是"打印"，不是"闸"。

---

## 七、测试数字

| | 结果 |
|---|---|
| **P17 原始基线**（实测） | `478 passed, 3 skipped in 207.63s` |
| **P17 改动后**（实测） | `494 passed, 3 skipped in 201.06s`，退出码 0 |
| **P25 改动后**（P25 实测，无并发改动） | `2 failed, 500 passed, 3 skipped in 270.78s` —— 那 2 红就是本文件 5.1.1 那两条 |
| **第③条改写后**（实测，无并发改动） | `503 passed, 3 skipped in 273.56s`，退出码 0 |
| **修掉那个真漏洞后**（实测，无并发改动，**LF 修回之后重跑**） | **`506 passed, 3 skipped in 294.50s`，退出码 0** |

**500 + 2 = 502 ⇒ 503**：P25 交付时那 2 红由本文件 5.1.1 的两条重写守卫接住
（不是删掉它们换来的绿），**另加 1 项是新增的**
`test_the_frame_gate_is_not_wired_and_must_not_be`。

**503 + 3 = 506**：新增的三项是
`test_the_probe_observes_the_real_render_path`、
`test_the_gate_is_dead_code_when_it_is_never_executed`、
`test_the_gate_can_be_proved_live_by_running_it_and_the_p17_guards_say_so`。

**`test_p17_showcase_demo_verdict.py` 单独跑：20 passed**（16 → 17 → 20）。

**⚠️ 一条必须写下来的测量事故**：本次**第一次**跑全量套件报了
`3 failed, 500 passed, 3 skipped`，红的 3 项全在 `test_visual_qa.py`，
而我**一个字没改过那个文件**。
原因是我给 pytest 进程设了 `PYTHONIOENCODING=utf-8`：
它被继承到 `test_visual_qa.py` 派生的 `visual_qa.py` 子进程，
子进程于是按 UTF-8 输出，而那个测试自己按 **GBK** 解码子进程输出
（`UnicodeDecodeError: 'gbk' codec can't decode byte 0x94`）。
**⇒ 那 3 红是我的环境变量造成的，不是回归。**
判据：`test_visual_qa.py` 单独跑（38 passed, 3 skipped），
用**标准跑法**重跑全量 = 503 passed / exit 0。
**记在这里是因为本项目已经作废过一次被自己的变异污染的套件数字**，
这一次差点又作废一次 —— **区别是这次作废的是一次，而不是一次结论。**

478 + 16 = 494，**与新增的 16 项守卫逐项吻合**，无回归。

标准跑法：
```
cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q \
  --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py
```

---

## 八、改动文件清单

**P17 原始交付：**

| 文件 | 性质 |
|---|---|
| `tests/test_p17_showcase_demo_verdict.py` | **新增**，16 项守卫 |
| `docs/P17_SHOWCASE_DEMO.md` | **新增**，本文件 |

**2026-10-03 第③条改写（P25 之后）：**

| 文件 | 性质 |
|---|---|
| `tests/test_p17_showcase_demo_verdict.py` | **改写两条 + 新增一条**（16 → 17 项）；未删任何一条 |
| `docs/P17_SHOWCASE_DEMO.md` | 改写第 3.2 / 3.5 / 四 / 五 节 |

**2026-10-03 修 5.4 那个真漏洞：**

| 文件 | 性质 |
|---|---|
| `tests/test_p17_showcase_demo_verdict.py` | **再新增两项**（17 → 20 项）；第②条重写的守卫加了动态可达性断言；未删、未放松任何一条 |
| `tests/_p17b_reach.mjs` | **新增**：把 render.mjs 自己的顶层代码跑一遍并观测闸有没有被 spawn 的探测器 |
| `docs/P17_SHOWCASE_DEMO.md` | 新增第 5.4 / 5.5 / 6.2 节，改写第七节数字 |

**本次改写未改动任何生产代码。** 未动 `visual_qa.py`、
未动 `frame_baseline.py`、**未动 `render.mjs` 的接线**（M1/M2 只在变异窗口内改过，
复原后 sha256 与 `ad23a6c` 一致）、未动 `render.mjs` 的清理逻辑（`:95-108`）、
未实现 H3 渲染器，未改 `FinanceShowcaseWide.tsx` 的 `resolved.map`，
未改 `GENERATIVE_SCENE_TYPES`，未渲染任何成片，未动 P19–P25 的任何成果，未改账本。