# 执行指令 — 补守卫：白名单名字可以被重新绑定到源文件

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 本指令**取代**先前的 `docs/WORKORDER_P11_TEST_POLLUTION_FIX.md`（那项已完成，提交 `0567d2c`）。
> 范围很小：一条守卫 + 它的变异测试。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| 上游 | 本地领先 `origin/main` **10 个提交，未推送** |
| 基线 | `235 passed, 2 skipped` |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

**开工前先记录 `studio/src/templates/finance-showcase/design/tokens.ts` 的 sha256，收尾时比对。**
当前应为 `6a89a5b453779418…`，`lg: 40` 恰好出现 1 次。

---

## 一、指挥窗口复验发现的洞（已实测，非推断）

`0567d2c` 的核心成果是对的：`space_tokens(path=...)` 已接受副本路径，
三条测试改用 `tmp_path` 副本，全量跑完源文件逐位未变——指挥窗口独立复现了这三条。

**但那条结构性守卫有一个真漏洞。**

`tests/test_chart_geometry.py` 的 `test_no_test_in_this_module_can_reach_the_real_tokens`
检查的是**接收者的名字**：

```python
receiver = ln.strip().split('.write_')[0]
assert receiver in {'dst', 'copy', 'probe'}
```

它问的是"这个名字叫什么"，**不是"这个名字绑定到哪"**。

指挥窗口实测了这样一个变异（白名单里的名字被重新绑定到真文件，再写）：

```python
dst = tmp_path / 'tokens.ts'
dst = TOKENS_TS                      # 变异：重绑到真文件
src_bytes = TOKENS_TS.read_bytes()
dst.write_bytes(src_bytes.replace(b'lg: 40', b'lg: 88'))
```

结果：

| 现象 | 结果 |
|---|---|
| 源文件是否被污染 | **是**，`lg: 88` 写入，sha256 → `2b796b83800d5800…` |
| 结构性守卫 | **通过**（`dst` 在白名单里） |
| 最终为何转红 | `space_tokens()` 的断言失败，**不是**那条守卫 |

**所以 `0567d2c` 声称的"no test holds a writable handle"尚未成立。**
原 bug 的形状仍能重现并污染文件，只是这次被别的断言偶然抓到。

（指挥窗口已把源文件还原为 `6a89a5b4…`，与 HEAD 一致，全量 235 passed。）

---

## 二、同一句话在别处已经写对了

这条守卫自己的 docstring 批评过这个毛病：

> A guard that rejects correct code for using a variable is the same mistake as
> the assertion that fires for the wrong reason: both make the reader distrust
> the next red.

**批评是对的，代码没照做。** 你的任务是让代码兑现 docstring 已经声称的性质。

---

## 三、要求

守卫必须断言的是**绑定关系**，而不是名字。具体：

1. 白名单里的每个名字（`dst` / `copy` / `probe`）在其**任何一次绑定**时，
   右侧都必须是 `tmp_path` 的子路径，不得是 `TOKENS_TS` 或任何指向 `studio/src/` 的路径。
2. 仍然**不得**因为拼写不同而误报正确的代码——`dst.write_bytes(...)` 是对的
   （`dst` 就是 `tmp_path/'tokens.ts'`）。
3. 断言要能覆盖**多行**的绑定，例如
   ```python
   dst = (
       TOKENS_TS
   )
   ```
   必要时用 AST 而不是逐行文本匹配。**AST 是首选**：逐行匹配正是当前守卫的病根。

### 验收标准（唯一且硬）

第一节那个变异——把白名单名字重绑到 `TOKENS_TS` 再写——必须让
**`test_no_test_in_this_module_can_reach_the_real_tokens` 本身**转红。

不是"套件某个测试转红"。**红在这条守卫上，才算修好。**
若它只是让别的断言红而这条仍过，等于没修。

---

## 四、变异测试

至少包含：

| 变异 | 期望 |
|---|---|
| 白名单名字重绑到 `TOKENS_TS`（第一节那个） | **这条守卫**转红 |
| 绕过式：`TOKENS_TS.write_bytes(...)` 直接写 | 这条守卫转红 |
| 名字拼写变体（`d = tmp_path/'x'` 后 `d.write_text`） | **不得**误报 |
| 守卫退回逐行字符串匹配 | 红（它会漏掉多行绑定） |

**「变异存活」≠「变异无效」**：存活项要判定是真漏洞还是方向上无效的变异，
两种都写进 commit。**不要造 contrived 输入去杀无效变异。**

若沿用 `studio/scripts/mutation_harness.py`，请注意它只还原**测试文件**，
不还原被污染的 token——含"原地改写"类变异的运行结束后**必须手工核对 sha256**。

---

## 五、纪律

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**
- 交付时报告：**全量测试数字**、**逐条变异结果（含存活判定）**、
  **第一节那个变异具体红在哪条测试上**、以及 `tokens.ts` 的 sha256 比对结果
- **不要修改 `studio/src/templates/finance-showcase/design/tokens.ts`**
- 不要动 `docs/UPGRADE_PROGRESS.md`（账本由指挥窗口统一更新）
- 不要删除 `out/` 下任何证据目录

---

## 六、队列

修完本条后，下一项是 **11.2 接线守卫**
（`docs/WORKORDER_P11_11_2_WIRING.md`，需把其中基线 `234 passed` 更新为实测值）。
指挥窗口会在你交付后统一更新那份指令，届时再派工。
