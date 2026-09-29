# Remotion 动效张力提升 — 调研结论与执行记录（2026-09-30）

> Phase 5 交付。三路调研：① 抖音爆款动效语言 ② Remotion 特效技术栈（版本精确：直接读 4.0.529/530 npm 包 .d.ts + 文档源码）③ 配乐音效与混音规范。
> 已执行成果：`pure_remotion_demo_v3.mp4`（28.1s，1080×1920，BGM+全套音效，母带 −14.2 LUFS/−1.1 dBTP）。

## 1. 抖音爆款动效语法（已按参数实现 ✅）

| 模式 | 调研参数 | 实现状态 |
|---|---|---|
| 数字滚动 count-up | 45–60f，缓出三次 `1-(1-t)^3`，**必须 tabular-nums** | ✅ AnimatedNumber（前导数字解析+后缀保留） |
| punch-in + 白闪 + 震动 | scale 1.10–1.15 / 5–8f；白闪 2–4f；震动指数衰减 5–15f | ✅ ImpactWrap（spring d12/s160 + 3f 白闪 + ±9px/6f 衰减） |
| 卡点量化 | 120–128 BPM 主流；`round(900/bpm)` 帧/拍 | ✅ bpm prop → 分段起点吸附拍边界 |
| 柱状图生长 | spring damping 20/stiffness 100，6–10f 错峰，微过冲 | ✅ 7f 错峰（半拍 @126）+ 冠军条金色发光 |
| 花字逐字 slam | 1 帧错峰，scale 1.4→1，back.out | ✅ KineticChars（标题+要点） |
| 颜色体系 | 黑底+高饱和；白正文/金数字/绿正红负，≤3 色 | ✅ 已是既有令牌体系 |
| 集中线/光扫/暗角冲击/RGB 分离 | 集中线 8–15f、光扫 12–18f 一次、暗角 3–6f、RGB split 2–6f | ✅ 全部实现 |
| 节奏规范 | 前 3 秒钩子（72% 用户 3s 内划走）；30–60s 视频需 8–15 屏；**15–17s 完播率最优**；单屏 ≤3 个数字 | 📐 已按 28s/6 屏执行；时长档位进 v4 |
| 冻结-爆发（先抑后扬） | 落点前定格 15–30f | ⏳ v4 |
| 概率环（百分比环） | SVG dashoffset 与计数同步落地 | ⏳ v4 |
| 数字滚轮（odometer） | 每位数字 0-9 竖条 translateY，最右位转最久 | ⏳ v4（大数专用） |
| 排名翻转赛跑图 | 逐帧插值+每帧重排序，top10 上限，翻转点=卡点 | ⏳ v4（注意 r/dataisbeautiful 的"滥用警告"） |

## 2. Remotion 特效技术栈（版本精确结论）

**采纳（已装/立即可用）：**
- `@remotion/noise`（MIT，纯 JS 零成本）——✅ 已用于震动（noise2D 替代正弦，更"脏"更自然）；v4 可做光斑有机漂移
- `@remotion/media-utils`（MIT）——✅ 已用于 BassPump：`visualizeAudio({numberOfSamples: 8, optimizeFor:'speed'})` 低频能量 → 全屏 2.8% 呼吸脉冲
- `@remotion/transitions` 的 **`pushCut()`**（CSS，4.0.500+，专为抖音卡点设计：punch+flash 转场）——v4 把分段装配迁到 `TransitionSeries` 时采用；**注意**：与本管线"帧内转场保绝对秒"原则冲突，需先验证音频对齐策略
- `@remotion/effects`（Remotion License，70+ 效果：zoomBlur/glow/chromaticAberration/scanlines/vignette/shine/noiseDisplacement…）——只挂媒体组件（Solid/Img/Video），**纯 DOM 模板用不上**；AI 片段模板（drama/psa/story 的 OffthreadVideo）要电影感 LUT/辉光时的正确工具，需 `--gl=angle`（5090 上 D3D 后端，headless 可用）

**暂缓（附理由）：**
- `@remotion/three`（WebGL 3D）——headless 需 `--gl=angle`，已知 angle 内存泄漏需分段渲染；纯数据视频 3D 张力/成本比低。真 3D 需求时 `<ThreeCanvas>` + 5090 可行
- `@remotion/lottie`——LottieFiles 许可逐资产核查 + svg renderer 帧成本高；自研组件已覆盖需求
- `@remotion/gsap`——GSAP 3.13 起全免费（含 SplitText），但核心 spring/interpolate 已够用；仅当需要复杂 stagger 编排时引入
- `@remotion/motion-blur`——children 每帧重渲 N 倍，samples>5 是性能杀手

**性能杀手清单（本机 1080×1920 实测相关）**：backdrop-filter（最恶劣）、动画 feTurbulence（软件逐像素）、CSS 大半径 blur/box-shadow 滥用、CameraMotionBlur samples>5、OffthreadVideo（官方已建议迁移 `@remotion/media <Video>`——5.0 前不变）。本机 NVENC 可用但 Phase 0 已定 x264 crf18 为 QA 基准。

## 3. 音频管线（网络受限的全合成方案 ✅）

- 资产站（Pixabay/Mixkit/Kenney/爱给）本机直连全部不可达（沙箱白名单仅 npm/pypi/HF；代理 7897 不通外网）。
- **方案**：`make_audio_assets.py` numpy 确定性合成——126 BPM BGM（kick/hat/bass/泵动 pad，16 小节 intro→build→full→out）+ 5 音效（whoosh/impact/pop/ding/riser）+ 精确拍网格 JSON。**卡点零检测误差、确定性可复现、零版权风险**。
- 备选（网络恢复时）：Pixabay Content License / Mixkit Free License / Kenney CC0，manifest 记录来源+许可+下载日期作审计链；librosa 节拍检测脚本已就绪（`start_bpm=120`，70–150 倍频保护）。
- **母带链（定稿）**：渲染 → 解码 WAV → `loudnorm=I=-14:TP=-2:LRA=11` → AAC 320k（TP 目标留 2dB 余量吸收编码过冲）→ 实测 −14.2 LUFS/−1.1 dBTP。首次直接 MP4 上 loudnorm 曾因 AAC 过冲反复不收敛——**必须走 WAV 中转**。
- SFX 电平（调研惯例）：whoosh −9~−6dB 于 BGM、impact 瞬态 +3~+6dB、pop/ding −12~−9dB；impact 提前 0.18s 的 whoosh 引导。

## 4. v4 候选清单（按 观感收益÷成本 排序）

1. 冻结-爆发节奏（落点前定格 15–30f → count-up+震动+白闪齐发）
2. 百分比环分段（SVG dashoffset + 计数同步，`StatSchema` 加 `ring: true`）
3. odometer 数字滚轮（hero 大数）
4. 排名翻转赛跑图（`chart.type='race'`，逐帧插值）
5. `pushCut` 转场迁移 TransitionSeries（先解决绝对秒对齐：把音频事件也量化进同一网格）
6. 15s/30s/60s 时长档位变体（完播率数据支持 15–17s 优先）
7. 无缝循环结尾（末帧≈首帧，完播率放大器）
8. AI 片段模板的电影感：`@remotion/effects` lut()/glow() + `--gl=angle` 实测
