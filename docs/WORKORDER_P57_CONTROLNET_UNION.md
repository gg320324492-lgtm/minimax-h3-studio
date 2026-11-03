# 执行指令 — P57：Fun ControlNet Union 2.0 拉取 + 5090 实跑验证 → **给裁定数据，不做裁定**

> 给执行 agent。本文件**自包含**。你只负责执行与记录，**是否纳入生产由指挥窗口 + 用户裁定**。
> ⚠️ **前置：P55（ComfyUI 0.43.2 升级 + 回归）必须已完成且回归绿。开工前先确认。**
> ⚠️ **与 P56 共用一块 GPU——若 P56 在跑，等它完成再开本项（串行，不并行）。**

---

## 零、环境

| 项 | 值 |
|---|---|
| 前置 | `docs/P55_COMFYUI_UPGRADE.md` 回归通过；P56 若在跑则等它完成 |
| ComfyUI | E:\ComfyUI @ v0.43.2（Union 2.0 要求 0.38.0+，已满足） |
| 下载目标 | `E:\ComfyUI\models\model_patches\`（**该目录现为空**） |
| GPU | RTX 5090 32GB |
| 报告 | `E:\Minimax-H3\docs\P57_CONTROLNET_UNION_VERDICT.md` |

**⚠️ 本项目工作树里有不属于你的在制工作**（`studio/src/Root.tsx`、
`tests/test_p48_reaccept.py`、`intro_video/` 等）——**不碰、不提交、不恢复。**

---

## 一、已调研的事实（本指令建立在此之上，不是引述）

**Fun ControlNet Union**（阿里 PAI，VideoX-Fun 管线训练）：叠加在 H3 transformer 之上的
ControlNet-Union（legacy 版只含 `control_proj_in` + 5 个 control_blocks，约 6.8 GB，
挂在第 0/10/20/30/40 层）。

| 项 | 值 |
|---|---|
| **本项装的版本** | **Union 2.0**（legacy 已被官方标记为过时）：
  `https://huggingface.co/Comfy-Org/MiniMax-H3/resolve/main/model_patches/minimax_h3_fun_controlnet_union_2.0_pruned_bf16.safetensors` |
| 控制信号 | **Canny / Depth / HED / MLSD / Pose 五种控制视频** + 遮罩局部重绘（inpainting） |
| 官方工作流模板 | Template Library > Video > **"MiniMax H3 Fun ControlNet Union"**
  （`video_minimax_h3_fun_controlnet_union.json`，ComfyUI 0.38.0+） |
| 采样参数（legacy 版文档） | `num_inference_steps=40`、`guidance_scale=1.0`（**蒸馏模型，>1 会重复施加 guidance 并劣化输出**）、`control_context_scale=1.0` 最强控制（调低减弱，0 关闭） |
| 显存（legacy 版数据） | transformer ~62 GB + Qwen3-VL ~62 GB 需 offload——**2.0 pruned 版实际占用待你实测** |
| 帧数 | 自动对齐到 VAE 可解码的 **17k+5**，时长上限 15 秒，固定 24 fps |
| 来源 | `alibaba-pai/MiniMax-H3-Fun-Controlnet-Union-2.0`（HF 模型卡） |

⚠️ **官方文档对 Union 2.0 的 ComfyUI 用法在单独页面，参数可能与 legacy 不同——
以模板内的节点默认值为准，不要照抄上面的 legacy 数字**。

---

## 二、你要做的事

### 第 1 步：下载 + 模板加载

1. 下载 Union 2.0 到 `E:\ComfyUI\models\model_patches\`（落盘后核大小再继续，防网络截断）；
2. 从 ComfyUI 模板库加载 "MiniMax H3 Fun ControlNet Union" 工作流，**另存为
   `workflows/video_minimax_h3_fun_controlnet_union.json`**（这是它在本仓的第一份落盘副本）；
3. 确认模板要求的节点在 0.43.2 下全部可解析。

### 第 2 步：能力验证（**每条都实测，贴数字**）

**准备一条控制视频**（5–10 秒即可）：
- **Pose**：用现有素材或公开示例姿态视频；若无，用本机 ollama + 任意手段都行——
  **但控制视频本身是输入不是产出，可以从简**（甚至程序化画一个简笔火柴人序列）；
- **Depth**：同上一条或换一条。

每路控制跑一条 5 秒生成，记录：

| 维度 | 怎么测 |
|---|---|
| **能否跑** | 5090 32GB 上是否 OOM；用了什么 offload 策略 |
| **显存峰值** | 实测（nvidia-smi 采样或 ComfyUI 日志） |
| **速度** | 端到端秒/条（5 秒片） |
| **控制是否生效** | ⚠️ **这是核心**：同 prompt 同 seed，`control_context_scale=1.0` vs `0`（关闭控制）各跑一次——**若两者像素几乎相同，控制没生效**，那比 OOM 更严重，必须报告 |
| **规格** | ffprobe：17k+5、24fps、音轨 |
| **画质** | 抽帧放 `E:\out\p57\compare\` 供用户肉眼裁定（命名 `{控制路}_scale{值}_f{帧号}.png`） |

### 第 3 步：给裁定数据（**不裁定**）

报告回答四个问题（每个都带实测数字）：

1. **5090 32GB 能不能跑**（offload 策略 + 显存峰值）；
2. **速度能不能进生产**（一条 5 秒片多少分钟——对照：H3 直出约 1–3 分钟级）；
3. **控制是否真生效**（scale 1.0 vs 0 的像素差 + VLM 读画面对比）;
4. **五路里哪几路值得进管线**（Pose/Depth 是短剧刚需候选，Canny/HED/MLSD 视验证结果）。

---

## 三、验证协议

1. **先确认 P55 回归绿**（升级没验好，本项全部无效）；
2. **控制生效性要用控制变量**（scale 1.0 vs 0，同 seed 同 prompt），
   **不许只看"画面像被控制了"**；
3. **贴原始输出**（显存、耗时、ffprobe、像素差），不贴结论句；
4. ⚠️ **一块 GPU，与 P56 串行**；**外推等于没测**（每条实测计时）；
5. ⚠️ **磁盘**：视频放 `E:\out\p57\`，收尾删大文件留对比帧与表格；
   ⚠️ **`studio/.remotion/water-renewal-bundle`（1.5 GB）不是你的，别删**；
6. ⚠️ `tests/test_markdown_text_is_intact.py` 守 U+FFFD——中文报告用 `read_bytes`/`write_bytes`；
7. ⚠️ GBK 控制台读非 ASCII 用字节判断。

---

## 四、不要动的东西

- `E:\ComfyUI\models\` 下其他已装模型——不删不挪
- `E:\ComfyUI\custom_nodes\`——不装新节点（官方模板若要求额外自定义节点，**先报告**再决定）
- 本项目工作树的在制工作（见零节）
- **P56 的文件**（LoRA、对比工作流、对比帧）——不碰
- `docs/UPGRADE_PROGRESS.md`——账本指挥窗口写
- `DiagOutputDir`——禁止触碰
- **P53/P54 的半成品**——不碰

**本指令授权你修改**：`E:\ComfyUI\models\model_patches\`（新增 2.0 权重）、
`workflows/`（**新增** fun_controlnet_union 工作流落盘副本）、
`E:\Minimax-H3\docs\P57_CONTROLNET_UNION_VERDICT.md`、必要的测量脚本。

---

## 五、交付

- 提交信息用**英文**，结尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- **提交但不推送**（只 stage 你自己的文件，显式路径）
- 交付时报告：
  - **权重下载校验 + 模板加载结果**
  - **四问的答案**（能跑吗/多快/控制生效吗/哪几路值得留）——全部带实测数字
  - **显存峰值与 offload 策略**
  - **对比帧目录路径**（供用户肉眼裁定）
  - **磁盘纪律**
  - 改动的文件清单
- **如实报告你的操作失误比做出漂亮结果重要得多**
