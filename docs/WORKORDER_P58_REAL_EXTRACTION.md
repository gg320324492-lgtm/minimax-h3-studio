# 执行指令 — P58：真实素材的提取→控制链验证 → **给裁定数据，不做裁定**

> 给执行 agent。本文件**自包含**。
> ⚠️ **前置：P57 已完成**（Union 2.0 权重在位、合成信号下控制确认生效）。
> **用户裁定（2026-11-04）：先测真实提取链，再决定 ControlNet 是否纳入生产。**
> 本项就是那个"再定"的依据。

---

## 零、环境

| 项 | 值 |
|---|---|
| ComfyUI | `E:\ComfyUI` @ v0.43.2（commit `423cbd20`，开工前实测确认） |
| 权重 | `models/model_patches/minimax_h3_fun_controlnet_union_2.0_pruned_bf16.safetensors`（8.38 GB，SHA256 `cd48bdc1…` 已双重核验） |
| P57 工作流 | `E:\Minimax-H3\workflows\video_minimax_h3_fun_controlnet_union.json`（官方模板落盘副本） |
| GPU | RTX 5090 32GB；P57 实测控制生成显存峰值 31.4–31.8 GB——**生成时不要并发任何 GPU 任务** |
| 输出 | 全部放 `E:\Minimax-H3\out\p58\`（**新规矩：不在 E 根建目录、不在 C 盘产生数据**） |
| 报告 | `E:\Minimax-H3\docs\P58_REAL_EXTRACTION_CHAIN.md` |

**⚠️ 本项目工作树里有不属于你的在制工作**（`studio/src/Root.tsx`、
`intro_video/`、`studio/public/audio/intro/`、`studio/src/templates/model-intro/`）——
**不碰、不提交、不恢复。**

---

## 一、已核实的事实（本指令建立在此之上）

1. **P57 已证明**：控制分支真生效（PSNR 12.3–14.7 dB @ 同 seed strength 1.0 vs 0；
   strength 是 skip add 的 alpha，=0 数学 no-op，源码 `comfy_extras/nodes_minimax_h3.py:515`）；
   五路全跑通；**但控制信号是程序化合成的（火柴人+球）**，
   "哪一路跟随最准"与"真实素材下能不能用"P57 不答——**本项答**。
2. **提取节点内建**（指挥窗口已查 `E:\ComfyUI\comfy_extras\`）：
   `nodes_sdpose.py`（SDPose）、`nodes_depth_anything_3.py`（Depth Anything 3）。
   ⚠️ **提取模型权重是否已下载未核实**（`models/` 下只见 `controlnet` 目录）——
   **开工先查，缺就下载并核 SHA256**（下载纪律同 P57：aria2c 分块 + 落盘校验，
   **警惕包装脚本恒返回 0 的假成功**——P57 栽过一次）。
3. **真实素材候选**（按优先级）：
   - `E:\Minimax-H3\water_renewal\01_reference\` 或 `intro_video/` 的真实片段
     （⚠️ 781 MB 媒体未入库，只读，**用前先确认文件在**）；
   - `E:\ComfyUI\input\` 已有素材；
   - 都不合适就自取一段 5–10 秒含人物动作的公开素材（**报告里写清来源**）。
4. **P55 已验证 v0.43.2 同 seed 逐字节确定**——本项的 A/B 对照可以放心用同 seed。

---

## 二、你要做的事

### 第 1 步：搭真实链

对 **Pose 与 Depth 两路**（短剧刚需候选；Canny/HED 属边缘类冗余，MLSD 属线段类，P57 数据显示特异性场景才值得）：

```
真实视频 → [SDPose / Depth Anything 3 提取] → 控制视频 → [P57 工作流的控制生成] → 输出
```

- 每路先**单独验证提取质量**：抽 3 帧控制图放 `out\p58\extract\`，
  **肉眼 + 数值**（骨架点数量/深度图梯度分布）报告提取是否可用——
  **提取烂了后面全白测，这一步不合格就停下来报告**；
- 控制视频规格对齐 P57 工作流的输入要求（864×480×124 或模板原生值）。

### 第 2 步：生成与对照（每路）

| 对照 | 目的 |
|---|---|
| 同 seed，strength 1.0 vs 0.0 | 复验真实信号下控制仍生效（P57 只在合成信号上验过） |
| 真实控制 vs 合成控制（同 seed） | **本项核心**：真实素材的提取噪声会不会让控制失效或劣化画质 |
| 无控制分支的纯 H3 直出（同 prompt 同 seed） | 画质基线——控制分支会不会拉低画质 |

每格实测：耗时、显存峰值、ffprobe 规格、逐帧 PSNR/像素差、抽 3 帧放 `out\p58\compare\`。

### 第 3 步：回答三个裁定问题（**给数据，不裁定**）

1. **真实提取链端到端能跑吗**（含模型下载、提取质量、生成成功）；
2. **控制跟随在真实素材上的表现**——与 P57 合成场景的"结构建议级"相比如何
   （⚠️ VLM 在 P57 被实测不可信，**生效性判读用像素差 + 肉眼**，VLM 只做旁证并标注）；
3. **生产可用性**：显存余量（P57 已 <1.2 GB，真实链加提取节点后还剩多少）、
   端到端总耗时（提取 + 生成）、画质是否可接受。

---

## 三、验证协议

1. **先证明提取质量再跑生成**（提取烂了生成对照无意义）；
2. **贴原始输出**（提取帧、PSNR、显存、耗时），不贴结论句；
3. **外推等于没测**；**写数字要么实测要么标注未测**；
4. **一块 GPU 串行**；提取节点若需 CPU 推理也要报告耗时；
5. **磁盘**：`out\p58\` 收尾留证据删大文件；
   ⚠️ `studio/.remotion/water-renewal-bundle`（1.5 GB）不是你的，别删；
6. ⚠️ GBK 控制台读非 ASCII 用字节判断；写中文报告用 `read_bytes`/`write_bytes`
   （`tests/test_markdown_text_is_intact.py` 守全仓 U+FFFD）；
7. **不装新自定义节点**——内建节点不够用就停下来报告缺什么。

---

## 四、不要动的东西

- `E:\ComfyUI\models\model_patches\` 的 Union 2.0 权重——只读
- P57 的脚本与报告（`experiments/p57_*.py`、`docs/P57_*.md`）——参考，不改
- 本项目在制工作（零节清单）
- `docs/UPGRADE_PROGRESS.md`——账本指挥窗口写
- `DiagOutputDir`——禁止触碰
- `workflows/video_minimax_h3_fun_controlnet_union.json`——原件不改，
  需要变体就在 `out\p58\` 或 `workflows/` 用新文件名

**本指令授权你**：下载提取模型权重到 `E:\ComfyUI\models\`（核 SHA256）、
新增 `workflows/` 落盘副本、新增 `experiments/p58_*.py`、写报告。

---

## 五、交付

- 提交信息用**英文**，结尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- **提交但不推送**（只 stage 你自己的文件，显式路径）
- 交付时报告：
  - **提取模型下载与校验**（缺了才下，下了必核）
  - **两路提取质量**（数值 + 抽帧，不合格就停）
  - **三组对照的实测数字**（每路）
  - **三个裁定问题的数据答案**
  - **显存余量与端到端耗时**（生产可用性的硬数字）
  - **对比帧目录**（供用户肉眼裁定）
  - **磁盘纪律**、改动文件清单
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 六、队列

- 本项完成后：**用户裁定 ControlNet 纳入/保留/卸载**，然后进入下一轮（若纳入，
  才谈接线到短剧管线；若不纳入，权重卸载或保留按裁定）。
- 主线已并回：P53（qa_layers 债）、P54（bubble sizes）、P57（本报告的前置）。
