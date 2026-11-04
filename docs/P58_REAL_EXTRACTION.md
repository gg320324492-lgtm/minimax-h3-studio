# P58：真实素材的提取→控制链验证 —— 数据报告

> 工单：`docs/WORKORDER_P58_REAL_EXTRACTION.md`（2026-11-04）
> 前置：P57（Union 2.0 合成信号下控制确认生效）。
> **本报告只给裁定数据，不裁定。** 对比帧在 `out/p58/compare/`，供肉眼裁定。
> 所有数字均为实测；未测的项目明确标注。生效性判读以像素差为主，
> 肉眼观察仅作旁证并标注（P57 已实测 VLM body_orientation 与肉眼矛盾，
> 本项**未调用 VLM**）。

---

## 0. 速览

| 裁定问题 | 数据答案（详见 §6） |
|---|---|
| 真实提取链端到端能跑吗 | **能**。权重下载+SHA256 校验、两路提取、两路生成、提取+生成一体图全部 success；一体图端到端 pose 356.1s / depth 248.7s（含提取，864×480×124） |
| 真实素材上控制跟随如何 | strength 1.0 vs 0.0 逐帧 PSNR：pose 13.89 dB（12.24–15.88）、depth 14.58 dB（11.24–16.95）——与 P57 合成信号的 12.3–14.7 dB 同级；提取噪声未使控制失效（若失效，s1 与 s0 应逐帧一致） |
| 生产可用性（显存/耗时/画质） | 全程显存峰值 31,679 MiB / 32,607 MiB，**余量 928 MiB**；一体图峰值不高于纯生成（提取模型先卸载）；画质肉眼无崩坏，PSNR 对基线 13.9/14.6 dB——是否可接受留给裁定 |

---

## 1. 环境与权重

- ComfyUI `E:\ComfyUI` @ v0.43.2，commit `423cbd20511becb1f16122ab518e92e58bfa03d9`（开工实测，与工单一致）。
- Union 2.0 权重 `model_patches/minimax_h3_fun_controlnet_union_2.0_pruned_bf16.safetensors` 只读未动。
- **提取权重开工核查：全部缺失**（`models/checkpoints`、`models/geometry_estimation` 均只有占位文件），按工单下载并以 aria2c 内置 checksum + 本地 `sha256sum` 双重核验：

| 权重 | 落盘 | 字节 | SHA256（实测=HF LFS oid） |
|---|---|---|---|
| SDPose wholebody | `models/checkpoints/sdpose_wholebody_fp16.safetensors` | 1,916,645,792 | `63d01f9a7494560693b24767f4469d59c9d3266b31ff0a253e74d1e611442721` ✓ |
| RT-DETR v4-x-hgnet | `models/diffusion_models/rt_detr_v4-x-hgnet_fp16.safetensors` | 123,968,978 | `581f9af9bbabb664d1891cbccd823308b176ecd409146f954dfa39af3bec2476` ✓ |
| Depth Anything 3 base | `models/geometry_estimation/depth_anything_3_base.safetensors` | 541,524,124 | `418c0d2ea857e2d1215fa51baa46833f499a62eb2400ec63d337aa20d326414f` ✓ |

- 未安装任何新自定义节点；提取链全部内建节点（`nodes_sdpose.py`、`nodes_depth_anything_3.py`、RTDETR_detect、ResizeImageMaskNode）。
- 服务器裸 `main.py --port 8188`（与 P57 相同，无显存旗标），用后已停。

## 2. 真实素材

按工单优先级取第 1 顺位：`water_renewal/07_edit/WaterRenewal_1080p.mp4`
（1920×1080@30fps，198.06s，495,113,808 B，只读未动；真实纪录片实拍，非合成）。

镜头选择过程落盘：`out/p58/water_scan_2s.jpg`（全片每 2s 总览）、`out/p58/scan_w*.jpg`（候选窗口细扫）、`out/p58/check_shot_169_174.jpg`（边界确认）。
**选定 t=169.0–174.17s**：4 人在岸边栽种作业（弯腰、递物、遮挡、烧录中文字幕俱全）——比 P57 火柴人难得多，正是"真实提取噪声"该有的难度。

切片规格（与 P57 控制视频完全对齐）：`p58_real.mp4` 864×480@24fps ×124 帧 h264（`out/p58/work/real_clip.mp4` 存档）。

## 3. 提取质量门槛（先证明提取，再跑生成）

配置全部照官方模板子图原值：RT-DETR threshold 0.5 / class `person` /
**max_detections 2**；SDPose batch 16；绘制 body+hands+face+feet、stick 4、
face_point 2、score 0.5；DA3 mono、resolution 504、v2_style。

### 数值（`out/p58/extract_metrics.json`）

| 指标 | Pose（SDPose） | Depth（DA3 base） |
|---|---|---|
| 耗时（GPU 串行） | 117.9s | 41.3s |
| 显存峰值（超基线） | 9,151 MiB（+3,767） | 7,698 MiB（+0，未超提取 pose 后的已缓存水位） |
| 检出失败帧 | **0 / 124** | — |
| 骨架像素/帧 | mean 6,049 / min 2,279 / max 6,394 | — |
| ≥200px 连通分量/帧 | 直方图 {2:1, 3:35, 4:88}（注：一人骨架可断多段，此数≠人数） | — |
| 亮度结构 | — | mean 182.9 / std 65.7；逐帧 std 51.4–75.6 |
| 梯度（Sobel） | — | mean 1.82 / p95 6.0（有结构、不碎） |
| 时序 MAD（对源 RGB 2.36） | — | 1.77（同量级→深度跟得上运动，非冻结非噪声） |

### 肉眼（`out/p58/extract/*_f{030,062,093}_pair.png`，源|控制并排）

- **Pose**：被检出者骨架与真人姿态吻合（白衣人双腿开立/手臂伸展的骨架正确）。局限如实记录：**模板 max_detections=2，4 人只出 2 副骨架**；第二副常为上半身残段（遮挡所致）。
- **Depth**：近亮远暗排序正确、人物呈近景亮块、结构平滑；**烧录字幕框被当作近景平面**（底部白矩形）——真实素材特有伪影，裁定时应知悉。

**门槛判定：两路均通过**（有检出、有结构、无冻结），继续生成对照。

## 4. 三组对照（每路；同 seed 1086599926715797、同模板 prompt、864×480×124、20 步）

生成臂（本项新跑，全部 success，规格全部 h264/864×480/24fps/124f/aac）：

| run | 耗时 | 显存峰值 MiB |
|---|---|---|
| pose_real_s1 | 253.2s | 31,484 |
| pose_real_s0 | 245.0s | 31,647 |
| depth_real_s1 | 298.9s | 31,664 |
| depth_real_s0 | 170.2s | 31,679 |
| pose_e2e_s1（一体图） | 356.1s | 31,544 |
| depth_e2e_s1（一体图） | 248.7s | 31,545 |

逐帧比对（124 帧，`out/p58/compare_metrics.json`）：

| 对照 | MAD mean（min–max） | PSNR mean（min–max） | 判读 |
|---|---|---|---|
| **① 生效性** pose_real_s1 vs s0 | 39.03（29.9–49.2） | **13.89 dB**（12.24–15.88） | 控制在真实信号下真生效，量级与 P57 合成信号（12.3–14.7 dB）同级 |
| **① 生效性** depth_real_s1 vs s0 | 35.03（24.4–54.1） | **14.58 dB**（11.24–16.95） | 同上 |
| **② 真实 vs 合成** pose（vs P57 pose_s1） | 16.45（8.9–39.4） | 19.50 dB（12.70–23.66） | 真实控制输出与合成控制输出显著不同；但两者互差（19.5 dB）小于各自对基线的偏离（13.9 dB 对应更大像素差）——prompt 主导内容、控制改姿态的格局未变 |
| **② 真实 vs 合成** depth（vs P57 depth_s1） | 21.86（14.2–32.9） | 17.27 dB（14.74–19.87） | 同上 |
| **③ 画质基线**（s0 即无控制） | 见 ① | 见 ① | s1 对基线 PSNR 13.9/14.6 dB；肉眼旁证：s1 画面无崩坏、人物完整、沙粒质感与基线同级 |
| 附：一体图 vs 两段式 pose | 3.08 | 32.48 dB | mp4 中间件对 pose 控制几乎无影响 |
| 附：一体图 vs 两段式 depth | 10.38（5.0–17.8） | 22.40 dB | h264 中间件会压平深度渐变，**深度路建议一体图或无损中间件** |

### ③ 的 no-op 证明（实测，不是外推）

源码 `comfy_extras/nodes_minimax_h3.py:605`：`strength == 0` 时 Apply 直接返回**未打补丁的** model。
实测交叉验证：pose_real_s0（真实控制、strength 0）vs P57 pose_s0（合成控制、strength 0）
→ **124/124 帧逐像素一致，demux 后 h264 码流字节一致**；pose_real_s0 vs depth_real_s0 同样 124/124 一致。
即三路 s0 是同一条"无控制纯 H3 直出"，不同控制视频在 strength 0 下对输出零影响（容器 SHA 不同仅因 ComfyUI 把 prompt JSON 嵌进 mp4 元数据）。

### 肉眼裁定材料

- `out/p58/compare/{pose,depth}_f{030,062,093}_quad_src_ctrl_gen_baseline.png`：**源|控制|s1 生成|s0 基线** 四联。
- `out/p58/compare/*_effectiveness_*.png`、`*_real_vs_synth_*.png`、`*_e2e_vs_two_stage_*.png`：两两并排。
- 肉眼旁证（本项未调用 VLM；P57 实测 VLM 不可信）：f093 pose 四联中，s1 生成人物**双臂外展**与提取骨架（白衣人手臂伸展）吻合，s0 基线手臂下垂朝向不同；f062 depth s1 人物呈背面视角与真实深度图最近亮块（背面白衣人）一致。

## 5. 显存与耗时（生产可用性硬数字）

- GPU 总显存 32,607 MiB；**本项全程最高峰 31,679 MiB（depth_real_s0），余量 928 MiB**——与 P57 的 31.4–31.8 GB 水位相同。
- **一体图（提取节点与 H3 同图）峰值 31,544/31,545 MiB，不高于纯生成**：ComfyUI 在采样前卸载提取模型，真实链入图不额外吃显存。
  - 该结论有效性已核验：`run_pose_e2e_s1.json` 的 `execution_cached` 列表只含模型加载器与采样链，新增提取节点 900–905 及 174/705/709 均未缓存；`run_depth_e2e_s1.json` 缓存列表含 174/705/709（源视频解码复用），但 **DA3 提取节点 910–912 未在缓存列表内**。服务器日志末两轮 354.37s / 246.89s 且打印 SDPose 权重加载记录——两路提取确实在同图内执行，不是被跳过后的空跑。
- 端到端耗时（含提取）：pose 一体图 356.1s；depth 一体图 248.7s；两段式合计 371.1s / 340.2s（含两次提交与 mp4 落盘）。5 秒片段 4–6 分钟量级。
- 单独提取：pose 117.9s / 峰值 9,151 MiB；depth 41.3s / 峰值 7,698 MiB。提取全程 GPU 推理，无 CPU 回退。

## 6. 三个裁定问题的数据答案

1. **端到端能跑吗**：能。缺的两件 SDPose 权重 + DA3 权重下载并双重校验；两路提取 0 失败帧；两路生成 + 一体图 6 轮全 success；端到端 4–6 分钟/5s 片段。
2. **控制跟随**：真实信号下 strength 1.0 vs 0 PSNR 13.89（pose）/ 14.58（depth）dB，与 P57 合成信号同级——**提取噪声没有让控制失效**（失效则 s1≈s0、PSNR→∞）；真实 vs 合成控制输出互差 19.5/17.3 dB，控制信号差异确实传导进生成；骨架跟随的贴近度（"结构建议级"是否仍成立）请以 §4 四联帧肉眼裁定——本轮素材 4 人只出 2 副骨架、第二副常残缺，跟随上限受 max_detections=2 与遮挡制约。
3. **生产可用性**：显存余量 928 MiB（与 P57 相同，一体图不更差）；耗时见 §5；画质无崩坏但 PSNR 对基线 13.9/14.6 dB（控制的代价幅度与合成信号一致）；深度路若走两段式，h264 中间件对控制信号有可见影响（一体图 vs 两段式 22.4 dB），pose 路几乎无影响（32.5 dB）。

## 7. 磁盘纪律与改动文件

- 一切新文件均在 `E:\Minimax-H3\` 内（`out/p58/` 共 63 MB 证据）或 `E:\ComfyUI\models/`（工单授权的权重 2.6 GB）；未在 E 根建目录、未在 C 盘产生数据。
- 收尾清理：`E:\ComfyUI\output\p58\`（8 个中间 mp4）已删；`out/p58/` 保留全部裁定证据（extract/compare/runs/controls + 全部 JSON 记录）；`E:\ComfyUI\input\` 保留 `p58_real.mp4` 与两个控制 mp4 供复现。
- 在制工作（`studio/src/Root.tsx`、`intro_video/`、`studio/public/audio/intro/`、`studio/src/templates/model-intro/`）未碰；`workflows/video_minimax_h3_fun_controlnet_union.json` 原件未动（新变体 `workflows/video_p58_*.json`，该目录本被 gitignore，不入库）；P57 脚本与报告未改。

新增文件（提交内容）：
- `experiments/p58_extract.py` —— 提取链提交 + 显存/耗时采样
- `experiments/p58_measure_extract.py` —— 提取质量门槛度量
- `experiments/p58_build_workflows.py` —— 生成变体（两段式 UI + 一体图 API prompt）构建
- `experiments/p58_runner.py` —— 生成运行器（UI/API 双格式）
- `experiments/p58_measure.py` —— 三组对照 PSNR/MAD/一致性测量
- `docs/P58_REAL_EXTRACTION.md` —— 本报告

## 8. 失误如实记录

1. **aria2c 校验竞态 ×2**：两次在 aria2c 尚在写盘时抢跑 `sha256sum`，把读写中的文件误判为"下载损坏"并重下（第一次还删掉了可能已完好的文件）。实际网络并无损坏；教训：校验必须在进程结束后做。
2. **假成功 ×1（工单警告的原样复现）**：第一次跑提取时 `cd` 到主仓库 `experiments/`（脚本在工作树），Python 报"找不到文件"，但命令末尾 `| tail` 吞掉退出码，后台任务报"exit 0 完成"。被读记录文件时的 FileNotFoundError 抓到。此后所有关键命令不再接管道。
3. 小错：ComfyUI 启动用了不存在的 `--log-file` 参数（退出码 2，改重定向）；aria2c 命令行 `checksum=` 漏 `--` 前缀被当 URI（退出码 1，修正）；`p58_extract.py` DA3Render 动态组合子字段漏 `output.` 前缀（服务器 400 拒绝，修正）。三起均即时发现修正，未影响数据。

## 9. 复现

```bash
# 服务（用后停）
cd /e/ComfyUI && venv/Scripts/python.exe main.py --port 8188
# 提取（GPU 串行，先 pose 后 depth）
python experiments/p58_extract.py pose && python experiments/p58_extract.py depth
python experiments/p58_measure_extract.py
# 生成 4+2 轮（脚本 p58_build_workflows.py 生成 workflows/video_p58_*.json
# 与 out/p58/api_p58_*_e2e_s1.json，再逐个 p58_runner.py 提交）
python experiments/p58_build_workflows.py
python experiments/p58_measure.py
```

seed 固定 1086599926715797（模板自带值）；P57 产物（合成控制臂、pose_s0 基线交叉验证）位于 `out/p57/runs/`。
