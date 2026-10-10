# 《让水体重新呼吸》第二版

完整成片为 3 分 18 秒，1920×1080，30 fps。制作使用本仓库的 Remotion 合成层，新增独立入口，不替换原有项目与模板。

追加节奏加快版：整体提速 8%，时长约 3 分 3 秒。画面、配乐、旁白与字幕同步提速，声音保持音高；保留完整内容及片尾呼吁。单独输出到桌面“第二版成片/节奏加快版”。在原版导出完成后运行 `water_renewal/scripts/pace_version.py` 可复现。

Studio 的 `WaterRenewal` 展示最新加快版交付文件；`WaterRenewalEdit` 与单章预览保留可编辑的原始制作层。导出脚本先渲染制作层，再由加快版脚本统一调整节奏，确保预览、交付及字幕一致。

## 剪辑结构

| 时间 | 内容 |
|---|---|
| 00:00–00:24 | 一条河的期待：真实河道、问题与治理动机 |
| 00:24–00:49 | 从问题到方案：共同研判、调试与装备布设 |
| 00:49–01:26 | 气泡技术：微观示意、清理、管线与现场运行 |
| 01:26–02:12 | 生态浮岛：运输、模块组装、植物准备、协作入水与生态作用 |
| 02:12–02:38 | 持续检验：底泥界面、现场观察与维护 |
| 02:38–03:18 | 从气泡、绿植与实干的人，递进到家园、未来与持续行动 |

## 本版升级

- 重写全部 16 段旁白，音色沿用第一版的 Kokoro-82M `zm_yunyang` 男声，通过朗读节奏、停顿与配乐递进加强结尾力量。
- 新生成两段纪录片管弦配乐，后段逐渐进入更饱满的旋律，旁白出现时自动降低配乐。
- 保留第一版干净的两段 H3 原理动画，明确显示“原理示意 · 非现场实拍”。
- 第二批生态浮岛素材成为完整章节，新增植物根系与微生物作用动画。
- 单独设计高清封面，并将完整封面用于视频开头 3 秒，第一帧即可作为缩略图。
- 旁白字幕逐句对齐，使用 43 px 字号、深色衬底与重点词强调；章节标题、重点句与现场标注分层设计。
- 照片增加平滑推近，现场视频重新取段，竖拍素材使用独立构图。
- 镜头之间增加约 0.7 秒柔和叠化，章节切换约 0.9 秒，标题同步缓入缓出。
- 终版保持真实现场性质，片尾“水清岸绿”明确作为愿景表达。
- 最后一句旁白、字幕与尾卡统一采用呼吁：“让我们一起，共建人与自然和谐共生的美好家园！”

## 文件与复跑

- `00_project/editorial.json`：旁白、排程与时长。
- `00_project/voice_manifest.json`：实际音频长度。
- `00_project/captions.json`：与实际语音对齐的字幕。
- `05_audio/`：旁白、原创生成配乐、混音与响度检测。
- `07_edit/`：成片中间导出与画面验收。
- `studio/src/water-renewal/`：六个可单独预览的章节与完整成片。

运行环境沿用本机工作室。制作步骤：

```powershell
& 'E:/ComfyUI/venv/Scripts/python.exe' water_renewal/scripts/prepare_media.py
& 'E:/Minimax-H3/liaozhai_demo/acestep-env/Scripts/python.exe' water_renewal/scripts/generate_music.py
& 'E:/ComfyUI/venv/Scripts/python.exe' water_renewal/scripts/generate_voice_original.py
& 'E:/ComfyUI/venv/Scripts/python.exe' water_renewal/scripts/finish_audio.py
```

在 `studio/` 目录运行：

```powershell
& 'C:/Program Files/nodejs/node.exe' node_modules/@remotion/cli/remotion-cli.js studio src/water-renewal/index.tsx --no-open --port=3108
& 'C:/Program Files/nodejs/node.exe' bin/render-water.mjs still
& 'C:/Program Files/nodejs/node.exe' bin/render-water.mjs render
```

来源：用户提供的第一、第二批素材；第一版对应的 `E:/promo_video/assets` 干净原理动画与真实河道环境声。旁白沿用第一版的本地 Kokoro-82M `zm_yunyang`；配乐使用本地 ACE-Step 1.5，新配乐的生成记录保存在 `05_audio/music/provenance.json`。
