# Remotion Phase 0 渲染基准报告（2026-09-29）

> 环境：Windows 11 / RTX 5090 32GB / 32 CPU 线程 / 66GB RAM / Node v24.16.0 / pnpm 9.15.9
> 测试对象：EP01 真实资产 dummy 时间线 —— 12 个 768×1344 片段（共 1454 帧 / 60.583s @24fps）、
> 19 条字幕事件、 premixed AAC 48k 立体声 → 输出 1080×1920 H.264
> 配置：remotion@4.0.529 全家族，chrome-headless-shell（自动下载 113MB 到 `node_modules/.remotion/`）

## 1. 核心结论

**60.58s 的 1080×1920 成片（12 个 OffthreadVideo + 19 条字幕 + 混音轨）38.8s 渲染完成，约 1.55 倍实时。**
瓶颈在片段解码与帧截图（CPU），不在编码——NVENC 几乎无收益。**定稿编码配置：x264 crf18 + jpeg 截帧 + `colorSpace:'bt709'` + 并发 16。**

## 2. 渲染耗时矩阵

| 配置 | 总耗时 | 备注 |
|---|---|---|
| 并发 8（x264 crf18） | 40.0s | |
| **并发 16（默认，=32线程一半）** | **38.8s ± 0.5s**（官方 benchmark 3 轮：39.83s ± 0.47s） | ✅ 最优 |
| 并发 24 | 42.8s | 过并发反而退化 |
| PNG 截帧（并发16） | 83.9s | 2.2 倍慢，仅 alpha 需求才用 |
| NVENC 14M（并发16） | 37.3s | 只快 1.5s；profile 降 Main、文件 110MB（x264 crf18 的 2 倍）→ 弃用 |
| bundle() | 1.0s | 项目尚小；selectComposition 元数据 0.3s |

> 硬编注意：`hardwareAcceleration` 合法值是 `disable | if-possible | required`（不是 "disabled"）；
> `videoBitrate` 是字符串 `"14M"`/`"14000K"`，且与 `crf` 互斥（同时传直接报错）。

## 3. ⚠️ 关键坑：jpeg 截帧默认输出 yuvj420p（挂 QA）

- 现象：`pixelFormat:'yuv420p'` 已显式传入，输出仍是 `yuvj420p`（full range），`qa_final.py` 第 79 行严格判等必挂。
- 原因：Node API **不读 `remotion.config.ts`**（仅 CLI 生效）；Rust compositor 对 jpeg 输入自行决定 range。
- **解法（定稿）**：`colorSpace: 'bt709'` → 输出 `yuv420p` + `color_range=tv` + bt709 三件套色彩标签，渲染速度无损耗。PNG 截帧虽也得到 yuv420p，但 2.2 倍慢，不用。
- 目检验证：bt709 版与 yuvj 版抽帧对比亮度/层次完全一致（真实数据转换，非仅贴标签）。
- **附带收益**：成品带规范 bt709 色彩标签，比现有 PIL 管线（无标签）更规范。

## 4. 定稿 render.mjs 默认参数

```
codec=h264  crf=18  imageFormat=jpeg  pixelFormat=yuv420p
colorSpace=bt709  concurrency=16（显式传，不依赖默认值）
```

输出规格实测：h264 High / 1080×1920 / 24/1 / 1454 帧 / yuv420p / tv / bt709 / AAC 48k stereo / 60.63s —— **qa_final.py 的容器规格检查项全部可过**（响度由上游 mix_audio 保证）。

## 5. 字体与中文

- `simhei.ttf` 自托管（`public/fonts/` + FontFace + delayRender）✓；系统字体（微软雅黑）在本机 headless 下也可用 ✓；中文无豆腐块（renderStill 目检通过）。
- 渲染关键字体仍统一走自托管（跨机可移植）；`.ttc` 集合文件不直接用，需要时先转 ttf/woff2。

## 6. 遗留给 Phase 1 的决策点

1. **768×1344 → 1080×1920 的适配方式**：`objectFit:'cover'`（本基准，裁掉 ~1.6% 宽度、不变形）vs 现有超分管线的直接拉伸（Lanczos 到 1080×1920）。Phase 1 A/B 时和 v2 成片对齐后二选一。
2. **逐片段超分**：本基准直接用 768×1344 原片由浏览器放大，正式链路是 Real-ESRGAN 逐片段超分到 1080×1920 后原分辨率装配（画质远好于浏览器插值）。
3. 字幕样式令牌（tokens.ts）目前是近似值，Phase 1 从 `burn_subtitles_v2.STYLES` 精确移植并用 qa 字幕宽度检查校准。

## 7. 测试产物

- `studio/out/ep01_bt709.mp4` — 定稿配置参考渲染（50.8MB）
- `studio/out/ep01_c16.mp4` — yuvj420p 对照版（问题复现样本）
- `studio/out/probe.png` — 字体探针帧
- `studio/public/jobs/phase0/` — 硬链接资产 + props（`emit_phase0_props.py` 可随时重建）
