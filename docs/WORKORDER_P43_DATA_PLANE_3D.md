# 执行指令 — 补 `data-plane-3d` 渲染器：总计划授权的 Three.js 边界之内

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **本项的成败不在"能不能画"，而在"画出来的东西有没有内容"。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `f87380b`（已推送） |
| 基线 | **先自己实测**（上次 `719 passed, 4 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**（cv2 只装在 3.10）。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，命令以 `cd E:/Minimax-H3 &&` 开头。
**⚠️ `git add` 用显式路径**，不要用 `-A` 或 `.`。
**⚠️ `studio/package.json` 与 `pnpm-lock.yaml` 在工作树里有未提交改动，归属不明** ——
**本项若要改它们（装依赖需要），先在交付里说明，不要静默带上别人的改动。**

**开工前记录 sha256，收尾比对**：
- `studio/src/templates/finance-showcase/FinanceShowcaseWide.tsx`
- `studio/scripts/visual_qa.py`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺口

`SceneType` 声明 22 个类型，`SCENE_RENDERERS` 注册 **21 个**（P26 之后）。
**唯一缺的两个是 `video` 与 `data-plane-3d`**（P26 的 `UNRENDERED_SCENE_TYPES` 显式记录）。

它们落到 `MissingScene`，**整段渲染出类型名加 "not implemented in P4"**。

### 2. ⚠️ 总计划自己划了 Three.js 的界，且 `data-plane-3d` 正在界内

`docs/UPGRADE_MASTER_PLAN.md:205` 原话：

> **Three.js 边界**：默认 React + SVG + CSS 3D。
> **仅 data-plane / 大规模 3D columns / 真 3D camera 场景引入 `@remotion/three`**。
> **Dashboard 用 Three.js 属错误架构。**

**⇒ 引入 `@remotion/three` 是总计划明确授权的，而 `data-plane-3d` 正是那三个例外之一。**
**⚠️ 而 `video` 不在授权范围内**（它不需要 Three.js，它需要外部素材，
**而 `studio/public` 里零个视频文件**）—— **本项不做 `video`。**

### 3. 依赖现状（指挥窗口实测）

```
package.json          声明 three / @react-three / drei ？  —— 无
node_modules/three            —— 不存在
node_modules/@react-three     —— 不存在
```

**⇒ 需要先引入依赖。** ⚠️ **这意味着要动 `package.json` / `pnpm-lock.yaml`，
而那两个文件在工作树里已有归属不明的改动。**

### 4. ⚠️ 本项最大的风险：**做出一个"能跑但没内容"的渲染器**

这是本项目反复栽跟头的地方，**账本里有六次**：
`generative`（死在一个字段上）、
`LOCKED_SCENE_TYPES`（放了几个月没人读）、
`chartLanguage` / `audioLanguage`（至今零消费）、
`motion.ease`（图谱设了但从不读）、
顶层 `audio`（zod 剥掉，渲染分支永久不可达）。

**⚠️ 而 `data-plane-3d` 有特别的风险**：
它叫"数据平面"——**如果画出来的是一堆随机飘着的点，
那它和"一个会动的 `MissingScene`"没有区别。**

---

## 二、你要交付的三件事

### 第 1 件事：**先判定它该画什么**，再写代码

⚠️ **这是本项最重要的一步。** 在写任何渲染代码之前回答：

**(a) `data-plane-3d` 画的是什么？**
⚠️ **总计划只给了名字，没给内容。** 请找出依据：
`MASTER_PLAN.md` 里有没有更细的描述？`docs/` 里有没有？
**⚠️ 若找不到依据，如实说"没有依据"** —— **那本身是合法的交付**，
**本项目已接受过十二次「实测说不出想要的结果」。**

⚠️ **不要编一个看起来很像的粒子系统。** 若判 A 的依据是"我觉得应该是这样"，
**那是编的**，而它会成为又一个"声明了但没人验证"的东西。

**(b) 若有依据，它的数据从哪来？**
**图谱的 `content` 给什么？** ⚠️ 查 `showcase-v1.ts` 里 `content` 的形状
（是 `z.record(z.string(), z.unknown())` 开放袋子 ⇒ **任何形状都合法**，
**但也意味着"没有契约"**）。

**(c) `visual_qa` 能验它吗？**
**画得对不对，是二值事实还是主观判断？**
⚠️ **若只能靠"看起来是 3D"，那它无法被验收** —— 而**无法被验收的东西不该建**。

### 第 2 件事：实施（**若第 1 件事判 A**）

⚠️ **三条硬要求**：

1. **必须从 `content` 读数据，不许硬编码** ——
   **六个已完成的渲染器全部走 `useDesign()` 取 token、从 `content` 取数据**；
   **一个硬编码点阵的渲染器等于没有**；
2. **必须能被 `visual_qa` 检出它不是 `MissingScene`** ——
   现有守卫 `graph_scene_renderable`（P21）会在图谱用到无渲染器类型时 FAIL，
   **你的改动应当让那条守卫转绿**（因为类型不再落空）；
3. **⚠️ 依赖引入的方式要说清** ——
   `pnpm add` 会同时改 `package.json` 与 `pnpm-lock.yaml`，
   **而这两个文件在工作树里已有别人的改动**。
   **请先 `git diff` 那两个文件、看清现有改动是什么，再决定怎么做**，
   **并在交付里明确说明你动了什么、为什么**。
   **不要静默把别人的改动一起提交。**

### 第 3 件事：给"它不是 MissingScene、而且画得有内容"上一条守卫

⚠️ **本项的守卫必须能抓住「渲染器存在但画不出东西」**。
**只有"类型不再落空"这条是不够的** —— 那正是会产出装饰的判据。

**判读要求（本项目被骗十一次）**：

- **必须真的渲染并断言画面里有东西**，不能断言源码里 import 了某个包
  —— ⚠️ **`import '@react-three/three'` 在代码里存在，不等于画面里有 3D**；
- **⚠️ 判据要用像素**：例如"画面中存在深度线索"（近大远小 / 透视）
  **而不是"调用了某个 API"**。
  ⚠️ **但请小心别造一台误报机**（P34 的教训：22 处行号引用里 4 处是刻意引用注释块）。

**至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 让它渲染一张空场景（照旧渲染器名但不画内容） | 守卫红 |
| 让它画一个硬编码的固定点阵（与 `content` 无关） | 守卫红 |
| 让判据永远判"通过" | 守卫红 |

**「变异存活」≠「变异无效」**：存活项判定"真漏洞"还是"无效变异"，
两种都写进 commit。**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果**；**且要证明它不是死分支**。
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **⚠️ "红在错误的理由上"不算通过** —— P35 的 M4 红在 `NameError`、
   P36 的第二条红在 `SyntaxError` 且 pytest 收集阶段就中止。
4. **每条毒变异之后从快照复原，收尾核对两个 sha256。**
5. **⚠️ 五条高频复发**：先证明被测对象存在再测量；**外推等于没测**（P37 的帧数外推错 89）；
   写数字要么实测要么标注未测；确认变异生效前不要宣称存活；
   **CRLF 用字节计数验**（**`read_text`+`write_text` 会把纯 CRLF 文件整个翻成 LF**，
   指挥窗口刚因此毁过 2049 行）；路径分隔符；**别把长跑命令管道进 `tail`**。
6. **⚠️ 磁盘**：`render.mjs` 记录过 **118 个 bundle 把 C: 盘 TEMP 填到 46 GB**。
   **输出到 E: 盘**，跑完清理，收尾报告写明造了什么、删了什么。
7. **⚠️ `tests/test_markdown_text_is_intact.py` 守着全仓 markdown 的 U+FFFD** ——
   写中文文档用 `read_bytes`/`write_bytes`。
8. **py-3.10 有 cv2 但没有 pytest** —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**。

---

## 四、不要动的东西

- **⚠️ `studio/src/water-renewal/**`、`studio/bin/render-water.mjs`、
  `studio/tsconfig.water.json`、`water_renewal/` —— 刚提交的独立管线，本项不碰**
- **⚠️ `studio/package.json` 与 `pnpm-lock.yaml` 里归属不明的既有改动** ——
  见第 2 件事第 3 条
- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— **账本由指挥窗口统一更新**（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md` —— 只读
- `out/p13_probe/**` 与 `out/*.mp4` —— 只读；`DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要做 `video`**（见第 2 条：不在 Three.js 授权范围内、且无素材）
- **不要改 `GENERATIVE_SCENE_TYPES`**（P15 记录的"差一行"线索是**待裁定**的）
- **不要动 P19–P42 的任何成果**、不要改 `themes.ts`

**本指令授权你修改**：`studio/src/templates/finance-showcase/scenes/**`（新组件）、
`FinanceShowcaseWide.tsx` 的注册表、依赖清单（**按第 2 件事第 3 条**）、相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **(a) 它该画什么 + 依据**（**若答"没有依据"，说清并给出替代方案**）
  - **(b) 数据从哪来**
  - **(c) `visual_qa` 能验它吗**
  - **裁定 A/B/C + 理由**
  - **依赖怎么引入的、你对 `package.json` 既有改动做了什么**
  - **全量测试数字**
  - **逐条变异结果**（贴 `-rf` 原始输出）
  - **两个 sha256 的比对**
  - **磁盘纪律**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染`
- **⚠️ `git add` 用显式路径，不要 `-A` 或 `.`**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**同类的另一个**：`video` —— **本项不做**（不需要 Three.js、而是需要外部素材，
而 `studio/public` 零个视频文件）。**等有素材再说。**

**P17 其余部分**：即便 `data-plane-3d` 建好，P17 仍过不了 ——
它要求「45–60s 商业级 demo」，而**「premium」至今无可测判据**（P17 裁定），
且参考片（P37）实测**只给到布局层面**，且**推翻了"与本项目底色冲突"的说法**
（23–51s 近白 `[252,252,252]`、67–83s 近黑）。

**已裁定关闭**：11.1 / 12.2 / 12.3 / 13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1。