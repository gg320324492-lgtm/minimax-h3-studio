# 执行指令 — 修 `visual_qa.py` 静默通过：图谱不存在时它报告「一切正常」

> 给执行 agent。本文件**自包含**。你只负责执行，**不做放行/退回裁定**。
> 这是 P13 勘察（`6eca430`）的附带发现，但**它是本项目最危险的一类失效**：
> **QA 工具在被喂错东西时报告「通过」。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 仓库 | `E:\Minimax-H3`（git，分支 `main`） |
| HEAD | `6eca430`（**本地，未推送** —— 推送因 TLS 握失败，网络整体不通，`curl https://github.com` 返回 HTTP 000） |
| 基线 | **先自己实测**（上次是 `373 passed, 2 skipped`） |
| 跑法 | `cd /tmp && py -3.12 -m pytest E:/Minimax-H3/tests/ -q --ignore=E:/Minimax-H3/tests/test_take_selection_behaviour.py` |

⚠️ **不要尝试推送** —— 推送由指挥窗口裁定，且当前网络不通。

**开工前记录 sha256，收尾比对**：
- `studio/scripts/visual_qa.py`
- `studio/scripts/ab_field.py`
- `studio/src/schemas/showcase-v1.ts`

---

## 一、指挥窗口已实测的事实（本指令建立在此之上，不是引述）

### 1. 缺陷：`--props` 指向不存在的文件时，`visual_qa.py` 报告「一切正常」

`studio/scripts/visual_qa.py:761`：

```python
props = None
if args.props and args.props.exists():
    props = json.loads(args.props.read_text(encoding='utf-8'))
```

**文件不存在时：不报错、不警告、`props` 保持 `None`。**

而下游 `:773` 是 `if props is not None and not args.frame:` ——
**整段 `rule_missing_asset` 被静默跳过**。

**结果：一次什么都没跑的 QA，输出一份「无发现」的报告，退出码 0。**

这在 CI 里等价于绿灯。**图谱路径打错一个字符，QA 就变成了空转。**

### 2. 同仓库的另一个工具对**同一标志**约定相反

`studio/scripts/ab_field.py:471-472`：

```python
props = Path(args.props)
if not props.exists():
    ap.error(f'--props not found: {props}')
```

**`ab_field.py` 硬报错，`visual_qa.py` 静默通过。**
同仓库、同一个标志、两种相反的行为 —— 任何读过一处的人都会被另一处误导。

### 3. 恰好有一个函数知道该怎么报，但零调用方

`visual_qa.py:615` —— `def rule_duplicate_check_props(props_path: Path) -> Finding:`

指挥窗口实测：**全仓只有定义处一个命中**（外加 pyc），
**零调用方**。据上一轮勘察报告，它恰好是**唯一会正确报告 UNVERIFIABLE 的函数**。

**先自己复核这条**（可能我漏了动态调用）。

### 4. P13 的另一条实测事实与本项直接相关

上一轮测出：**把 `s01` 的值改成 9999，`visual_qa.py` 报告逐字节相同、退出码相同。**
即**没有任何一层能察觉"改了一个 scene"**。

这与本项同源：**QA 工具对自己的输入缺少校验**。

---

## 二、你要交付的三件事

### 第 1 件事：先复核，再动手

**独立复现第 1 条的失效形态**（不要采信我的描述）：
用 `--props` 指向一个不存在的路径，跑 `visual_qa.py`，**贴出完整的 stdout 与退出码**。

同时复核第 3 条（`rule_duplicate_check_props` 是否真无调用方）。

⚠️ **本项目有"结果红不等于交付物"的教训，也有"验收复现不出来"的记录** ——
指挥窗口独立复现执行 agent 自报的验收**两次都复现不出来**。
**所以你自己的结论也要能被独立复现。**

### 第 2 件事：修它，并把两个工具的约定统一

**核心要求：`--props` 指向不存在的文件必须硬失败，不能静默通过。**

请判定并说明**用哪种方式**：

| 方式 | 说明 | 代价 |
|---|---|---|
| **A：`ap.error()`** | 与 `ab_field.py` 一致，立即退出非零 | 最小的改动；**但 `visual_qa.py` 是被测试调用的**，改退出码可能让既有测试转红 |
| **B：报一条 `UNVERIFIABLE` 的 Finding** | 走规则体系，让报告本身说明为什么没跑成 | 更符合"QA 报告"的语义；**但退出码怎么定需要你判定** |

**先读 `rule_duplicate_check_props`（`:615`）再说选哪个** ——
如果它已经实现了 B 的语义，接上它比重新发明要好。

⚠️ **注意一个已存在的守卫**：
`tests/test_p13_scene_cache_facts.py` 有一条
`test_that_gate_still_exits_zero_so_nothing_upstream_notices`，
**它断言当前的"退出 0"行为**（那是 P13 勘察刻意钉住的"现状"）。
**你修好之后它会红 —— 那正是它该红的时刻**，
但你要**读它、确认它钉的是"现状"而非"应然"，然后决定改守卫还是删守卫**。
**不要为了让套件绿而回退修复。**

### 第 3 件事：给"QA 工具的输入校验"上一条守卫

**判读要求（本项目反复栽跟头的地方）**：

- **必须真的跑 `main(argv)` 断返回值与输出**，不能断言源码里出现 `ap.error` 字符串
  —— 那是文本存在性断言，本项目已被骗过五次。
- **必须同时断两件事**：
  (a) 不存在的 props → 非零退出 / 明确的 UNVERIFIABLE 报告；
  (b) **存在的 props → 仍然正常跑完并退出 0**。
  只断 (a) 的守卫，会被"永远报错"的实现骗过 ——
  **本项目吃过一次这种亏**（第一版守卫数 `assert` 存在性，被 `assert True` 骗过）。

**至少两条变异，各贴 `-rf` 原始输出**：

| 变异 | 期望 |
|---|---|
| 去掉报错逻辑（恢复静默跳过） | 守卫红 |
| 让 `main` 无条件 `return 1`（永远失败） | 守卫红（这条专抓上面那个陷阱） |

**若某变异存活**，判定"真漏洞"还是"无效变异"，两种都写进 commit。
**不要造 contrived 输入去杀无效变异。**

---

## 三、验证协议（不达标不算完成）

1. **变异必须先证明落地，再读测试结果。** 本项目发生过两次
   「变异没落地却读了结果」，报出的 passed 数与变异无关。
   → **注入后先 assert 变异在文件里，再跑 pytest。**
2. **贴 `-rf` 原始输出**，不贴"被 X 守卫杀掉"这种结论句。
3. **红的理由必须对。** 守卫红在别的断言上不算通过。
   **看到红的理由不对，先查现场再下结论。**
4. **每条毒变异之后从快照复原源文件，收尾核对三个 sha256。**
5. **写长文本在字节层操作**；**不要在 bash 双引号里写带反引号的 Python 代码**
   —— 指挥窗口刚因此产出四个 0 字节垃圾文件。
6. **行尾按文件实测**，不要相信任何人的断言包括本工单的。
7. `/tmp` 在 bash 与 Python 中解析不同（`C:\Users\pc\AppData\Local\Temp`）——
   上一轮 agent 因此还原失败过一次。

---

## 四、不要动的东西

- `studio/public/jobs/**` —— gitignore 的 staging 副本，**只读**
- `docs/UPGRADE_PROGRESS.md` —— 账本由指挥窗口统一更新
- `docs/UPGRADE_MASTER_PLAN.md`
- `out/` 下任何证据目录（含 `out/p13_probe/`）；`DiagOutputDir`
- `tests/test_take_selection_behaviour.py` —— cv2 只装在 3.10，本项 `--ignore`
- **不要实现 P13 的缓存** —— 那是另一项，且结论是"现在不建"
- **不要顺手改 `ab_field.py`** —— 它是**正确**的那一方，
  要做的是让 `visual_qa.py` 与它一致（或论证为什么不一致），不是改它

**本指令授权你修改**：`studio/scripts/visual_qa.py`、相关测试文件、
以及新增文档。

---

## 五、交付

- 提交信息用**英文**，结尾加
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- **提交但不推送**（且当前网络不通）
- 交付时报告：
  - **失效形态的完整复现**（stdout + 退出码）
  - **A / B 你选了哪个 + 依据**（特别是你怎么处理那条钉住"现状"的守卫）
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
**P14** Render Worker / Fast Preview（**P13 已测出：bundle 只占单次渲染 6%**
—— 1.2s/19.6s，且 `studio/public` 是 **127 文件 / 810.6 MB**，
体积大但文件数少所以拷贝快；**长驻进程才是 bundle 复用的前提**）、
**P15** SR 路由、**P16**–**P18**。

**P13 已裁定（`6eca430`）**：
- **bundle 复用 = B，不值得建**（占 6%，且每进程 `mkdtemp` + `finally` 删除，
  当前形态下这 1.2s 根本省不掉）
- **scene 级重渲 = C，现在不建**，收益 63–72% 够大，但被三个实测事实挡住：
  (a) **产物不可复现**（同图三次 711054/710851/712303 字节，
  concurrency=1 亦然，而 ffmpeg 对同一输入逐字节相同）
  ⇒ **缓存不能靠"重渲比对"验证命中**；
  (b) **没有任何一层能察觉"改了一个 scene"**；
  (c) 拼接后 re-encode 成本未实测，63–72% 是上限。
- **瓶颈不在 bundle，在"没有 scene 级入口"和"没有 scene 级 diff"** ——
  都不是 `job_state.json` 能解决的。

**P12 遗留（未动）**：`chartLanguage` / `audioLanguage`（声明了但零消费，
P11 方向；`.strict()` 管不到）。

**P11 剩 11.1 / 11.3**，卡在同一个**实测解锁条件**：
- **11.1** —— 仪器已建成（`chart_geometry.py` / `c6d7a5a`），修复器**故意未写**：
  已交付图表比值 **0.278**，无碰撞可修。
  **若你发现任何图表确实接近碰撞，停下并上报** —— 那会推翻这个结论。
- **11.3** `MAX_REPAIR_ROUNDS=3` —— 依赖 11.1；轮次应由
  "重新测量仍在碰撞"决定，而非计数器。
