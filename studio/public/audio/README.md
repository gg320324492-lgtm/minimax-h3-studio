# 音频资产投放口（替换合成素材的规范）

> **公开仓库说明**：Mixkit 许可不允许原始音频文件的独立再分发，因此 4 个 Mixkit
> 派生文件（`bgm_main.m4a`、`sfx_whoosh/impact/coin.m4a`）**只在本地、不入库**。
> 仓库内自带的是合成兜底版（`bgm_synth_126.m4a` + `make_audio_assets.py`）与
> CC0 的 Kenney 音效。新克隆机器：跑一遍 `make_audio_assets.py` 或按本 README
> 自行获取授权素材，再执行 `import_real_assets.py` 完成替换。

`studio/scripts/make_audio_assets.py` 合成的 BGM/音效是**无网络的兜底方案**，听感有天花板。
拿到更好的真实素材时，按下面的规范替换（渲染端不用改代码，只换文件）：

## 目录约定

```
studio/public/audio/
├── bgm_tech_126.m4a     # 主 BGM（report 模板默认引用）
├── pump_envelope.json   # 低频呼吸包络（必须与 BGM 重新生成）
├── bgm_beats.json       # 拍网格（126 BPM，卡点量化的依据）
└── sfx_*.m4a            # whoosh / impact / pop / ding / riser
```

## 替换 BGM 的步骤

1. 放入新文件（保持文件名，或改后同步改 report props 的 `narration.src`）。
2. **重新生成拍网格与包络**（真实音乐的拍点需要检测，推荐 librosa）：

```bash
E:/ComfyUI/venv/Scripts/python.exe -c "import librosa" 2>/dev/null || \
  E:/ComfyUI/venv/Scripts/python.exe -m pip install librosa
```

参考实现（Phase 5 调研验证的配方）：`librosa.beat.beat_track(units='time', start_bpm=120)`，
70–150 BPM 倍频保护；低频包络 = 20–150Hz 频段 STFT 幅值按视频帧降采样归一化。
输出与 `pump_envelope.json` 同构（`{fps, values[]}`），`bgm_beats.json` 同构（`{bpm, beats:[{t,bass}]}`）。
**注意**：换 BGM 后把 report props 的 `bpm` 改成新曲实测 BPM，卡点量化才会对齐。

3. 响度交给 `master_audio.py` 母带链（目标 −14 LUFS / TP −1.5），素材本身不必预制响度。

## 替换音效

同名覆盖 `sfx_*.m4a` 即可。电平参考（Phase 5 调研惯例，模板音量已按此设定）：
whoosh −9~−6dB、impact 瞬态 +3~+6dB、pop/ding −12~−9dB（相对 BGM 底）。

## 许可审计

引入任何外部素材时，在本目录追加 `manifest.json`，每个文件记录：
`{"file": ..., "source_url": ..., "license": ..., "download_date": ...}`。
许可白名单：CC0 > Pixabay Content License / Mixkit Free License（免署名可商用）>
CC-BY（需在视频描述署名）。**禁入**：CC-BY-NC、爱给网未标"免费商用"的条目。
