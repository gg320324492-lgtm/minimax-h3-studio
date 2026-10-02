# 执行指令 — P13 Scene Cache：先量收益，再决定建不建

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 本指令**不是**"去实现增量构建"。它先要回答一个问题，答案可能是"不值得建"。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `b516f42`（**本地，未推送** —— 上一轮推送因 TLS 握失败，网络整体不通，`curl https://github.com` 返回 HTTP 000） |
| 基线 | **先自己实测**（上次是 `365 passed, 2 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ **不要尝试推送** —— 推送由指挥窗口裁定，且当前网络不通。

**开工前记录 sha256，收尾比对**（最近四项都动过这些）：
- `studio/bin/render.mjs`
- `studio/scripts/visual_qa.py`
- `studio/src/schemas/showcase-v1.ts`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. P13 完全没有实现

`docs/UPGRADE_MASTER_PLAN.md:138`：

```
| P13 | Scene Cache / 增量构建 | `job_state.json` + hash 缓存 | 改一个 scene 不重跑全片 |
```

- 全仓检索 `job_state` / `sceneCache` / `scene_cache`：**零实现**
- 账本 13.1 / 13.2 两行**都是空的**（连结论格都没写）

### 2. 渲染端每次重建 800 MB bundle —— 且这个文件记录过一次严重事故

`studio/bin/render.mjs:43-59` 的注释（原样）：

```
// The bundle is ~800 MB and it is scratch: it exists only while this process
// runs. Left to itself `bundle()` writes it to os.tmpdir() via mkdtemp and
// NEVER deletes it (prepareOutDir in @remotion/bundler), so every render leaks
// one copy of studio/public onto the system drive — 118 of them filled a C:
// TEMP to 46 GB.
```

`:57` —— `const bundleDir = fs.mkdtempSync(path.join(scratchRoot, 'render-'));`

**每次渲染都 `mkdtemp` 一个新目录，`finally` + SIGINT 处理删除。**
所以事故已修（不会泄漏），但代价是**每个进程都要重新 bundle 一次 800 MB**。

### 3. 没有任何 scene 级入口

`studio/bin/` 只有三个文件：

| 文件 | 粒度 |
|---|---|
| `render.mjs` | **全片**（`--comp` + `--props`） |
| `still.mjs` | **单帧**（`--frames` 逗号分隔） |
| `export-schema.ts` | 无渲染 |

**没有"只渲某一个 scene"的入口。** 13.2「改一个 scene 只重跑该 scene 的
preview/QA/final」**连入口都不存在**。

### 4. QA 端同样没有 scene 粒度

`studio/scripts/visual_qa.py:746-751`：

```python
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--props', type=Path)
```

**只有 `--props`，没有 `--scene`。**

---

## 二、你要交付的三件事

### 第 1 件事：**量收益**，产出 `docs/P13_CACHE_PAYOFF.md`

**这是本项的核心。没量出收益就不要建。**

必须给出**实测数字**，不是估算：

1. **一次 bundle 真实耗时**。跑一次 `render.mjs`（或用 `--props` 指向
   `pipeline/examples/showcase_demo.json`），量出 `bundle done in Xs` 那行。
   **若渲染太慢跑不动，量到 bundling 阶段就停，并如实说明。**
2. **改一个 scene 的"最坏情况"现在是多久** —— 因为只能全片重渲。
3. **能省多少**：把上面两个数字摆在一起，让读者自己判断。

> **特别小心**：这个项目的历史教训是**「结果红不等于交付物」**
> 以及**「先证明被测对象存在，再测量」**。
> 本项目测过一次 150 帧场景的**帧 120**（80% 处、生命周期 exit 阶段、
> 图表已退场），测出来的"墨迹"全是背景噪声 —— **测的位置不对，数字全无意义**。
> 你量 bundle 耗时就量 bundle，不要顺带量别的东西。

### 第 2 件事：**判定建不建**，写清依据

必须回答：

> 按第 1 件事的实测数字，P13 现在建了**能省多少**？
> 这个量级值不值一个 `job_state.json` + hash 缓存？

三档结论：

| 结论 | 条件 | 动作 |
|---|---|---|
| **A：值得建** | 收益显著且判据明确 | 给最小设计（见第 3 件事），**但不实现** |
| **B：不值得建** | 收益小、或瓶颈在别处 | 记录理由，并说明**瓶颈到底在哪** |
| **C：部分值得** | 例如 bundle 可复用但 scene 级重渲不值得 | **拆开**，逐条给结论 |

**B 和 C 是完全合法的结论**，本项目已接受过 P12 的
「零段值得建」。**不要为了交差而建。**

⚠️ **注意 bundle 与 scene 缓存是两个不同的事**：
- bundle 复用 → 省的是**每次启动**的固定开销（800 MB 拷贝 + webpack）
- scene 级重渲 → 省的是**改动一个 scene**时的整片重渲

**它们的价值可能差一个数量级**，请分开算，不要混为一谈。

### 第 3 件事：给"该不该重建"上一条守卫

无论建不建，**这条守卫都有价值**：它把"缓存正确性"这条性质先钉住，
将来谁真的建缓存时，判据已经存在。

请加守卫断言**当前系统的真实性质**（不是理想性质）：

> **同一份 props 连续渲染两次，产物应当一致**；
> **改一个 scene 之后，当前系统会重渲全片**（这是要被记录的事实，不是要被掩盖的）。

**要求**：

- **不要断言一个不存在的 `job_state.json`。** 断言不存在的文件，
  写出来的守卫会在文件出现的那天失效或误报 —— 本项目吃过这种亏
  （断言 `"mkdtemp" in source` 结果匹配到了解释该 bug 的注释）。
- 守卫必须落在**可测的行为**上。若某条性质此刻无法测量，
  **如实写明"不可测"并说明为什么**，不要写一条假装能测的断言。

**至少两条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 让 `visual_qa.py` 的 `--props` 接受一个不存在的图谱 | 守卫红（若它断言"非法输入必须报错"） |
| 在图谱里改一个 scene 的值，看现有系统是否察觉 | 按实测结果断言，并写清是"察觉"还是"不察觉" |

**「变异存活」≠「变异无效」**：存活项判定"真漏洞"还是"无效变异"，
两种都写进 commit。**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
   **看到红的理由不对，先查现场再下结论。**
4. **每条毒变异之后从快照复原源文件，收尾核对三个 sha256。**
5. **量渲染前先看磁盘**：`render.mjs` 的注释记录过 **118 个 bundle 把 C: 盘填到 46 GB**。
   **确认你要用的输出目录，并在跑完后清理** —— 不要再造一次同样的事故。
6. **行尾按文件实测，不要相信任何人的断言包括本工单的。**
   用 `read_bytes` 精确匹配写回。
7. **写长文本在字节层操作**；**不要在 bash 双引号里写带反引号的 Python 代码**
   —— 指挥窗口刚因此产出四个 0 字节垃圾文件。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— cv2 只装在 3.10，本项 `--ignore`
- **不要实现 scene 级缓存或 bundle 复用** —— 结论未裁定，实现越界
- **不要删任何已有的 bundle 目录或 out/ 目录**

**本指令授权你修改**：新增 `docs/P13_CACHE_PAYOFF.md`、新增测试文件。
**若第 2 件事结论为 A**，可另加设计文档，但**不要写实现代码**。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（且当前网络不通）
- 交付时报告：
  - **bundle 真实耗时的实测数字**（这是最重要的一项）
  - **建不建的判定 + 依据**（bundle 复用与 scene 级重渲**分开给结论**）
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **三个 sha256 的比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**跨阶段**：1.3 / 10.2（VLM Critic provider 抽象；
**已裁定标依赖、不合并、不重复建** —— 仓库至今无 `take_critic.py`）、
**P14** Render Worker / Fast Preview（与本项相邻 —— 若本项测出瓶颈在 bundle，
P14 的"长驻 bundle"就是它的自然形态）、**P15** SR 路由、**P16**–**P18**。

**P12 遗留（未动，方向相反、修法不同）**：
- `chartLanguage` / `audioLanguage` —— 声明了但**零消费**（P11 方向：
  「声明了但没人读」，而本系列修的是「有人读但喂不进去」）。
  `.strict()` **管不到它们**（链条里没有未声明键）。

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** Repair Planner —— 仪器已建成（`chart_geometry.py` / `c6d7a5a`），
  修复器**故意未写**：已交付图表比值 **0.278**，无碰撞可修。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由
  "重新测量仍在碰撞"决定，而非计数器。
