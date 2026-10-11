# P49 — 十个场景的相机声明了「多久」却没声明「往哪走」

> 交付报告。**不含放行/退回裁定** —— 那是指挥窗口的事。
> 守卫：`tests/test_p49_camera_move_is_not_a_freeze.py`

---

## 一、根因判定：**数据问题**，不是架构问题

**`charts_demo.json` 漏写了相机通道；渲染器一直是对的。**

依据三条，全部实测：

1. **渲染器的通道词汇是交付过、在用的。** `pipeline/examples/showcase_demo.json`
   四个场景全都带通道：`s01_kpi` `scale:[1.06,1.0]`、`s02_dash`
   `translateZ:[-220,0] + rotateY:[-9,0] + rotateX:[5,0]`、`s03_columns`
   `rotateX:[12,2] + translateY:[60,0]`、`s04_calendar` `scale:[1.04,1.0]`。
   ⇒ 通道机制存在、可用、被另一个交付图谱使用。**不是架构缺件。**
2. **没有任何文档要求「无通道时应当有默认漂移」。**
   `docs/UPGRADE_MASTER_PLAN.md` 全文检索相机只命中 Three.js 边界（:205）
   与组件清单；`docs/P16_REFERENCE_BENCHMARK.md:215` 明确写
   「相机在**我们的图谱里是声明式的**」；`CameraRig.tsx` 的 docstring 说的是
   **分层视差**（多层不同 translateZ + 一个相机变换），**不是**「没有通道时
   该漂一点」。⇒ **找不到依据，故不编造默认运动。**
3. **`camera.focus` 本身就是一个哑声明**（本次顺带发现，未修）：
   `showcase-v1.ts:105` 声明了 `focus`，`cameraStateAt` 里**没有 focus 项**，
   CameraRig 也不读它。⇒ 补一个「默认 focus 行为」等于再造一个没人读的声明。

---

## 二、`motion.preset` 是不是第八个哑声明？——**在当前图谱上是**

核实过程（不是引述）：

- 全仓 `motion?.preset` 的消费点只有一处：
  `CameraRig.tsx:98` → `cameraMoveFrames(...)` → `ct`。
- `MOTION.profiles[x]` 只被 `primitives.tsx:76` 的 `profileOf(profile)` 读，
  而 `Stagger` 的 `profile` 是**组件自己的 prop，默认写死 `'premium'`**，
  **从来不接 `scene.motion.preset`**。
- 图表场景（`Chart.tsx`）**根本不用 `Stagger`**，mark 由
  `lifecycleAt` 的 `opts.enterFrames/staggerFrames`（默认 34/2）驱动。

⇒ 在 charts_demo 上，`motion.preset` 的**唯一**输出是 `ct`，而
`ct` 只喂给 `track(channel, ct, fallback)`；**十个场景一个通道都没有**，
`track` 全部回落到 fallback。**它被读取、它驱动了一个值、那个值乘了个零。**

⚠️ 说准一点：`preset` **不是「没人读」**——`test_p42` 之外还有
`beat/bindings.ts:166` 的 `camera-settle` 查询面读它。所以它是
**「读到了但乘零」**，属于哑声明的第三层（子键粒度），与
`docs/DIRECTOR_SCOPE_VERDICT.md:257` 已记的 `cameraLanguage.durationSeconds`
同一族 —— 那一条我也核实了：**`styleBible.tsx:32` 声明、`:79` 合并，
CameraRig 只读 `cameraDefaults.perspective`，`durationSeconds` 零读者。**

---

## 三、死的 1.13 s：两个独立问题，分开答

### (a) 是「相机没动」—— **这是缺陷，可修**
- `lifecycle.ts` 的 `focus` 相写死「**Nothing moves**」，
  `highlight` 相写死「held, not animated」。
  ⇒ **入场结束后标记静止，是设计如此，不是缺陷。**
- 所以本可以做「静止」的唯一东西是相机 —— 而它没有通道。**这才是缺陷。**

### (b) 是「入场结束太早」—— **不是**
实测 c01（150 帧 / 60fps）：

| 量 | 值 |
|---|---|
| `exitFrames` = `max(6, round(150*0.08))` | 12 |
| `exitStart` | **138** |
| `entranceFrames` = `min(round(150*0.34)=51, needed, 138)` | **51** |
| 最后一次标记运动（emphasis 到 1.0） | **帧 69**（`bSettle = 51+18`） |
| `cameraMoveFrames('premium',150,60)` = `2.6*60` | **156** |

**⚠️ 回答指挥窗口的问题：156 > 138 > 150，运动窗不是「超完就白搭」，恰恰相反 ——
它比整个场景还长 6 帧，所以 `ct` 在 `exitStart=138` 时才走到
`138/156 = 0.885`，相机**仍在动**。这正是加通道能填上死区的方向。**

反向对照（变异 M2）：把 preset 换成 `energetic`（`0.55*60=33` 帧），
运动在帧 33 就走完 ⇒ 死区**只是挪了位置**，帧 33 之后直到 138 全静。实测守卫变红。

---

## 四、十处各给了什么通道，理由是什么

**全部十处：`{"perspective": 1600, "scale": [1.04, 1.0]}`。**

### 为什么是 `scale` 而不是 `rotateY` —— 实测，不是品味

第一版我确实给十个场景都加了 `rotateY: [-3,3]`（参考片相机就是 orbit，
`P37` 测到 51–55s 有真 3D 相机运动）。**在柱图上量出来是错的**，弃用：

```
五根柱的中心 x（c01_bar，帧 137）
  只有 perspective（缺陷态）  314.5  648.0  981.5  1315.0  1647.5
                              间距 333.5 333.5 333.5 332.5   ← 均匀
  rotateY: [-3, 3]           304.0  645.5  981.5  1311.5  1636.0
                              间距 341.5 336.0 330.0 324.5   ← 右侧压缩 5%
  scale: [1.04, 1.0]         289.0  636.0  982.5  1329.0  1676.0
                              间距 347   346.5 346.5 347     ← 均匀
```

`rotateY` 把画面变成**梯形**：相邻柱距从近到远压缩 5%，
**基线不再水平**，且强调柱的 `61.4M` **标签被顶出画面**。
**柱子用长度编码数值 —— 这不是风格选择，是数据失真**，
与账本里悬而未决的「s03 `rotateX:[12,2]` 把竖柱剪斜」同族。

`scale` 是刚性变换：柱→标签偏移实测 `[0.0, -0.5, 0.5, 0.5, 0.5]` px，
柱距按作者系数等比缩放。**它是八个通道里唯一不会让「长度即数值」失真的。**

### 为什么是 `[1.04, 1.0]`

- **是交付过的字面值**：`showcase_demo.json` `s04_calendar` 就是 `scale:[1.04,1.0]`
  （`s01_kpi` 是 `[1.06,1.0]`）。**不是我编的数。**
- **向内收（settle inward）**：画面只会变小，**结构上不可能裁切** ——
  而 `rotateY` 那版实测就把标签裁掉了。
- 密集数据构图（calendar 网格）比单个 hero 数字（1.06）更接近，
  故取 1.04。

### 「十个场景一个值」—— 这是**规则的结论**，不是省事

规则是**按图表类型**给的：这里十个场景都是「单一刚性平面 + 标记编码数值」，
上面那条实测说 `scale` 对这种平面正确、`rotateY` 不正确。
**规则对十个都成立，所以答案对十个都相同。**
若某个场景的标记**不**编码数值，它可以走别的通道 —— 这里不存在这种场景。

⚠️ **诚实交代**：我第一版选「十个场景同一个值」的原因是
**我找不到逐场景的依据，拿统一值来降低自己猜错的概率**。
那是避险，不是推理，我当时没有写出来。指挥窗口驳回得对。
真正给出依据的是上面那张柱距实测表。

### 有几个场景真的需要相机运动？—— **十个都需要（实测）**

在**未修复**图谱上逐场景测 `f71 → f137` 的变化像素：

| 场景 | 修复前 | 修复后 |
|---|---|---|
| c01_bar | 0 | 75855 |
| c02_line | 0 | 30865 |
| c03_area | 0 | 43663 |
| c04_slope | 0 | 68801 |
| c05_bubble | 0 | 18405 |
| c06_heatmap | **9434** | 130468 |
| c07_rank | 0 | 42694 |
| c08_volume | 0 | 83521 |
| c09_sparkline | 0 | 11671 |
| c10_bar_long | 0 | 94129 |

**九个场景是 0。** `c06_heatmap` 的 9434 px **不是**相机在动 ——
密集测下来它的 changed 在**帧 ~84 归零**：18 个格子把入场拖得比 c01 的 69 帧更晚，
f71/f137 这一对量到的是**入场尾巴**，不是静止相。
**⇒ 十个场景都冻结，只是冻结的起点不同（c01 ≈69，c06 ≈84）。**
这也是守卫渲染**整段窗口**而不是采两帧的原因。

---

## 五、逐场景静止段（无损实测，非成片）

| | 帧 0–137 相邻帧对 | 冻结对数 | 最小 changed | 读数窗内最小 |
|---|---|---|---|---|
| **修复前 c01_bar** | 96（45–140） | **85** | **0** | **0** |
| **修复后 c01_bar** | 137（0–137） | **0** | **5981** | **5981** |
| **修复后 c09_sparkline** | 137（0–137） | **0** | 617 | **1457** |

修复前 c01 逐帧扫描：最后一处变化在 `51→52`（152 px），
`53→54` 起连续 0，`55→56` 有一个 152 px 孤立毛刺，
**到 `137→138` 全程 0**，`138→139`（退出）才 329026 px。
⇒ 冻结覆盖 **52→138 = 86 帧 ≈ 1.43 s**。
（工单给的「70→138，68 帧，1.13 s」是采样窗口；密集扫出来起点更早。）

---

## 六、守卫

`tests/test_p49_camera_move_is_not_a_freeze.py`，**进套件、无环境开关**。

| 测试 | 作用 | 需渲染 |
|---|---|---|
| `test_every_scene_declares_a_camera_channel_that_moves` | **逐场景**结构断言 | 否 |
| `test_no_two_adjacent_frames_between_start_and_exit_are_identical` | 无损帧，`0..exitStart-1` **每一对**都必须变化 | 是 |
| `test_the_dead_pair_predicate_rejects_frozen_frames` | 判据双向自测 | 否 |
| `test_the_channel_predicate_rejects_a_constant_and_accepts_a_move` | 通道判据自测 | 否 |
| `test_a_scene_with_only_a_constant_camera_is_reported_dead` | 结构判据自测 | 否 |

- **跑在无损帧上**：`bin/still.mjs`，1920×1080，逐像素比较。
  `rule_freeze` 跑在成片上（226 kbps，冻结段仍有 281–2329 px 编码抖动）
  返回 30/30 PASS —— **守卫绝不复用那个输入。**
- **窗口来自图谱**：`exitStart` 取 `visual_qa.exit_window_start`（该镜像已由
  `test_p42` 断言等于 `charts/lifecycle.ts`，不重造第二份）。
- **不把「查不了」当过**：渲染失败**重试 4 次**后**失败**，
  绝不返回 PASS；缺任何一帧直接断言失败（本项就被自己的缺帧骗过一次，
  见下）。node 缺失时 **skip 并说明未查**，不是 pass。

### 三条变异（`-rf` 原始输出）

| 变异 | 期望 | 实测 |
|---|---|---|
| **M1 删掉相机通道**（还原冻结） | 红 | `2 failed` —— 结构测试 + 像素测试**都红**，像素报 `83 adjacent frame pair(s) pixel-identical, first at [(53,54)]` |
| **M2 `preset: energetic`**（运动帧 33 走完，死区**挪位置**） | 红 | `1 failed` —— **只有像素测试红**，结构测试绿（通道还在）。这正是专抓「换个地方静止」 |
| **M3 判据恒真**（`_dead_pairs` → `return []`） | 红 | `1 failed` —— 像素测试**变绿**（证明恒真判据对主断言不可见），自测抓住：`assert [] == [(0, 1)]` |

每条变异后从**字节快照**复原，收尾核对 sha256：**两次均 `YES`（逐字节相同）**。

---

## 七、未修的相邻缺陷（只登记，不在本项范围）

1. **`camera.focus` 无消费方** —— `showcase-v1.ts:105` 声明，
   `cameraStateAt` 无此项，CameraRig 不读。补行为＝造新哑声明，**故不补**。
2. **`bible.camera.durationSeconds` 无消费方** —— `DIRECTOR_SCOPE_VERDICT.md:257`
   已登记，子键粒度哑声明。
3. **`beat/bindings.ts:166` 的 `camera-settle` 在 150 帧场景上返回帧 156**，
   即「相机在场景结束后才安定」。`showcase_demo` 的 229 帧场景无此问题
   （156 < 229）。charts_demo 若改用别的场景长度会踩到。
4. **`docs/P48_REACCEPTANCE.md` §四.1 的数字现在是修复前状态** ——
   该文件按工单只读，未改；账本由指挥窗口更新。

---

## 八、我的操作失误（如实记录）

1. **「十个场景一个值」是避险，不是推理。** 第一版选统一 `rotateY` 的理由是
   「我找不到逐场景的依据，用统一值降低猜错概率」—— 当时没写出来。
   真正的依据是后来那张柱距实测表；`rotateY` 已被实测否决。
2. **「查不了就当过」——我自己犯过一次。** 一次整段渲染失败（我重定向了输出），
   `grep -c "changed=0"` 返回 **0**，看起来是「零冻结对」。
   实际那一帧**根本没渲出来**，`measure.py` 只比较存在的文件。补查发现
   **138 帧里缺 21 帧（117–137）**。守卫里因此加了
   「每个期望帧都必须存在」的断言。
3. **`c01_rotateY.json` 只改了 c01，我拿它去量 c09/c06**，得出一组假的
   `changed=0`，差点当成「rotateY 对稀疏图无效」写进报告。发现后重做。
4. **变异脚本的还原校验用 `git status --porcelain`**，把**并行 agent** 对
   `test_p42` 等文件的改动算成「没还原干净」，误报一次。已改为只比对
   我自己那两个文件的 sha256。
5. **`out/p49_probe/mk_variant.py` / `apply_channel.py` 是我写的一次性脚本**，
   放在 `out/` 下（gitignore），**没有**复制任何帧/图进仓库。
6. **第一次全量测试我报了「`2 failed`」并下了结论，后来发现那是并行 agent 正在
   改文件造成的**，不是我的回归。**我在基线跑的时候就撞过一次同样的假红，
   却第一次没有先怀疑并发就往下走。** 重跑单跑即过。
7. **第一次 `apply_fix.py` 把文件从 CRLF 写成混合换行**（原文件 394 处 CRLF、
   0 处裸 LF，我插入的 70 行是裸 LF）。`git diff` 显示整块替换才暴露出来。
   已统一回 CRLF 并用**字节计数**复核（434 CRLF / 0 裸 LF）。
8. **scratch 用相对路径时，node 在 `cwd=studio` 下解析**，`--props` 指向
   `studio/out/...` 找不到文件；第一次渲 138 帧时我用了
   `>/dev/null 2>&1`，把失败吞掉，又顺手把一个 `grep -c` 的 0 当成了结果。
   **这是第 2 条那次「查不了就当过」的直接成因。**

---

## 九、文件清单与 sha256

### 全量测试

标准跑法（`--ignore=test_take_selection_behaviour.py`），**共跑了 4 次**，
如实记录 —— **数字随并发变，这本身是结论的一部分**：

| 次数 | 结果 |
|---|---|
| 开工前 | `2 failed, 750 passed, 6 errors`（并行 agent 正在改 `test_p42`） |
| 改图谱后 | `2 failed, 770 passed, 4 errors`（两个 `test_p48` 因我的修复变红，已修） |
| 复跑 | `1 failed, 771 passed`（残留 `render-*` bundle 来自**别人的** `render.mjs`；单跑即过） |
| **并发清空后** | **`766 passed, 4 skipped, 0 failed, 6 errors`** |

最后一遍的 6 个 error **全部在 `test_chart_type_defaults_are_real.py`**，
原因逐字为 `ENOBUFS` / `Timeout`（日志里 18 次 ENOBUFS）。
**该文件我没有碰过**；单跑 `11 passed in 26.41s`。
**⇒ 这是本机在并发渲染下的已知假红（工单与 P48 都记过），
不是我引入的回归，但也不该被当成「通过」——它报的是 error，不是 pass。**

基线是 `757 passed, 4 skipped`；现在 `766 passed`，
净增 **+9**：本项守卫 5 项 + P51 那批（并行 agent 的，不是我的）。

| 文件 | 动作 |
|---|---|
| `pipeline/examples/charts_demo.json` | 改（十处加 `scale: [1.04, 1.0]`） |
| `tests/test_p49_camera_move_is_not_a_freeze.py` | 新增 |
| `tests/test_p48_reaccept.py` | 改（两个测试，见下） |
| `docs/P49_CAMERA_MOTION_REPORT.md` | 新增（本文件） |

**`tests/test_p48_reaccept.py` 为什么动**：P48 那两个测试断言 c01
**就是**冻结的，而我的修复让它不成立了。**该文件自己的失败信息写着**
「If this is now fixed, update this guard AND the ledger — the freeze was a
real finding」；docstring 也写着「Re-derive the numbers ... do not delete
the check」。所以按它自己的指示：**重测数字、不删检查**。
- 测试 1 反转为断言**不再冻结**，填入实测的 **7995 px**（不是猜的）。
- 测试 2 **与影片状态解耦**：改用「一帧与自己配对」造出真冻结对。
  它要证明的是**仪器**（`rule_freeze` 会被 h264 抖动骗过），
  不该依赖影片当前是否冻结 —— 否则 P49 一修它就失去意义。

**sha256（开工记录 vs 收尾）**

| 文件 | 开工 | 收尾 |
|---|---|---|
| `CameraRig.tsx` | `60dda4b1…9cc553` | `60dda4b1…9cc553` **未改** |
| `design/tokens.ts` | `607b6c7b…d3e1df` | `607b6c7b…d3e1df` **未改** |
| `charts_demo.json` | `6bee91ff…6b7596` | `61620122…a1d8fc` 已改 |

⚠️ **`tokens.ts` 未改的理由**：无需改。`cameraMoveFrames` 的语义
（「premium = 2.6 s」）是对的，且工单第 2 条要求**不得改 `premium` 语义**
除非裁定必须改 —— 实测证明 156 > 138 的重叠正是需要的，不需要动。
**因此也没有测试因为它变红。**

---

## 十、磁盘纪律

- 全部输出在 `E:\Minimax-H3\out\p49_probe\**`；
- `TMPDIR`/`TEMP`/`REMOTION_SCRATCH_DIR` 指 E 盘各自 scratch；
- `--public-dir` 指**空目录**（避免每个 bundle 复制 773 MB `studio/public`）；
- 未触碰 `studio/.remotion/water-renewal-bundle`（1.5 GB，非本项）；
- `out/charts_demo.mp4`、`out/p45_vlm/**`、`out/p48_reaccept/**` **只读**；
  **未跑 `p45_control_render.py`**（其输出路径硬编码在 `out/p45_vlm/**`）。