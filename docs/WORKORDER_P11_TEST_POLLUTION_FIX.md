# 执行指令 — 修复测试污染源文件的缺陷（优先于 P11 第三项）

> 给执行 agent。本文件**自包含**，不依赖任何既往对话。
> 发出方是指挥窗口（复验官）。你只负责执行，**不做放行/退回裁定**。
>
> **优先级说明**：本指令**取代** `docs/WORKORDER_P11_11_2_WIRING.md` 成为你的第一项任务。
> 11.2 接线守卫的派工**暂缓**，原因见第五节。

---

## 零、角色、仓库与环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| 你的角色 | **执行 agent**。写代码、跑测试、自证。**不做放行/退回裁定** |
| 上游状态 | 本地领先 `origin/main` **7 个提交，未推送** |
| 全量测试基线 | `234 passed, 2 skipped` —— 已在 `lg: 40` 下实测确认 |

环境（已实测，**不要改动**）：
- pytest 只装在 **Python 3.12**：用 `py -3.12 -m pytest`
- cv2 只装在 3.10 → `tests/test_take_selection_behaviour.py` 必须 `--ignore`
- 标准跑法（**从仓库外跑**，既定协议）：
  ```
  cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q \
      --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py
  ```

---

## 一、缺陷：测试会污染源文件，且污染会自我维持

### 现象

`tests/test_chart_geometry.py` 有三条测试**原地改写** `studio/src/templates/finance-showcase/design/tokens.ts`：

```python
original = tok.read_bytes()
try:
    tok.write_bytes(original.replace(b'lg: 40', b'lg: 88'))
    ...
finally:
    tok.write_bytes(original)
```

正常结束靠 `finally` 还原。但一旦测试进程**被中断**（Ctrl-C、kill、超时），
`finally` 不执行，`tokens.ts` 就停在 `lg: 88`。

### 指挥窗口补充的实测（复现步骤已验证）

用 `lg: 40` 的真实文件跑这条测试，**正常路径下污染会被 `finally` 还原**。
把自己置于污染态（文件已是 `lg: 88`）再跑同一条测试，实测结果是：

```
FAILED test_a_changed_design_token_moves_the_geometry_with_it
E  assert 1620.0 < 1620.0
```

**注意红在哪一句**：红的是第二段 `assert after < before`（plot.w 1620 vs 1620），
而**真正该抓这件事的 `assert sp['lg'] == 88.0` 反而通过了** —— 因为文件已经是 88。
测试用"结果不相等"间接报错，**不是用它声称的机制报错**。

这一点对修法有直接影响：**只把替换去掉、不动其余断言，这条测试可能变红也可能变绿，
取决于 `after` 与 `before` 是否碰巧相等** —— 所以第三节要求杀的那个变异，
必须由**新的守卫**（源文件只读 / 替换真的发生了）来保证，而不是靠这条旧断言的副作用。

### 为什么它会自我维持（关键）

还原之后**再跑一次**，链条变成：

1. `original = tok.read_bytes()` 读到的已经是 `lg: 88`
2. `original.replace(b'lg: 40', b'lg: 88')` —— **匹配不到任何东西，什么也不替换**
3. `space_tokens()` 读回 88，`assert sp['lg'] == 88.0` **通过**，
   但后续 `assert chart_geometry.space_tokens()['lg'] == 40.0` **失败**
4. `finally` 把 `original`（**即 88**）写回去 → **污染固化**

此后每次运行都会失败，且失败会持续把 88 写回去。**这不是测试不稳定，是它把仓库钉住了。**

**第 4 步是"自我维持"的确切原因**，比"下次 replace 匹配不到"更靠前：
即使 `finally` **正常运行**，它写回的 `original` 本身就是被污染的那一版，
所以固化不依赖进程被打断。中断只决定**第一次**污染怎么发生的。

### 它打掉了什么（指挥窗口已实测）

`SPACE.lg` 变成 88 后，下列 4 条断言连锁失败：

| 失败断言 | 现象 |
|---|---|
| `band_step(5) == 334±3` | 得 324.0 |
| `band_step(16) == 104.2` | 得 101.25 |
| 隐含 gutter `== 58.6` | 得 108.0 |
| `worst ratio == '0.278'` | 实测 0.286 |

**仪器本身没有错，断言也没有错** —— 两者都建立在 `lg: 40` 这个真实设计值上。
`git show HEAD:studio/src/templates/finance-showcase/design/tokens.ts` 是 `lg: 40`，
P6.7 遗留项要求的是让**步长**向 `4…96` 靠拢，不是把某个 token 改成 88。

### 已确认的前提

指挥窗口已把 `tokens.ts` 还原为 `lg: 40`，工作树干净，
全量 `234 passed, 2 skipped`。**你开工时基线是绿的。**

---

## 二、修法（方案 A，已由指挥裁定）：源文件全程只读

**核心矛盾**：这几条测试的价值是"证明仪器读的是源文件而不是写死的字面量"，
而为了证明这件事去**改写源文件**，本身自相矛盾。

**做法**：

1. `chart_geometry.space_tokens()` 增加一个可选路径参数：
   ```python
   def space_tokens(path: Path | None = None) -> dict[str, float]:
       """... `path` exists so tests can point this at a COPY. Nothing in this
       module should ever write to the real design tokens."""
   ```
   默认仍读 `studio/src/templates/finance-showcase/design/tokens.ts`，
   保持 CLI 与既有调用行为不变。

2. 三条测试改为：用 pytest 的 `tmp_path` **复制**一份 `tokens.ts`，
   对副本做 `lg: 40 → lg: 88` / 删除 `lg` 的替换，
   再 `chart_geometry.space_tokens(path=copy)`。

3. **`chart_geometry.py` 与 `tokens.ts` 全程不得被写入。**

### 必须自证的性质

加一条守卫，断言**源文件在任何测试运行后都不变**。建议做法：
在测试模块里记录进入时的 `tokens.ts` 字节（`hashlib.sha256`），
在每条会用到它的测试结束时比对；或加一个 autouse fixture 做前置快照 + 后置比对。

这条守卫的意义：**它必须能让"将来有人再引入原地改写"立刻变红**。

---

## 三、变异测试（硬要求）

至少包含，逐条记录结果：

| 变异 | 期望 |
|---|---|
| `space_tokens()` 忽略 `path` 参数，永远读真实源文件 | 红（副本测试会失效） |
| `space_tokens()` 改成返回写死字面量 | 红 |
| 删掉守卫"源文件运行后未变" | 红 |
| 把 `lg: 40 → 88` 的替换去掉（测试改成不验证任何变化） | 红 |

**「变异存活」≠「变异无效」**：若某变异存活，先判定它是真漏洞还是无效变异
（方向上不可能改变行为的那种），两种都要在 commit 里写明理由。
**不要为了杀掉无效变异去造 contrived 输入。**

### 第四条变异的一个陷阱（指挥窗口实测，见第一节补充）

旧测试**在污染态下确实会红**，但红在 `assert 1620.0 < 1620.0`，
而不是它声称要抓的那句 `assert sp['lg'] == 88.0`。

所以"去掉替换"这个变异，**不要指望靠旧断言的副作用被抓住** ——
如果你的新写法让 `after == before` 仍然成立，旧断言会**变绿**。
新守卫必须独立地断言两件事：

1. **源文件运行后逐字节未变**（`lg: 40` 仍在）
2. **副本上确实发生了替换**（替换后的副本里 `lg: 88` 出现，且 `original` 里没有）

第 2 条尤其重要：它把"我改的是副本"变成一个**可证伪的事实**，
而不是"我调了一个看起来像替换的方法"。

---

## 四、必须复查的一件事（指挥窗口有一条未结的疑点）

指挥窗口在 `lg: 88` 下实测到：**渲染 c01 场景时 x 标签行整行空白**
（标签带 y790-820 最大亮度 49 = 柱体填充，而同帧轴标签行有 95 的真文字）。

在 `lg: 40` 下标签**正常渲染**于 y932-946（那正是 11.1 实测过的位置）。

**你在修完测试污染后必须重新验证这一点**，并明确回答：

1. 在**当前 HEAD（`lg: 40`）**下，渲染 `pipeline/examples/charts_demo.json`
   的第 0 场（c01_bar），x 标签是否正常渲染？
2. 若仍空白，**它与 `SPACE.lg` 无关**，需要定位真实根因。
3. 若正常，则可确认那是 88 特有现象；但仍需说明
   **`lg` 变大是否会让标签被推出可视区** —— 即 `padY = lg*2` 增大后
   `plot.h` 缩水，标签行是否可能落到画布外。这是**几何关系问题**，
   与当前是否触发无关，值得写进 11.1 的已知风险。

渲染命令（注意 `--props` 必须指向**被跟踪的源图谱**）：
```
cd E:/Minimax-H3 && node studio/bin/still.mjs --comp FinanceShowcaseWide \
    --props pipeline/examples/charts_demo.json --out <你的临时目录> --frames 40
```
用 `tmp` 目录，**不要写进 `out/` 证据目录**。

---

## 五、为什么 11.2 接线守卫暂缓

派工基线写在 `docs/WORKORDER_P11_11_2_WIRING.md` 里是 `234 passed`，
而执行 agent 实测拿到 `4 failed, 230 passed` —— **问题不在它，在源文件被污染**。
在几何真值可能失真的 HEAD 上写守卫，等于让守卫对着一个未知的布局立约。

修完本指令、第四节复查有结论后，再恢复 11.2 派工。

---

## 六、纪律

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（推送由指挥窗口裁定）
- 交付时必须报告：**全量测试数字**、**逐条变异结果**（含存活项及判定）、
  **第四节的三个问题的答案**、以及你改动的文件清单
- 不要动 `docs/UPGRADE_PROGRESS.md`（账本由指挥窗口统一更新）
- 不要删除 `out/` 下任何证据目录；不要碰 `DiagOutputDir`
- **不要修改 `studio/src/templates/finance-showcase/design/tokens.ts`** ——
  本任务就是要让任何人都改不动它

---

## 七、指挥窗口自己的归因错误（同一类失效的另一面，值得你知道）

指挥窗口在派工前把这次污染归因为"外部编辑"，**归错了**。
真实原因是上一轮的全量 pytest 自己污染了它。

错的方式和这个缺陷同源：**我把"文件 mtime 很新"当成了"有人改过它"的证据，
而没有去查"是谁写的"** —— 事实上只需 grep 一次
`tests/test_chart_geometry.py` 就能看到那三处 `write_bytes`。

**教训**：一次"看起来像外部原因"的现象（本项目反复出现"有人改了文件"这类
归因），第一反应应该是**在仓库内找写入方**，而不是找仓库外的原因。
测试污染源文件这件事，在本项目里已经发生过一次，是同一条老教训的新形态：
**一个会改变世界的动作，来源不明时先查来源。**
