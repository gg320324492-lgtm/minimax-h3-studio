# piyao_2026 Final QA Report

**Video**: 它只是换了一个地名_参赛版_1080P.mp4  
**Checks**: 17/17 PASS

| Check | Result | Detail |
|-------|--------|--------|
| resolution 1920x1080 | PASS | 1920x1080 |
| video codec h264 | PASS | h264 |
| pix_fmt yuv420p | PASS | yuv420p |
| fps 24 | PASS | 24/1 |
| audio aac 48k stereo | PASS | aac/48000/2ch |
| duration 100-115s | PASS | 109.30s |
| audio covers video (within 0.15s) | PASS | 109.30s / 109.30s |
| integrated -15..-13 LUFS | PASS | -13.8 LUFS |
| true peak <= -1 dBTP | PASS | -2.0 dBTP |
| all subtitle blocks fit 1920px | PASS | widest "第二步，查地点。画面里的建筑、天..." = 1674px |
| no narration overlap | PASS | clean |
| nothing exceeds video end | PASS | clean |
| all shots have recorded seeds | PASS | complete |
| recorded lengths match config | PASS | consistent |
| AI label present (corner) | PASS | corner disclaimer found |
| AI label present (end card) | PASS | end-card AI label found |
| dramatization disclaimer | PASS | found |