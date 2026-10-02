# 执行指令 — P6.8 Depth 层级：接线了但没人用，且第三层以上没有深度差

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 本指令**取代**此前对 6.8 的任何口头描述（账本第 157 行的表述已被下方实测订正）。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| 基线 | **先自己实测**，不要相信工单里的数字 |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 账本的表述需要订正

账本第 157 行写「`DEPTH` translateZ 阶梯存在，**但四个场景没有一个用它**」。

**实测补充：`DEPTH` 不是死 token，它被接线了。**

- `studio/src/templates/finance-showcase/design/styleBible.tsx:3`
  `import {..., DEPTH, ...} from './tokens'`
- `styleBible.tsx:73` — `depth: mergeSection({...DEPTH} as Record<string, unknown>, b.depth)`
- `styleBible.tsx:173` — `DEPTH: s.depth`

**它进了 StyleBible、被导出、可被 `b.depth` 合并覆盖。**
只是**零场景读取** `useDesign().DEPTH`。

这个区别很重要：**"接线了但没人用"和"没接线"是两个不同量级的缺陷。**
前者的修复是接线消费方，后者的修复是接线本身。请按实测描述，不要沿用账本旧措辞。

### 2. 图谱完全无法影响 `DEPTH`

| 检查 | 结果 |
|---|---|
| `pipeline/schemas/showcase-v1.schema.json` 里 `depth` 出现次数 | **0** |
| `pipeline/**` 与 `studio/public/**` 全部 JSON 里设 `"depth"` | **0 处** |
| 设 `"depthCue"` | **0 处** |

**任何图谱都碰不到 depth。** 这不是"作者没设"，是"schema 没有这条通路"。

### 3. `DEPTH_CUE` 只有一个场景在用，且**三层封顶**

`studio/src/templates/finance-showcase/design/themes.ts:88`（dark）/ `:104`（light）：

```
depthCue: ['0 14px 40px …', '0 30px 84px …', '0 46px 132px …']   // 恰好 3 项
```

`studio/src/templates/finance-showcase/scenes/BrowserStack.tsx:257`：

```tsx
const depth = DEPTH_CUE[Math.min(i, DEPTH_CUE.length - 1)] ?? SHADOW.floating;
```

**第 4 个窗口及以后，`Math.min` 把它钳到第 3 项** ——
即 4 层以上的窗口堆叠**每一层都是同一个阴影**，视觉上完全没有深度差。

**这是本项最值得修的一处真缺陷**，且它有明确判据：
**造一个 ≥4 层的 BrowserStack，逐层量阴影是否真的不同。**

### 4. `DEPTH` 的阶梯也不是等差的

`tokens.ts:95-101`：`z0=0, z1=60, z2=140, z3=240, zHero=380`
差值 `60 / 80 / 100 / 140`。这条阶梯的注释已经诚实说明了它零使用 ——
**那段注释是本项目"如实记录未完成"的正面范例，不要把它删掉。**

---

## 二、你要交付的三件事

### 第 1 件事：给 `DEPTH_CUE` 的三层封顶加守卫 + 修掉它

**先测后修**：造一个 ≥4 层的 BrowserStack，
用已有的渲染/`visual_qa.py` 量出第 4 层与第 3 层的阴影**是否相同**。

- 若**相同** → 这是真缺陷。决定修法：
  - 扩 `depthCue` 到 ≥4 层（要选扩展规则，写清依据），**或**
  - 让 clamp 有意义（例如超过 3 层时按序循环 / 按比例插值）。
  **两种都可行，但都要说明为什么。**
- 若**不同** → 说明我的判断错了，如实上报，**不要硬修**。

**守卫要求**：断言「第 N 层的阴影与第 N-1 层不同，N 取到 `depthCue.length`」。
**该守卫必须能失败** —— 把 `depthCue` 缩回两项，它必须红。

**变异至少两条，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| `depthCue` 从 3 项缩到 2 项 | 守卫红 |
| 把 `Math.min(i, …)` 改成恒取 0（全部塌成最远层） | 守卫红 |

### 第 2 件事：给 `DEPTH` 补上诚实标注

`tokens.ts` 里 `DEPTH` 的注释已经说了"no scene uses it" ——
**它现在不准确了**（已接线，只是零消费）。请订正为：

- 它**已**通过 `styleBible.tsx:73 / :173` 接线并可被 `b.depth` 覆盖；
- **零场景读取** `useDesign().DEPTH`（给出你的 grep 证据）；
- 图谱**无法**影响它（schema 零通路，给出你的检索证据）。

**不要删 `DEPTH`** —— 删掉是超出本项范围的决定。
**也不要为了让场景"用上"它而去改任何场景的构图**：
那会改变已交付画面，超出"修复失效"的范畴。

### 第 3 件事：判定「depth 该不该由图谱驱动」

`DEPTH` 接了线、可被 `b.depth` 覆盖，但**图谱里没有任何通路能设它**
（schema 零声明）。这是一条**接了线却永远收到空值的通道**。

请判定并写清依据：

- 若 depth **应当**由图谱驱动 → 给出最小 schema 增补设计（字段名、类型、
  边界、与 `locked_fields.py` 的关系），**但先不实现**，把设计写进 commit message。
  → 是否实现由指挥窗口与用户裁定，**不要自己扩 schema**。
- 若 depth **不应当**由图谱驱动（场景深度是构图函数，与 `spreadZ` 一致）
  → 把结论写进注释，并把 `DEPTH` 标注为"有意保留、当前零消费"。

**注意 `locked_fields.py` 的 `LOCK_RULES`**：若你设计的字段可能落在
11.1 修复器的合法杠杆里（`camera` / `layout` / `motion` 是放行的），
要在交付里指出这一点。

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
4. **每条毒变异之后从快照复原源文件，收尾核对 sha256。**
5. **写长文本在字节层操作**（`read_bytes` + 精确匹配 + 写回），
   `tokens.ts` 与 `styleBible.tsx` 都是 CRLF 文件 —— 用 `read_text`/`write_text`
   会静默翻转行尾，本项目已因此毁掉一次提交。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— cv2 只装在 3.10，本项 `--ignore`

**本指令授权你修改**：`design/tokens.ts`、`design/themes.ts`、
`design/styleBible.tsx`、`scenes/BrowserStack.tsx`，以及新增测试文件。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthroply.com>`
- **提交但不推送**（推送由指挥窗口裁定）
- 交付时报告：
  - **全量测试数字**（实测基线 + 改完后）
  - **「第 4 层阴影是否真的与第 3 层相同」的实测证据**（这是最重要的一项）
  - **逐条变异结果**（贴 `-rf` 原始输出，含存活判定）
  - **`DEPTH` 该不该由图谱驱动的判定 + 依据**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**

---

## 六、队列

**跨阶段**：1.3 / 10.2（VLM Critic provider 抽象；已裁定
**标依赖、不合并、不重复建**，仓库仍无 `take_critic.py`）、
**6.7 Spacing 尺度**（见 `docs/WORKORDER_P6_67_SPACING_SCALE.md`）、
**P12–P18 七段全部未开工**。

**P11 剩两项，卡在同一个解锁条件**：
- **11.1** —— 仪器已建成（`chart_geometry.py`，`c6d7a5a`），修复器故意未写：
  已交付图表比值 **0.278**，无碰撞可修。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由
  "重新测量仍在碰撞"决定，而非计数器。
