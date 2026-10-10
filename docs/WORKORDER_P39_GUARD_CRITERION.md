# 执行指令 — 修 4.9 守卫的判据不一致：前半段按字段名，后半段按裸数字

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `a9038d9`（已推送） |
| 基线 | **先自己实测**（⚠️ 见第一节第 3 条：**当前有 1 条已知红**，不是你的） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ `tests/test_take_selection_behaviour.py` **必须 `--ignore`**。
⚠️ **标准跑法不要导出 `PYTHONIOENCODING`**。

**⚠️ Shell 状态在两次工具调用之间不保持** —— 有 agent 因此中断过。
**全程用绝对路径**，命令以 `cd E:/Minimax-H3 &&` 开头。

**⚠️ 工作树里有不属于本线的东西**：`studio/src/water-renewal/`（12 个文件）、
`studio/bin/render-water.mjs`、`studio/tsconfig.water.json`、`studio/package.json` 与
`pnpm-lock.yaml` 的改动、`.cache/`。
**⚠️ 那不是你的 —— 不要碰、不要提交、也不要为了让它变绿而改它。**
**⚠️ `git add` 用显式路径，不要用 `-A` 或 `.`**（上一项 P36 的六个文件就是被并发 agent 的
`git commit` 卷走的）。

**开工前记录 sha256，收尾比对**：
- `tests/test_p4_9_ledger_numbers_resolve.py`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺陷：**同一个文件里两种判据**

`tests/test_p4_9_ledger_numbers_resolve.py`：

**前半段（`:280-292`）已经是按字段名判定的** —— 而且判得很精确：

```python
assert not _value_is_field_value(DATA_COLUMNS, 'fieldHeight', 480), (
    'fieldHeight 480 is the phantom 4.9 invented; it must not resolve')
assert not _value_is_field_value(BROWSER_STACK, 'columnWidth', 520), (
    '520 is a windowWidth, not a columnWidth; a value must resolve only for its own field')
```

**后半段（`:305-317`）却退回到裸数字全仓扫描**：

```python
def test_the_two_numbers_4_9_invented_still_exist_nowhere():
    """`场高 480` and `translateY(-330*s)` were never real. Pin the absence."""
    files = sorted(
        [p for p in SRC_ROOT.rglob('*.ts')] + [p for p in SRC_ROOT.rglob('*.tsx')]
        + [p for p in PIPELINE.rglob('*.json')]
    )
    for value in PHANTOM_NUMBERS:              # PHANTOM_NUMBERS = [480, 330]
        pattern = re.compile(r'(?<![\d.])' + str(value) + r'(?![\d.])')
        hits = [...]
        assert hits == [], f'{value} now appears in: {hits}'
```

**⇒ 任何在任何源文件里用了 `480` 或 `330` 的代码都会让它变红，
无论那个数字与 4.9 声称的东西有没有关系。**

### 2. 触发它的是什么

**`studio/src/water-renewal/`（不属于本线、未跟踪）里出现了这两个数字**：

```
BubbleScene.tsx:13   <Statement top={330} .../>
EcologyScene.tsx:30  <BlendSequence from={330} durationInFrames={105}>
ValidationScene.tsx:12 <BlendSequence from={330} .../>
```

**⇒ 那是时间轴偏移参数，与 4.9 那条账本缺陷毫无关系 —— 纯粹是数字撞了。**

### 3. ⚠️ 当前基线：**1 条已知红**，不是你的

```
FAILED tests/test_p4_9_ledger_numbers_resolve.py::test_the_two_numbers_4_9_invented_still_exist_nowhere
3 failed 时共有三条，其中另两条是：
  · test_markdown_text_is_intact  ← 已在 5a754d2 修掉
  · test_p14_render_entry_points  ← GBK 控制台把省略号显示成替换字符，纯假象
```

**⇒ 本项修完，那条应当转绿。请先自己实测确认基线。**

---

## 二、你要交付的三件事

### 第 1 件事：先回答"这条守卫到底该断言什么"

⚠️ **它的意图是**「4.9 声称修过的东西至今不存在」。

**但「不存在」这个词需要精确化**：

- **强版本（现在的）**：**整个仓库里任何文件都不含 `480` / `330`** ⇒
  **过强**，会拦住任何碰巧用这些数字的无关代码；
- **弱版本**：只要 **`fieldHeight` 不解析为 480、`translateY` 不回到 DataColumns** 即可 ⇒
  **前半段的 `_value_is_field_value` 已经在断言这件事**。

⚠️ **请判断：后半段是否还有独立的价值？**

- **若没有** —— **删掉它，并说清"它的断言已被前半段完全覆盖"**；
- **若有** —— **给出它该断言什么**，并说明**为什么前半段覆盖不到**。

⚠️ **⚠️ 不要为了让它绿而弱化它。** **本项目拒绝过很多次"把红变绿"。**
**若你认为这条断言本身有价值而只是判据写错了**，那就**改判据、保留断言**。
**若你认为它没有独立价值**，那就是删 —— **但要说清理由。**

### 第 2 件事：实施，并检查这份文件里**还有没有第三种判据**

⚠️ **本项目最常见的失效是「同一件事在两处用两种口径断言」** ——
`brandLanguage` 在 schema 里、在 resolver 里、在 docstring 里各有一份，
**三份都可能漂移**。

请**通读这份测试文件**，报告：

- **它有几处判据？分别是什么？**
- **有没有第三种与前两种都不一致的？**

### 第 3 件事：给"判据本身"上一条守卫

⚠️ **这一条是本项真正的价值。**

**要求**：断言**这份测试文件里所有"某个值解析为某字段的值"的判断，
用的是同一个 resolver**（`_value_is_field_value` 或其等价物），
**而不是有的走它、有的走裸文本匹配**。

**判读要求（本项目被骗十次）**：

- **必须真的调用那个 resolver 并断言它的行为**，
  **不能**断言源码里出现 `_value_is_field_value` 这个名字 ——
  ⚠️ **本项目被文本存在性断言骗过十次**；
- **守卫要能回答**：「如果有人给后半段换回裸数字扫描，它会红吗？」

**至少三条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 把后半段改回裸数字扫描 | 守卫红 |
| 给 `_value_is_field_value` 加一个恒真的旁路 | 守卫红 |
| 让判据永远判"通过" | 守卫红 |

⚠️ **"红在错误的理由上"不算通过**（P35 的 M4 红在 `NameError`、P36 的第二条红在 `SyntaxError`）。
⚠️ **别让探针的异常变成判定**（P31/P34/P36 各栽过一次）。

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果**；**且要证明它不是死分支**。
2. **贴 `-rf` 原始输出**，不贴结论句。
3. **每条毒变异之后从快照复原，收尾核对 sha256。**
4. **⚠️ 高频复发**：先证明被测对象存在再测量；确认变异生效前不要宣称存活；
   CRLF 用字节计数验（**`p.write_text()` 在 Windows 上翻译行尾**）；
   路径分隔符；别把长跑命令管道进 `tail`；`tests/test_markdown_text_is_intact.py` 守着全仓 U+FFFD。
5. **py-3.10 有 cv2 但没有 pytest** —— 若测量需要 cv2，写进普通函数并用 3.10 脚本驱动，
   在 3.12 套件里 **skip 而不是撒谎**。

---

## 四、不要动的东西

- **⚠️ `studio/src/water-renewal/`、`studio/bin/render-water.mjs`、
  `studio/tsconfig.water.json`、`studio/package.json`、`pnpm-lock.yaml`、`.cache/`**
  —— **不是本线的、不要碰、不要提交、不要为了让它变绿而改它**
- `studio/public/jobs/**` —— **只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新（**你报告，我改**）
- `docs/UPGRADE_MASTER_PLAN.md`、`docs/P1*.md`~`docs/P3*.md`
- `out/p13_probe/**` 与 `out/*.mp4` —— 只读；`DiagOutputDir` —— **禁止触碰**
- `tests/test_take_selection_behaviour.py` —— 本项 `--ignore`
- **不要改 `DataColumns.tsx` / `BrowserStack.tsx`** ——
  **本项只改断言方式，不改被断言的代码**
- **不要动 P19–P37 的任何成果**、不要改 `scene_graph.py` 与 P36 的生成器

**本指令授权你修改**：`tests/test_p4_9_ledger_numbers_resolve.py`、必要时新增测试与文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（**只 stage 你自己的文件**）
- 交付时报告：
  - **后半段有没有独立价值 + 你的判定与理由**（最重要）
  - **这份文件里有几种判据、有没有第三种**
  - **守卫方案 + 三条变异的 `-rf`**
  - **基线与改完后的全量数字**
  - **sha256 比对**
  - 改动的文件清单
- 有未提交工作时**不要用 `git checkout -- <file>` 清污染`
- **⚠️ `git add` 用显式路径**，不要用 `-A` 或 `.`
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

**待你裁定**：**P27 B-2**（末帧近黑）、**P27 B-3**（冻结 8.03s）。

**已裁定不建**（只等你决定是否正式关闭）：
13.1 / 14.1 / 14.2 / 15.1 / 15.2 / 18.1 / 12.3 / 11.1。

**运行中**：P38（P12.2 ScenePlanner）—— **⚠️ 它改 `pipeline/` 下的新模块，与本项无冲突。**

**跨阶段剩**：1.3 / 10.2（标依赖、不合并、不重复建）。