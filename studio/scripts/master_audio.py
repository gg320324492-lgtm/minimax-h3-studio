"""Master a rendered MP4's audio to broadcast spec (Phase 6.1).

Chain (WAV intermediate — loudnorm directly on MP4+AAC is non-convergent because
AAC re-encode overshoot on transients keeps moving true peaks; the WAV hop plus a
2 dB TP headroom in the loudnorm target absorbs it):
  decode → loudnorm I=<target> TP=<target-12> LRA=11 → AAC 320k remux (video copied)
  → measure → up to 2 corrective gain/limit rounds until I ∈ [target-1, target+1]
    and TP ≤ -0.5 dBTP.

Usage:
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/master_audio.py <video.mp4> [--target -14]
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')
sys.path.insert(0, str(ROOT))
from ffmpeg_env import FFMPEG  # noqa: E402


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True)


def measure(mp4: Path) -> tuple[float, float]:
    """Return (integrated_lufs, true_peak_dbtp) via loudnorm's JSON print."""
    r = run([FFMPEG, '-hide_banner', '-i', mp4, '-af', 'loudnorm=print_format=json', '-f', 'null', '-'])
    blocks = re.findall(r'\{[^{}]*"input_i"[^{}]*\}', r.stderr)
    if not blocks:
        raise RuntimeError(f'loudnorm JSON not found in stderr:\n{r.stderr[-2000:]}')
    d = json.loads(blocks[-1])
    return float(d['input_i']), float(d['input_tp'])


def decode_wav(mp4: Path, out_wav: Path) -> None:
    r = run([FFMPEG, '-y', '-v', 'error', '-i', mp4, '-vn', '-ac', '2', '-ar', '48000', '-c:a', 'pcm_s16le', out_wav])
    if r.returncode:
        raise RuntimeError(f'decode failed: {r.stderr[-500:]}')


def remux(wav: Path, video: Path, out: Path) -> None:
    r = run([FFMPEG, '-y', '-v', 'error', '-i', wav, '-i', video,
             '-map', '1:v:0', '-map', '0:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k', out])
    if r.returncode:
        raise RuntimeError(f'remux failed: {r.stderr[-500:]}')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('video', type=Path)
    ap.add_argument('--target', type=float, default=-14.0, help='integrated LUFS target')
    ap.add_argument('--tp-target', type=float, default=-2.0, help='loudnorm TP target (headroom for AAC overshoot)')
    args = ap.parse_args()
    video: Path = args.video.resolve()
    if not video.exists():
        print(f'not found: {video}', file=sys.stderr)
        return 1
    tgt_i = args.target
    tgt_tp = args.tp_target

    tmp = Path(tempfile.mkdtemp(prefix='master_'))
    wav_a, wav_b = tmp / 'a.wav', tmp / 'b.wav'

    decode_wav(video, wav_a)
    r = run([FFMPEG, '-y', '-v', 'error', '-i', wav_a,
             '-af', f'loudnorm=I={tgt_i}:TP={tgt_tp}:LRA=11', '-ar', '48000', '-c:a', 'pcm_s16le', wav_b])
    if r.returncode:
        raise RuntimeError(f'loudnorm failed: {r.stderr[-500:]}')

    out_tmp = tmp / 'out.mp4'
    remux(wav_b, video, out_tmp)
    i_lufs, tp = measure(out_tmp)
    print(f'pass1: {i_lufs:.1f} LUFS / {tp:.1f} dBTP')

    iters = 0
    cur_wav = wav_b
    while (i_lufs < tgt_i - 1.0 or i_lufs > tgt_i + 1.0 or tp > -0.5) and iters < 2:
        gain = max(-3.0, min(3.0, tgt_i - i_lufs))
        dst = tmp / f'g{iters}.wav'  # 每轮独立文件名（ffmpeg 拒绝输入输出同路径）
        if tp > -1.0:
            r2 = run([FFMPEG, '-y', '-v', 'error', '-i', cur_wav,
                      '-af', f'alimiter=limit=0.8:level=false,volume={gain}dB,alimiter=limit=0.85:level=false',
                      '-c:a', 'pcm_s16le', dst])
        else:
            r2 = run([FFMPEG, '-y', '-v', 'error', '-i', cur_wav,
                      '-af', f'volume={gain}dB,alimiter=limit=0.85:level=false',
                      '-c:a', 'pcm_s16le', dst])
        if r2.returncode:
            raise RuntimeError(f'gain pass failed: {r2.stderr[-500:]}')
        cur_wav = dst
        remux(cur_wav, video, out_tmp)
        i_lufs, tp = measure(out_tmp)
        print(f'correct {iters + 1}: {i_lufs:.1f} LUFS / {tp:.1f} dBTP (gain {gain:+.1f}dB)')
        iters += 1

    bak = video.with_suffix('.mp4.bak')
    video.rename(bak)
    try:
        shutil.move(str(out_tmp), str(video))
    except OSError:
        bak.rename(video)  # 失败则还原
        raise
    bak.unlink()
    ok = (tgt_i - 1.5 <= i_lufs <= tgt_i + 1.5) and tp <= -0.5
    print(f"MASTERED: {i_lufs:.1f} LUFS / {tp:.1f} dBTP -> {'OK' if ok else 'STILL OUT OF RANGE'} ({video})")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
