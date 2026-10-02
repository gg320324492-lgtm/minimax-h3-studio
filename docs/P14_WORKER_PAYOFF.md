# P14 Render Worker — 长驻 bundle 的真实成本实测

> 结论先行：**长驻 worker 不值得建（B）；分级渲染（scene/draft/full）现在也不值得建（C），
> 但理由和 P13 不同 —— P13 说"没有 scene 级 diff"，P14 实测出更靠前的一条：
> **一次渲染里根本没有"值得复用的重复"。**
>
> 数字全部来自本机实测。**没有实现长驻 worker，没有实现分级渲染。**
> 基线 `34316a3`，分支 `main`。渲染于 Windows 11 / RTX 5090 / Node v24.16.0 /
> remotion@4.0.529，`pipeline/examples/showcase_demo.json`，
> `--comp FinanceShowcaseWide`，1920×1080@60，801 帧（4 个 scene）。

---

## 0. 本项为什么不是"去实现长驻 worker"

P13 测出 bundle 占单次渲染 6%（1.2s / 19.6s），并推断"长驻进程 → 省掉这 1.2s"。
**那条推理链的脆弱处是：长驻进程本身的成本从没被测过。** 本项测的就是这个成本。

先给最重要的一个数字，因为它推翻了整条推理链的前提：

| | 冷（每次一进程，现状） | 热（同进程第二/三次渲） |
|---|---|---|
| **整片渲 wall** | **21368 / 20633 / 20069 ms** | **18693 / 19277 ms** |
| `render.mjs` 自报 total | 21.0s / 20.2s / 19.6s | — |
| bundle | 1.2s | **0s（省掉了）** |
| metadata | 0.3–0.6s | — |

**热渲不比冷渲快。** 18693ms 的热渲 vs 20069ms 的冷渲，差 1.4s，
**恰好就是那 1.2s 的 bundle**。也就是说：

> 长驻进程**只**省掉 bundle，**一点也**没有让渲染本身变快。
> 而 bundle 在一次全片渲染里只有 1.2s。

这不是"收益比看起来小"。这是**收益的上界被钉死在 1.2 秒**，
因为渲染阶段（18.7s）根本不碰 bundle —— 它读的是磁盘上已经写好的
`index.js`，bundle 只是一个**文件**，不是一个常驻对象。

---

## 1. 常驻 bundle 的内存占用：**262 MB，不是 800 MB**

### 1.1 800 MB 是磁盘，不是内存 —— 这是本项最容易搞错的一件事

`bundle()` 产出的是一个**目录**（175 个文件 / 799.6 MB），Remotion 之后
**从磁盘读它**。它从来没有被读进进程的堆。所以"常驻 800 MB bundle ⇒
进程常驻 800 MB"是错的，差了一个数量级以上的量级。

### 1.2 怎么量的（对照实验，不是读任务管理器）

两个进程，同一台机器，同样的 `node --expose-gc`：

| 角色 | 做什么 | RSS（MB，强制 GC 后 5 次采样） |
|---|---|---|
| **control** | `import` 同样的模块，什么都不做 | `57.1,57.1,57.1,57.1,57.1` / `57,57,57,57,57` |
| **bundled** | `bundle()` 然后持有 serveUrl，空闲 | `327.5,327.3,327.3,327.3,327.3` / `318.5,318.5,318.6,318.6,318.6` |

**差值 = 常驻一个活 bundle 的内存代价。**

- control ≈ **57 MB**
- bundled ≈ **318–328 MB**
- ⇒ **长驻 bundle ≈ 262 MB 常驻内存**

方法说明：`process.memoryUsage().rss`，每个采样前调用两次 `global.gc()`
（所以必须 `node --expose-gc`），间隔 150ms 取 5 次。
要求 5 次一致才认这个数 —— **RSS 单独一个读数是噪声**，
因为 V8 不会立刻把释放的页还给 OS。实测 5 次全部一致到 ±0.1 MB。

### 1.3 空闲会不会涨（泄漏还是固定成本）

```
IDLE_SERIES=318.3 ×30 个采样点，跨 90 秒
IDLE_FIRST=318.3 IDLE_LAST=318.3 IDLE_GROWTH_MB=0
```

**零增长。** 90 秒内 30 个采样点全部 318.3 MB。
所以 262 MB 是**固定成本**，不是泄漏 —— 一个长驻 worker 会一直占这 262 MB，
但不会一直涨。

### 1.4 峰值另算：渲片时会更高

第一次渲片的瞬间实测 **610.5 MB**（bundle 531 → selectComposition 589 → renderStill 610）。
但那不是"常驻成本"，那是渲染期峰值，且渲完回落到 **336 MB**。
**判据：常驻 262 MB，峰值 ~610 MB。**

---

## 2. bundle 何时失效：**Remotion bundler 不自动重建（实测）**

这是工单说的"最大的复杂度来源"。实测结论：**不自动重建，必须自己判。**

### 2.1 怎么证的（这里我犯了一个错，先记下来）

**第一版实验测了个寂寞。** 我往 `overlays.tsx` 顶部注入
`export const ZZ_P14_INJECTED_MARKER = '...'`，然后到 bundle 产物
`index.js` 里 grep 这个字符串。结果：**显式 `bundle()` 之后仍然 grep 不到**。

看起来像"改动永远进不去"。**不是 —— webpack 把没人 import 的导出
tree-shake 掉了，那个 marker 从来没进过产物。**
我在测一段**死代码**，而且没先证明被测对象存在。
（这正是本项目"先证明被测对象存在，再测量"那条教训。）

**改成构造上可观测的改动**：改 `Root.tsx` 里 `Phase0Probe` 的
`durationInFrames={150}` → `{151}`。这个 Composition **没有 `calculateMetadata`**，
所以 `selectComposition` 会把这个字面量原样报出来。不用 grep，数字自己会说话。

### 2.2 实测输出

```
[inval] select-BEFORE-edit                  {"ms":379,"frames":150}
[inval] edited                              {"changed":true}
[inval] ... 静置 5 秒 ...
[inval] select-AFTER-edit-same-serveUrl     {"ms":322,"frames":150}   ← 没变
[inval] verdict-auto-rebuild                {"baseline":150,"afterEdit":150,"autoRebuilt":false}
[inval] select-AFTER-explicit-rebundle      {"ms":298,"frames":151}   ← 变了
[inval] REBUNDLE_MS=1109
[inval] REBUNDLE_PICKS_UP_EDIT=true
[inval] SECOND_REBUNDLE_MS=958
[inval] RESTORE_MATCHES_ORIGINAL=true
```

**结论：改一个 `.tsx` 之后，已存在的 bundle 不会自动重建。**
静置 5 秒后仍然是 150（旧的），显式再 `bundle()` 一次才变成 151（新的）。
**所以长驻进程必须自己带一套失效判据。**

### 2.3 但判据很便宜 —— 这是本项最重要的转折

失效判据的代价必须和它要省下的 1.2s 比，不能和"缓存"比。
`studio/src` 实测 **56 个文件 / 0.4 MB**：

| 判据 | 耗时（3 次复测） | 说明 |
|---|---|---|
| **mtime**（stat 每个文件，hash 路径+mtimeMs+size） | **0.21–1.53 ms** | 最便宜的检查 |
| **内容 sha256**（读+hash 每个文件） | **2.15–2.38 ms** | 唯一能发现"改了但 mtime 不变"的 |
| `bundle()` 本身 | **958–1331 ms** | 被省掉的那 1.2s |
| `import` 渲染器模块 | 163 ms | 长驻进程顺手也省了 |

**0.2ms 的检查买 1200ms 的节省。** 从纯开销看，判据根本不是瓶颈。

> **实测附带的一条：对 mtime 判据有利，且是本项自己撞出来的。**
> 失效实验结束时把 `Root.tsx` 复原成**逐字节相同**的内容
> （sha256 `ac816317…`、`git diff` 为空），
> 但源目录的 mtime 指纹从 `67f85de8…` 变成了 `125fda80…`（56 文件不变）。
> ⇒ **一次内容为空的改动也会让 mtime 判据误报失效。**
> 这不是缺陷（判据宁可多失效一次，也不能拿旧 bundle 渲新代码），
> 但它意味着 mtime 判据每次误报都要付 1.2 秒的 `bundle()`。
> 内容 sha256（2.2ms）没有这个问题 —— 上面那次复原**不会**改变内容哈希。

---

## 3. 固定开销 vs 可变开销

### 3.1 一次全片渲染的拆分（不渲任何东西，只量固定栈）

```
[fixed] inProcMs=1526 bundleMs=1192 selectMs=334 frames=801
[fixed] inProcMs=1546 bundleMs=1218 selectMs=328 frames=801
[fixed] inProcMs=1706 bundleMs=1227 selectMs=479 frames=801
```

bash 侧 wall 1981 / 1999 / 2190 ms ⇒ **进程启动 + 模块加载 ≈ 300–460ms**。

### 3.2 一次全片渲染（801 帧，1920×1080@60）

| 项 | 时间 | 占 20.3s | 性质 |
|---|---|---|---|
| node 启动 + `import` 渲染器 | **~300 ms** | 1.5% | 固定（每进程） |
| **bundle** | **1200 ms** | **6%** | 固定（每进程） |
| selectComposition metadata | **330–480 ms** | 2% | 固定（每进程） |
| **渲染 801 帧** | **~18.7 s** | **92%** | **可变（按帧数）** |
| **合计** | **20.3 s** | | |

> **固定开销合计 ≈ 1.9 s（9%），可变开销 ≈ 18.4 s（91%）。**
> 长驻进程最多把固定的那 1.9s 里的 bundle+启动（约 1.5s）摊掉，
> 而生产管线**一天只渲一次全片**（见 4.1）—— **摊不掉。**

---

## 4. 建不建

### 4.1 决定性的一条：生产管线一天只渲一次

`ceo_mindread_ep01/scripts/render_with_remotion.py:70` 是唯一的生产调用点：

```python
if run(['node', STUDIO / 'bin' / 'render.mjs',
        '--comp', args.comp, '--props', props, '--out', out_path,
        '--crf', args.crf, '--concurrency', args.concurrency]) != 0:
```

**一次 subprocess，一次全片，进程退出。**
长驻 worker 的全部收益来自"同一进程渲多次"，而**生产路径上一次都不多渲**。
`render.mjs:7` 自己也写着"批量产能升级为常驻服务是 Phase 4 事项"。

### 4.2 净省多少：把成本减干净

| | 金额 |
|---|---|
| 省掉 bundle | **+1.2 s** |
| 省掉进程启动 + import | +0.3 s |
| **减：常驻内存 262 MB 永久占用** | 不是时间成本，是**占用** |
| **减：bundle 目录永久不删（800 MB）** | **把"每次泄漏"换成"永久占用"** |
| **减：必须自建失效判据** | 0.2ms/次判据 + 一套没人写过的代码 |
| **减：并发安全从 mkdtemp 兜底变成自己负责** | 见 4.4 |
| **减：与 46 GB 事故的清理逻辑正面冲突** | 见 4.3 |
| **收益在生产路径上实际到手** | **0.0 s（一天渲一次，无第二次可摊）** |

### 4.3 磁盘：这是个坏交换，不是好交换

`render.mjs:43-47` 记录的事故是 **118 个泄漏的 bundle 填满 C: 盘 46 GB**。
那段清理逻辑（`finally` + SIGINT + SIGTERM）是**为修这个事故写的**。

长驻进程意味着那 800 MB 目录**不再被删 —— 它会一直在**。

> **这不是"消灭了泄漏"，是"把每次泄漏换成永久占用"。**
> 一次泄漏 = 事后可查、随渲染结束而止；
> 永久占用 = 没人会因为它结束而注意到它，除非有人专门去查。

**结论：这一条单独就足以否掉长驻 worker。** 因为它要求先放松一条
已经因为一次真实事故而写下的安全约束，而收益是 1.2 秒。

### 4.4 并发：从"白拿"变成"自己负责"

`render.mjs:57` 的 `mkdtempSync` 让两个并发渲染**各拿一个目录**，
共享 bundle 这件事在今天**不可能发生**。长驻 worker 只有一个目录。

实测同一 serveUrl 上两个重叠 `renderStill`（不同帧）：
`MISMATCHED_FRAMES=0/3`，**这个窄场景下没测出损坏**。
但 P13 已经证明**同图重渲本身就不逐字节可复现**（711054 / 710851 / 712303），
而 `visual_qa.py` 的报告**对场景改动逐字节相同**（P13 实测）——
**所以"渲错了"这件事，没有任何一层能发现。**

⚠️ **"这个窄场景没坏"不能推广成"并发安全"。**
它只说明：两个只读帧请求共用一个 bundle 没坏。
它**没有**说明：两个并发渲染 + 中途有人调 `bundle()` 会怎样 ——
那正是失效判据和并发交叉的地方，**本项没有测，也没有测它的时间**。

### 4.5 判定

**长驻 worker = B（不值得建）。**
理由按重要性排：

1. **净收益在生产路径上是 0** —— 一天渲一次全片，没有第二次可摊（4.1、4.2）。
2. **它要求放松一条已经因真实事故写下的磁盘清理约束**（4.3）。
3. **热渲不比冷渲快**（第 0 节）—— 除了那 1.2s，什么都没变快。
4. 常驻 262 MB + 永久 800 MB 磁盘占用（1.1、4.3）。
5. 并发安全的兜底消失，而错了没人能发现（4.4）。

**诚实说明哪条不是决定性的**：失效判据**不是**理由 ——
它只要 0.2ms（2.3），便宜得可以忽略。工单猜它是"最大的复杂度来源"，
**实测下来它不是**。这条推理是错的，也是本项推翻工单预设的地方之一。

---

## 5. 分级渲染（scene / draft / full）：C，现在不建

### 5.1 scene 级：P13 的收益依然成立，卡点依然成立

P13 实测单 scene 重渲省 **63–72%**（改 s01：19.6s → 7.3s）。
那个收益是真的，本项**没有推翻它**。

挡住它的三条也依然成立，本项**复核确认**：
(a) 产物不可复现；(b) 无人比较图谱、无人察觉 scene 变更；(c) re-encode 成本未实测。

**但本项要补一条 P13 没说的**：即使 (b)(c) 都解决了，
**在 4–10 个 scene 的成片上，分级渲染的上限就是 1.2s × (scene 数 − 1)**，
因为它建立在"bundle 被复用"之上，而 bundle 每进程只有 1.2s。
**scene 级 diff 解决的是"渲多少帧"，本项解决的是"渲几秒"。**
两者是不同的钱，不能相加成"分级渲染能省 70%"。

### 5.2 draft 级：渲染快不快的关键数，实测不在这里

"draft 模式"（低分辨率 / 低帧率预览）的前提是**渲染是瓶颈**。
第 3 节实测：**渲染 801 帧 = 18.7s，占 91%**，
所以渲染**确实是**瓶颈 —— 这个前提成立。

但要省下渲染时间，得先知道渲染时间花在哪，而本项**没有测**：
并发多少、GPU 占比、每帧成本随分辨率怎么变。
**在测出这些之前，"draft 能省多少"是估算，不是实测。**
工单说"请实测，不要估算" —— 我实测了固定/可变拆分，
**但没有实测 draft 的分辨率-时间曲线，所以不给 draft 档的收益数字。**

### 5.3 瓶颈到底在哪（复核 P13 的答案）

P13 的答案是「没有 scene 级入口 + 没有 scene 级 diff」。
**本项复核后要改一个字：这两个都不是最靠前的。**

> **最靠前的瓶颈是：一次渲染里没有"值得复用的重复"。**
> bundle 1.2s 已经在 P13 被判为不值得；本项进一步证明**连它也没省到**
> （热渲不比冷渲快，省下的就是那 1.2s，仅此而已）。
>
> 所以真正卡住分级渲染的不是"缺一个 `--scene` 入口"，
> 也不是"缺一个 diff 算法"，而是：
> **在 4–10 个 scene、801 帧、20 秒的成片上，
> 没有任何一层的时间被"重复劳动"占住到值得引入缓存或常驻的程度。**

按"能省的时间"排序，可动的与不可动的：

| | 时间 | 能不能动 |
|---|---|---|
| 渲染 801 帧 | 18.7s | **唯一的大头**，但要动它得先知道它花在哪（未测） |
| bundle | 1.2s | 能省，要长驻；长驻的代价更大（4.2–4.3） |
| selectComposition | 0.33–0.48s | 能省，要长驻；同上 |
| 进程启动 + import | ~0.3s | 能省，要长驻；同上 |
| 场景局部性 | 省 63–72% **帧数** | 真实存在，但入口不存在、diff 不存在、re-encode 未测 |

**"重渲 63% 的帧"和"省 1.2 秒的 bundle"是两份不同的钱，
而当前系统里能拿到的只有后者，且拿它要付出 800 MB 常驻占用。**

---

## 6. 顺带发现（不属于 P14，未修）

1. **`render.mjs` 静默忽略任何未知 flag。**
   `still.mjs:36-48` 会校验未知 flag 并 `exit 2`（那段是修
   "`--frames` 写成 `--frame` 静默选了别的帧"加的），
   **`render.mjs` 没有同样的校验**：`get(key, fallback)` 只按名字取值，
   剩下的 argv 一概不管。
   实测：`render.mjs --comp Phase0Probe --frames 10` → **忽略 `--frames`，
   渲完整 150 帧，exit 0**。
   这和 `still.mjs` 当年被修的是**同一个缺陷类**，一个修了另一个没修。
   已用守卫钉住当前行为（红→绿即代表被修，届时需重写）。
   **本工单只授权守卫不授权修行为，故未改。**
2. **两个入口对未知 flag 的约定相反**（上条的另一面）：`still.mjs` 拒绝，
   `render.mjs` 放行。同仓库、同一个 flag 类别，两种约定。

---

## 7. 守卫

`tests/test_p14_render_entry_points.py`，8 条，**全部实测行为**：

| 守卫 | 断言的是 |
|---|---|
| `test_a_scene_selector_does_not_exist_on_any_entry_point[still.mjs]` | 跑真命令，`--scene` → exit 2 且报"Unknown flag" |
| `... [render.mjs]` | 跑真命令，`--scene` 被忽略，**渲完整 150 帧** |
| `test_the_rejected_flag_list_shows_scene_and_frame_range_are_absent` | 工具自报的 flag 清单里没有 scene / frameRange / imageRanges |
| `test_an_unknown_comp_exits_nonzero_and_writes_no_output_file` | 非法 comp → exit≠0 **且不留下 mp4** |
| `test_a_valid_single_frame_render_still_works` | **正向**（防止"永远红"的守卫） |
| `test_an_out_of_range_frame_is_refused_not_clamped` | 越界 → 非零退出 + 无 PNG + RangeError |
| `test_render_mjs_silently_ignores_a_flag_it_does_not_understand` | 第 6 节第 1 条 |
| `test_a_finished_render_leaves_no_bundle_directory_behind` | 渲完磁盘上**没有** bundle 目录（46 GB 事故的守卫） |

**为什么不用 `assert 'frameRange' not in source`**
—— 工单点名了这个坑（`assert "mkdtemp" in source` 匹配到了解释该 bug 的注释）。
这里让**工具自己报出它接受的 flag**，断言落在"它接受什么"这个可测行为上。

**为什么守卫要跑真渲染**
—— 因为要证明"当前只能全片渲染"和"单帧渲染可用"，
这两件事**只有跑一次才知道**。约 20 秒/文件，值得。

### 7.1 变异结果（`-rf` 原始输出）

**变异 1 —— 让 `render.mjs` 接受一个不存在的 `--comp`**
（`id: comp` → `id: 'FinanceShowcaseWide'`；注入后先 `grep -c MUTANT` = **1**、
sha256 变为 `d44093b6...`，确认落地后才跑测试）
```
FAILED ::test_a_scene_selector_does_not_exist_on_any_entry_point[render.mjs-required1]
FAILED ::test_render_mjs_silently_ignores_a_flag_it_does_not_understand - Ass...
FAILED ::test_an_unknown_comp_exits_nonzero_and_writes_no_output_file - Asser...
3 failed, 5 passed in 87.00s (0:01:26)
```
**存活判定：全部是"被杀"，无存活。**
主杀手是 `test_an_unknown_comp_exits_nonzero_and_writes_no_output_file`，
红在**正确的断言**上：`an unknown --comp exited 0` + 确实写出了
`never_written.mp4`。另外两条也是真红（变异把 comp 钉死成
FinanceShowcaseWide，于是 `150f` 不再出现），不是无关噪声。

**变异 2 —— 让 `still.mjs` 对越界 `--frame` 静默返回**
（`frame` → `Math.min(frame, 0)`；注入后先 `grep -n MUTANT` 命中 `:165`、
sha256 变为 `e307685a...`，确认落地后才跑测试）
```
FAILED ::test_an_out_of_range_frame_is_refused_not_clamped - AssertionError: ...
1 failed, 7 passed in 23.19s (0:01:23)
```
**存活判定：被杀，且只杀了一个。** 红在**正确的断言**上：
`an out-of-range frame exited 0 (exit 0)`，且日志显示
`[still] frame 9999 -> .../out_of_range.png` —— **真的写出了一张帧 0 的图，
标着 9999**。这正是守卫要防的"错得像对的"。

**变异 3 —— 让 `render.mjs` 跳过 bundle 清理**（长驻化会绕过的那段）
（`rmSync` 加 `if (!process.env.P14_MUTANT_KEEP)`，运行时置该变量；
注入后先 `grep -n MUTANT` 命中 `:65`、sha256 变为 `92243ebc...`）
```
FAILED ::test_a_finished_render_leaves_no_bundle_directory_behind - Assertion...
1 failed, 7 passed in 22.59s (0:01:22)
```
**存活判定：被杀。** 红在正确的断言上，消息直接点名泄漏的目录：
```
AssertionError: the render left bundle directories behind:
['render-MQ5ipz', 'render-ngDP7Y', 'render-Nsa2rB', 'render-tpjw53'].
```
**这条最重要**：它就是 46 GB 事故的守卫。
**长驻化会主动绕过这段逻辑 —— 所以这个守卫必须在改动之前就红。**

**每条变异后已从快照复原，收尾 sha256 三重核对通过（见第 8 节）。**

---

## 8. 测试与校验

| | 结果 |
|---|---|
| 基线（改之前，自测） | `379 passed, 2 skipped in 60.83s` |
| 改之后 | **`387 passed, 2 skipped in 79.82s`** |
| 差 | **+8**，正是新守卫，**零回归** |

三个受保护文件的 sha256，**开工前 vs 收尾**：

| 文件 | 开工前 | 收尾 | |
|---|---|---|---|
| `studio/bin/render.mjs` | `fdbb16e4…36ca85` | `fdbb16e4…36ca85` | ✅ |
| `studio/scripts/visual_qa.py` | `9db0198e…565db3` | `9db0198e…565db3` | ✅ |
| `studio/src/schemas/showcase-v1.ts` | `3294bd06…09ca278` | `3294bd06…09ca278` | ✅ |
| `studio/bin/still.mjs`（额外记录） | `98fb12d5…a124727` | `98fb12d5…a124727` | ✅ |

`grep -rn MUTANT studio/bin/` → **clean**（无残留变异）。

---

## 9. 磁盘纪律

**全部 scratch 都显式指到 E: 盘**（`REMOTION_SCRATCH_DIR=E:/Minimax-H3/out/p14_probe/scratch`），
一次都没碰 C: TEMP。

**我造了什么**

| 路径 | 大小 | 处理 |
|---|---|---|
| `out/p14_probe/scratch/lld-const` | 800 MB | **已删** |
| `out/p14_probe/scratch/inval-const` | 800 MB | **已删** |
| `out/p14_probe/scratch/mem-const` | 800 MB | **已删** |
| `out/p14_probe/scratch/fixed-const` | 800 MB | **已删** |
| `out/p14_probe/scratch/conc-const` | 800 MB | **已删** |
| `out/p14_probe/scratch/conc_out` | 7.3 MB | **已删** |
| `out/p14_guard_scratch/` | 每条守卫一个 800 MB bundle | **自动删除**（fixture `finally`），已确认不存在 |
| 变异 3 泄漏的 4 个 `render-*` | 800 MB × 4 | **自动删除**（同上 fixture） |
| `out/p14_probe/*.mp4`、`trace_measure.json`、探针脚本 | ~2 MB | **保留**（证据，gitignored） |

**合计制造约 4 GB（不含守卫自动清理的那 5 次），已全部删除。**
`studio/.remotion/bundle/` 复查为**空目录**（我自己每次都覆盖了 `REMOTION_SCRATCH_DIR`）。

**发现的、不是我的既有 bundle 目录 —— 报告，未删除**

| 路径 | 大小 | mtime |
|---|---|---|
| `C:\Users\pc\AppData\Local\Temp\remotion-webpack-bundle-pyY1Lw` | **39 MB** | 2026-10-02 18:03 |
| `C:\Users\pc\AppData\Local\Temp\remotion-v4.0.529-assetsw5235hsi3b` | 4 KB | 2026-10-02 23:13 |

两个都在 C: TEMP，**都是 10-02（我开工前）留下的**，不是本项产生的。
按工单要求**只报告不删除**。量很小（合计 39 MB），
但注意它们正是 `render.mjs:43-47` 那类泄漏的残留形状 ——
**在所有清理逻辑都已就位的情况下仍然存在**，
说明除了 mkdtemp 那条路径，Remotion 自己还有一处会往 TEMP 落东西。
本项没有追这条线（超范围），**留作已知项。**

---

## 10. 复现

```bash
export REMOTION_SCRATCH_DIR="$PWD/out/p14_probe/scratch"   # 绝不用 C: TEMP

# 常驻内存（对照实验）
node --expose-gc studio/out/p14_probe/mem_probe.mjs --role control
node --expose-gc studio/out/p14_probe/mem_probe.mjs --role bundled \
     --props pipeline/examples/showcase_demo.json --comp FinanceShowcaseWide

# 失效判据（自动复原源文件，末尾打印 RESTORE_MATCHES_ORIGINAL）
node --expose-gc studio/out/p14_probe/invalidate_probe.mjs \
     --props pipeline/examples/showcase_demo.json --comp Phase0Probe \
     --edit studio/src/Root.tsx --from 'durationInFrames={150}' \
     --to 'durationInFrames={151}'

# 判据成本
node studio/out/p14_probe/invalidation_cost.mjs studio/src
```

探针脚本在 `studio/out/p14_probe/`（gitignored），
**放在 `studio/` 下是因为 ESM 要在那里解析 `@remotion/bundler`** ——
第一版放在仓库根直接 `ERR_MODULE_NOT_FOUND`。

**没有写任何 worker 代码，没有改 `render.mjs` 的清理逻辑，
没有实现分级渲染，没有删任何不是我自己造的目录。**

---

## 11. 给将来谁建这一项的话

判据已经钉死了，重估时请照着量，不要照着信：

1. **先证明有第二次可摊。** 现在没有 —— 生产管线一天渲一次全片。
   判据：`render_with_remotion.py:70` 每次都起新进程。
2. **磁盘那条会挡路。** 要长驻就得先放松 46 GB 事故的清理逻辑。
   判据：`test_a_finished_render_leaves_no_bundle_directory_behind`。
3. **改 `render.mjs` 之前先修未知 flag 静默忽略**（第 6 节）——
   一个静默忽略 flag 的入口接受长驻服务请求，是这类事故的配方。
4. **失效判据不贵（0.2ms），但必须存在** —— bundler 不 watch（第 2 节）。
   不要因为它便宜就跳过它，否则 worker 会拿旧 bundle 渲新代码。
   优先用内容 sha256（2.2ms）而不是 mtime（0.2ms）：
   实测一次内容为空的改动就会改变 mtime 指纹（第 2.3 节），
   mtime 判据会多付几次 1.2 秒的假失效。
5. **262 MB 常驻 + 800 MB 常驻磁盘** 是实价，不是零。
6. **未测的部分别当已测**：并发渲染 + 中途 re-bundle 的交叉
   （4.4 只测了"两个只读帧请求"）、draft 模式的分辨率-时间曲线（第 5.2 节）、
   re-encode 成本（P13 的 (c)）。这三项本项都没有数字。
