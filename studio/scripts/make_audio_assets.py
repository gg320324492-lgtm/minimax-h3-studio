"""Synthesize the studio's license-free audio assets: beat-exact BGM + SFX kit.

Why synthesized: foreign SFX/BGM sites are unreachable from this machine, and a
generated track has its beat grid known EXACTLY by construction (no beat detection
error) — ideal for 卡点-rendered video. Everything is deterministic numpy → wav,
then compressed to m4a via the bundled ffmpeg.

Outputs (under studio/public/audio/):
  bgm_tech_126.m4a      32s tech bed @126 BPM (kick/hat/bass/pumping pad, 4-bar intro→build→full→outro)
  sfx_whoosh.m4a  sfx_impact.m4a  sfx_pop.m4a  sfx_ding.m4a  sfx_riser.m4a
  bgm_beats.json        exact beat grid {bpm, beat_interval, beats:[{t,bass}]} for the renderer

Run: E:/ComfyUI/venv/Scripts/python.exe studio/scripts/make_audio_assets.py
"""

from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r'E:\Minimax-H3')
sys.path.insert(0, str(ROOT))
from ffmpeg_env import FFMPEG  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / 'public' / 'audio'
SR = 48000
BPM = 126.0
BEAT = 60.0 / BPM            # 0.47619s
BARS = 16                     # 16 bars * 4 beats = 64 beats ≈ 30.5s
TOTAL = BARS * 4 * BEAT


def env_exp(n: int, decay: float) -> np.ndarray:
    t = np.arange(n) / SR
    return np.exp(-t * decay)


def sine(freq: float, n: int, phase: float = 0.0) -> np.ndarray:
    return np.sin(2 * np.pi * freq * np.arange(n) / SR + phase)


def sweep(f0: float, f1: float, n: int, curve: float = 1.0) -> np.ndarray:
    t = np.arange(n) / SR
    k = (t / t[-1]) ** curve
    f = f0 + (f1 - f0) * k
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def lowpass(x: np.ndarray, alpha: float) -> np.ndarray:
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += alpha * (v - acc)
        y[i] = acc
    return y


def place(buf: np.ndarray, x: np.ndarray, at_s: float, gain: float = 1.0) -> None:
    i0 = int(at_s * SR)
    i1 = min(i0 + len(x), len(buf))
    if i1 > i0:
        buf[i0:i1] += x[: i1 - i0] * gain


def kick() -> np.ndarray:
    n = int(0.14 * SR)
    body = sweep(160, 45, n, curve=0.4) * env_exp(n, 28)
    click = np.random.default_rng(7).standard_normal(int(0.004 * SR)) * 0.4
    out = body.copy()
    out[: len(click)] += click
    return out * 0.9


def hat(open_: bool = False) -> np.ndarray:
    dur = 0.09 if open_ else 0.035
    n = int(dur * SR)
    noise = np.random.default_rng(11).standard_normal(n)
    # 简易高通：信号减去低通
    hp = noise - lowpass(noise, 0.35)
    return hp * env_exp(n, 55 if open_ else 90) * 0.16


def bass_note(freq: float, n: int, gate: float = 1.0) -> np.ndarray:
    x = sine(freq, n) + 0.35 * sine(freq * 2, n) + 0.15 * sine(freq * 0.5, n)
    a = int(0.004 * SR)
    env = np.ones(n)
    env[:a] = np.linspace(0, 1, a)
    env *= np.exp(-np.arange(n) / SR * 3.5)
    return x * env * gate * 0.32


def pad_chord(freqs: list[float], n: int) -> np.ndarray:
    out = np.zeros(n)
    for f in freqs:
        out += sine(f, n, phase=np.random.default_rng(int(f)).uniform(0, 6.28))
        out += 0.4 * sine(f * 1.005, n)
    a = int(0.25 * SR)
    r = int(0.25 * SR)
    env = np.ones(n)
    env[:a] = np.linspace(0, 1, a)
    env[-r:] *= np.linspace(1, 0.6, r)
    return lowpass(out, 0.06) * env * 0.05


def build_bgm() -> tuple[np.ndarray, list[dict]]:
    total_n = int(TOTAL * SR) + SR  # +1s tail for decay
    buf = np.zeros(total_n)
    A1, C2, G1, E2 = 55.0, 65.41, 49.0, 82.41
    chord_prog = [[A1, 110.0, 164.81], [A1, 110.0, 164.81], [C2, 130.81, 196.0], [G1, 98.0, 146.83]]
    kick_snd, hat_snd, hat_open = kick(), hat(False), hat(True)

    beats_meta = []
    for bar in range(BARS):
        bar_t = bar * 4 * BEAT
        section = 'intro' if bar < 2 else ('build' if bar < 6 else ('full' if bar < 14 else 'out'))
        # pad per bar (和弦进行)
        ch = chord_prog[bar % 4]
        place(buf, pad_chord(ch, int(4 * BEAT * SR)), bar_t,
              0.8 if section in ('intro', 'out') else 0.5)
        for b in range(4):
            t = bar_t + b * BEAT
            beat_idx = bar * 4 + b
            # kick 每拍（intro/out 弱一点）
            g = 0.7 if section in ('intro', 'out') else 1.0
            place(buf, kick_snd, t, g)
            # hat 反拍（build 起）
            if section in ('build', 'full'):
                place(buf, hat_snd, t + BEAT / 2, 1.0)
                if b == 3:
                    place(buf, hat_open, t + BEAT / 2, 1.4)
            # bass 十六分 Push（full 段最密）
            if section == 'full':
                f = ch[0]
                for k, gate in ((0.0, 1.0), (0.5, 0.5), (0.75, 0.7)):
                    place(buf, bass_note(f, int(0.2 * SR), gate), t + k * BEAT)
            elif section == 'build':
                place(buf, bass_note(ch[0], int(0.3 * SR)), t)
            # 记录拍网格（含 kicker 能量近似：intro/out 弱拍）
            beats_meta.append({'t': round(t, 3), 'bass': round(g if b % 1 == 0 else 0.5, 2),
                               'bar': bar, 'section': section})
    # final impact tail
    place(buf, kick() * 1.2, TOTAL - 0.05, 1.0)

    # master: soft clip + fade out + normalize
    buf = np.tanh(buf * 1.25)
    fade = int(1.5 * SR)
    buf[-fade:] *= np.linspace(1, 0, fade)
    buf = buf[: int(TOTAL * SR) + int(0.6 * SR)]
    peak = np.abs(buf).max()
    buf = buf / peak * (10 ** (-14 / 20))  # ≈ -14 dBFS peak 余量
    stereo = np.stack([buf, buf], axis=1)
    return stereo, buf.copy(), beats_meta


def sfx_bank() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(42)
    bank: dict[str, np.ndarray] = {}
    # whoosh：噪声带通扫频 + 汉宁窗
    n = int(0.55 * SR)
    noise = rng.standard_normal(n)
    whoosh = lowpass(noise, 0.12) - lowpass(noise, 0.02)
    w = np.hanning(n) ** 1.5
    bank['whoosh'] = whoosh * w * 0.9
    # impact：低频 thud + 噪声 click
    n = int(0.6 * SR)
    thud = sweep(180, 38, n, curve=0.35) * env_exp(n, 12)
    click = rng.standard_normal(int(0.01 * SR)) * 0.5
    imp = thud * 0.95
    imp[: len(click)] += click
    bank['impact'] = imp
    # pop：超短 click + 下滑 blip
    n = int(0.09 * SR)
    blip = sweep(900, 320, n) * env_exp(n, 60)
    pop = np.zeros(n)
    c = rng.standard_normal(int(0.003 * SR)) * 0.6
    pop[: len(c)] += c
    pop += blip * 0.8
    bank['pop'] = pop * 0.9
    # ding：双正弦泛音
    n = int(0.5 * SR)
    ding = (sine(1760, n) + 0.5 * sine(2637, n) + 0.25 * sine(3520, n)) * env_exp(n, 9)
    bank['ding'] = ding * 0.55
    # riser：噪声 + 上扫正弦，1.2s 渐强
    n = int(1.2 * SR)
    rise_sine = sweep(200, 1300, n, curve=2.0) * np.linspace(0.15, 1, n) ** 2
    rise_noise = lowpass(rng.standard_normal(n), 0.25) * np.linspace(0, 1, n) ** 2
    bank['riser'] = (rise_sine * 0.5 + rise_noise * 0.35) * 0.8
    return bank


def to_m4a(wav_path: Path) -> Path:
    out = wav_path.with_suffix('.m4a')
    subprocess.run([FFMPEG, '-y', '-v', 'error', '-i', str(wav_path),
                    '-c:a', 'aac', '-b:a', '192k', str(out)], check=True)
    wav_path.unlink()
    return out


def write_wav(path: Path, stereo: np.ndarray) -> Path:
    import wave
    data = (np.clip(stereo, -1, 1) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())
    return path


def pump_envelope(mono: np.ndarray, fps: int = 24) -> dict:
    """Per-frame bass energy (20-150 Hz STFT magnitude, normalized 0-1) at video fps.

    Replaces runtime visualizeAudio in the template (Phase 5.5 measured it doubled
    render time): the renderer just indexes this array by frame.
    """
    n_fft = 2048
    hop = SR // fps
    win = np.hanning(n_fft)
    freqs = np.fft.rfftfreq(n_fft, 1 / SR)
    band = (freqs >= 20) & (freqs <= 150)
    vals = []
    for i in range(0, max(len(mono) - n_fft, 1), hop):
        spec = np.abs(np.fft.rfft(mono[i:i + n_fft] * win))
        vals.append(float(spec[band].mean()))
    v = np.array(vals)
    v = v / max(v.max(), 1e-9)
    k = 3
    v = np.convolve(v, np.ones(k) / k, mode='same')
    return {'fps': fps, 'values': [round(float(x), 4) for x in v]}


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    bgm, mono_master, beats = build_bgm()
    outputs: dict[str, Path] = {}
    p = write_wav(OUT_DIR / '_bgm.wav', bgm)
    outputs['bgm_tech_126'] = to_m4a(p)
    for name, x in sfx_bank().items():
        stereo = np.stack([x, x], axis=1)
        p = write_wav(OUT_DIR / f'_{name}.wav', stereo)
        outputs[f'sfx_{name}'] = to_m4a(p)

    env = pump_envelope(mono_master)
    (OUT_DIR / 'pump_envelope.json').write_text(json.dumps(env), encoding='utf-8')
    print(f'pump envelope: {len(env["values"])} frames @ {env["fps"]}fps')

    grid = {
        'bpm': BPM,
        'beat_interval': round(BEAT, 5),
        'total_bars': BARS,
        'beats': beats,
    }
    (OUT_DIR / 'bgm_beats.json').write_text(json.dumps(grid, indent=1), encoding='utf-8')

    for k, v in outputs.items():
        print(f'{k}: {v.name} {v.stat().st_size // 1024}KB')
    print(f'beat grid: {len(beats)} beats, {BPM} BPM, beat={BEAT:.4f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
