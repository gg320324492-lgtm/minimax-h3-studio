# P55 执行报告 — ComfyUI v0.34.0 → v0.43.2 升级尝试：**已回滚**

> 执行日期：2026-11-04。执行者：Claude（worktree `vigorous-bouman-918316`）。
> **一句话结论：升级已完成并跑完全部五条回归，其中核心回归③（同 seed 生成一致性）
> 失败——v0.43.2 在同 prompt 同 seed 下生成不同的画面。按工单第三节预授权执行了回滚，
> 回滚后 E:\ComfyUI 的代码与 pip 环境均已验证恢复原状，且同 seed 输出与升级前基线逐字节一致。**

---

## 一、回滚点（升级前已建立）

| 项 | 值 |
|---|---|
| git tag | `local-pre-upgrade-0.34`（指向 `12d52794` = v0.34.0） |
| pip freeze | `E:\Minimax-H3\out\p55\pip_freeze_0.34.txt`（192 行） |
| custom_nodes 清单 | `E:\Minimax-H3\out\p55\custom_nodes_0.34.txt`（仅 `ComfyUI-FlashVSR_Ultra_Fast`） |
| r2v 基线视频 | `E:\Minimax-H3\from_e_root\out\p55\baseline_r2v_034.mp4`（prompt_id `d32451db`，270.0 s） |

基线规格（ffprobe 实测，`probe_baseline_self.json`）：
**h264 864×480 @ 24 fps，124 帧（= 7×17+5 ✓ 17k+5 帧格），aac 立体声 32 kHz**。
视频流 md5 `f13a831ccb8eea5abb6576e9678ad12f`，音频流 md5 `e300dfe400abca85cf003b235ecae2a9`。

⚠️ 工单规格行写的是"768p"，但本项目两条工作流的实际设定是
`ResolutionSelector 0.4 MP 16:9 → 864×480`（工作流内 MarkdownNote 的对照表亦如此）。
判定以 ffprobe 实测与升级前后一致为准；"768p"记录为工单笔误。

⚠️ 工单回归②列的三条工作流中 **`workflows/video_minimax_h3_fl2v.json` 不存在**
（`workflows/` 下只有 t2v、r2v 与一个 r2v 备份）。fl2v 模型物料已在位
（`minimax_h3_fl2va_pruned_int8_convrot.safetensors` + 两个 turbo LoRA），
应是 P56（Pika Flex 对比）尚未产出该工作流。本报告按存在的两条执行。

## 二、升级执行（第 1 步）

1. `git checkout v0.43.2` —— 成功（442 个提交的差距）。
2. **pip 红线检查**：先 `pip install --dry-run -r requirements.txt` 实测（`pip_dryrun_0432.txt`）——
   v0.43.2 的 requirements 中 torch/torchvision 为**裸名**（无版本约束），dry-run 确认
   `torch 2.11.0+cu128 / torchvision 0.26.0+cu128 全部已满足、不动`，xformers 不在依赖里。
   将安装的只有 frontend/templates 等周边包。**未触发工单的"torch 大版本变更"停止条款。**
3. 正式安装成功；升级后 `pip freeze` 存档 `pip_freeze_0.43.2.txt`，torch 系逐包复核未变。

## 三、五条回归的结果

| # | 回归 | 结果 | 关键证据 |
|---|---|---|---|
| ① | 启动无新报错 | **过**（带一条新增信息性 warning） | 见 3.1 |
| ② | 工作流加载与规格 | **过**（t2v、r2v；fl2v 不存在） | 见 3.2 |
| ③ | 同 seed 生成一致 | **FAIL** | 见 3.3（触发回滚） |
| ④ | FlashVSR 节点存活 | **过** | 见 3.4 |
| ⑤ | 项目侧引用不破 | **过** | 见 3.5 |

### 3.1 启动日志对比

- v0.34：唯一 warning 是已知的 "need pytorch with cu130" 提示。
- v0.43.2：同样的 cu130 提示 + **新增一条** `On windows we are currently forcing
  single GPU mode ... use: --cuda-device all`——信息性提示（本机本来就单卡），非错误。
- 两个版本启动日志里均无 error / traceback / failed（日志全文在
  `E:\Minimax-H3\from_e_root\out\p55\comfy_v034_startup.log` / `comfy_v0432_startup.log`）。

### 3.2 工作流加载与规格

- **r2v**（v0.43.2，同 seed 复跑）：成功，输出规格 **h264 864×480 @ 24 fps、124 帧、
  aac 立体声 32 kHz** —— 与基线规格逐项一致（`compare_r2v.json` 的 specs 段）。
- **t2v**（v0.43.2）：成功（prompt_id `069adc1d`，235.8 s），输出规格同上
  （`probe_t2v_0432.json`）。
- ⚠️ 过程中发现：`experiments/bench.py` 的 UI→API 转换器**不支持 subgraph**
  （t2v 的全部生成逻辑在一个 subgraph 定义里，转换出的 UUID 节点会被 API 以
  `missing_node_type` 拒绝——这在 v0.34 下同样发生，是转换器的能力边界，不是升级回归）。
  为本次验证在 `experiments/p55_runner.py` 里实现了 subgraph 展开
  （`definitions.subgraphs` 内嵌定义、`-10/-20` 虚拟桥节点、按 name 匹配桥接、
  内部 link 前缀重映射），展开结果经 dry-run 逐节点核对（`t2v_expand_check2.txt`）。

### 3.3 核心：同 seed 生成一致性 —— **FAIL（触发回滚）**

实验设计：同一 r2v 工作流、同 prompt、`RandomNoise.noise_seed` 显式钉死为
`261662374822964`（工作流原值），升级前后各渲染，逐流 md5 + 逐帧 PSNR 对比。

**结果：画面变了。**

| 对比项 | v0.34 基线 | v0.43.2 | 判定 |
|---|---|---|---|
| 视频流 md5 | `f13a831c…` | `d5e83c59…` | 不同 |
| 音频流 md5 | `e300dfe4…` | `2c4bf034…` | 不同 |
| 规格 | 864×480/24fps/124帧/立体声 | 相同 | 一致 |
| 逐帧 y-PSNR | — | **mean 20.46 dB，min 8.88，max 23.39** | 远低于编码噪声线（50+ dB） |

- 124/124 帧**全部**显著不同（y-PSNR 分布：16–20 dB 49 帧、20–24 dB 73 帧、<16 dB 2 帧，
  `frame_psnr.txt`）——不是个别帧、不是色彩偏移，是整条采样轨迹的分叉。
- **VLM 读画面**（`base_f001/cand_f001.png`、`base_f075/cand_f075.png`）：
  首帧语义相同（俯视屋顶、红斗篷小超人、夜城），但斗篷形状、胸口徽章、楼窗排布等细节不同；
  最差帧（n75，8.88 dB）语义仍相同（机甲爪自上方逼近、男孩趴屋顶），但男孩姿态/表情、
  机甲爪形态完全不同。**同镜头设计、不同轨迹。**
- **排除非确定性**（关键对照实验）：v0.43.2 下同 seed 重启服务器重跑第二次，
  视频流、音频流 md5 与第一次**逐字节一致**（`compare_r2v_repeat.json`）。
  ⇒ v0.43.2 自身完全确定；差异是**确定性的版本行为变化**。
- 源码层定位（`git diff 12d52794 v0.43.2`，diff 全文存 `E:\Minimax-H3\from_e_root\out\p55\diff_*.txt`）：
  v0.43.2 把 H3 的数值路径大面积 **comfy-kitchen 化**——
  - `comfy/ops.py`（+377 行）：int8/nvfp4 量化权重的线性层与 dequant 移向 kitchen 实现；
    H3 扩散模型是 `int8_convrot` 量化、文本编码器是 `nvfp4_awq` 量化，两者 dequant 路径都在其中；
  - `comfy/ldm/minimax/model.py`：attention 调用改写（`preferred_attention=ComfyAttention()`、
    `v.clone()` 移除、`denoise_mask` 缩放等）；
  - `comfy/ldm/minimax/vae.py`：解码器重写（融合 rms+rope kernel、tiled_decode 算法重写、
    int8 attention 分支）——视频与音频 VAE 解码都受影响（音频流 md5 同样变化与此吻合）；
  - `comfy/ldm/modules/attention.py`（+76 行）：新增从 checkpoint metadata 读取 attention
    config 的机制。**已实测排除**：两个 H3 checkpoint 的 safetensors metadata 里均无
    attention config（`no attention metadata`），此机制未启用。
  - 采样器/sigma shift 数学未变（`model_sampling.py` 仅新增 r2v 不用的 IMG_TO_IMG_VELOCITY；
    `res_multistep` 实现未动）。
- **归因结论**：差异机制明确（上述数值路径重写 → 同 seed 采样轨迹确定性分叉），
  但 v0.43.2 没有任何配置级开关能恢复 v0.34 的 kernel 路径（kitchen 化不是可选 feature），
  且三处重写叠加，无单一"罪魁提交"可回退 cherry-pick。文本编码节点
  （MiniMaxH3ReferenceToVideo）是一体节点，无法在不重写节点的情况下单独隔离 conditioning 对比。

**⇒ 命中工单第三节回滚触发条件：③"生成结果改变"。按预授权执行回滚，不硬修。**

### 3.4 FlashVSR 存活

`ComfyUI-FlashVSR_Ultra_Fast` 在 v0.43.2 下正常加载（启动日志 `IMPORT 0.0s`），
四个节点类 `FlashVSRNode / FlashVSRNodeAdv / FlashVSRInitPipe / WavespeedFlashVSRNode`
全部出现在 `/object_info`（对比文件 `object_info_034.json` / `object_info_0432.json`）。

### 3.5 项目侧引用

`grep -r "video_minimax_h3" --include=*.py` 全仓 12 个文件，两类引用逐一核验：

1. **工作流文件路径引用**（10 个脚本指向 `E:\ComfyUI\user\default\workflows\` 副本、
   1 个指向 `E:/Minimax-H3/video_minimax_h3_r2v.json`）：`user/` 目录不在 git 跟踪内，
   checkout 不触碰，升级后实测三个工作流副本仍在；
   `E:/Minimax-H3/video_minimax_h3_r2v.json` 这个引用升级前即失效（主仓库根无此文件），
   非本次升级造成。
2. **节点类名引用**（`MiniMaxH3ReferenceToVideo / MiniMaxH3SigmaShift /
   MiniMaxH3ImageToVideo / MiniMaxH3AddGuide`）：四个类在 v0.43.2 的 `/object_info`
   中全部仍注册（v0.34→v0.43.2 节点类 903→1026；消失的 9 个类全是
   ByteDance/Kling/Ltxv/OpenAI/Veo 云 API 节点，本项目无引用）。

## 四、回滚执行（第 4 步）

```bash
cd /e/ComfyUI && git checkout local-pre-upgrade-0.34   # → v0.34.0
venv/Scripts/python.exe -m pip install -r E:/Minimax-H3/out/p55/pip_freeze_0.34.txt
```

- 回滚后 `pip freeze` 与升级前快照**逐行一致**（唯一差异是升级期间新增的
  `comfyui-workflow-templates-media-assets-02`，v0.34 代码不 import，已卸载后 diff=0）。
- torch 系（2.11.0+cu128 / 0.26.0+cu128）全程未动。
- **回滚恢复验证（黄金证据）**：回滚后重启 v0.34、同 seed 复跑 r2v，
  输出视频流 md5 = `f13a831ccb8eea5abb6576e9678ad12f`、音频流 md5 = `e300dfe400abca85cf003b235ecae2a9`
  ——**与升级前基线逐字节一致**（`compare_rollback.json`）。
  ⇒ 回滚完全恢复原生成行为；同时反证 v0.34 自身也是确定的。

## 五、给指挥窗口的裁定材料

升级的动因（P56 Pika Flex 需要 0.43.2+、P57 ControlNet Union 需要 0.35.0+）仍然成立，
但**接受 v0.43.2 等于接受"全部既有 seed 的产出作废"**（生成管线从 prompt+seed 锁定
变为不可复现）。可选路径：

1. **保持 v0.34**，P56/P57 的模板依赖在需要时再评估（部分模板可能兼容 0.34 或可手工改）；
2. **接受 v0.43.2 + 全量重锁 seed**：若生产线不依赖历史 seed 复现，语义质量未观察到退化
   （见 3.3 的 VLM 读帧），但需重跑所有既有工作流的 seed 校准；
3. **等上游**：向上游报告 H3 产出在 0.34→0.43.2 间不可复现的问题，看是否有官方说明
   （int8_convrot/nvfp4 kernel 更换是否有精度声明）。

## 六、证据文件清单

均在 `E:\Minimax-H3\from_e_root\out\p55\`（执行时按当期工单写在 `E:\Minimax-H3\from_e_root\out\p55\`；
执行结束后按用户 2026-11-04 的整理指令把 `E:\out` 等项目相关目录统一挪入
`E:\Minimax-H3\from_e_root\`，下文路径已按新位置书写。大文件按工单要求留证据，
mp4 合计仅约 6 MB，全部保留）：

| 文件 | 内容 |
|---|---|
| `baseline_r2v_034.mp4` / `candidate_r2v_0432.mp4` / `candidate_r2v_0432_repeat.mp4` / `candidate_t2v_0432.mp4` / 回滚验证 mp4 | 五次生成产物 |
| `compare_r2v.json` / `compare_r2v_repeat.json` / `compare_rollback.json` | 逐流 md5 + PSNR |
| `frame_psnr.txt` | 124 帧逐帧 y-PSNR |
| `base_f001.png` / `cand_f001.png` / `base_f075.png` / `cand_f075.png` | VLM 读帧素材 |
| `comfy_v034_startup.log` / `comfy_v0432_startup.log` / `comfy_v034_rollback.log` | 三次启动日志 |
| `run_*.log` | 五次 API 提交记录（prompt_id、seed、耗时） |
| `pip_freeze_0.34.txt` / `pip_freeze_0.43.2.txt` / `pip_freeze_after_rollback.txt` | 环境三快照 |
| `pip_dryrun_0432.txt` / `pip_install_0432.log` / `pip_rollback.log` | pip 过程记录 |
| `object_info_034.json` / `object_info_0432.json` | 两版节点注册表 |
| `diff_nodes_minimax_h3.txt` / `diff_minimax_model.txt` / `diff_minimax_vae.txt` | 关键源码 diff |
| `t2v_expand_check2.txt` / `t2v_131.txt` | subgraph 展开核对 |

新增脚本（随本报告提交）：`experiments/p55_runner.py`（钉死 seed 的 API 提交器 +
subgraph 展开）、`experiments/p55_compare.py`（逐流 md5 + PSNR 对比）。

## 七、执行中的失误记录（如实）

1. **bench.py 的 `--seed` 参数是死的**（解析后从未使用）——基线实验前才实测发现，
   改为在 p55_runner 里显式钉死并打印 pinned 值。
2. **subgraph 展开器第一版有两个 bug**：按数组索引对齐 wrapper.inputs 与 sg.inputs
   （实际两者顺序错位，prompt 桥被绑到了 ResolutionSelector 的 width 输出）；输出桥的
   顶层 link 字段索引写反（src/dst 混淆）。第一次 dry-run 对照中发现，均改为按 name
   匹配 / 修正索引后 dry-run 逐节点核对通过。
3. **自确定性实验第一次白跑**：未意识到 ComfyUI 对完全相同的 prompt 会命中执行缓存
   （0.4 s 返回同文件），重启服务器清缓存后重跑才拿到真数据。
4. **ffmpeg stats_file 的冒号转义**在 Git Bash 下解析失败两次，最终用 cd + 相对路径绕过。
