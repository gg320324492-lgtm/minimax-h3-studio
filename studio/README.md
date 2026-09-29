# minimax-studio — Remotion 合成层

MiniMax-H3 视频工作室的程序化合成层。三层架构中的"合成渲染层"：
GPU 生成层（ComfyUI+H3，Python 侧）产出片段 → 本层按 timeline 契约装配出成片。

## 快速上手

```bash
# 依赖（node_modules 会被 pnpm 清掉浏览器缓存，装完必须跑 ensure）
pnpm install && npx remotion browser ensure

# 实时预览（Studio，改代码即时热更）
pnpm dev

# 渲染（模板 × props）
node bin/render.mjs --comp ReportVertical --props public/jobs/report_demo/props_meta.json --out out/demo.mp4

# 出单帧（封面/检查）
npx remotion still CoverCard --props=<cover.json> --output=cover.png
```

## 模板注册表（Root.tsx）

| Composition | 规格 | 输入 |
|---|---|---|
| `DramaVertical` | 1080×1920@24 | timeline_v2.json（AI 片段+字幕+混音） |
| `PsaWide` | 1920×1080@24 | 同上 |
| `StoryAnimation` | 2560×1440@24 | 同上 + titlecard/endcard |
| `ReportVertical` | 1080×1920@24 | report-data.json（纯数据，零 GPU） |
| `CoverCard` | still | cover props（背景帧+标题+角标） |

## 铁律（详见仓库根 REMOTION_MOTION_UPGRADE / BENCHMARK 文档）

1. **改 `src/schemas/*.ts` 后必须 `pnpm exec tsx bin/export-schema.ts`**，Python 侧按导出的 JSON Schema 校验。
2. 渲染参数定稿：x264 crf18 + jpeg + `colorSpace:'bt709'`（缺它输出 yuvj420p 挂 QA）+ 并发 16——`bin/render.mjs` 已内置，别绕过。
3. Node API 不读 remotion.config.ts；渲染参数必须显式传。
4. 中文渲染字体走 `public/fonts/` 自托管（FontFace+delayRender），数字用 Bahnschrift（Windows 自带）。
5. 音频母带：`scripts/master_audio.py`（WAV 中转 loudnorm，−14 LUFS），直接 MP4 上 loudnorm 不收敛。
6. 契约自检：`E:/ComfyUI/venv/Scripts/python.exe scripts/check_contract.py`。

## 脚本

| 脚本 | 用途 |
|---|---|
| `bin/render.mjs` | Node API 渲染桥（bundle 缓存/编码参数/色空间） |
| `bin/export-schema.ts` | zod → JSON Schema 导出（双端契约） |
| `scripts/emit_props.py` | 任意项目 timeline v1 → v2 props + 硬链接 staging |
| `scripts/word_timestamps.py` | 词级卡拉OK时间戳注入（faster-whisper，ASR 词面只当对齐标尺） |
| `scripts/make_audio_assets.py` | 合成 BGM/SFX/拍网格/呼吸包络（126 BPM，免版权） |
| `scripts/master_audio.py` | 音频母带（−14 LUFS 自动收敛） |
| `scripts/qa_report.py` | report 成片 QA 门禁（10 项） |
| `scripts/check_contract.py` | 契约同步自检 |

## 许可

Remotion License（个人/≤3 人公司免费）。5.0 起渲染需传 `licenseKey: "free-license"`。
