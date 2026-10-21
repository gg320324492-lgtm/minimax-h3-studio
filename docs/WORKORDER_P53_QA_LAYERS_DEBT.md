# 执行指令 — P53：还 `qa_layers.py` 的一笔已知债，**并查清状态陈述有没有守卫**

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> ⚠️ **本项的第一条债是登记在案的，第二条是没人看守的。第二条才是重点。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | 指挥窗口派工时的 `main`（⚠️ **本仓有别的会话在提交**，见第四节） |
| 基线 | **⚠️ 本机全量套件测不出稳定数字** —— 三次连跑三个不同失败集合，<br>而每个失败文件单跑都绿。**开工前自己测一次，并注明是否并发、是否清过探针。** |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**（GBK 控制台把 `—` 显示成替换字符）。
**读非 ASCII 用字节判断，别信控制台。**

**⚠️ Shell 状态在两次工具调用之间不保持**。**全程用绝对路径**。
**⚠️ `git add` 用显式路径**，不要用 `-A` 或 `.`。

**开工前记录 sha256，收尾比对**：
- `studio/scripts/qa_layers.py`
- `tests/test_p40_docstring_counts_match_code.py`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 第一条债：**登记在案的过期数字**

`studio/scripts/qa_layers.py:264-266`：

```
'calling it on two different graphs). MEASURED: 22 scene '
'types declared by SceneType, 13 named by '
'SCENE_RENDERERS, 9 in between rendering the MissingScene '
'placeholder. No threshold — …'
```

**实测（用 `tests/test_p26_scene_type_coverage.py` 自己的解析器）**：

| | 散文写的 | 实测真实 |
|---|---|---|
| `SceneType` 声明 | 22 | **22** ✅ |
| `SCENE_RENDERERS` 注册 | **13** | **20** ❌ |
| 落空渲染 | **9** | **2**（`video` / `data-plane-3d`）❌ |

**⇒ 这正是 P26/P38 当年裁定过的那个数字（"9 种 → 2 种"）** ——
P38 订正了 `visual_qa.py:1051-1054` 的 docstring，**漏了这里**。

### 2. ⚠️⚠️ 而它**不是漏网之鱼** —— 它是**登记在案的未偿还债务**

`tests/test_p40_docstring_counts_match_code.py` 有 `_KNOWN_DEBT`：

```python
_KNOWN_DEBT = {('studio/scripts/qa_layers.py', 'SCENE_RENDERERS'): …}
```

**且有一条专门的守卫** `test_the_known_debt_sites_are_still_the_debt_they_claim`，
它要求：**该站点仍在引用那个过期数字、那个数字仍不等于真实值**，
并写着 *「the day it is fixed, this goes red and the entry must be deleted」*。

**⇒ 机制设计得很好：这条债不会悄悄变化，但也不会有人去还。**
**⇒ 指挥窗口的判断：真正该做的不是"抓新的过期数字"，是"还这笔债"。**

### 3. ⚠️ 第二条：**没有任何东西看守的状态陈述**

`studio/scripts/qa_layers.py:270-272`：

```
'font_size': ('UNVERIFIABLE on all 333 corpus frames when no --declared-px is '
              'supplied, because a ratio needs both sides. It is Layout in what '
              'it MEASURES, and it is dead in this CLI as shipped.'),
```

**⚠️ P52（`e027040`）刚刚改变了 `rule_font_size` 的行为**：
它现在**永远返回 `UNAVAILABLE`**（不再是"没给 `--declared-px` 时 UNVERIFIABLE"），
而且**它照旧测量**（bands / median / declared / ratio 全在 `extra` 里）。

**⇒ 那段散文现在每一句都不成立了**：状态错了（UNVERIFIABLE → UNAVAILABLE）、
"dead in this CLI" 也不对了（它测量，只是不判）。

**⚠️ 而它没有被任何守卫看着** ——
P40 的守卫只管**集合大小**这类数字，**不管"某规则在某条件下的判读状态"这种陈述**。
**⇒ P52 刚制造了一个新的、无看守的过期陈述。这就是本项的重点。**

### 4. `MEASURED_NOTE` 这个字典存在的理由，**恰好就是"防漂移"**

`qa_layers.py:170-172` 的注释：

> *"MEASUREMENTS THAT QUALIFY AN ENTRY. Kept beside the table so a reader does
> not have to take the layer on faith, **and so a guard can assert the layer
> without the measurement drifting out of the file that states it**."*

**⇒ 这个字典自己宣称它需要守卫。而它的两条测量陈述现在都漂了。**

---

## 二、你要交付的东西

### 第 1 件事：**还第一笔债**（机械，但必须做对）

1. 把 `:264-266` 的数字改成实测值（**22 / 20 / 2**），⚠️ **不要只改能改的那部分** ——
   **"9 in between" 也是错的**，且它是 P26/P38 专门裁定过的那条；
   ⚠️ **同时确认那句散文的其他部分是否还成立**（例如 "rendering the MissingScene placeholder"）；
2. **删掉 `_KNOWN_DEBT` 里那一条** —— ⚠️ **守卫会强制你删**
   （`test_the_known_debt_sites_are_still_the_debt_they_claim` 断言该站点不再引用那个数字、
   且该数字不再不等于真实值）。**删之前请确认守卫真的会红。**

### 第 2 件事：**修第二笔债（font_size 状态陈述）**

⚠️ **⚠️ 这条不是"把 UNVERIFIABLE 改成 UNAVAILABLE"就完事。**
请先回答：**那段散文该说什么？**

- 它现在的三句：**状态**（UNVERIFIABLE…）、**理由**（ratio 需要两边）、
  **结论**（"dead in this CLI as shipped"）；
- ⚠️ **P52 之后，这三句分别该是什么？** 请按 P52 的实际行为写，
  **并明确指出"它仍然测量，只是不判"** ——
  **因为丢掉"它仍在测量"这个事实，读者会以为这台仪器没在工作。**

⚠️ **⚠️ 而这里有一个真问题，不是文字问题**：
**`MEASURED_NOTE` 声称需要守卫，而 `font_size` 这一条证明它没有。**
**⇒ 请判定：**
- **A. 给"状态陈述"建一条守卫**（例如：某规则的判读状态必须与实际调用一致）；
- **B. 不建**，并说清为什么这个缺口可接受；
- **C. 别的**。

⚠️ **若选 A，请先证明它不会误报** ——
**"状态陈述"的写法比"集合大小"自由得多，一台宽泛的匹配器会满地误报。**
⚠️ **⚠️ 特别提醒**：本项目刚在 P51 做完一件事 ——
**一份判据该有的形状是"可判定、且能指出正负类"**，
**而"某条散文说某规则是 UNVERIFIABLE"这种陈述，判据是什么？**

### 第 3 件事：**若第 2 件事判 A，给它三条变异**

| 变异 | 期望 |
|---|---|
| **把 `rule_font_size` 的判读从 UNAVAILABLE 改成别的**（例如改回 UNVERIFIABLE） | 守卫红（**专抓"散文与实现脱钩"**） |
| 让散文里的状态陈述与实现一致、但守卫判据恒真 | 守卫红 |
| 让判据永远判"通过" | 守卫红 |

⚠️ **"红在错误的理由上"不算通过**。⚠️ **每条毒变异后从字节快照复原，收尾核对 sha256。**

---

## 三、验证协议

1. **测量前先证明被测对象存在**（先确认那两处散文真的不成立，别只读代码）；
2. **贴原始输出**，不贴结论句；
3. ⚠️ **五条高频复发**：先证明被测对象存在再测量；**在错误的尺度上测等于没测**；
   **外推等于没测**；**写数字要么实测要么标注未测**；**CRLF 用字节计数验**；
4. ⚠️ **磁盘**：本项基本不渲染。**若你渲染，输出到 E 盘**，跑完清理。
   ⚠️ **⚠️ 指挥窗口上一轮忘了清自己 8 MB 的探针残留，
   而失败的 `test_a_finished_render_leaves_no_bundle_directory_behind` 恰恰是查残留的。别成为下一个。**
5. ⚠️ `tests/test_markdown_text_is_intact.py` 守着全仓 markdown 的 U+FFFD。
6. ⚠️ py-3.10 有 cv2 但没有 pytest —— 需要 cv2 就写进普通函数用 3.10 驱动。

---

## 四、不要动的东西

- `docs/UPGRADE_PROGRESS.md` —— **账本由指挥窗口统一更新**
- ⚠️⚠️ **本仓有别的会话在提交，而且工作树里有不属于本项的在制工作**：
  ```
   M studio/src/Root.tsx
  ?? intro_video/
  ?? studio/public/audio/intro/
  ?? studio/src/templates/model-intro/
  ```
  **⚠️ 那不是你的，不要碰、不要提交、不要为了让它变绿而改它。**
  **⚠️ 并且：既然别的会话会提交，你的提交可能与它撞车 ——
  `git add` 务必用显式路径，且提交前先 `git status` 看一眼。**
- ⚠️ **`tests/test_p42*`、`test_p46*`、`test_p27*`、`test_p49*`、`test_p50*`、
  `test_p51*`、`test_chart_type_defaults_are_real.py`、`tests/tautology_criterion.py`**
  —— **P49/P50/P51 的成果，别碰**
- `out/charts_demo.mp4`、`out/p45_vlm/**`、`out/p48_reaccept/**` —— 只读
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`~`docs/P52*.md` —— 只读
- `DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要动 `studio/src/**`**（本项只改 `studio/scripts/qa_layers.py` 与测试）
- **不要动 P19–P52 的任何成果**

**本指令授权你修改**：`studio/scripts/qa_layers.py`、
`tests/test_p40_docstring_counts_match_code.py`（**仅限 `_KNOWN_DEBT` 那一条与其守卫**）、
相关测试、新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（**只 stage 你自己的文件**）
- 交付时报告：
  - **第一笔债：改了什么、守卫是不是真的红了**（贴 `-rf`）
  - **第二笔债：那三句散文分别该是什么 + 你的依据**
  - **⚠️ "状态陈述要不要守卫"：A / B / C + 理由**（最重要）
  - **若选 A：那三条变异的 `-rf`**
  - **若选 A：你的判据为什么不会误报**（**正负类各是什么**）
  - **全量测试数字 + 是否并发 + 是否清过探针**
  - **两个 sha256 比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染**；用**字节层快照**
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列（供你了解上下文，不必处理）

- **并行跑**：**P54** 在修 `c05_bubble` 的 `chart.sizes` 惰性字段
  （**不同文件，无冲突**）。
- **P49 登记未修**：`camera.focus`、`bible.camera.durationSeconds` **零读者**。
- **P43 `data-plane-3d`** —— 判 C。**`video`** —— 等外部素材。
- **P16 / P17** —— 卡在 "premium" 无判据。
- **已裁定关闭**：11.1 / 12.2 / 12.3 / 13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1。