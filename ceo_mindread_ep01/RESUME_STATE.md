# FixAll v3 执行状态（重启后恢复用）

**更新时间**: 2026-09-02 22:45 左右（重启前）

## 已完成
- [x] P0 环境准备（重启后需要再次启动 ComfyUI）
- [x] P1 响度+立体声修复 ✅ 已验证：-14.3 LUFS / -1.6 dBTP / stereo 48kHz
  - 脚本: `scripts/mix_audio_v4.py`（timeline 驱动 + loudnorm + sidechain ducking + asplit 修复）
- [x] P3 代码全部写好：
  - `scripts/build_timeline.py`（校验器已验证，能正确抓 S06 溢出）
  - `scripts/burn_subtitles_v2.py`（自动换行 <=1000px）
  - `scripts/qa_final.py`（自动化 QA）
  - `scripts/finalize.py` 已更新（真 seed manifest、封面改进、桌面同步）
  - `scripts/gen_reference_sheets.py`（P6 定妆 16 张）
- [x] P5 目录清理：日志/测试文件归档，02_keyframes 已落帧，旧脚本进 `_archive/`
- [x] P5 音频改名：S01 对白归位 INTERN/（dialogue.json 已同步）
- [x] dialogue.json 重写（timeline 驱动的 placement 格式）
- [x] `03_video_raw_v2_archive/` 存有旧镜头备份；S05A（咖啡杯 22 帧）保留在原位

## 重启后待做（按序）
1. 启动 ComfyUI（桌面 Start-ComfyUI.bat 或 `cd /e/ComfyUI && venv/Scripts/python.exe main.py --listen 0.0.0.0 --port 8188 --disable-smart-memory --bf16-vae`）
2. **验证显存干净**: `nvidia-smi --query-gpu=memory.used --format=csv,noheader` 应 < 2GB
3. 后台跑 P2: `cd /e/Minimax-H3/ceo_mindread_ep01 && nohup bash -c '"E:/ComfyUI/venv/Scripts/python.exe" scripts/gen_keyframes_v3.py all 2>&1' > logs/gen_v3_all.log 2>&1 &`
   - 12 takes（S01=124, S02=141, S03A/B/C=56x3, S04=192, S05B=192, S06=226x2, S07=192, S08=141, S09=56）
   - 预计 2~2.5h；seed 会实时写入 00_project/seed_manifest.json
   - 注意：重启后第一次跑 init 恢复正常（~25s），单镜 5~10 分钟
4. P2 完成后:
   - `python scripts/select_takes.py`（S06 如需指定 T02: `python scripts/select_takes.py S06_T02`）
   - `python scripts/build_timeline.py`（必须 0 warning 通过）
   - `E:/Minimax-H3/pipe_4k_fast.py 07_edit/EP01_PICTURE_LOCK_720P.mp4 07_edit/EP01_UPSCALED_1440p.mp4`（约 25 min）
   - ffmpeg Lanczos -> 07_edit/EP01_PICTURE_MASTER_1080P.mp4
   - `python scripts/mix_audio_v4.py`
   - `python scripts/burn_subtitles_v2.py`
   - `python scripts/finalize.py`（自动同步桌面 MiniMax-H3-Outputs）
   - `python scripts/qa_final.py`（全 PASS 才算完成）
5. P6 定妆（GPU 空闲窗口）: `python scripts/gen_reference_sheets.py all`（约 25 min）

## 关键路径
- 项目: `E:\Minimax-H3\ceo_mindread_ep01\`
- 交付: `C:\Users\pc\Desktop\MiniMax-H3-Outputs\EP01_CEO_Mindread\09_final\`
- 计划文件: `C:\Users\pc\.claude\plans\sharded-scribbling-nygaard.md`
