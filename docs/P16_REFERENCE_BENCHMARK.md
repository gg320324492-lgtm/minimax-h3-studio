# P16 — 参考视频 Benchmark：当初的「对齐」是什么，以及 12 个维度现在能不能判

> Work order: `docs/WORKORDER_P16_REFERENCE_BENCHMARK.md`. This file records what
> was measured, what was concluded, and what was deliberately NOT built.
>
> **一句话结论**：`reference_analyze.py` 缺的不是代码，是**输入**。参考片不在本机，
> 也不在仓库里；而账本里三处「对齐参考片」的表述，经查是**人眼看片 + 手工调 token**，
> **没有留下任何可复用的测量**。12 个维度里 9 个判 B（不可判定），0 个判 A。

---

## 1. 指挥窗口给的前提，逐条复核

指挥窗口说 `reference_analyze.py` 零实现。**复核为真**：

```
$ git ls-files | grep -i "reference_analysis\|reference_analyze"
(无输出)
$ find E:/Minimax-H3 -maxdepth 3 -name "reference_analy*"
(无输出)
```

全仓无此文件，无 `reference_analysis.json`。**P16.1 确实零产出。**

但本项要问的是另一件事：**账本里那三处「对齐参考片」，当初是怎么做的？**

---

## 2. 第 1 件事的答案：「对齐」是人眼看片 + 手工调 token，没有任何测量

### 2.1 三处表述的出处

| 账本位置 | 原文 |
|---|---|
| `UPGRADE_PROGRESS.md:65`（3.6） | 「`pipeline/examples/showcase_demo.json`：**对齐参考片 24-40s 的四类代表 scene**」 |
| `UPGRADE_PROGRESS.md:85`（4.3） | 「Scene A — KPI Hero（**参考片 24s**）」 |
| `UPGRADE_MASTER_PLAN.md:129`（P4） | 「复刻参考片 24–40s 视觉结构」 |

`:85` 的「24s」在代码里也有对应注释（**只是注释**）：

```
studio/src/templates/finance-showcase/scenes/BrowserStack.tsx:14
   * Scene 2 — Browser Stack (reference film ~26-30s)
studio/src/templates/finance-showcase/scenes/DataColumns.tsx:154
   * Scene 4 — Calendar / Data Grid (reference film ~34-38s)
```

### 2.2 溯源：这些数字是谁写的

`git log -S "参考片"` 只有三个提交，**全部是规划与实现文本，没有任何一次是测量**：

| 提交 | 日期 | 引入 |
|---|---|---|
| `71da3cd` | 2026-09-30 | P0 审计，**创建** `UPGRADE_MASTER_PLAN.md`（第 104 行「参考视频第 24 秒以后」） |
| `a707d31` | 2026-09-30 | P3 scene graph |
| `3cd20ff` | 2026-09-30 | P4 FinanceShowcaseWide |

**原始任务书已经不可考。** `71da3cd` 之前，transcript
（`de13ac51-0410-498f-a45e-da600163098e.jsonl`）的第一条 user 消息是
「你来担任这个项目新阶段建设的复验官 / 这是第一阶段内容：」—— **「第一阶段内容」之后
的内容在 transcript 里已经丢失**（该条 content 以这句话结束，紧接的就是 agent 自己的
回话）。所以 24s 这个数字**不是本项目测出来的**，它来自一个我们拿不到的外部输入。

### 2.3 决定性证据：那些数字没有任何脚本与之对应

四个 scene 的时间戳（24s / 26-30s / 32s / 34-38s）如果来自片源，应当能反查到一个
分析产物。**全仓反查的结果是零**：

```
$ git grep -n "26-30\|34-38\|参考片 24" -- . ':!docs/UPGRADE_PROGRESS.md'
docs/UPGRADE_MASTER_PLAN.md:129          ← 规划文本
pipeline/examples/showcase_demo.json:2   ← _note 字符串
studio/.../BrowserStack.tsx:14          ← 注释
studio/.../DataColumns.tsx:154          ← 注释
```

**四条命中，三条是散文，一条是注释。没有任何一处是计算结果。**

### 2.4 手工调的证据：token 是试出来的

`3cd20ff` 的 commit body 自述了调参过程（原文）：

> Rendered 801 frames at 1920x1080@60 in 22.8s (~35x realtime). **Fixed three
> layout defects found by inspecting frames**: absolutely positioned planes
> missing their centring transform, browser windows spaced so tightly their
> titles collided, and the KPI suffix overlapping the last digit.

**「found by inspecting frames」= 抽帧目检**。这不是测量，是看。这与账本 4.9 自己
记录的血泪完全一致（「布局问题本就不在单元测试能力范围内，靠抽帧目检」）。

而 `design/tokens.ts` 的颜色是另一条路径来的——**不是看片**：

```
studio/src/templates/finance-showcase/design/tokens.ts（源码注释）
   The reference language (premium fintech product film): near-black, warm
   off-white ink, one gold accent, and colour used only where it carries
   meaning. Less than 3 hues per screen.
```

**这些是规则陈述，不是量出来的数值。** PALETTE 里的十六进制值没有任何一处标注
「这是从片子里取的色」。

### 2.5 逐条交付（工单第 1 件事的要求）

| 项 | 答案 | 证据 |
|---|---|---|
| 当初的手段 | **人眼看片 + 抽帧目检 + 手工调 token** | `3cd20ff` commit body；`design/tokens.ts` 注释 |
| 是否有产物 | **否**。没有 `reference_analysis.json`，没有对照帧目录，没有任何片源派生数据 | `git ls-files` 反查零命中 |
| 产物在哪 | **不在**。P4 的产物是四份 `.tsx` 组件 + `tokens.ts`，它们是**复刻品**不是**测量** | `3cd20ff --stat` |
| 与 12 维度的差距 | **12/12 全无**。四个 scene 的 token 里没有一条能追溯到片源的数值 | 见第 4 节 |

> **⚠️ 这不是指控。** 当时没有 `reference_analyze.py` 要跑，也没有片源文件在手。
> 「看片 + 手调」在那个信息条件下是合理的做法。本项的价值是：**把这件事从账本的
> ✅ 里拿出来**——`3.6` 和 `4.3` 标为 ✅，读起来像「对齐已完成且可验证」，而实际上是
> 「对齐过一次，无法复现」。

---

## 3. 参考素材是不是同一部片：不是，而且两批素材都不是它

指挥窗口给了三批候选。逐一核实：

### 3.1 `ceo_mindread_ep01/01_reference/` —— **不是**（实测）

```
19M  27 个文件  三个子目录 ceo / intern / office
ceo/CEO_01.mp4      205830 字节
intern/INTERN_01.mp4 184876 字节
office/OFFICE_01_WIDE.mp4 279390 字节
office/OFFICE_02_DESK.mp4  268868 字节
```

**目视了 `ceo/CEO_MASTER_REFERENCE.png` 与 `office/OFFICE_MASTER_REFERENCE.png`：
真人在镜前的角色定妆照**（西装中年男性、深色办公室）。这不是运动图形产品片。

`ceo_mindread_ep01/scripts/gen_references.py` 的 docstring 自述了它是什么：

> Generate MASTER_REFERENCE images using **MiniMax-H3 R2V pipeline**. … We use the
> R2V workflow: take a generic reference photo as Picture 1 … We extract the first
> frame as our MASTER_REFERENCE.

**这批素材是 EP01 短剧管线的 AI 生成角色一致性锚点**，方向恰好相反——它是用模型
**生成**片子的输入，不是拿来**分析**的片子。

### 3.2 `experiments/_ref_analysis/` —— **不是**（实测，且这是个陷阱）

名字最像，但内容是另一回事：

```
cuts.txt  87 行切点，3.633s → 268.2s（约 4.5 分钟）
probe_liaozhai.py  docstring 第一行：
   """Style probe: can our H3 pipeline reproduce the 涛涛狐言《鬼新娘》 look?
```

**目视了 `f_162.png` 与 `f_31.png`：1958 年中国手绘动画**（水墨赛璐璐、古代人物、
宣纸底色）。帧尺寸 **1930×1080**（不是 1920）。

它的目的是**风格复现探针**（`probe_liaozhai.py` 建 t2v / r2v 两个 ComfyUI 图对比
我们的产出），不是产品片分析。**它确实是一次真实的「参考片分析」的残留——但分析的是
另一部片（动画片），而且没有留下 P16 需要的任何维度产物。**

> ⚠️ **这个发现值得记下来**：本项目**做过**参考片分析，做在 `liaozhai_demo` 上，
> 做在一部动画片上，产物是 `cuts.txt`（87 个切点）+ 11 张 `f_*.png` 抽帧 +
> 对比拼图。**它证明了方法可行，也证明了它与 P16 无关。**

### 3.3 片源本身：不在本机

有界搜索（`find E:/ -maxdepth 4`，排除 node_modules / conda / MATLAB /
DockerData / ComfyUI / Minimax-H3 / QQMusicCache）：**60 个 mp4/mov/webm，全部是
本项目自己的产出**（`promo_video` 的微纳米气泡宣传片 v2–v10、`H3_local_private`
的 EP01 分镜、`LivePortrait` 的合成 AI/LivePortrait）。另查了
`C:/Users/pc/{Downloads,Desktop,Videos,Documents,Music,Pictures}`：
`Desktop/设计短片/` 下是 **Codex 生成的 PNG 图像**，不是视频。

**`git ls-files | grep -E "\.(mp4|mov|webm|mkv|avi)$"` → 零命中**（媒体全部 gitignore）。

### 3.4 ⚠️ 顺带一个反直觉的事实：图谱的 `bpm` 也**不是**从片子里来的

`showcase_demo.json` 的 `bpm: 128.998` 看起来像是「卡点对齐到参考片音乐」。实测
来源是**另一条完全无关的音轨**：

```
studio/public/audio/bgm_beats.json
   bpm: 129.2
   beat_interval: 0.4644
   source: "mixtrack_Digital_Clouds.mp3"
   beats: 208 条
```

P9 提交 `41947f6` 的标题就是「the tempo in the graph was three beats a minute
wrong」——图谱原声明 126 BPM，与这条 Mixtrack 音轨的 129.2 差 3.00，最小二乘拟合
得 128.998。**这条 BGM 是本项目自己的音乐资产，与参考片无关。** 所以 12 个维度里
唯一的「量化对齐」也是对**自备音轨**做的，不是对片子的。

---

## 4. 12 个维度逐个裁定

裁定标准（工单第 2 件事）：**A** = 有输入、有仪器、**判据可定**；
**B** = 缺输入 / 缺仪器 / **判据定不出**；**C** = 本项目已有同口径的实测。

> **前提（适用于全部 12 个维度）**：本裁定**不含**「输入存在」这一层。
> `ceo_mindread_ep01/01_reference/`（真人定妆照）、`experiments/_ref_analysis/`
> （动画片探针）**都不是**参考片，**参考片本身不在本机也不在仓库**（第 3 节实测）。
> 因此**没有任何一个维度满足 A 的「有输入」**。下面仍然逐维度记录**除了输入之外
> 还缺什么**——因为将来片源补齐时，这些缺口会立刻显形，而那时再查一遍要重做全部分析。

| # | 维度 | 裁定 | 除了输入之外还缺什么 | 依据（实测，非引述） |
|---|---|---|---|---|
| 1 | **scene 边界** | **B** | **判据定不出**。切点检测在**动画片**上做过（`cuts.txt` 87 个切点），但那部片是连续手绘动画，边界是构图突变；产品片是**程序化图形**切换，帧间差分布完全不同 | `cuts.txt` 实测 87 行 / 3.633–268.2s。⚠️ 注意 `out/p13_probe/` 的 9 个有序帧目录**不是** scene 边界——它们是 6 对**重跑对照**（P24 语料），41 帧/21 帧 = 0.68s/0.35s |
| 2 | **时长** | **B** | **输入即判据**。总片长 82s、24–40s 段 16s 这两个数都需要片源；且「时长分布」需要知道有几场切 | 片子不存在。`showcase_demo.json` 的 13.35s 是**我们自己的**，不是参考的 |
| 3 | **色彩** | **B** | 仪器有（P22），**语料无**。`rule_contrast` 是**主题常量查表**，读 `themes.ts`，不读帧——换片子它给同一个数 | `visual_qa.py:652` docstring：「takes no frame, reads none, and returns the same table whatever is under inspection」 |
| 4 | **布局** | **B** | 仪器有（`measure_frame.py`），**但对齐口径无法定义**。没有片源，「对齐」这个词没有参照系 | `measure_frame.py` 存在；P6.2 铁律要求量像素，但量「与谁对齐」需要片源 |
| 5 | **运动** | **B** | 有一个孤立探针 `experiments/motion_analysis.py`（帧间差 + FROZEN/LOW/moving 阈值），但它是 **EXPERIMENTAL**，路径硬编码 `E:\Minimax-H3\work_frames\motion`（该目录不存在），阈值是拍脑袋的常数不是量出来的 | 实测脚本存在，`FRAMES_DIR` 指向不存在的目录 |
| 6 | **相机** | **B** | 相机在**我们的图谱里是声明式的**（`camera.translateZ` / `rotateY` 等轨道）。要从片子里反推相机运动需要光流/单应估计——**本项目零此仪器**，且判据（怎么算「同样的相机语言」）无定义 | `CameraRig.tsx` 是消费者；`git grep` 无任何片源相机估计代码 |
| 7 | **图表** | **B** | 有全套自研图表组件与几何仪器（`chart_geometry.py`），但那是**复刻侧**的。要从片子里数「有几张图、什么类型、什么布局」需要先有帧 | P7 交付了 9 种图表；**这 12 个维度指的是片子里有什么，不是我们有什么** |
| 8 | **字体** | **B** | **判据定不出**。`rule_font_size` 测的是**我们声明的字号是否被渲染出来**（需要 `--declared-px`）；从片子里反推字体需要字形识别（OCR/字体分类），本项目零此仪器 | `visual_qa.py:617` 签名 `rule_font_size(a, declared_px=None)`——没有 declared 就 UNVERIFIABLE |
| 9 | **转场** | **B** | **判据定不出，且 schema 未约定词汇**。`Transition` schema 的 `in` / `out` 是**自由 `string`**（不是 enum），所以「片子里有几种转场」这个问题连答案的类型都没有 | `showcase-v1.schema.json:221` — `"in": {"type": "string"}`，无 enum |
| 10 | **密度** | **B** | 仪器无，判据无。「密度」可以指元素数/帧、面积占比、运动量——**三个不同的量**，没有一个被定义 | `git grep density` 在 `studio/scripts/` 下**零命中** |
| 11 | **亮度** | **B** | 仪器有且已实测（P22: **531,100,800 像素**；P23: **297 个内部样本**二阶差分），**但语料是 `out/p13_probe/` ——我们自己的渲染帧**，不是片子。**口径不同，不可复用** | P22 §4 实测语料「corpus themes: `{'premium-dark': 333}`」——全是自己的 premium-dark |
| 12 | **beat** | **B** | 判据**有**（P9 BeatGrid + 守卫），**仪器有**（`beatGrid.ts` / `beatSnap.ts`），**但唯一语料是自备音轨** | `bgm_beats.json` 的 `source: "mixtrack_Digital_Clouds.mp3"`（第 3.4 节） |

### 4.1 汇总

| 裁定 | 数量 | 维度 |
|---|---|---|
| **A：现在能分析** | **0** | —— |
| **B：不可判定** | **12** | 全部 |
| **C：已存在同口径** | **0** | —— |

**⚠️ 为什么没有一个判 C**，尽管工单列了三条「本项目已有」：

工单的警告是准的——**「本项目已经有某个测量」不等于「它属于 P16 的那个产物」**。
逐项核对结果是**三条全部口径不同**：

| 工单说「已有」 | 实际语料 | 是不是 P16 的产物 |
|---|---|---|
| 亮度：P22 的 531,100,800 像素 | `out/p13_probe/` 的 333 帧，**全部 `premium-dark`**，是我们自己的渲染 | ❌ **不是**。测的是我们的帧的像素分布，不是片子的 |
| beat / 时长：P9 BeatGrid 已完成 | `studio/public/audio/bgm_beats.json`，源是 **Mixtrack 自备音轨** | ❌ **不是**。测的是我们的音乐，不是片子的 |
| 色彩 / 对比度：P22 的 24 对 WCAG | `rule_contrast` 读 `themes.ts` 常量，**不读帧** | ❌ **不是**。换任何片子它给同一个数 |

**三条「已有测量」都是对我们自己产物的测量。** 它们证明了仪器可用，
但**没有一条测过参考片**，因为参考片从来不在手上。

---

## 5. 交付物为什么是这份文档而不是 `reference_analysis.json`

工单写明「不要为了让 `reference_analysis.json` 存在而造一个空壳」，
且「若大部分维度都判 B，交付物就是那份逐维度判定 + 记录文档」。

**12 个维度全部判 B，所以交付物就是第 4 节那份逐维度判定。**
没有写 `reference_analyze.py`（工单第四节明令禁止），
没有造 `reference_analysis.json`。

**这是本项目接受的第五次「实测说不出想要的结果」**（前四次：collision /
rule_duplicate / rule_contrast_frame / flicker），且与 P17 同一裁定路径。

### 5.1 P16 解锁需要什么

按依赖顺序，每一步都能被独立验证：

1. **片源入库** —— 缺这个，后面全部 B 变成「待判」。落点建议
   `experiments/_ref_analysis/` 之外的独立目录（现有那个是动画片探针，
   名字已经骗过本项一次，见第 3.2 节）。
2. **片源身份记录** —— 「哪一部、时长、帧率、来源」写进仓库。
   现在连**片名**都无法确定（第 2.2 节），这是比「缺文件」更根本的缺口。
3. **12 个维度的判据先行** —— 第 4 节已标出哪些**除了输入还缺东西**：
   相机（无仪器）、字体（无仪器）、密度（无仪器 + 无定义）、
   转场（schema 无枚举）、scene 边界（判据未定）**这五个即使拿到片源也仍然判 B。**
   另七个补上片源后可直接进入 A 的设计。

---

## 6. 与账本的关系

`docs/UPGRADE_PROGRESS.md` **未修改**（工单第四节：账本由指挥窗口统一更新）。
本项请求账本做三处订正，**留给指挥窗口裁定**：

| 位置 | 现表述 | 本项实测 |
|---|---|---|
| `:65`（3.6） | 「对齐参考片 24-40s 的四类代表 scene」+ 状态 ✅ | 对齐发生过，**但方式不可复现且无产物**。✅ 建议降级为「四类 scene 已实现（对齐口径：人眼 + 手调）」 |
| `:85`（4.3） | 「Scene A — KPI Hero（参考片 24s）」+ 状态 ✅ | 「24s」**无任何脚本对应**，来源不可考（第 2.3 节）。建议标注为「来源不可考」 |
| `:438`（P16） | 状态 ⬜，两行空 | **维持 ⬜ 正确**，但原因应从「没做」改为「**缺输入 + 5 个维度缺判据/仪器**」 |

⚠️ **未修正的理由**：工单第四节明令「不要修改 `docs/UPGRADE_PROGRESS.md`
（账本是指挥窗口的）」。且工单第一节已警告**账本本身是待验证的主张**——
本项恰好在账本里查出一处「来源不可考」的表述（`:85` 的 24s）。
**由指挥窗口改，而不是执行 agent 改。**

---

## 7. 本项的方法论，与它复现的一次旧伤

**这次栽在同一个地方**：账本写「✅ 对齐参考片」，读起来是一个**已验证的事实**，
实际是一个**不可复现的回忆**。工单第一节已经警告过要查证，本项查完的结论是
**警告是对的，而且账本在这一处确实错了**。

`UPGRADE_PROGRESS.md` 自己记录过两次同类事故：

- **P4.9**：「第一次「已修」是假的……未复验就写下了「已修」」
- **P0 check_contract 假通过**

本项是第三次：**「已对齐」也是假的**——不对齐从未发生，而是一次性的、无记录的
人眼判断被写成了 ✅。

**记账规则建议给指挥窗口**（不在本项授权范围内，仅记录）：
任何 ✅ 声称「与某外部物对齐」的条目，应同时给出**可复现的产物路径**
或**明确的「一次性判断，不可复现」标注**。否则下一个读到账本的人
（本项就是）会把它当成事实——账本的可信度正是靠这个维持的。

---

## 8. 守卫

逐维度裁定本身由 `tests/test_p16_reference_is_not_an_input_free_measurement.py`
守住（**9 项**）。它守的是**裁定会失效**，不是「某个文件存在」。

### 8.1 工单那个问题的答案

> 「如果明天有人把参考分析写出来，这份测试会怎么反应？」

**答案是一个明确的失败**，而且是被**两个不同的断言**各守一次：

| 场景 | 反应 |
|---|---|
| `reference_analysis.json` / `reference_analyze.py` 被提交或落盘 | 红色，消息写明**「裁定过期了，不是裁定错了」**，并列出该重判的文档 |
| 任何媒体文件被提交进仓库 | 红色，列出文件名（该事实决定全部 12 个维度） |
| 12 维度表少一行 / 汇总数与表对不上 / 文档开始声称「有可复用测量」 | 红色，且消息点名是哪个维度 |

第一行的措辞是刻意的：**分析写出来不是成就，是一次必须由人重新裁定的触发器。**
写成「该文件已存在」的守卫会在分析落地的当天变绿，并且永远不会问那 12 个 B 怎么改。

### 8.2 变异结果（实测，`-rf` 原始输出见交付报告）

| 变异 | 期望 | 实测 |
|---|---|---|
| 判定声称存在可复用测量 | 红 | ✅ **红**（`test_...how_the_alignment_was_actually_done`） |
| 汇总声称 A=1 | 红 | ✅ **红**（`{'A': 1} != {'A': 0}`） |
| 删掉一个维度的判定行 | 红 | ✅ **红**（`11 == 12`） |
| 对齐声称可复现 | 红 | ✅ **红** |
| **守卫判据永远通过**（触发器） | 红 | ✅ **红** |
| **守卫判据永远通过**（媒体否定） | 红 | ✅ **红** |
| 弱化 12 行计数断言 | 红 | ⚠️ **存活** —— 见 8.3，判定为**冗余而非漏洞** |
| 弱化自检断言 | 红 | ⚠️ **存活** —— 同上 |

### 8.3 两条存活项：判定为「真冗余」，不去造 contrived 输入杀它

`row_count_weakened` 把 `assert len(rows) == 12` 改成 `<= 12 or True`，套件照样绿。
**实测它为什么不构成漏洞**：

- 独立跑变异后的守卫，对删行的文档，它**仍然拒绝**，走的是下一条断言
  （`['转场'] appear in P16.1 but hold no row`）；
- 而那条断言**是被见证测试覆盖的**（`test_the_verdict_table_guards_...` 里显式
  断言 `'转场' in dropped_alarm`）。

**结论：这两条断言是冗余的，不是失效的。** 删掉一条，另一条仍然抓住同一件事。
为杀一条冗余断言去造 contrived 输入，正是工单禁止的（「不要造 contrived 输入去杀无效变异」）。

### 8.4 本项在守卫上栽的三次，都记在这里

1. **弱断言存活（真漏洞，已修）**：`assert '**0**' in summary and '**12**' in summary`
   被「A 从 0 改成 1」变异穿过——因为 C 行也是 `**0**`，两个 `**0**` 行共用一个子串。
   改成按行解析每个裁定的计数。
2. **散文冒充判定（真漏洞，已修）**：`d not in text` 是全文子串测试，
   「转场」在 §5.1 的散文里也出现，所以删掉表格里的判定行它照样绿。改成解析判定表的行。
3. **自检测的是副本（真漏洞，已修）**：自检调用的是自己那份谓词副本，
   而变异改的是守卫里的调用点——五个「永远通过」变异全部存活（7 passed, exit 0）。
   改成守卫与自检调用**同一个** `_analysis_artifacts` / `_media_files`。

以及一次**红得对但理由错**（已修）：见证测试把 mutant 写到 `tests/` 之外的目录，
`ROOT` 因此指向别处，2 failed + **4 skipped**，看着像杀死其实是找不到仓库；
改成写进 `tests/` 本目录并在 `finally` 删除。

> **仍然是护栏的护栏**：文件内部无法阻止有人把它改坏，能做到的是让这件事**不局部**——
> 关掉警报现在要动两处，而第二处本身就是「盯着第一处」的那条测试。这一点写在
> 守卫的 docstring 里，因为假装能做到更强是本项目吃过的亏。