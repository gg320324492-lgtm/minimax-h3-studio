# 执行指令 — 修 `render.mjs` 静默忽略未知 flag：拼错的参数会渲出一整部片子

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 这是 P14 勘察（`16275da`）的附带发现，但**它是本项目修过一次的同类缺陷的漏网之鱼**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `16275da`（**本地，未推送** —— 网络整体不通，`curl https://github.com` 返回 HTTP 000，已连续多次） |
| 基线 | **先自己实测**（上次是 `387 passed, 2 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ **不要尝试推送。** 推送由指挥窗口裁定，当前网络不通。

**开工前记录 sha256，收尾比对**：
- `studio/bin/render.mjs`
- `studio/bin/still.mjs`
- `studio/scripts/visual_qa.py`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺陷：`render.mjs` 静默忽略任何未知 flag

`studio/bin/render.mjs:23-39` 只有两种参数处理：

```js
const requireArg = (key) => { ... process.exit(2); }   // 必填缺失才报错
const codec = get('codec', 'h264');                     // 未知 key → undefined → 用默认值
```

**没有任何未知 flag 检查。** 后果：

- `--frames 10` 被**完全忽略**，150 帧全渲，**退出码 0**
- `--prods x.json`（`props` 拼错）→ 但这个会被 `requireArg` 抓到（因为缺 `props`）
- `--crf abc` → `Number('abc')` = `NaN` → 传给渲染器，行为未知
- 任何拼错的、任何不存在的 flag，都**静默通过**

### 2. 同仓库的 `still.mjs` 修过这个 bug，`render.mjs` 漏了

`studio/bin/still.mjs:31-43` 的注释原样：

```
// Hand-rolled flag parsing is why `--frames` where `--frame` was meant used to
// fall through to a default instead of complaining. Unknown flags are now an
// error, because a typo that silently selects a different frame produces a
// wrong image rather than a failure.
```

`still.mjs:43` 确实有：

```js
`Unknown flag --${name}. Known value flags: ...`
```

**指挥窗口实测确认**：`render.mjs` 里 `unknown` 相关处理**零处**。
**同仓库、同类 bug、修了一处漏了一处。**

### 3. 这与刚修完的 `visual_qa.py` 静默通过**同构**

`6e86b46` 刚修掉：`visual_qa.py` 被喂不存在的 `--props` 时报告「通过」+ 退出 0。

**同一失效家族**：工具在被喂错东西时报告成功。
那一次的教训是 —— **这不是一个 bug，是一类**，而这一类是
「入口接受任意输入、错的那个和对的那个返回同样的成功」。

### 4. P14 已裁定：长驻 bundle 不值得建（**不要重新讨论**）

`16275da` 的结论：**B + C**，什么都没实现。关键数字：

- **bundle 是磁盘上的目录，不是常驻对象** —— Remotion 从磁盘读它，从未在堆上。
  「800 MB bundle → 800 MB 常驻」的假设**错了一个数量级**。
  实测常驻成本：**262 MB**（对照 57 MB vs 常驻 318–328 MB）。
- **bundler 不 watch**：改 `durationInFrames={150}`→`{151}` 后 5 秒仍是 150，
  **只有显式重新 bundle 才变 151**。但**失效判据极便宜**：
  mtime **0.21 ms**（56 文件）/ 内容 hash **2.15 ms**，对照省下的 1200 ms。
  —— 工单猜这是最大复杂度来源，**实测它是最便宜的一环**。
- **固定开销 1.9 s（9%）/ 可变 18.4 s（91%）**。
- **`render_with_remotion.py:70` 一个进程渲一部片子** ⇒
  **生产路径净省 0.0 s**。
- 且它靠**放松 46 GB 事故的清理逻辑**换来那 1.2s —— 用每次泄漏换永久 800 MB 占用。

---

## 二、你要交付的三件事

### 第 1 件事：先复现，再动手

**独立复现第 1 条的失效形态**（不要采信我的描述）：

- 用一个未知 flag 跑 `render.mjs`，**贴出完整输出与真实退出码**。
- ⚠️ **测退出码不要用管道** —— 指挥窗口刚因此差点误判（`| tail` 读到的是 `tail` 的）。
  用 `> file 2>&1; echo $?`。
- ⚠️ **磁盘纪律**：`render.mjs:45-47` 记录过 **118 个 bundle 把 C: 盘 TEMP 填到 46 GB**。
  **把输出目录放 E: 盘**，**跑完清理**。收尾报告列出造了什么、删了什么。

**若你发现已有守卫钉住了当前的静默行为，先读它** ——
上一轮 agent 因此正确处理过同类情况（`6e86b46` 里它重写而非删除了钉住现状的守卫）。

### 第 2 件事：修它，并**与 `still.mjs` 对齐**

`render.mjs` 必须**对未知 flag 报错**。

⚠️ **注意一个已被 P14 钉住的事实**：`tests/test_p14_render_entry_points.py` 里
可能有一条守卫**钉住了"当前静默忽略"的行为**（上一轮 agent 明确说
"pinned the current behavior with a note that it must be rewritten (not deleted) when fixed"）。

**你要读它、确认它钉的是现状而非应然、然后重写它 —— 不要删除、不要放松。**
**不要为了让套件绿而回退修复。**

**对齐时请注意两者的差异**：`still.mjs` 有 `VALUE_FLAGS` 集合；
`render.mjs` 的 flag 种类不同（有 `codec` / `crf` / `bitrate` / `hw` / `concurrency` 等带默认值的）。
**请说明你如何界定 `render.mjs` 的"已知 flag"集合**，以及**布尔型 flag 怎么表示**
（`still.mjs` 用 `--as-file` 这样的形式，`render.mjs` 有吗？查清楚再动手）。

### 第 3 件事：给"渲染入口的输入校验"上一条守卫

**判读要求（本项目反复栽跟头的地方）**：

- **必须真的跑进程断返回值与输出**，不能断言源码里出现 `Unknown flag` 字符串
  —— 那是文本存在性断言，本项目已被骗过**五次**。
- **必须同时断两个方向**：
  (a) 未知 flag → 非零退出**且指名是哪个 flag**；
  (b) **全部已知 flag（含带默认值的那些）→ 仍然正常渲染**。
  只断 (a) 的守卫**会被"永远报错"的实现骗过** ——
  **本项目吃过一次这种亏**（第一版守卫数 `assert` 存在性，被 `assert True` 骗过）。

**至少两条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 移除未知 flag 检查（恢复静默） | 守卫红 |
| 让 `render.mjs` 对**任何**参数都报错 | 守卫红（这条专抓上面那个陷阱） |

⚠️ **变异 2 要小心**：它会让渲染真的启动，**必然产生 bundle 目录**。
**必须清理**，且收尾报告要写明。

**若某变异存活**，判定"真漏洞"还是"无效变异"，两种都写进 commit。
**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
4. **每条毒变异之后从快照复原源文件，收尾核对三个 sha256。**
5. **⚠️ 磁盘纪律**（见第 1 件事）：输出到 **E:** 盘，跑完清理，
   收尾报告列出造了什么、删了什么。**发现不是你的既有 bundle 目录，报告但不要删。**
6. **测退出码不要用管道。** 用 `> file 2>&1; echo $?`。
7. **写长文本在字节层操作**；**不要在 bash 双引号里写带反引号的 Python 代码**。
8. **`/tmp` 在 bash 与 Python 中解析不同**（`C:\Users\pc\AppData\Local\Temp`）。
   上一轮 agent 因此**把 714 KB 泄漏进仓库根**（相对 `--out` + `render.mjs` 不拒绝未知 flag）。
   **用绝对路径。**
9. **行尾按文件实测**，不要相信任何人的断言包括本工单的。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录（含 `out/p13_probe/`）；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— cv2 只装在 3.10，本项 `--ignore`
- **不要实现 P14 的长驻 worker 或分级渲染** —— 已裁定 B + C，**不要重新讨论**
- **不要改 `render.mjs` 的清理逻辑**（那段是为修 46 GB 事故写的）
- **不要改 `still.mjs`** —— 它是**正确**的那一方
- **不要删任何不是你自己造的既有 bundle 目录**

**本指令授权你修改**：`studio/bin/render.mjs`、相关测试文件、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（且当前网络不通）
- 交付时报告：
  - **失效形态的完整复现**（真实退出码 + 输出）
  - **你怎么界定 `render.mjs` 的已知 flag 集合 + 布尔型怎么处理**
  - **你怎么处理那条钉住现状的守卫**（重写 / 删除，理由）
  - **全量测试数字**（实测基线 + 改完后）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **三个 sha256 的比对**
  - **磁盘纪律**：造了什么、删了什么、发现了什么不是你的
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**跨阶段**：1.3 / 10.2（VLM Critic provider 抽象；
**已裁定标依赖、不合并、不重复建** —— 仓库至今无 `take_critic.py`）、
**P15** SR 路由、**P16**–**P18**。

**已裁定不要再讨论**：
- P13 `13.1` = **B 不值得建**（bundle 只占 6% 且每进程 mkdtemp）、
  `13.2` = **C 现在不建**（被产物不可复现 / 无人察觉 scene 变更 / re-encode 未实测挡住）
- P14 = **B + C**（常驻 bundle 净省 0.0s，靠放松 46 GB 清理逻辑换来 1.2s）
- P12 = **零段值得建**

**P13 遗留的两处未决**：`visual_qa.py` 的 `--frame` + 坏 `--props` 组合未测；
props 分支的 finding 现在排在 frame findings 之前。

**P12 遗留**：`chartLanguage` / `audioLanguage`（声明了但零消费，P11 方向）。

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** —— 仪器已建成（`chart_geometry.py` / `c6d7a5a`），修复器**故意未写**：
  已交付图表比值 **0.278**，无碰撞可修。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由
  "重新测量仍在碰撞"决定，而非计数器。
