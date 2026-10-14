# 执行指令 — 1.3 / 10.2 第二阶段：VLM 判据的**读数准确率**实测

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **本项不建任何东西。本项只做一次测量，测量结果决定这条路开不开。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `f8f6d52`（已推送） |
| 基线 | **`719 passed, 4 skipped`**（指挥窗口刚实测；⚠️ 历史基线数字已过期过，见第五节） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**（cv2 只装在 3.10）。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**（GBK 控制台会把省略号显示成替换字符，
P40 那次差点被当成真的 U+FFFD）。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，命令以 `cd E:/Minimax-H3 &&` 开头。

**⚠️ `git add` 用显式路径**，不要用 `-A` 或 `.`。
**⚠️ 工作树当前是干净的** —— 不再有"归属不明的既有改动"（那批已在 `0b80d77` 提交）。
**但你渲染时可能自己制造未提交文件，收尾要清干净并说明。**

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. P41 留下的底座

`studio/scripts/vlm_critic.py`（**488 行**）。关键接口：

| 符号 | 作用 |
|---|---|
| `expected_strings(scene)` | 从图谱 scene 算出**应当出现在画面上的字符串** |
| `probe_text(path, text)` | 拿一张帧问 VLM 有没有那串文字 |
| `parse_verdict(text)` | 解析 VLM 的回答 |
| `unavailable_reason(...)` | **单一裁决点**：什么时候报 UNAVAILABLE |
| `assert_reproducible(probe, times=2)` | 同一问题问两次，比对是否逐字相同 |
| `rule_frame_shows_text(probes)` | 主规则：画面上有没有该有的文字 |
| `FrameProbe` / `ask_vlm` / `format_value` | 其余部件 |

⚠️ **它已经有 UNAVAILABLE 路径与可复现性断言** —— 这两条是 P41 的主要成就，**不要拆**。

### 2. 本机 VLM

ollama 在跑（`http://127.0.0.1:11434`），已装 `qwen2.5vl:7b`（6.0 GB）。
**冷加载约 64 秒；驻留后约 0 秒。**

⚠️ **`ollama` 是外部进程，随时可能不在** ——
**本项的第一件事就是先测它在不在，并把"在/不在"写进报告。**

### 3. ⚠️ P41 那次 0/12 的结论，**指挥窗口已查明是选错了样本**

P41 在 `c02_line` 上实测 0/12 命中，指挥窗口当时记为"`showValues: false`、值从未被画"。

**指挥窗口本次实测十个场景的 `showValues`：**

```
c01_bar       showValues=True    n=  5  fmt=compact  [48200000, 39900000, ...]
c02_line      showValues=False   n= 12  fmt=int      [22, 31, 28, ...]
c03_area      showValues=None    n=  8  fmt=int      [12, 19, 16, ...]
c04_slope     showValues=None    n=  0  fmt=int      []
c05_bubble    showValues=True    n=  6  fmt=None     [12, 28, 45, ...]
c06_heatmap   showValues=None    n=  0  fmt=int      []
c07_rank      showValues=None    n=  0  fmt=compact  []
c08_volume    showValues=None    n= 12  fmt=None     [18, 34, 26, ...]
c09_sparkline showValues=None    n= 12  fmt=None     [22, 31, 28, ...]
c10_bar_long  showValues=True    n=  8  fmt=int      [31, 48, 39, ...]
```

**⚠️ 三点，全部影响本项设计：**

**(i) `showValues` 是三态**（`True` / `False` / 字段缺失）。
**六个场景根本没有这个字段。** 而 `charts/options.ts:113` 的默认值是
`showValues: false` ⇒ **字段缺失 ⇒ 不显示数值**。
⇒ **十个场景里只有三个（`c01_bar` / `c05_bubble` / `c10_bar_long`）会画出数值。**

**(ii) 数据在 `content.chart.values`**，不是 `chart.series`
（P41 之前我猜错了位置，⚠️ 你别沿用任何"series"的假设，先自己读图谱）。

**(iii) ⚠️ `options.ts:130-144` 记着一条血案**：
> *「一个声明面能让一个能工作的选项变成惰性。」*

**⇒ `showValues: True` 不等于数值一定画出来了。** 图谱说了 `True`，
渲染器可能仍然不画（`TYPE_OPTIONS` 表、类型分派、emphasis 逻辑都可能吞掉它）。
**⇒ 你必须以**渲染出来的像素**为准，不要以图谱为准。**

### 4. ⚠️ 上一个 agent 踩过的坑，别踩

- `studio/public/jobs/showcase_demo.json` 是**过期 staging 副本**（仍带 P11 已删的 `ease` 键），
  渲染会抛 `Unrecognized key: "ease"`。**tracked 图谱在 `pipeline/examples/` 与
  `pipeline/graphs/`**（⚠️ **是 `graphs/` 不是 `examples/`**，p29 那张图在 `graphs/`）。
- ⚠️ **`still.mjs` 传局部帧号还是全局帧号**：裁剪后的单场景图谱要用**局部**帧号，
  直接传全局帧号会触发 `validateFrame` 报错。
- **输出到 E: 盘**（`out/` 下），⚠️ **不要覆盖 `out/*.mp4`**（P27 证据目录）。

---

## 二、你要交付的**唯一**一件事：**读数准确率**

### ⚠️ 本项的判据已经存在，**不要重新设计判据**

P41 已建好判据：**「图谱说这个场景会打印 48.2M —— 那串文字在画面上吗？」**
**闭合问题、零阈值、字符串相等。** **本项不动它。**

### 第 1 件事：**先造正类样本**（这是本项的全部难点）

⚠️ **"读得准"这个问题，只有存在"确实画了数值的帧"时才问得出来。**
**而三个 `showValues: True` 的场景是否真的画了，指挥窗口未实测。**

**请按此顺序做，每一步都要报告实测数字：**

1. **渲染那三个场景的若干帧**（`c01_bar` / `c05_bubble` / `c10_bar_long`），
   **你自己挑帧**（⚠️ 入场动画有 `enterFrames`，**数值可能在动画中途才出现** ——
   **请覆盖动画早期/中期/晚期，不要只取一帧**）。
2. **用 `expected_strings(scene)` 算出每帧应当出现哪些字符串**。
   ⚠️ **先检查它对这些场景算得对不对** —— `c01_bar` 是 `valueFormat: compact`
   （`48200000` ⇒ 期望串是什么？`48.2M`？`48M`？），
   `c05_bubble` 是 `valueFormat: None`（默认 `auto`）。
   ⚠️ **`expected_strings` 若算错了，那不是 VLM 的错，是判据的错 —— 说清是谁的错。**
3. **用 PIL/numpy（不要 VLM）先看一眼**：画面上**到底有没有**那些数字。
   **这一步是必要的**：若像素里根本没有数字，VLM 读不出是必然的，
   那就**根本不是 VLM 的准确率问题，是没有正类**。

### 第 2 件事：**测准确率**（在**确实画了数值**的帧上）

⚠️ **分母必须是"画面上确实有数字"的帧，不是全部帧。**
**否则你测的是"这张图里没有数字"而不是"VLM 读不读得准"。**

对每一帧问 **闭合问题**（P41 的 `probe_text`），记录：

| 指标 | 怎么算 |
|---|---|
| **召回率** | 该出现的字符串里，VLM 找到了几个 / 应出现几个 |
| **假阳性** | VLM 说"有"，而**像素里其实没有**（用 numpy 交叉验证） |
| **可复现性** | 同一帧问两次是否逐字相同（P41 的 `assert_reproducible`） |

⚠️ **必须贴原始输出**，不贴结论句。
⚠️ **VLM 可能读不出小字** —— **若如此，如实说，这条路关闭。**

### 第 3 件事：**测真实成本**（⚠️ 不许外推）

P41 工单明确要求过"实测 42 帧的真实耗时，**不要用单帧耗时外推**"。
**本项同样：实测你实际测的帧数的总耗时与单帧耗时，两者都报。**
⚠️ **模型可能随上下文增长而变慢。**

---

## 三、⚠️ 判读要求（本项目被骗十一次）

- **必须真的调 VLM 并记录它的原始回答**，不能断言源码里有 `qwen` 或某个字段名；
- **必须真的看像素**（PIL/numpy）来确认"画面上有没有数字" ——
  **否则你无法区分「VLM 读不出」与「本来就没画」**，
  **而这两个结论导向完全相反的裁定**；
- ⚠️ **别让探针的异常变成判定**（P31/P34/P36 各栽过一次：
  一对相同的 `KeyError` 被比较成 "INERT"）；
- ⚠️ **不要造 contrived 输入去凑数字**。

---

## 四、验证协议

1. **测量前先证明被测对象存在**（先证明那三个场景真的画了数值）。
2. **贴原始输出**，不贴结论句。
3. **⚠️ 五条高频复发**：先证明被测对象存在再测量；**在错误的尺度上测等于没测**；
   **外推等于没测**（P37 的帧数外推错 89 帧、P41 的单帧耗时不能外推 42 帧）；
   写数字要么实测要么标注未测；**CRLF 用字节计数验**（`read_text`+`write_text`
   会把纯 CRLF 文件整个翻成 LF —— 指挥窗口刚因此毁过 2049 行）。
4. **⚠️ 磁盘**：`render.mjs` 记录过 **118 个 bundle 把 C: 盘 TEMP 填到 46 GB**。
   **输出到 E: 盘**，跑完清理，收尾报告写明造了什么、删了什么。
5. ⚠️ `tests/test_markdown_text_is_intact.py` 守着全仓 markdown 的 U+FFFD ——
   写中文文档用 `read_bytes`/`write_bytes`。
6. ⚠️ py-3.10 有 cv2 但没有 pytest —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**。

---

## 五、不要动的东西

- `docs/UPGRADE_PROGRESS.md` —— **账本由指挥窗口统一更新**（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md` —— 只读
- **⚠️ `studio/scripts/vlm_critic.py` —— 本项原则上不改它。**
  ⚠️ **若你发现它有 bug，改之前先在报告里说清是什么 bug、你打算怎么改、为什么必须改。**
  **仅改 docstring/注释/类型标注是允许的；改判定逻辑需要先说明。**
- `studio/scripts/visual_qa.py`、`take_ranker.py`、`locked_fields.py` —— 不碰
- `studio/src/**`（除非要回答"为什么这个选项没生效"，**那时只读、不改**）
- `out/*.mp4`、`out/p13_probe/**` —— 只读；`DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要动 P19–P43 的任何成果**、不要改 `themes.ts`
- **⚠️ 不要装任何模型、不要下载任何权重** —— `qwen2.5vl:7b` 已在本机
- **⚠️ 不要把任何帧/图复制进仓库**（本项目从不跟踪媒体）

**本指令授权你修改**：**新增**一个文档（测量报告）、
必要时**新增** `studio/scripts/` 下的测量脚本（**若你写了脚本，说明它是否值得留下**）、
必要时新增测试（**若判据本身要动**）。

---

## 六、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（**只 stage 你自己的文件**）
- 交付时报告：
  - **`ollama` 在不在**（开工时的状态）
  - **那三个场景到底画没画数值**（**像素实测**，不是读图谱）
  - **`expected_strings` 对它们算得对不对**；若错，是谁的错
  - **召回率 / 假阳性 / 可复现性**，各贴原始输出
  - **真实成本**（总耗时 + 单帧耗时，都实测）
  - **⚠️ 一句话裁定：这条路开还是关**（**这是最重要的**，
    **理由必须基于上面的实测数字，不是印象**）
  - 全量测试数字
  - 磁盘纪律（造了什么、删了什么）
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**；
  若确需复原，用**字节层快照**（`read_bytes`/`write_bytes`）
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 七、队列（供你了解上下文，不必处理）

- **P43 `data-plane-3d`** —— 已判 **C（不做）**，`75cf549`。
  ⚠️ **给它注册渲染器会让 9 条守卫转红，且 P21 拿它当自己的夹具。**
- **`video` 渲染器** —— 不需要 Three.js，需要外部素材，
  而 `studio/public` **零个视频文件**。**等素材。**
- **P17**（45–60s 商业级 demo）—— **"premium"至今无可测判据**，过不了。
- **P16** —— 参考片已送达并重判（12 维度 4A/5B/3C），但 premium 一维不可判定。
- **已裁定关闭**：11.1 / 12.2 / 12.3 / 13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1。

**基线注意**：工单里写的 `719 passed` 是指挥窗口刚实测的**真实**基线。
⚠️ **历史上它曾是 `718 passed, 1 failed`** —— 差的那条是
`test_markdown_text_is_intact` 抓到 P42 工单里的一个 U+FFFD，已在 `f8f6d52` 修掉。
**若你测出别的数字，如实说，那是新信息，不要往工单基线上凑。**