# 执行指令 — P47：修 `area` 渲染成裸线，以及一类**现有守卫全都看不见**的失效

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **缺陷已由指挥窗口用像素坐实，不是推断。你可以复核，但不必重新论证。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `8ea6790`（已推送） |
| 基线 | **`739 passed, 4 skipped`**（⚠️ 历史基线过期过，**实测为准，不要往工单数字上凑**） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**（GBK 控制台把省略号显示成替换字符）。

**⚠️ Shell 状态在两次工具调用之间不保持**。**全程用绝对路径**。
**⚠️ `git add` 用显式路径**，不要用 `-A` 或 `.`。

**开工前记录 sha256，收尾比对**：
- `studio/src/templates/finance-showcase/charts/types.tsx`
- `studio/src/templates/finance-showcase/charts/options.ts`
- `pipeline/examples/charts_demo.json`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺陷的代码位置与机制

`studio/src/templates/finance-showcase/charts/types.tsx:266-272`：

```tsx
const LineOrArea: React.FC<{series: Series; defaultArea: boolean}> = ({series, defaultArea}) => {
  const f = useFrame();
  return <PathMark series={series} withArea={option('line', 'showArea', f.opts) ?? defaultArea} />;
};

export const Line: React.FC<{series: Series}> = ({series}) => <LineOrArea series={series} defaultArea={false} />;
export const Area: React.FC<{series: Series}> = ({series}) => <LineOrArea series={series} defaultArea />;
```

`studio/src/templates/finance-showcase/charts/options.ts:194-202`：

```ts
export const option = <K extends keyof ChartOptions>(chart, key, overrides?) => {
  void chart;
  const v = overrides?.[key];
  return v === undefined || v === null ? DEFAULT_CHART_OPTIONS[key] : v;
};
```

**`option()` 永不返回 `undefined` 或 `null`** ——
值为 undefined/null 时它返回 `DEFAULT_CHART_OPTIONS[key]`，
而 `DEFAULT_CHART_OPTIONS.showArea` 是 `false`（`options.ts:117`）。

**⇒ `?? defaultArea` 右侧是死代码 ⇒ `Area` 与 `Line` 逐字节相同，
除非图谱显式设 `showArea: true`。**

### 2. 交付的那张图谱正好踩中，**而且两边是反的**

```
c02_line   type=line-chart  chart.type=line  showArea=True    <- 叫 line 的有面积填充
c03_area   type=area-chart  chart.type=area  showArea=None    <- 叫 area 的是裸线
```

### 3. 指挥窗口的像素证据

渲染全局帧 250（c02）与 400（c03）：

```
ink_frac  c02_line: 0.04748
ink_frac  c03_area: 0.00568      <- 8.4 倍
两帧差异像素: 429189
```

**并已看图确认**：`c02` 有渐变面积填充，`c03` 是裸线。

**⇒ 这条缺陷落在已交付并通过视觉验收（P27）的 `charts_demo.mp4` 里。**

### 4. ⚠️ 为什么**所有现有守卫都是绿的**

| 守卫 | 为什么看不见 |
|---|---|
| **A/B 矩阵** | 它测「翻转这个选项画面变不变」⇒ `showArea` 变 **400053 px**，**它是 LIVE 的** |
| **`test_comment_citations_resolve`** | 只管注释引用，不管行为 |
| **`TYPE_OPTIONS` 表**（`options.ts:147-166`） | 只核对**名字**在不在，不核对**默认值**对不对 |
| **`test_chart_registry.py`** | 只核对注册表 |
| **P45 的 VLM 判据** | 只问「图谱声明的数字画上去了吗」，不问图长得对不对 |

**⚠️ 这是一类本项目尚未记录过的失效形态**：
**「一个选项是活的，但它的默认值对它自己那个类型是错的」**
⇒ 静默产出错的画面，**而每一条现有守卫都全绿。**

⚠️ `options.ts:130-144` 记着上一代的同类事故：
> *「一个声明面能让一个能工作的选项变成惰性。」*

**⇒ 这是它的表亲：不是选项惰性，是**默认值**惰性。**

---

## 二、你要交付的东西

### 第 1 件事：**先回答一个设计问题，再写代码**

⚠️ **`showArea` 的默认到底应该由谁决定？**

现在的形状是「`DEFAULT_CHART_OPTIONS.showArea = false`」，
**⇒ 任何 `type: area-chart` 不显式写 `showArea: true` 就渲染成裸线。**

**请判断并说明**：

- **方案 A**：让 `Area` 的默认生效（图谱没写就画填充），
  `Line` 的默认不生效（图谱没写就不画）——
  **则类型本身决定了默认，图谱可覆盖**；
- **方案 B**：保持 `DEFAULT_CHART_OPTIONS.showArea = false`，
  但把 `area-chart` 在**图谱侧**显式设成 `true` ——
  **则图谱是唯一真相来源，渲染器只认图谱**；
- **方案 C**：你认为还有更好的形状。

⚠️ **⚠️ 本项的难点不是写代码，是「不制造一个新的哑声明」。**
**`DEFAULT_CHART_OPTIONS` 是有测试钉住的**，
**若你改它的语义，请说明哪些测试会红、为什么那些红是对的**。
⚠️ **不要为了让测试变绿而弱化断言。**

⚠️ **⚠️ 特别注意一个陷阱**：`option()` 分不清「图谱没写」与「图谱写了 false」。
**方案 A 若要成立，需要能区分这两种情况** ——
**请说明你怎么区分，并说明这会不会是第六个「声明了但没人读」的东西。**

### 第 2 件事：**实施，并修交付图谱的倒置**

⚠️ **两层都要修**：

1. **渲染器层**（`types.tsx`）：`Area` 应当有面积；
2. **图谱层**（`pipeline/examples/charts_demo.json`）：
   `c02_line` 的 `showArea: true` 与 `c03_area` 的缺失**是倒置的** ——
   **请按你裁定的方案修正，并说明修正后 `c02` 与 `c03` 的画面各是什么。**

⚠️ **改了图谱就意味着 `charts_demo` 的画面变了** ——
**请报告改完之后整片的帧数与时长**（⚠️ **实测，不要算**）。

### 第 3 件事：**给「活的选项 + 错的默认值」上一条守卫**

⚠️ **这是本项真正的价值。守卫必须能抓住这一类，而不只是这一个。**

- **必须真的渲染并断言画面**，不能断言源码里有 `defaultArea` 这个名字
  —— ⚠️ **本项目被文本存在性断言骗过十一次**；
- ⚠️ **判据要能问「这个类型默认该画什么」**，
  **不能只问「这个选项翻转会不会动」**（那是 A/B 矩阵，已经有了，且它对这个缺陷全绿）；
- ⚠️ **别造一台误报机**：若你把它做成"每个类型都要有默认值断言"，
  很可能大面积误报。**请说明你的判据有多窄、为什么不会误报。**

**至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 让 `Area` 退回与 `Line` 相同（还原缺陷） | 守卫红 |
| 把某个类型的默认改错（**换一个类型**，证明它不是只为 area 特设） | 守卫红 |
| 让判据永远判"通过" | 守卫红 |

⚠️ **"红在错误的理由上"不算通过**（P35 红在 `NameError`、P36 红在 `SyntaxError`）。
⚠️ **别让探针的异常变成判定**（P31/P34/P36 各栽过一次）。
⚠️ **每条毒变异后从字节快照复原，收尾核对 sha256。**

---

## 三、验证协议

1. **测量前先证明被测对象存在**；
2. **贴 `-rf` 原始输出**，不贴结论句；
3. ⚠️ **五条高频复发**：先证明被测对象存在再测量；
   **在错误的尺度上测等于没测**；**外推等于没测**；
   写数字要么实测要么标注未测；确认变异生效前不要宣称存活；
   **CRLF 用字节计数验**（⚠️ 指挥窗口刚因此毁过 2049 行；
   `types.tsx` 与 `options.ts` **是纯 CRLF**，先测再动）。
4. **⚠️ 磁盘**：输出到 **E: 盘**，跑完清理，写明造了什么、删了什么。
   ⚠️ **`studio/.remotion/water-renewal-bundle`（1.5 GB）不是你的，别删。**
5. ⚠️ `tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD ——
   写中文文档用 `read_bytes`/`write_bytes`。
6. ⚠️ py-3.10 有 cv2 但没有 pytest —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**。
7. ⚠️ **不要与别的进程并发渲染** —— 指挥窗口上次这么做，
   52 次渲染里一条红在 `still b failed on frame 870`，**单独重跑即成功**。

---

## 四、不要动的东西

- `docs/UPGRADE_PROGRESS.md` —— **账本由指挥窗口统一更新**（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P37_REFERENCE_REANALYSIS.md`、`docs/P46_PROBE_INSTRUMENTS.md` —— 只读
- `studio/scripts/**` —— 不碰（P45/P46 的仪器，本项与它们无关）
- `out/*.mp4`、`out/p13_probe/**`、`out/p45_vlm/**`、`out/ab_matrix/**` —— 只读；
  `DiagOutputDir` —— **禁止触碰**
- ⚠️ **`out/charts_demo.mp4` —— 是 P27 的证据目录，只读，不覆盖**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要动 P19–P46 的任何成果**、不要改 `themes.ts`
- **⚠️ 不要改 `DEFAULT_CHART_OPTIONS` 以外的任何 `options.ts` 内容**，
  **除非第 1 件事裁定了必须改**
- **⚠️ 不要把任何帧/图复制进仓库**

**本指令授权你修改**：`studio/src/templates/finance-showcase/charts/types.tsx`、
`charts/options.ts`（**仅限第 1 件事裁定的范围**）、
`pipeline/examples/charts_demo.json`、相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（**只 stage 你自己的文件**）
- 交付时报告：
  - **方案 A/B/C 选了哪个 + 理由**（最重要）
  - **你怎么区分「图谱没写」与「图谱写了 false」**
  - **这会不会是第六个「声明了但没人读」的东西 —— 你的判断**
  - **改完之后 `c02` 与 `c03` 的画面各是什么**（像素证据）
  - **整片的新帧数与时长**（实测）
  - **守卫方案 + 它有多窄、为什么不会误报**
  - **逐条变异结果**（贴 `-rf` 原始输出）
  - **全量测试数字**
  - **三个 sha256 的比对**
  - **磁盘纪律**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**；
  若确需复原，用**字节层快照**（`read_bytes`/`write_bytes`）
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列（供你了解上下文，不必处理）

- **P43 `data-plane-3d`** —— 判 **C（不做）**。
- **`video`** —— 需要外部素材，`studio/public` 零个视频文件。**等素材。**
- **P45** —— VLM 判据**开**（114/114、0/47）。⚠️ 但它判的是"数字画上去了吗"，**不是"画得对不对"**。
- **P46** —— 色彩升 A、图表判 C、字体判 B、**相机推翻 P37**。
- **P16 / P17** —— 都卡在 "premium" 无判据。
- **已裁定关闭**：11.1 / 12.2 / 12.3 / 13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1。