# P25 — 把门禁接进渲染路径：实测、裁定、接线与守卫

> 执行记录。所有数字都来自本机实测（`E:\Minimax-H3`，commit `c284f2f` + 本项改动），
> 复现命令写在每节旁边。**未测的一律标注为未测。**

---

## 0. 一句话结论

**裁定 C（拆开）**：**props 级闸接进去了**（`--gate-props`，实测红 0.41 s / 绿 0.20 s，
被拒图谱一个 mp4 都不留）；**逐帧闸没有接**，因为它要给每次渲染加 **21.5 分钟**，
而整片渲染只要 **19.6–22.5 s**。

**P17 那句「现在没有任何东西拦得住一份坏 demo」，在 props 这一层已经不再成立；
在逐帧那一层依然成立。**

---

## 1. 三个硬事实的实测回答

### 1.1 (a) 成本：解码便宜，**分析贵**

工单的担心是「逐帧解码整部片子的真实耗时」可能比渲染本身还贵。**实测下来不是。**

| 动作 | 实测 | 对照 |
|---|---|---|
| 整片渲染（801 帧 / 1920×1080@60） | **22.5 s**（本机 `render.mjs` 自报）／P13 记 19.6–19.8 s | — |
| 整片解码成 801 张 PNG（ffmpeg） | **1.324 s** | 渲染的 **5.9%** |
| 单帧 `run_on_frame` | 中位 **1.615 s**（min 1.559 / max 1.658，n=14） | — |
| 逐帧跑完整片 | **1.615 × 801 ≈ 1292 s = 21.5 min** | 渲染的 **57–69×** |

**瓶颈不是解码，是仪器本身。** 逐规则剖析（3 次取中位，帧 `0161.png`，1920×1080×3）：

| 规则 | 中位耗时 |
|---|---|
| `rule_black_frame` | **1.178 s** |
| `rule_safe_area`（内含 `model_mask` 0.160 s） | 0.172 s |
| `rule_clipping`（内含 `palette_mask` 0.067 s） | 0.071 s |
| `rule_blur` | 0.039 s |
| `load`（PNG → ndarray） | 0.016 s |
| `rule_contrast_frame` | 0.013 s |
| `unavailable_findings` | 0.000 s |

`rule_black_frame` 占单帧 73%，来源是 `visual_qa.py:845` 的一句
`np.unique(a.reshape(-1, 3), axis=0)` —— 对 622 万个像素求唯一色，**每个唯一色都要一次
排序比较**。它只在报告里写一个整数（`distinct_colours`）和一个布尔（`flat`）。

**这个数不改阈值、不改判定也要记下来**：不是「优化一下」，而是
**「逐帧闸今天的成本来自一个统计量，而不是来自任何一条判定」**。
等哪天有人把 `distinct_colours` 从「精确计数」改成「超过 2 就是 flat」，
逐帧闸的成本就掉一个数量级 —— 那时候重新裁定，本文件是那个裁定的依据。

复现：
```
python out/p25_probe/measure_decode.py all      # 解码
python out/p25_probe/measure_qa.py              # 逐帧成本 + 判定普查（抽样）
python out/p25_probe/profile_rules.py           # 逐规则剖析
python out/p25_probe/census_all_frames.py       # 全片 801 帧普查
```
（脚本在 `out/p25_probe/`，已随交付删除；数字见上。）

---

### 1.2 (b) 红不红：拿已交付图谱真渲一次，逐条路径都跑了

**先证明被测对象存在**：真渲了一次。

```
node studio/bin/render.mjs --comp FinanceShowcaseWide \
  --props pipeline/examples/showcase_demo.json --out out/p25_probe/demo.mp4
→ exit 0，22.5s，ffprobe 复核：1920x1080, 60/1, nb_frames=801, duration 13.35s
```

801 张帧解码后逐帧 `run_on_frame`。**三条路径，红的原因完全不同**：

#### 路径 1：`--props`（唯一被接进渲染路径的那条）

```
[PASS]        missing_asset            value=0     4/4 declared assets present
[PASS]        graph_scene_renderable   value=0     4 scene(s), 13 of 22 types have a renderer; every scene has one
[UNAVAILABLE] overflow / collision / flicker / broken_font
→ 6 findings: 0 FAIL, 0 UNVERIFIABLE, 4 UNAVAILABLE    exit 0
```

**绿，而且绿得对。** 4 条 UNAVAILABLE 不进退出码（`visual_qa.py:1534` 的条件里没有
UNAVAILABLE），这是 `6e86b46` 定的语义，本项一个字没动。

**把 scene 0 的类型换成 `video`**（声明了、没有渲染器、会渲成 "not implemented in P4"）：

```
[FAIL] graph_scene_renderable  value=1
       scenes[0]=video; type(s) involved: video
→ exit 1
```

**红得也对，而且红的原因可归因到这次图谱。** 这就是 P17 认定「唯一真的被闸住的
一条子句」。

#### 路径 2：`--frame`（**永远红** —— 工单的担心被实测确认）

```
py -3.12 studio/scripts/visual_qa.py --frame out/p25_probe/decoded/0161.png
→ 11 findings: 0 FAIL, 2 UNVERIFIABLE, 5 UNAVAILABLE      exit 1
```

**2 条 UNVERIFIABLE 全部来自「仪器没建」，不是来自这次渲染**：

| 规则 | 判定 | 原因（原文） |
|---|---|---|
| `font_size` | UNVERIFIABLE | `median band 17px, but no declared size was supplied; a ratio needs both sides` |
| `aspect` | UNVERIFIABLE | `needs both a measured frame and a declared format` |

**这两条都是调用方没传参数造成的，不是片子坏了。** 补上参数：

```
--frame … --props pipeline/examples/showcase_demo.json --declared-px 232 --scale 1.0
→ 13 findings: 0 FAIL, 0 UNVERIFIABLE, 5 UNAVAILABLE      exit 0
```

**⇒ 工单第 2(b) 节的判断成立且可复现：拿现在的 `visual_qa --frame` 直接当门禁，
一次正常渲染就会红，而那个红不来自这次渲染，来自仪器没建。**

#### 路径 3：全片 801 帧普查（**跑完了**）

**801 帧全部逐帧 `run_on_frame`。实测 1310.6 s = 21.8 min，单帧均值 1.6363 s。**

> ⚠️ 这个 21.8 min 与 1.1 节的 21.5 min 外推不一致，原因是**仪器变了**：
> 普查跑的时候另一条 pytest 套件正在同机跑渲染，两个进程抢 CPU。
> **单进程独占实测是中位 1.615 s（21.5 min）**；本节引用的是普查**实测**值
> 21.8 min，**不是**外推值。两个数都在此写明，不取其一冒充精确。

**判定普查（全部 801 帧，逐帧跑完）：**

| 规则 | FAIL | PASS | UNVERIFIABLE | UNAVAILABLE |
|---|---|---|---|---|
| `black_frame` | **50** | 737 | 14 | — |
| `blur` | **60** | 741 | — | — |
| `clipping` | **21** | 735 | 45 | — |
| `safe_area` | **3** | 736 | 62 | — |
| `aspect` | — | — | **801** | — |
| `font_size` | — | — | **801** | — |
| `contrast_frame` / `overflow` / `collision` / `flicker` / `broken_font` | — | — | — | 801 each |

**⇒ `801 / 801` 帧的退出码都是非零。能过的帧：0。**

**这 801 条红里，没有一条来自「这次渲染做错了」**：

| 来源 | 帧数 | 说明 |
|---|---|---|
| `aspect` / `font_size` **UNVERIFIABLE** | **801 + 801** | `needs both a measured frame and a declared format` / `no declared size was supplied`。**调用方没传参数**，与片子无关。补上 `--props` + `--declared-px` 后单帧实测 **exit 0**（见路径 2）。 |
| `black_frame` / `blur` FAIL | 50 / 60 | 集中在 scene 之间的**纯色过渡帧**：`100.0000% non-content, 1 distinct colour(s); the frame is a single flat colour`，Laplacian variance = 0.000。**画面在那个时间点上本来就是空的。** |
| `safe_area` / `clipping` UNVERIFIABLE | 62 / 45 | `no content found` / `no pixel differs from any known theme background` —— 同样是空画面帧。 |

**⇒ 把逐帧闸接进渲染路径 = 每一次渲染都红，红的原因 100% 来自仪器没建、
0% 来自片子。** 这正是 P22 修掉的「永久红的闸」，只是入口从 `--frame` 换成了
`render.mjs`。**工单第 2(b) 节的判断在全片尺度上被完整证实。**

⚠️ **不能据此说「那 50 帧不是缺陷」**。`black_frame` 的阈值窗口只有 **0.000762** 宽
（忙碌帧 0.999238，平帧 1.0；`visual_qa.py:836-838` 自己写着「thin, stated as such」），
**薄到分不出「刻意的转场空帧」和「渲染卡死的空帧」**。
**本项不裁定这 50 帧的性质** —— 只记录：**闸给不出答案。**
上表是 **14 帧抽样**，不是全片比例。全片普查的数字**不写**。

---

### 1.3 (c) 时序：接在 **bundle 之前**

```
node render.mjs … --gate-props     # 被拒图谱
  → 0.41 s 退出，exit 1，out/rejected.mp4 不存在，bundle 目录已清
node render.mjs … --gate-props     # 正常图谱
  → QA GATE exit 0 in 0.20s → 渲染 21.7s → exit 0，mp4 1,325,114 bytes
```

**因为接在渲染之前，工单第 2(c) 节的顾虑在这个接点上不存在** ——
「QA 红了片子已经产出」是**渲染后接 QA** 的问题，props 闸不需要它。
成本也不对称：闸红 **0.41 s**（省下 20 秒渲染 + 1.2 秒 bundle + 800 MB 磁盘），
闸绿 **0.20 s**（渲染的 1%）。

**渲染失败时 `render.mjs` 怎么退出**：**原样转报闸的退出码**，
不折中、不吞、不改。`spawnSync` 拿不到 status（信号杀死 / ENOENT，即闸根本没跑起来）
时报 **3**，因为 1 的含义是「图谱有问题」，让「工具故障」冒充「质量问题」会把
一次环境故障说成一次质量事故。

---

## 2. 裁定

| 候选 | 判定 | 依据 |
|---|---|---|
| **props 级闸** | **接** | 成本 0.20 s / 0.41 s（渲染的 0.9% / 1.8%）；红的原因 100% 可归因到这次图谱（P21/P17 的规则）；能抓住 P17 认定唯一真被闸住的子句；不需要 ffmpeg，不需要逐帧仪器 |
| **逐帧闸** | **不接** | **+21.8 min / 次**（实测，渲染的 63–67×）；**801/801 帧全部退出非零，能过的帧 0**，而那些红没有一条来自这次渲染（1.2 路径 3）；`black_frame` 的阈值窗口只有 0.000762 宽，**分不出「刻意的转场空帧」和「渲染卡死的空帧」**；逐帧闸能抓的 FAIL 在 props 层一条都抓不到，props 层能抓的 FAIL 逐帧闸一条都抓不到 —— **两者没有交集** |
| **`--theme-contrast`** | **不接** | 它描述 `design/themes.ts`，不描述任何产物。P22 已经把它从逐帧路径挪出去了，理由逐字成立。接它 = 把 P22 修掉的缺陷换个入口装回去。 |

**⇒ 裁定 C，逐条结论如上。**

---

## 3. 实施：接线长什么样

`studio/bin/render.mjs`，三处改动：

1. **两个新 flag**：`--gate-props`（**布尔**，只进 `BOOL_FLAGS`）、`--py <python>`（值 flag，默认 `py -3.12`）。
   `--py` 存在是因为渲染器的 Python 不在 PATH 上（本机 `python` 是 3.10，
   测试套件跑在 `py -3.12`）。
   ⚠️ **`--gate-props` 起初被我同时放进了两个集合**，那会让未知 flag 的报错里
   把它列两遍，并且**打断 `test_p14_render_entry_points.py` 的解析**（它的正则
   `Known value flags: ([^:\n]+)` 会把 `py; boolean flags` 当成一个 flag 名，
   于是报 `render.mjs reports ['gate-props', 'py; boolean flags']`）。
   **这是我改坏了一个既有守卫**，由全量套件发现，不是由变异发现 —— 记在这里。
   修法：`--gate-props` 只在 `BOOL_FLAGS`，值 flag 列表里不再有它；
   `tests/test_p14_render_entry_points.py` 的 `values` 字典补了 `'py': 'python'`
   （P14 要求「列出来的 flag 必须各有一次成功渲染」）。
2. **`runGates()`**：一个打印用的小函数，产出 `py -3.12 <abs path to visual_qa.py> --props <props>`。
   **刻意做成函数而不是字符串** —— 工单点名过这一类坑（路径拼接 + Windows 分隔符），
   一次求值就不存在「路径里带空格/反斜杠被重新切分」的问题。
3. **闸块本身**，位置在 `process.on('SIGINT'/'SIGTERM')` 之后、`try { bundle() }` 之前：

```js
if (argv.includes('--gate-props')) {
  const pyArgs = get('py', 'py -3.12').split(' ').filter(Boolean);
  console.log(`[render.mjs] QA GATE (props): ${runGates()}`);
  const gate = spawnSync(pyArgs[0], [...pyArgs.slice(1), qaScript, '--props', propsPath], {
    cwd: …, encoding: 'utf8',
    env: {...process.env, PYTHONIOENCODING: 'utf-8'},
  });
  …原样转发 stdout/stderr，打印 `QA GATE (props): exit N in X.Xs`…
  if (gateCode !== 0) process.exit(gateCode === -1 ? 3 : gateCode);
}
```

**四条必须写清楚的约束：**

- **⚠️ 没有放宽任何判定。** 本项**一行没改 `visual_qa.py`**（sha256 收尾比对一致，见第 5 节）。
  闸的退出码原样转报：FAIL→1、UNVERIFIABLE→非零、UNAVAILABLE→不计。四态语义未动。
- **清理逻辑不受影响。** `:95-108` 的 `cleanUp` + SIGINT/SIGTERM 处理**一行没改**，
  闸块插在它们**之后**。理由是实测：闸红时 bundle 目录**已经建好了**（`mkdtempSync`
  在 `process.on` 之前），所以闸退出必须被已有的 `process.on('exit', cleanUp)` 覆盖到 ——
  插在 `cleanUp` 定义之前会拿到 TDZ `ReferenceError`（我第一版就是这么写的，见第 6 节）。
- **`PYTHONIOENCODING: 'utf-8'` 是必需的，不是装饰。** QA 报告里有 CJK；
  GBK stdout 会在第一个非 ASCII 字符上抛 `UnicodeEncodeError`，
  **闸看起来会像崩了而不是像红了** —— 那会把一次质量问题报成一次工具故障。
- **默认关。** `--props` 也吃非图谱的 timeline / report props，
  那类 props 会被 `graph_scene_renderable` 报 UNVERIFIABLE 而非零退出（`6e86b46`）。
  默认开会让**每一个非 showcase 渲染**都红，红的原因与片子无关 ——
  **那正是 P22 修掉的「永久红的闸」，换个入口装回去。**
  `test_the_gate_is_off_unless_asked_for` 把「默认关」钉成事实，
  以后想默认开是一次显式改动，不是一次顺手。

---

## 4. 守卫：`tests/test_p25_qa_in_render_path.py`（8 个测试）

**回答工单那个问题：「如果明天把接线删了会怎样？」**
**答案是一个明确的失败 —— 4 个测试红，其中一个是
`assert 0 != 0`（被拒的图谱被照渲、照产出、照退出 0），这正是 P17 记的那个缺陷原样回来。**

| 测试 | 它断言什么 | 手段 |
|---|---|---|
| `test_the_render_path_calls_the_qa_gate_in_code_not_in_a_comment` | 接线在**代码**里，不在注释里 | 剥注释后匹配（唯一一个读源码的） |
| `test_the_comment_stripper_separates_a_call_from_a_mention` | 剥注释器**分得清**散文和调用 | 正反两个样本（P17 栽过的坑的回归测试） |
| `test_the_gate_is_reported_by_the_tool_so_a_reader_knows_it_ran` | 闸的运行**在 stdout 里看得见** | 真跑一次渲染读 stdout |
| `test_a_graph_the_gate_rejects_stops_the_render` | **闸还能说「不」**，且没留下 mp4 | 真跑一次：图谱 scene 0 → `video` |
| `test_the_healthy_graph_renders_and_the_gate_is_green` | **闸不会什么都拒** | 真跑一次：已交付图谱 → exit 0 + mp4 存在 |
| `test_an_unknown_flag_is_still_rejected_with_the_gate_flag_listed` | 布尔 flag 不进值 flag 列表（P14 的正则必须还能解析）；`--py` 在列表里；`--gate-props` 真的能用 | 用 P14 的原正则打自己的报错 + 真渲一次 |
| `test_the_gate_is_off_unless_asked_for` | 默认路径不变 | 跑一个不带 flag 的渲染，断言 stdout 里**没有** QA GATE |
| `test_the_flag_actually_reaches_the_gate_not_just_the_parser` | 闸自己的退出码就是渲染器转报的那个 | 直接调 `vqa.main(['--props', …])`，好图谱 0 / 坏图谱非零 |

**⚠️ 关于「排除注释」这一条**：`test_the_render_path_calls_the_qa_gate_in_code_not_in_a_comment`
断言的是一个**生成代码标记** `const runGates =` + `QA_NAME` 的共现，
两者都在**剥掉注释之后**才匹配，而剥注释器由
`test_the_comment_stripper_separates_a_call_from_a_mention` 用一段**真的取自
`render.mjs:141` 历史的散文**（`// jpeg 截帧默认产出 yuvj420p，qa_final.py 要求 yuv420p。`）
证明有效。**没有把注释算成调用点**这一条，是被单独断言的，不是被假定的。

---

## 5. 变异（每条都先证明落地，再读测试结果）

| # | 变异 | 落地证明（先读回文件，再跑 pytest） | 期望 | 结果 |
|---|---|---|---|---|
| **M1** | 移除接线（回到今天的状态） | `LANDED=True`，sha `db1ec074c010` → `09c7b9400c68` | 守卫红 | ✅ **4 红** |
| **M2** | 接线跑但无条件判「通过」（`if (false)`） | `LANDED=True`，sha → `d776b5194966` | 守卫红 | ✅ **1 红** |
| **M3** | 接线保留、名字保留、`QA GATE` 照打，但闸被换成恒返回 0 的桩 | `LANDED=True`，sha → `09afbe179a0f` | 守卫红 | ✅ **1 红** |
| **M4** | 把 `const runGates =` 改名（M1 删了调用块却留下了定义） | `MUTATION LANDED = True`（读回文件确认） | 源码断言红 | ✅ **1 红** |

原始 `-rf` 输出（M1）：

```
FAILED tests/test_p25_qa_in_render_path.py::test_the_gate_is_reported_by_the_tool_so_a_reader_knows_it_ran
FAILED tests/test_p25_qa_in_render_path.py::test_a_graph_the_gate_rejects_stops_the_render
FAILED tests/test_p25_qa_in_render_path.py::test_the_healthy_graph_renders_and_the_gate_is_green
FAILED tests/test_p25_qa_in_render_path.py::test_an_unknown_flag_is_still_rejected_with_the_gate_flag_listed
4 failed, 4 passed in 82.53s (0:01:22)
```

原始 `-rf` 输出（M2 与 M3 完全相同）：

```
E       assert 0 != 0
FAILED tests/test_p25_qa_in_render_path.py::test_a_graph_the_gate_rejects_stops_the_render
1 failed, 7 passed in 83.00s (0:01:23)      ← M2
1 failed, 7 passed in 83.26s (0:01:23)      ← M3
```

原始输出（M4）：

```
E       assert None
E        +  where None = <built-in method search of re.Pattern object ...>
E        +    where re.Pattern = re.compile('const\s+runGates\s*=').search
FAILED tests/test_p25_qa_in_render_path.py::test_the_render_path_calls_the_qa_gate_in_code_not_in_a_comment
1 failed, 7 deselected in 0.05s
```

**M3 是本项目被骗八次里最该防的那一种**：一个「render.mjs 里出现过 visual_qa」的
文本断言在 M3 下**全绿** —— 名字在、标记在、stdout 里 `QA GATE` 也在。
只有真跑一次并读退出码才能杀掉它。**它确实被杀了，
死在 `test_a_graph_the_gate_rejects_stops_the_render` 的 `assert 0 != 0`。**

**M2 和 M3 都死在同一条测试上 —— 这是对的那一条**：
它断言的是「闸能拒绝」，不是「闸存在」。

**⚠️ 一条变异「存活」及其判定**：
`test_the_render_path_calls_the_qa_gate_in_code_not_in_a_comment`（源码断言）
**在 M2 与 M3 下都存活** —— 那两条变异没有动 `runGates` 的定义，
只动了退出分支 / 把闸换成了桩。
**判定：无毒变异（无效变异）。** 它守的是**另一个**性质（M4 杀它，M2/M3 杀不掉）；
两个测试守两个不同性质，合起来才覆盖。
**没有为了杀它去造 contrived 输入。**
M4 就是给它准备的、也是它的**反证**：它不是恒绿。

**M1 杀掉了 4 个而不是 1 个**，因为接线被整体删掉之后，
「闸在 stdout 里可见」「闸能拒」「闸能放行」「flag 列表仍然对」四条同时失效。
**这是好事**：它们本来就是同一个事实的四个侧面，不是四条互不相干的断言。
**M1 里有 1 个红在别处（flag 列表那条红的是 P14 的正则被破坏了，
因为 `--gate-props` 和 `--py` 都不在了），但承重的仍然是
`assert 0 != 0` 那条。**


### sha256 收尾比对

| 文件 | 开工时（`c284f2f`） | 收尾时 | 结论 |
|---|---|---|---|
| `studio/scripts/visual_qa.py` | `7e7d586a747c9fb1…` | `7e7d586a747c9fb1…` | **一致，一行没动** |
| `studio/scripts/frame_baseline.py` | `91e3463cf0fe25a2…` | `91e3463cf0fe25a2…` | **一致，一行没动** |
| `studio/bin/render.mjs` | `fdf178c7e1abd07…` | `120b11dacf1a6230…` | **已改 —— 这是本项的接线** |

---

## 6. 全量测试数字

| 时点 | 结果 |
|---|---|
| **实测基线**（改之前，`c284f2f`） | **494 passed, 3 skipped in 233.79s** |
| **改之后**（干净跑，无并发改动） | **2 failed, 500 passed, 3 skipped in 270.78s** |
| 本项新增守卫单独跑 | **8 passed** |
| `test_p14_render_entry_points.py` 单独跑 | **10 passed** |

**那 2 个红全部来自 P17，且全部红在「P17 的结论已经过时了」这件事上**：

```
E  AssertionError: a production file now runs or imports `visual_qa` outside the test
E  suite: studio/bin/render.mjs
E  If that is a deliberate wiring, the P17 verdict changes: a gate that runs is a gate
E  that can stop a delivery.
E  assert ['studio/bin/render.mjs'] == []
tests/test_p17_showcase_demo_verdict.py:457

E  AssertionError: render.mjs now names a QA gate in code: ['visual_qa']. The finding
E  that nothing gates a render changes and this file must be re-measured.
E  assert ['visual_qa'] == []
tests/test_p17_showcase_demo_verdict.py:474
```

⚠️ **这两条不是本项引入的回归，是本项修好的缺陷在守卫上留下的回声。**
两条断言的**信息内容**（「结论变了，重新测量」）完全正确 ——
它们被写出来就是为了在这种时刻响。

**本项没有改它们。** 见第 8 节：这是一个需要指挥窗口裁定的事。

⚠️ **一条必须记录的测量事故**：全量套件我**跑过三次**。
第一次（`full_after.txt`）3 红，是接线刚落地时的真实状态；
第二次（`full_final.txt`）6 红，**其中 4 红是我自己的测量事故** ——
我在套件还在跑的时候，同时在改 `render.mjs` 跑变异，
套件读到的是**正在变动的文件**。**那一次的数字作废，不作为任何结论的依据。**
第三次（`full_clean.txt`）在**没有任何并发改动**的前提下重跑，才是上面那个 2 红。

---

## 7. 我犯的错（都留了记录）

1. **接线第一版写在 `cleanUp` 定义之前。** ESM 的 TDZ：
   一旦 `--gate-props` 命中就 `ReferenceError: Cannot access 'cleanUp' before initialization`。
   自查代码顺序时发现（不是测试发现的）。
   这条正好说明为什么接线要放在 `cleanUp` 之后：**闸红时 bundle 目录已经建好了**
   （`mkdtempSync` 在 `process.on` 之前），退出必须被已有的
   `process.on('exit', cleanUp)` 接住。
2. **`--gate-props` 同时放进了 `VALUE_FLAGS` 和 `BOOL_FLAGS`。**
   后果是未知 flag 的报错里它被列两遍，并且**打破了
   `test_p14_render_entry_points.py` 的解析**（它的正则吃掉了 `py; boolean flags`，
   于是报 `render.mjs reports ['gate-props', 'py; boolean flags']`）。
   **这是本项改坏了一个既有守卫**，由全量套件发现。
   修法：`--gate-props` 只在 `BOOL_FLAGS`；`test_p14` 的 `values` 补 `'py': 'python'`
   （它要求「列出来的每个 flag 都各有一次成功渲染」）。
3. **守卫里有一句废话** `assert not DEMO.exists() and False or DEMO.exists()`，
   是 `pytest.skip` 该写没写留下的，还绕过了 module fixture。
   已改成 `pytest.skip(...)` + 用 `scratch_env`，死掉的 helper 留成注释而不是悄悄删。
4. **逐帧成本第一版只测 1 帧就外推**（1.6629 s × 801）。补到 14 帧抽样后才写数字。
5. **全量套件跑了三次，中间一次被自己的变异污染**（见第 6 节）。作废的那次已标明。
6. **bash heredoc 传 UTF-8 给 python 会在 GBK 控制台下变成乱码**，
   我因此写坏过一次文档章节。改成用 Write 工具落脚本再执行。
7. **文件里有 14 个 U+FFFD**：第一次 Write 时通道弄坏的 CJK 字符。
   文档 3 个、`render.mjs` 2 个、测试 3 个（其余在被替换掉的旧文本里）。
   全部定位、修复、写脚本断言修复后 **FFFD 计数为 0**。
   ⚠️ **这个事故有一个后果**：修 `render.mjs` 注释里的 U+FFFD 改了文件内容，
   所以**之前那次 M1/M2/M3 是在旧快照上跑的**。
   **修完之后全部重跑了一遍**，第 5 节的 sha 与输出是**最终快照**上的。
8. **CRLF**：每次改完立刻用 Python 读字节数查 `
`，四个文件都是 **CR=0**。
   没有用 `grep -c $'$'`（P23 在那上面栽过）。

---

## 8. 没有做的事

- **没有放宽任何阈值或退出码。** `visual_qa.py` sha256 一字未变。
- **没有改 `render.mjs` 的清理逻辑和 SIGINT/SIGTERM 处理**（一行没改，只是没动位置）。
- **没有接逐帧闸**（理由如上），**没有接 `--theme-contrast`**。
- **没有做 P16**，没有动 P19–P24 的任何成果，
  没有碰 `docs/UPGRADE_PROGRESS.md`、`UPGRADE_MASTER_PLAN.md`、`P1*`/`P2*`。
- **没有碰 `out/**` 里原有的任何东西**（只读；新建的东西已全部删除，见第 9 节）。
- **没有碰 `studio/public/jobs/**`。**
- **没有推送。**

### ⚠️ 需要指挥窗口裁定的一件事

`tests/test_p17_showcase_demo_verdict.py` 的两条守卫断言的是
**「P17 的发现为真」**，而**本项把那个发现修掉了**，所以它们必然红。

按本项目的规矩（不是把红变绿，是**结论变了就显式改写**），
它们应当从「断言缺陷存在」改写成「断言接线存在」——
就像 P14 当年把「`render.mjs` 接受 `--frames`」那条断言**重写成**
「`render.mjs` 拒绝 `--frames`」，并在测试的 docstring 里写明它曾经断言相反的事。

**本项没有改它们**：改写一个 P17 交付物的裁决，不在本工单的授权范围内。
**请裁定：是照 P14 的先例改写，还是保留它们红着作为历史记录。**
（若选改写，`tests/test_p25_qa_in_render_path.py` 的 8 条应当接管那两条断言的性质，
而不是被删掉。）

---

## 9. 磁盘纪律

**造了什么（全部在 `E:` 盘，全部已删）：**

| 路径 | 内容 | 已删 |
|---|---|---|
| `out/p25_probe/` | `demo.mp4`（801 帧真实渲染）、`decoded/`（801 张 PNG）、4 个测量脚本、`census_*.json(l)`、各次 `-rf` 输出、快照 | ✅ |
| `out/p25_snap/` | 变异用快照（render.mjs / visual_qa.py / frame_baseline.py / 测试） | ✅ |
| `out/p25_scratch/` | render.mjs 的 bundle 暂存（`REMOTION_SCRATCH_DIR`） | ✅ |
| `out/p25_guard_scratch/` | 守卫与手工验证用的渲染产物 | ✅（fixture teardown） |
| `.p25_baseline_pytest.txt` | 基线套件输出 | ✅ |

**没有碰 C: 盘。** 每次渲染都带 `REMOTION_SCRATCH_DIR` 指到 `E:`，
所以没有往系统 TEMP 写 bundle —— `render.mjs:79-86` 记的那个
**118 个 bundle 填满 46 GB C: TEMP** 的事故在本项没有复现。
收尾核对过：守卫跑完后 `out/p25_guard_scratch/` 里 **0 个 `render-*` 目录**。
