# P57 执行报告 — Fun ControlNet Union 2.0：5090 实跑四问 → **给裁定数据，不做裁定**

> 执行日期：2026-11-04。执行者：Claude（worktree `musing-brahmagupta-f7ea15`）。
> 工单：`docs/WORKORDER_P57_CONTROLNET_UNION.md`。
> **一句话结论：Union 2.0 bf16 在 5090 32GB 上能跑（六条全部成功，显存峰值
> 31.4–31.8 GB，余量不足 1.2 GB）；一条 5 秒片 192–281 s（均值约 255 s ≈ 4.3 分钟）；
> 控制真生效（scale 1.0 vs 0 像素 PSNR 12.3–14.7 dB，两视频完全不同，且 strength=0
> 在实现里是数学 no-op，差异只能来自控制分支）；五路全部跑通、画质干净、各自
> 表现出与其控制风格一致的结构跟随。是否纳入生产由指挥窗口 + 用户裁定。**

---

## 〇、前置确认

| 项 | 值 |
|---|---|
| ComfyUI | `E:\ComfyUI` @ `423cbd20` v0.43.2（工单要求 0.38+ ✓，开工时实测确认） |
| P55 回归 | v0.43.2 已按裁定接受为最终状态，新基准 md5 存档（`docs/P55_COMFYUI_UPGRADE.md`） |
| GPU 串行 | 开工时队列空；P56 已完成（用户已裁定 t2v-only） |
| model_patches | 开工前确认为空目录 |

## 一、下载校验 + 模板加载

**权重**：`minimax_h3_fun_controlnet_union_2.0_pruned_bf16.safetensors`

- 落盘 `E:\ComfyUI\models\model_patches\`，大小 **8,382,288,792 B** = HF 服务端
  `content-length`（302 重定向后 200 响应头）逐字节一致。
- **SHA256 `cd48bdc11b1f1a3b934746c898d25123754b335c13d37d5c421f8373079282b4`**
  与 HF API `tree` 端点返回的 `lfs.oid` 一致（certutil 本地计算，字节比对）。
- safetensors 头解析：124 tensors，4.18B 参数，metadata
  `control_blocks_places=[0,5,10,15,20,25,30,35,40,45]`（10 注入块——**2.0 特征**；
  legacy 只有 5 块 0/10/20/30/40）、`adaln_basis`。
- 下载插曲（如实）：第一发 curl 单连接被代理掐断（curl exit 56，仅 68 MB），
  且包装脚本最后一行 `echo` 恒返回 0、后台通知显示"completed exit 0"——据日志
  发现实际只下了 68 MB。清理 .part 后改用 aria2c 16 连接（代理，实测 6–8 MB/s，
  约 16 分钟完成）。

**官方模板**：`video_minimax_h3_fun_controlnet_union.json`（91 KB，从
Comfy-Org/workflow_templates@main 拉取，与 0.43.2 内置模板库同源）

- 第一份落盘副本：`E:\Minimax-H3\workflows\video_minimax_h3_fun_controlnet_union.json`
  （`workflows/` 被 .gitignore:65 忽略——与 P55/P56 工作流同样只落盘不入库）。
- **节点可解析性**：30 个节点类型逐一对照运行中服务器的 `/api/object_info`——
  **后端全部存在，无需任何自定义节点**（工单红线"要装新节点先报告"未触发）。
  MarkdownNote 为前端专属节点，不在后端注册属正常。
- 模板内官方注释确认的关键参数（以模板为准，非 legacy 数字）：
  **20 步**（Lightning LoRA 开关默认 False → 走全模型 20 步路径）、
  `res_multistep` + `simple` sigma、`strength` 默认 1.0（= legacy 的
  `control_context_scale`，ComfyUI 侧改名）、**BasicGuider 无 guidance 输入**
  （蒸馏模型 CFG 内建，legacy 的 guidance_scale=1.0 在 ComfyUI 里无对应参数）。

**模板与本机物料的差异（全部如实替换，未下载任何未授权文件）**：

| 模板默认引用 | 本机状态 | P57 处置 |
|---|---|---|
| `…union_pruned_int8_convrot.safetensors`（legacy int8） | 无（工单指定装 2.0 bf16） | ModelPatchLoader → 2.0 bf16（已下） |
| `minimax_h3_video_vae_int8_convrot` | 无，本机是 fp16 | → fp16（P55/P56 生产同款） |
| SDPose 提取器（subgraph） | **节点内置但模型文件缺**：`sdpose_wholebody_fp16`（1.79 GB）+ `rt_detr_v4-x-hgnet_fp16`（118 MB）不在本机 | **未下载**（超出工单授权目录）；控制侧改为直接喂预处理控制帧——工单明文允许"控制视频是输入不是产出，可以从简，甚至程序化画火柴人" |

## 二、第 1 问：5090 32GB 能不能跑

**能。六条全部 success，无 OOM。**

| 运行 | 状态 | 用时(s) | 显存峰值 MiB | 空闲基线 MiB |
|---|---|---|---|---|
| pose_s1（首条，冷启动） | success | 274.7 | 31532 | 5327 |
| pose_s0 | success | 192.0 | 31700 | 26876 |
| canny_s1 | success | 272.2 | 31830 | 30149 |
| depth_s1 | success | 233.1 | 31573 | 27340 |
| hed_s1 | success | 280.7 | 31508 | 27547 |
| mlsd_s1 | success | 274.6 | 31446 | 26956 |

- **offload 策略：未用任何显存旗标**——服务器是裸 `main.py --port 8188`，
  ComfyUI 默认自动权重管理（权重按需换入换出，系统 RAM 128 GB 兜底）。
  这就是答案：**默认策略即可，不需要 --lowvram/--novram**。
- 峰值 31446–31830 MiB / 总 32607 MiB——**余量只有 0.8–1.2 GB**，
  0.4MP（864×480）是安全上限；升分辨率/加步数大概率触发 offload 降速或 OOM。
- 显存采样方法：`nvidia-smi --query-gpu=memory.used` 每 1 s 采样取最大值
  （含桌面进程 ~2–3 GB 背景占用；pose_s1 冷启动基线 5327 MiB，其余各条基线
  27 GB 上下为前一条权重未卸载所致——"高于基线"列因此不可横向比，
  **绝对峰值列才是答案**）。原始采样序列存 `out/p57/run_<label>.json`。

## 三、第 2 问：一条 5 秒片多慢

- **192–281 s/条，均值 254.6 s ≈ 4.2 分钟**（规格：864×480、124 帧、20 步、
  含 Union 控制分支 + 音频解码 + h264 封装）。
- 首条 274.7 s 是冷启动；pose_s0 仅 192 s 因权重全热。稳定区间看 233–281 s。
- 对照（同机实测）：H3 直出 r2v turbo 8 步 = 270 s（P55 基准，同 864×480×124）；
  H3 直出 t2v 全模型 20 步 @1344×768 = 1087 s（P56）。
  **控制 20 步 ≈ turbo 直出同量级**；比全模型直出便宜（分辨率不同，不换算）。
- 生产含义的数据点：进管线的话，5 秒镜头成本从 turbo 直出的 ~4.5 分钟变成
  ~4.3–4.7 分钟（本测试），**速度不构成否决项**；真正否决与否取决于画质裁定。

## 四、第 3 问（核心）：控制是否真生效

**生效。三层证据：**

1. **像素差（控制变量的 A/B）**：同 prompt、同 seed（1086599926715797，
   模板自带值钉死）、同 864×480×124、同 20 步，唯一变量 `strength` 1.0 vs 0.0。
   抽 f030/f062/f093 三帧逐帧比对：

   | 帧 | 平均绝对差（0–255） | PSNR |
   |---|---|---|
   | 30 | 34.98 | 14.74 dB |
   | 62 | 36.66 | 13.64 dB |
   | 93 | 51.11 | 12.31 dB |

   PSNR < 15 dB = 两个视频在像素层面**完全不同**——不是"几乎相同"，
   控制分支确实在改变输出。
2. **数学论证（排除噪声巧合）**：读 `comfy_extras/nodes_minimax_h3.py:515`，
   strength 是 `out["img"].add_(skip, alpha=self.strength)` 的 alpha——
   **strength=0 时控制残差严格乘零，模型输出与不挂控制逐元素相等**。
   因此上面 12–15 dB 的差异只能来自控制分支本身，不存在"两次运行随机漂移"的解释
   （同 seed 同采样链，P55 已验证 0.43.2 同 seed 重跑逐字节一致）。
   注意副作用：strength=0 时控制分支**仍被完整计算**（无短路），所以 scale-0 对照
   并不省时间——pose_s0 快是因为热缓存，不是关了控制。
3. **肉眼（对比帧）**：`pose_scale1.0_f062.png` 主体侧身背镜、**左臂向画面左侧
   伸出**——与控制骨架该帧的手臂展开方向一致；`pose_scale0.0_f062.png` 主体正面、
   双臂抬在胸前自由舞动——与骨架无关。五路 scale1.0 帧（见第六节）各自表现出
   与其控制风格一致的结构（MLSD 水平线段 → 地平线笔直；depth 梯度 → 沙丘纵深；
   canny/HED 的球边缘 → 身侧出现团块）。

**仪器如实记录——VLM 这一路不可信**：本机 qwen2.5vl:7b 对同一帧给出的
body_orientation 答案与肉眼判读矛盾（s1 明显侧身背镜，VLM 答 facing-camera），
arms 字段残缺未答出。工单要求的"像素差 + VLM 读画面对比"中，**VLM 部分判定为
仪器失效**，生效性结论由像素差 + 源码数学论证 + 肉眼对比支撑。

## 五、第 4 问：五路里哪几路值得进管线（数据，不裁定）

五路全部跑通、无崩溃、画质无明显劣化（864×480 下主体纹理干净、无撕裂）。
短剧刚需视角的数据点：

| 路 | 控制信号跟随（肉眼） | 用时 | 备注 |
|---|---|---|---|
| Pose | 手臂展开方向被跟随；主体位置仍居中（未逐字复制骨架轨迹） | 274.7/192.0 s | 蒸馏模型对 union 控制的响应是"结构建议"级，非"逐像素复制"级 |
| Depth | 纵深/地平线结构清晰 | 233.1 s | 最快 |
| Canny | 主体轮廓 + 球团块出现 | 272.2 s | |
| HED | 与 Canny 表现接近（同为边缘类，信号冗余） | 280.7 s | |
| MLSD | 地平线笔直（线段特征明显被跟随） | 274.6 s | 对建筑/室内场景可能有特异性 |

⚠️ 本测试控制信号是程序化合成场景（火柴人 + 球 + 地平线），非真实素材预处理链
（SDPose/Canny/Depth 提取器模型本机不全）——**各路"跟随度"的绝对水平会受控制信号
质量影响**；本数据回答的是"Union 2.0 在 5090 上五路都能跑、控制都在起作用、
速度同量级"，不回答"哪一路跟随最准"。后者需要真实提取链 + 用户肉眼裁定。

## 六、对比帧目录（供用户肉眼裁定）

`E:\Minimax-H3\out\p57\compare\`——18 张 PNG（f030/f062/f093 × 6 条运行），
命名 `{控制路}_scale{值}_f{帧号}.png`：
pose_scale1.0_* / pose_scale0.0_*（生效性 A/B 对）+ canny/depth/hed/mlsd_scale1.0_*（五路画质）。
生成视频原件（各 ~1.4 MB，h264+AAC）存 `out/p57/runs/`；控制输入视频存
`out/p57/controls/`；逐条原始测量（含 1 s 间隔显存采样序列）存 `out/p57/run_*.json`；
生效性原始数据 `out/p57/control_effectiveness.json`；汇总 `out/p57/summary.json`。

## 七、磁盘纪律

- 全部输出落在 `E:\Minimax-H3\out\p57\`（共 21 MB），**未在 E 盘根目录建任何
  文件夹、未在 C 盘产生数据**（下载落 `E:\ComfyUI\models\model_patches`，aria2c
  控制文件同目录且已清除；SHA256/日志全在项目内）。
- 大文件处置：8.38 GB 权重是交付物保留；`E:\ComfyUI\output\p57\` 的六条原件
  已拷入项目证据目录后**删除**；对比帧 PNG 与短视频为裁定证据，保留。
- 未触碰：`studio/.remotion/water-renewal-bundle`、P56 文件、`DiagOutputDir`、
  工作树在制工作（`studio/src/Root.tsx`、`tests/test_p48_reaccept.py`、
  `intro_video/`、`studio/public/audio/intro/`、`studio/src/templates/model-intro/`、
  `from_e_root/`）。

## 八、改动的文件清单

新增（本工单授权范围内）：

- `E:\ComfyUI\models\model_patches\minimax_h3_fun_controlnet_union_2.0_pruned_bf16.safetensors`（权重）
- `E:\Minimax-H3\workflows\video_minimax_h3_fun_controlnet_union.json`（官方模板第一份落盘副本；gitignored）
- `E:\Minimax-H3\workflows\video_p57_{pose_s1,pose_s0,canny_s1,depth_s1,hed_s1,mlsd_s1}.json`（实验变体；gitignored）
- `E:\Minimax-H3\out\p57\**`（证据；gitignored）
- `experiments/p57_control_assets.py`（控制视频生成器）
- `experiments/p57_build_workflows.py`（模板→变体构建器）
- `experiments/p57_runner.py`（API 提交 + 计时 + 显存采样）
- `experiments/p57_compare.py`（像素差 + VLM 生效性比对）
- `experiments/p57_measure.py`（汇总表）
- `docs/P57_CONTROLNET_UNION_VERDICT.md`（本报告）

## 九、执行中的失误记录（如实）

1. **curl 下载失败被包装脚本掩盖**：curl exit 56（代理掐断），包装脚本最后一行
   是 `echo` 恒返回 0，后台通知显示"completed exit 0"——我据日志发现实际只下了
   68 MB。教训：下载校验必须在下一动作前做，不能信包装层退出码。
2. **aria2c 预分配造成假校验通过**：aria2c 默认预分配全尺寸，下载中途 `stat` 看到
   8,382,288,792 B 与期望"一致"——若按工单"核大小再继续"就地放行会拿半截文件
   进 GPU。最终校验放在 aria2c 完成通知之后，并加 SHA256 对 HF 官方值。
3. **runner 拷贝产物静默失败两次**：history 里 SaveVideo 产物登记在 `images` 键
   （非 `videos`），且文件名带 `p57/` 子目录前缀——第一版拷贝逻辑没命中，五份
   产物滞留 ComfyUI output。修两处后手动补齐拷贝。
4. **ffmpeg `-vsync v0` 在本机版本不支持**（Octave mingw64 构建），抽帧首次运行
   报错；去掉该参数后正常。
5. **VLM 仪器判定失效**（见第四节）：qwen2.5vl:7b 读朝向与肉眼矛盾、格式残缺。
   这是仪器局限不是操作失误，但影响"VLM 读画面对比"这条证据链——已用源码数学
   论证 + 像素差补位。
6. **pose_s0 对照不省时间**：读源码前我以为 scale=0 会跳过控制分支计算；实际无
   短路（`add_(skip, alpha=0)` 仍全量计算）。不影响结论（差异仍归因于控制），
   但"关控制省钱"的直觉是错的，报告里已更正。
