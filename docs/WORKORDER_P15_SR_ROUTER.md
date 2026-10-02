# 执行指令 — P15 SR 路由：先判定路由依据存不存在，再决定建不建

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 本指令**不是**"去实现 SR Router"。它先要回答一个问题，答案可能是"没有依据可路由"。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `59f2cc3`（已推送，与 `origin/main` 同步） |
| 基线 | **先自己实测**（上次是 `389 passed, 2 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

**⚠️ 网络**：这台机器有一个**时通时不通的代理**（`127.0.0.1:7897`）。
**推送前先测**：`curl -s -o /dev/null -w "%{http_code}" --max-time 10 https://github.com`。
若返回 000 则直连（`-c http.proxy= -c https.proxy=`），若返回 200 则走代理。
**但本项是提交但不推送**，推送由指挥窗口裁定。

**开工前记录 sha256，收尾比对**：
- `studio/src/schemas/showcase-v1.ts`
- `studio/bin/render.mjs`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. P15 完全没有实现

`docs/UPGRADE_MASTER_PLAN.md`：

```
| P15 | SR 路由升级 | SR Router：程序化内容 native 直出免 SR；H3 走 sr_pipeline_v2；FlashVSR 仅纹理丰富镜头 | UI/文字绝不经过 Real-ESRGAN |
```

- 全仓检索 `sr_pipeline` / `flashvsr` / `real.?esrgan` / `seedvr` / `super.?res`：
  **只命中 `docs/` 里的 8 个 markdown，零个代码文件。**
- 账本 15.1 / 15.2 两行**都是空的**。

### 2. 路由依据**已经算出来了**，但可能没人用

`studio/src/schemas/showcase-v1.ts:87-90`：

```ts
/** Scenes that need H3 rather than the Remotion motion engine. */
export const GENERATIVE_SCENE_TYPES = new Set([
  'video',
  'data-plane-3d',
]);
```

`:316` 声明 `generative: boolean;`，`:373` 计算：

```ts
generative: GENERATIVE_SCENE_TYPES.has(s.type),
```

**这正是 SR 路由要的判定量 —— 而且它已经在 `calculateMetadata` 里被算出来了。**

### 3. ⚠️ 但指挥窗口实测：**`generative` 这个 prop 零消费方**

全仓检索 `generative`（`studio/src` 下）：

```
showcase-v1.ts:316   generative: boolean;              ← 声明
showcase-v1.ts:373   generative: GENERATIVE_SCENE_TYPES.has(s.type)   ← 赋值
```

**只有这两处。没有第三处。** 没有任何场景组件读它。

**若这条成立，P15 的路由器连输入信号都是哑的** —— 它算出来了、传下去了、没人接。

### 4. 已交付图谱里，`generative: true` 的场景数是 **0**

指挥窗口实测（`pipeline/examples/*.json`，共 **13 个场景**）：

| 出现次数 | type |
|---|---|
| 2 | `bar-chart` |
| 1 | `line-chart` / `area-chart` / `slope-chart` / `bubble-chart` / `heatmap` / `rank-chart` / `volume-chart` / `sparkline-chart` / `kpi-hero` / `browser-stack` / `dashboard` / `calendar` |

**`video` 和 `data-plane-3d` 一个都没有。** 即所有已交付内容**按设计都该 native 直出免 SR**。

**请独立复核第 3、4 条** —— 这两条决定本项的结论方向。

---

## 二、你要交付的三件事

### 第 1 件事：先复核，再判定

**独立复现第 3、4 条**（不要采信我的检索），然后回答：

> SR 路由器要依据 `generative` 来分流。**这个信号现在有消费方吗？**
> 若零消费方：**它算出来是为了什么？**（翻 git 历史：`a55d03d` 之前的提交里，
> 是谁引入 `GENERATIVE_SCENE_TYPES` 的、引入时有没有配套的消费方？）

⚠️ **注意本项目的判读陷阱**：**零命中 ≠ 死字段**。
间接消费要走 `useDesign()`、props 展开、或运行时字符串才能发现。
本项目已因此把 `sizes`/`sizeBy`/`showArea` 误报成惰性。
**若你判定 `generative` 有间接消费方，给出可复现的证据链。**

### 第 2 件事：判定建不建，写清依据

三档结论：

| 结论 | 条件 | 动作 |
|---|---|---|
| **A：值得建** | 路由信号有消费方、且确有内容需要 SR | 给最小设计（**不实现**） |
| **B：不值得建** | 信号是哑的，或无内容需要 SR | **记录理由，并说明 `generative` 这个哑信号怎么处理** |
| **C：拆开** | 例如「信号接线」值得做而「SR 路由」不值得 | **逐条给结论** |

**B 和 C 是完全合法的结论。** 本项目已接受过：
P12「零段值得建」、P13「B + C」、P14「B + C」。**不要为了交差而建。**

⚠️ **若判 B，请特别回答**：`generative` 这个**已经算出来、传下去、没人用**的信号，
按本项目的一贯纪律（惰性字段审计、6.7 的"死刻度"处理）**该怎么处理**？
是删掉，还是接线消费方，还是标注？**给出建议并说明依据**，但**不要自行实施**。

### 第 3 件事：给"`generative` 有没有消费方"上一条守卫

无论建不建，**这条守卫都有价值** —— 它把"哑声明"这个事实钉住。

守卫必须落在**可测行为**上：

- 断言**当前真实性质**（有消费方 / 零消费方），**不是**理想性质。
- **不能**用 `assert 'generative' in source` 这种文本存在性断言 ——
  **本项目已被这类断言骗过六次**，最近一次就在 `render.mjs` 修复的预检里
  （删掉检查后 `Unknown flag` 仍留在解释该修复的**注释**里）。
- **"零消费方"这类断言必须能红**：若将来有人接上消费方，它必须转红
  （否则就是记了一个从未验证过的事实）。

**至少两条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 在某个场景组件里加入对 `generative` 的真实读取 | 守卫红（若它断言零消费方） |
| 从 `GENERATIVE_SCENE_TYPES` 删掉 `'video'` | 守卫红（若它钉住了集合内容） |

**「变异存活」≠「变异无效」**：存活项判定"真漏洞"还是"无效变异"，
两种都写进 commit。**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
4. **每条毒变异之后从快照复原源文件，收尾核对两个 sha256。**
5. **⚠️ 磁盘纪律**：若你要渲染任何东西，注意 `studio/bin/render.mjs:45-47`
   记录过 **118 个 bundle 把 C: 盘 TEMP 填到 46 GB**。输出到 **E: 盘**，跑完清理。
   **本项大概率不需要渲染** —— 别为了"验证得更彻底"去渲一整部片子。
6. **测退出码不要用管道**（本窗口用 `| tail` 读到 `tail` 的退出码、差点误判）。
7. **写长文本在字节层操作**；**不要在 bash 双引号里写带反引号的 Python 代码**
   —— 指挥窗口刚因此产出四个 0 字节垃圾文件。
8. **行尾按文件实测**，不要相信任何人的断言包括本工单的。
   **`showcase-v1.ts` 实测是 CRLF**（400 CRLF / 0 裸 LF，改动后行数会变）。
9. **`/tmp` 在 bash 与 Python 中解析不同**（`C:\Users\pc\AppData\Local\Temp`）。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— cv2 只装在 3.10，本项 `--ignore`
- **不要实现 SR Router、不要扩 schema、不要接线 `generative` 的消费方** ——
  结论未裁定，实施越界。**第 2 件事只要建议 + 依据。**
- **不要碰任何 SR / 模型 / 权重相关的东西** —— 本项不下载、不推理、不调用 SR

**本指令授权你修改**：新增文档、新增测试文件。
**除守卫所需的最小改动外，不要改生产代码。**

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：
  - **`generative` 有没有消费方 + 可复现证据**（这是最重要的一项）
  - **它是怎么被引入的**（git 历史）
  - **建不建的判定 + 依据**，以及**哑信号该怎么处理的建议**
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **两个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**跨阶段**：1.3 / 10.2（VLM Critic provider 抽象；
**已裁定标依赖、不合并、不重复建** —— 仓库至今无 `take_critic.py`）、
**P16**–**P18**。

**已裁定不要再讨论**：
- P13 `13.1` = **B 不值得建**（bundle 只占 6%、每进程 mkdtemp）、
  `13.2` = **C 现在不建**（被产物不可复现 / 无人察觉 scene 变更 / re-encode 未实测挡住）
- P14 `14.1` = **B**（bundle 在磁盘不在堆，常驻 262 MB，生产路径净省 0.0s）、
  `14.2` = **C**（单次渲染没有值得回收的重复）
- P12 = **零段值得建**

**「入口静默通过」这一族已修两处**（`6e86b46` 的 `visual_qa.py`、
`306f327` 的 `render.mjs`）。**同类是否还有第三处，值得你在勘察时顺带留意**
（但不扩大范围去修）。

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** —— 仪器已建成（`chart_geometry.py` / `c6d7a5a`），修复器**故意未写**：
  已交付图表比值 **0.278**，无碰撞可修。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由
  "重新测量仍在碰撞"决定，而非计数器。
