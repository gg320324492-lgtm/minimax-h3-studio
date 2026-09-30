# 复验官交接文档 — 2026-10-01

> 给下一个接手复验职责的 agent。本窗口的角色是**独立复验官**，不是施工方。
> 施工方是另一个会话。两者是合作关系：施工方产出，本角色独立取证后裁定放行/退回。

---

## 一、这个窗口的职责

**独立取证，不采信施工方的任何自述。** 施工方的 commit message、进度表条目、汇报文字，
一律视为**待验证的主张**，不视为事实。

五项固定职责：

1. **阶段复验** — 每个 P 阶段提交后独立验证，给出「通过 / 有条件通过 / 退回」。
2. **抓假账** — 本项目已抓到**三次**「记为已修但无产物」。这是本角色最有价值的产出。
3. **推送裁定** — 判断「现在能不能推、先改什么再推」。施工方不会自行 push。
4. **闸门设定** — 阶段顺序的前置条件（例如「P5 开工前必须先接通 style_bible」）。
5. **兜底** — 用户明确说过「之后有问题直接提，你这里是所有问题兜底」。

**工作方式：先测量，再断言。** 本项目第一次假指控就源于未测量下结论，之后所有裁定都要求数字或可复现命令。

---

## 二、当前进度

总任务书 19 阶段（P0–P18），主文档 `docs/UPGRADE_PROGRESS.md`（进度总账）、
`docs/UPGRADE_MASTER_PLAN.md`（总规划）。

| 阶段 | 状态 | 备注 |
|---|---|---|
| P0 审计与生产边界 | ✅ | 12 条风险，修 4 条高危；产出 `pipeline_manifest.yaml` |
| P1 TakeRanker | ✅ | 替换 T01 硬默认，fail-closed |
| P2 ShotSpec + Prompt Compiler | ✅ | **`shot_specs.json` 字段待人工补全**（创作决策） |
| P3 Scene Graph | ✅ | 三端契约 + 卡点量化 |
| P4 FinanceShowcaseWide | ✅ | 四类 scene |
| P5 Motion Foundation | ✅ | 语义 spring + 转场 |
| P6 Design System | 🔄 | 6.1–6.6 ✅；**6.7 SPACE 尺度未统一、6.8 DEPTH 场景未用**；s03 相机斜柱留艺术判断 |
| P7 图表引擎 | 进行中 | 7.0 守卫 ✅、7.1 九种图表 ✅、7.2 统一生命周期 ✅；**下一步 P7.3** |
| P8–P18 | ⬜ | |

**状态**：见下方「复验核实」。工作树干净、`out/charts_demo.mp4` = 1950 帧 32.5s。

**磁盘已解决**：C: 原本 0 可用（127 个 Remotion 临时 bundle / 59 GB），现已清理到
TEMP 5.4 GB、C: 78 GB 可用（复验实测 **77.62 GB / 5.28 GB**，2026-10-01）。
根因也已修：临时目录指向 E:，渲染不再复制 `studio/public/`。

### 进度表的一处已知滞后（**接手时需注意 —— 已由下一窗口订正**）

`docs/UPGRADE_PROGRESS.md` 的**变更记录（changelog）是准确的，但任务表行和阶段表头不同步**：

- `| 7.2 | ... | ⬜ |` — 实际已完成并提交（`7a6bcaf`）
- `| 7.1 |` 行仍写「9 场 1350 帧 / A/B 23 项」，实际 10 场 1950 帧 / 24 项
- 表头 `P7 状态：⬜` 滞后

**判断依据：changelog 可信，任务行与表头需与 git log 交叉核对。**

> 2026-10-01 复核实测：上三条**全部成立**（`charts_demo.json` 10 场 1950 帧、`out/chart_ab.md` 24 行全 LIVE）。
> 但**本节原先还写了「表头 `P6 状态：🔄` 滞后」—— 那是错的**：`P6 🔄` 准确（6.7 尺度未统一、6.8 `DEPTH` 无场景使用，两处均已诚实标注）。
> **教训：交接文档本身也是待验证的主张，不是事实。** 订正见 `UPGRADE_PROGRESS.md` 变更记录 2026-10-01 复验条。

### 复验核实（2026-10-01，接手窗口实测）

原「106 项测试通过」**当前不可复现**：`python -m pytest tests/ -q` 直接 collection ERROR
（`No module named 'cv2'`）—— **pytest 只装在 Python 3.12、cv2 只装在 3.10，106 = 102 + 4
劈在两个解释器里**。实测 **102 passed / 3.16s**（`--ignore=tests/test_take_selection_behaviour.py`，
该文件 4 条测试全需 cv2）。**裁定：不动环境**（用户决定），缺口已记进 `UPGRADE_PROGRESS.md`。

另抓到 **「`lifecycle.check.ts` 60+ 项」是假账**（实测 29 个 `check(` 调用点 / 54 条断言），
以及 **`lifecycle.check.ts` 未接进 pytest** —— `scale.check.ts`、`projection.check.ts` 接了，它没有，
**P7.2 的 54 条守卫目前纯靠自觉**。已并入 7.3 待办。

---

## 三、既定铁律（不要重新商议）

1. **commit 后不自动 push**，除非用户或复验官明确授权。
2. **记账规则**：任何「已修」必须附可复现证据（具体代码值 + 抽帧截图路径）；
   **清理工作树的操作（如 `git checkout`）之后必须重验受影响项。**
3. **改图谱/配置前先 `git check-ignore <file>` 确认目标文件入库** ——
   改在不入库的文件上，从提交产物看等于没做（P6.0 踩过）。
4. **CLI 渲染一律 `--props` 指向入库源图谱**（`pipeline/examples/`）；
   `studio/public/jobs/` 是 gitignore 的暂存副本，只为 Remotion Studio 存在。
   `studio/scripts/stage_showcase.py --check` 可检测漂移（双向：源改了 / 副本被手改）。
5. **不产生零散计划** —— 一切进度记进 `docs/UPGRADE_PROGRESS.md`。

---

## 四、复验协议（实际有效的手法，按价值排序）

这些方法在本项目**各自至少抓到过一个真问题**。

1. **变异测试** — 把修复**改回旧实现**，确认对应测试**转红**。
   守卫的价值不在于通过，而在于能失败。用过：`diff_dir` 残留帧、
   `screenScaleFor` 方向反、Fritsch–Carlson 过冲、`projection.check.ts`。
2. **确定性构造原缺陷场景** — 把最初暴露问题的输入原样搭出来，用它打修复。
   用过：`diff_dir` 的 `a/=f00200+f00400` vs `b/=f00400`。
3. **全历史扫描** — `git log --all --diff-filter=A -- <路径>` 查敏感文件是否**曾**入库。
   只查 `.gitignore` 挡不住历史（R1）。
4. **从仓库外跑测试** — `cd /tmp && python -m pytest <repo>/tests/ -q`。
   证明可移植性；在仓库内跑会掩盖硬编码路径。
5. **像素量化，不靠目检** — 两两距离分布、bbox、逐像素 diff、backdrop 采样。
   用过：`DUP_THRESHOLD` 安全性（0.5 距最近真实差 34.5 倍）、
   Browser Stack 居中（+1.5px）、A/B 矩阵 24 项。
6. **交叉验证** — 同一对象在两个条件下的度量应一致：
   两主题的 `marks` bbox 应相同；mp4 抽帧 vs 新渲应只差编码噪声（实测 0.04%）。
7. **集合差** — 磁盘 `glob` vs manifest 条目；声明选项 vs 实现函数。
   用过：manifest 缺 `quality_compare.py`；17 个默认选项 vs `TYPE_OPTIONS` 覆盖。
8. **时间线核对** — 报告 `stat` 时间戳 vs 提交时间，验证「重跑后才提交」的说法。
9. **重渲取地面真值** — 不信已有成片，自己用源图谱渲一遍。

**工具清单**（都在 `studio/scripts/` 或 `studio/bin/`）：
`ab_field.py`（A/B 像素证据，`--registry` 查注册表）、`chart_ab_matrix.py`（矩阵 + 溯源报告）、
`measure_frame.py`（居中 bbox，背景相对判据，双主题有效）、`still.mjs`（单帧渲染，需 `--props`）、
`stage_showcase.py --check`（图谱漂移）、`projection.check.ts` / `scale.check.ts` /
`lifecycle.check.ts`（可执行检查，无 node 则 skip）。

---

## 五、本项目反复出现的失效模式（重点盯）

**模式一：记为已修但无产物。抓到三次。**
- P0：`check_contract` 在干净 clone 上假通过（`public/jobs/` 被 ignore，props 检查为空）
- P4：commit message 与进度表称「间距 330→250、窗宽 560→520」，代码里**搜不到**这两个值
- P6：称「只改图谱 camera，重渲确认生效」，实测图谱自 P3 起**从未被修改**（改的是 gitignore 的副本）

**模式二：看起来生效，实际不生效。**
- 图谱 `style_bible` 声明 **15 个键，只有 1 个真的生效**（`typography`），
  其余 4 个因类型不符被静默丢弃、`cameraLanguage` 因场景自带值而无效、
  `palette` 抄的是暗色原值，反而把亮主题打成明暗交替。
- `showArea` 在 `types.tsx` 里、注册表里也在 —— 但挂在 **Area 组件**上，每张 line 图都读不到。
- **源码级检查只证明「名字出现在文件里」，不能证明「这个场景真的读到并生效」。**
  所以必须配 A/B 像素证据。

**模式三：工具产出令人信服的错数字。**
- `diff_dir` 用 `next(glob)` 不按帧配对，**三个不同字段返回逐位相同的 33025 px**，
  而那数字是两个不同帧的内容差。裁判会给它从未做过的比较报出精确到小数点后的百分比。
- `measure_frame` v2 用绝对阈值，亮色背景动态范围 11 > 阈值 8 → **整片误判**，
  每一版在暗色上都正确。→ 现已改为「模型解释不了就拒绝出数 + 非零退出」。
- A/B 曾把「调用方路径写错」报成「字段是哑的」→ 现 `BAD PATH`(exit 2) 与 `INERT`(exit 1) 分词。

**模式四：修好一个精度问题，制造镜像缺陷。**
- mtime 猜测 → 严格模式（对）；`round` 起点 + `floor` 时长 → **1 帧重叠** →
  改 `floor` → **1 帧空隙**。同一量级反符号。
- 闸门从 `option()` 拆掉，**入口 `pickOptions` 还留着一道**，而 docstring 声称「表无法让图谱哑」。
- **正确解法通常在二元选项之外**：「由下一场 start 定义本场 end」「history 缺失即 None」、
  「用 `Object.keys(DEFAULT_CHART_OPTIONS)` 而非手维护表」。
  **看到换边，先问有没有让该错误无法写出来的构造。**

**模式五：取错对象，却得到格式正确的答案。**
- `enterFrames` 在 150 帧场景被 34% 封顶为 51 → 测「40 无变化、90 无变化」→ 读成字段坏
- `--frame` 是绝对帧号，写 90 落进第 1 场
- 在没有目标内容的帧上测 → 0px 看起来像「字段没接线」
- 现工具会报 `content on that frame: X%`，**必须主动看这一行**。

---

## 六、本角色自己栽过的（同样要避免）

- **两次未测量就断言**（指控「全部落在半帧内」、指控对方编造），两次都靠自己跑一遍数字纠正。
  → 教训：**先测再断言，包括对施工方的指控。**
- **五次误用 A/B 工具**（`--frames` 拼错、值类型不匹配、缺数组下标、多一层 `opts`、
  在错的帧上测）—— 前两次被工具拦下，后三次全部报成 INERT，**与「字段是哑的」无法区分**。
  → 这三条直接催生了工具的输入校验与 `BAD PATH` 分词。
- **P7.2 那轮三次图读出错**：目检判定「渲染出亮色 Browser Stack、props 没进组件」，
  顺着这条线查了四层代码，最后**像素测量全盘否定目检**（实为暗色、bbox 正是满帧柱状图）。
  → 结论：**只认数字；目检结论必须先过一遍像素量。**
  → 附带：该轮早期对 `charts_demo.mp4` 的目检不可靠，**不再作为证据引用**。

---

## 七、待办与我留下的盯防点

**接手后第一件事建议**：跑一遍
`git log --oneline -5 && git status --short && python -m pytest tests/ -q`
（**注意：`python` 当前指向 3.10、无 pytest，会报 `No module named 'pytest'`；带 pytest 的解释器是
`C:\Users\pc\AppData\Local\Programs\Python\Python312\python.exe`，但它没有 cv2，所以这条命令
会停在 collection ERROR 而不是给出测试数 —— 见第一节「复验核实」**）
以及**逐条核对进度表任务行与 git log**（见第二节的滞后说明）。

- **P7.3**：annotation 避让 / 数字格式 / theme / stagger / emphasis 收口 —— 下一个施工目标
- **P8 时我盯一条**：把 A/B 矩阵接进 `tests/` 当 CI 项。
  现在它是「跑一次存一份报告」，跑不跑全凭自觉；接进去才能从流程变成机制。
- **P6 未完**：6.7 `SPACE` 仍 8…168 而非规定的 4…96；6.8 `DEPTH` 无场景使用（已诚实标注）；
  s03 相机 `rotateX:[12,2]` 把竖柱剪斜（**艺术判断，未擅自改**）
- **P2**：`shot_specs.json` 的 subject/action/camera 拆分待**人工**补全
- **音频**：`out/audio_preview.m4a` 听感验收待人工

---

## 八、一句话总结这个项目

**架构方向是对的，四类问题反复出现：假账、哑声明、工具给错数字、修复制造镜像缺陷。**
有效的对策只有两个：**让错误在结构上不可表达**（而非选对参数），
以及**让每个数字都能被独立重跑**（而非相信一句「已验证」）。
