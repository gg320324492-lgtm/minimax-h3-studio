# 执行指令 — P56：Pika H3 Flex 拉取 + 三场景同 seed 对比实测 → **给裁定数据，不做裁定**

> 给执行 agent。本文件**自包含**。你只负责执行与记录，**切换与否由指挥窗口 + 用户裁定**。
> ⚠️ **前置：P55（ComfyUI 0.43.2 升级 + 回归）必须已完成且回归绿。开工前先确认。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 前置 | `docs/P55_COMFYUI_UPGRADE.md` 的回归已通过（**开工前读它确认**） |
| ComfyUI | E:\ComfyUI @ v0.43.2（P55 升级后） |
| GPU | RTX 5090 32GB（**一块，不要并发跑两个生成任务**） |
| 下载目标 | `E:\ComfyUI\models\loras\` |
| 报告 | `E:\Minimax-H3\docs\P56_PIKA_FLEX_COMPARISON.md` |

**⚠️ 本项目工作树里有不属于你的在制工作**（`studio/src/Root.tsx`、
`tests/test_p48_reaccept.py`、`intro_video/` 等）——**不碰、不提交、不恢复。**

---

## 一、已调研的事实（本指令建立在此之上，不是引述）

**Pika H3 Flex**（Pika Labs，2026-10-29 开源）：在 H3 基座上多任务后训练 +
把 50 步蒸馏到 **6 步** + 奖励反馈精调。以 **LoRA 适配器**形式发布，
**复用本地全部 H3 基座文件，新增只有两个 LoRA**：

```
https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/loras/pika_h3_flex_fl2va_v1_bf16.safetensors   (1.96 GB)
https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/loras/pika_h3_flex_ref2va_v1_bf16.safetensors  (1.96 GB)
```

**官方参数（[docs.comfy.org](https://docs.comfy.org/tutorials/video/pika/pika-h3-flex)，已核实）**：

| 项 | 值 |
|---|---|
| 步数 | **固定 6 步**（训练时调度如此，**加步数不增细节**） |
| 采样器 / 调度器 | `lcm` + `ManualSigmas`，**sigma 列表保持 7 个值**（少了破坏调度） |
| CFG | 1.0（经 `BasicGuider`） |
| LoRA 强度 | 1.0 |
| ⚠️ **禁止叠加** | **不要与 turbo / Lightning 等第二加速 LoRA 同用** |
| 版本要求 | T2V 模板 0.43.2+；R2V / FL2VA 0.30+ |
| 典型输出 | 5 秒 1344×768，原生立体声 |
| 参考 | Ref2VA：单次最多 12 个参考（9 图 + 3 视频 + 3 音频），视频/音频参考各需 2–15 秒且合计 ≤15 秒 |
| 授权 | 按 MiniMax H3 社区许可分发，**商用前需审阅条款**（写进报告） |

**本地现状（对比基座）**：r2v 用 `ref2v_turbo_4step_v0.1`（4 步）、
fl2v 用 `fl2v_turbo_8step_v1.0`（8 步）、t2v 无 turbo（完整步数，备份文件名标 20 步）。

---

## 二、你要做的事

### 第 1 步：下载两个 LoRA + 搭一条对比工作流

1. 下载（HuggingFace，走代理或直连都行，**网络不通就换着试**——本机代理时通时断）；
2. 从现有 `workflows/video_minimax_h3_r2v.json` 复制出对比版（**副本放 `workflows/` 下新文件名，
   ⚠️ 不改原工作流**）：插入 `LoraLoaderModelOnly`（Pika Flex ref2va），
   采样器改 `lcm`、调度器改 `ManualSigmas`、7 个 sigma 值、CFG 1.0、6 步。

### 第 2 步：三场景同 seed 对比（**本项的核心**）

**控制变量：同 prompt、同 seed、同分辨率、同时长**。每场景 turbo 与 Flex 各跑一条：

| 场景 | 本地基座（A） | Flex（B） | 额外注意 |
|---|---|---|---|
| **r2v**（主力） | turbo_4step v0.1，4 步 | pika_flex_ref2va，6 步 | A 是现状基准；**B 不要叠 turbo** |
| **fl2v** | turbo_8step v1.0，8 步 | pika_flex_fl2va，6 步 | |
| **t2v** | 完整步数（约 20） | pika_flex_fl2va（T2V 用 fl2va 适配器），6 步 | **这里速度差异最大** |

**prompt 用现有管线的真实场景**（比如 `charts_demo` 无关——用 water_renewal 或
model-intro 的真实需求，或自造一条含人物 + 对白 + 运镜的 prompt）——
**不要用 contrived 的空 prompt**。

### 第 3 步：测量（**每条都实测，贴数字**）

| 维度 | 怎么测 |
|---|---|
| **速度** | 秒/条（端到端），同卡同条件下 A/B 各测 |
| **帧数/规格** | ffprobe：17k+5 帧格、24fps、分辨率、音轨存在 |
| **指令遵循** | prompt 里放 **2–3 个可判定的元素**（一个数字、一句字幕、一个动作），用 P45 的 VLM 仪器（`studio/scripts/vlm_critic.py`，qwen2.5vl:7b）读画面验证——**A/B 各自命中几个** |
| **画面稳定性** | 相邻帧差/冻结段（本项目的现有仪器 `ab_field.frame_ink` / P49 守卫的测法） |
| **画质** | ⚠️ **"哪个更好看"不可判定——你不裁定**。把 A/B 各抽 3 帧放到 `E:\out\p56\compare\`（命名规范：`{场景}_{A或B}_f{帧号}.png`），**供用户肉眼裁定** |

### 第 4 步：给裁定数据（**不裁定**）

报告按场景给一张表：

```
场景 | 基座 | 速度A | 速度B | 规格B是否达标 | 指令遵循A/B | 稳定性A/B | 对比帧目录
```

**并给一句明确的数据结论**（例如："r2v 上 Flex 速度慢 0.3s 但指令遵循 3/3 vs 2/3、
无冻结段；t2v 上 Flex 快 4.2 倍"），**最终去留留给用户**。

---

## 三、验证协议

1. **先确认 P55 回归绿**——升级没验好就对比，对比无效；
2. **A/B 控制变量**：seed、prompt、分辨率、时长必须逐字相同，**有一条不同就重跑**；
3. **贴原始输出**（耗时、ffprobe、VLM 原始回答），不贴结论句；
4. ⚠️ **一块 GPU 串行跑**；**外推等于没测**（每条都实测计时）；
5. ⚠️ **下载校验**：LoRA 文件落盘后核大小（1.96 GB 级）再加载，防止网络截断；
6. ⚠️ **磁盘**：视频放 `E:\out\p56\`，收尾删大文件留表格与对比帧；
7. ⚠️ `tests/test_markdown_text_is_intact.py` 守 U+FFFD——中文报告用 `read_bytes`/`write_bytes`；
8. ⚠️ GBK 控制台读非 ASCII 用字节判断。

---

## 四、不要动的东西

- **原工作流 `workflows/video_minimax_h3_*.json` 三个文件**——只复制不改；
  ⚠️ **若对比后指挥窗口裁定切换，改原工作流是下一项，不是你**
- `E:\ComfyUI\models\` 下其他已装模型——不删不挪
- 本项目工作树的在制工作（见零节）
- `docs/UPGRADE_PROGRESS.md`——账本指挥窗口写
- `DiagOutputDir`——禁止触碰
- **P53/P54 的半成品**（`tests/test_p48_reaccept.py` 等）——不碰

**本指令授权你修改**：`E:\ComfyUI\models\loras\`（新增两个 LoRA 文件）、
`workflows/`（**新增**对比工作流，不改原件）、
`E:\Minimax-H3\docs\P56_PIKA_FLEX_COMPARISON.md`、
必要的测量脚本（放 `E:\Minimax-H3\out\p56\` 或 studio/scripts/，说明是否值得留）。

---

## 五、交付

- 提交信息用**英文**，结尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- **提交但不推送**（只 stage 你自己的文件，显式路径）
- 交付时报告：
  - **两个 LoRA 下载校验**
  - **三场景对比表**（见第 4 步）+ 每条的实测数字
  - **指令遵循的 VLM 原始输出**（A/B 各自）
  - **对比帧目录路径**（供用户肉眼裁定）
  - **授权条款要点**（商用相关）
  - **磁盘纪律**
  - 改动的文件清单
- **如实报告你的操作失误比做出漂亮结果重要得多**
