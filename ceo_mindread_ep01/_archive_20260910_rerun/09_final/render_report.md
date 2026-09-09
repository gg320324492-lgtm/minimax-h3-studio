# 《总裁突然听见实习生的心声》EP01 - Final Render Report (v3 FixAll)

**Generated**: 2026-09-03 03:24:10

## Final Output
| Item | Value |
|------|-------|
| Duration | 60.58s |
| Resolution | 1080 x 1920 |
| Codec | H.264 High / yuv420p |
| FPS | 24/1 |
| Audio | AAC 48000Hz 2ch 320kbps |
| Loudness | -14 LUFS (loudnorm) |
| Bitrate | 4.93 Mbps |
| File Size | 35.6 MB |

## Pipeline
- 生成: MiniMax-H3 Ref2VA (int8_convrot) + 4-step turbo LoRA, 768x1344 @24fps
- 一致性: R2V MASTER_REFERENCE (<Picture 1/2/3>)
- 超分: Real-ESRGAN_x2plus fp16 tile=512 (pipe_4k_fast.py) -> Lanczos 1080x1920
- TTS: Kokoro-82M 本地 (CEO=zm_yunyang, INTERN=zf_xiaoxiao; 心声 lowpass 4k)
- 混音: mix_audio_v4.py - timeline驱动, BGM sidechain ducking, loudnorm -14 LUFS, 立体声
- 字幕: burn_subtitles_v2.py - timeline驱动, 自动换行(<=1000px)
- 总 takes: 12 (生成时实时记录 seed, 见 seed_manifest.json)

## Shots
| Shot | Take | Frames | Duration | Seed |
|------|------|--------|----------|------|
| S01 | 01 | 124 | 5.17s | 12001 |
| S02 | 01 | 141 | 5.88s | 13001 |
| S03A | 01 | 56 | 2.33s | 14001 |
| S03B | 01 | 56 | 2.33s | 14101 |
| S03C | 01 | 56 | 2.33s | 14201 |
| S04 | 01 | 192 | 8.00s | 15001 |
| S05A | 01 | 22 | 0.92s | - |
| S05B | 01 | 192 | 8.00s | 16001 |
| S06 | 01 | 226 | 9.42s | 17001 |
| S07 | 01 | 192 | 8.00s | 18001 |
| S08 | 01 | 141 | 5.88s | 19001 |
| S09 | 01 | 56 | 2.33s | 20001 |
