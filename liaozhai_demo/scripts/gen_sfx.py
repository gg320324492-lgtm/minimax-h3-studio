"""License-clean SFX for liaozhai_demo: rain bed, thunder, door creak,
candle-light whoosh, head-turn sting, dawn birds. All synthesized.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
PROJECT = Path(r'E:/Minimax-H3/liaozhai_demo')
OUT = PROJECT / '05_audio' / 'SFX'
RNG = np.random.default_rng(20260924)
CFG = json.loads((PROJECT / '00_project' / 'story.json').read_text(encoding='utf-8'))
FPS = CFG['fps']
TITLECARD = CFG['titlecard_duration_s']
ORDER = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08', 'S09', 'S10']

bnd = {}
t = TITLECARD
for sid in ORDER:
    dur = CFG['shots'][sid]['length'] / FPS
    bnd[sid] = (t, t + dur)
    t += dur
print(f"S02 = {bnd['S02'][0]:.2f}, S07 = {bnd['S07'][0]:.2f}, S10 = {bnd['S10'][0]:.2f}")

OUT.mkdir(parents=True, exist_ok=True)


def save(name, sig, gain=0.5, sr=SR):
    peak = np.max(np.abs(sig)) or 1.0
    data = (sig / peak * gain * 32767).astype(np.int16)
    wav = OUT / f'{name}.wav'
    wavfile.write(str(wav), sr, data)
    m4a = OUT / f'{name}.m4a'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(wav),
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', str(m4a)], check=True)
    wav.unlink()
    print(f'  {m4a.name}')


# ---- rain bed: 20s loopable, band-passed noise + droplet ticks ----
def rain_bed():
    n = 20 * SR
    noise = RNG.standard_normal(n)
    b, a = signal.butter(2, [400 / (SR / 2), 3800 / (SR / 2)], btype='band')
    body = signal.lfilter(b, a, noise)
    lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.13 * np.arange(n) / SR + 1.0)
    body *= lfo
    ticks = np.zeros(n)
    for _ in range(240):
        p = int(RNG.integers(0, n - 400))
        d = RNG.standard_normal(int(0.006 * SR)) * np.exp(
            -np.arange(int(0.006 * SR)) / SR * 900)
        ticks[p:p + len(d)] += d * RNG.uniform(0.2, 0.8)
    tb, ta = signal.butter(2, [1800 / (SR / 2), 6800 / (SR / 2)], btype='band')
    ticks = signal.lfilter(tb, ta, ticks)
    sig = body * 0.75 + ticks * 0.5
    fade = int(0.25 * SR)
    sig[:fade] *= np.linspace(0, 1, fade)
    sig[-fade:] *= np.linspace(1, 0, fade)
    save('SFX_RAIN_BED', sig, 0.5)


# ---- thunder rumble ----
def thunder():
    n = int(3.2 * SR)
    t = np.arange(n) / SR
    noise = RNG.standard_normal(n)
    b, a = signal.butter(2, [50 / (SR / 2), 300 / (SR / 2)], btype='band')
    rum = signal.lfilter(b, a, noise)
    rum *= np.exp(-t * 1.4) * np.minimum(1, t * 22)
    crack_n = int(0.25 * SR)
    crack = RNG.standard_normal(crack_n) * np.exp(-np.arange(crack_n) / SR * 26)
    rum[:crack_n] += crack * 1.4
    save('SFX_THUNDER', rum, 0.85)


# ---- wooden door creak (slow pitch-bent tone + grain) ----
def door_creak():
    n = int(1.6 * SR)
    t = np.arange(n) / SR
    f = 320 * (1 + 0.5 * np.sin(2 * np.pi * 3.1 * t)) * np.exp(-t * 0.5)
    phase = 2 * np.pi * np.cumsum(f) / SR
    v = np.sin(phase) * (0.6 + 0.4 * signal.square(2 * np.pi * 22 * t) * 0.3)
    v += 0.35 * RNG.standard_normal(n) * np.exp(-t * 1.2)
    v *= np.hanning(n) ** 0.5
    b, a = signal.butter(2, [180 / (SR / 2), 2600 / (SR / 2)], btype='band')
    save('SFX_DOOR_CREAK', signal.lfilter(b, a, v), 0.5)


# ---- candle-light soft whoosh ----
def candle():
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    noise = RNG.standard_normal(n)
    b, a = signal.butter(2, [600 / (SR / 2), 2400 / (SR / 2)], btype='band')
    v = signal.lfilter(b, a, noise) * np.exp(-((t - 0.3) ** 2) / 0.02)
    save('SFX_CANDLE', v, 0.4)


# ---- head-turn sting: dissonant cluster shriek + sub ----
def sting():
    n = int(2.0 * SR)
    t = np.arange(n) / SR
    v = (np.sin(2 * np.pi * 622 * t * (1 + 0.006 * np.sin(2 * np.pi * 9 * t)))
         + np.sin(2 * np.pi * 660 * t)
         + 0.7 * np.sin(2 * np.pi * 932 * t * (1 - 0.004 * t)))
    vib = 1 + 0.02 * np.sin(2 * np.pi * 26 * t)
    v *= vib
    v *= np.exp(-t * 2.2) * np.minimum(1, t * 40)
    sub_n = int(0.8 * SR)
    sub = np.sin(2 * np.pi * 42 * np.arange(sub_n) / SR) * np.exp(-np.arange(sub_n) / SR * 5)
    v[:sub_n] += sub * 1.2
    save('SFX_STING', v, 0.8)


# ---- dawn birds: FM chirps ----
def birds():
    n = int(4.0 * SR)
    sig = np.zeros(n)
    for _ in range(7):
        start = int(RNG.uniform(0.2, 3.0) * SR)
        dur = RNG.uniform(0.12, 0.3)
        m = int(dur * SR)
        t = np.arange(m) / SR
        f0 = RNG.uniform(2200, 3800)
        sweep = f0 * (1 + 0.35 * np.sin(2 * np.pi * RNG.uniform(6, 14) * t))
        phase = 2 * np.pi * np.cumsum(sweep) / SR
        chirp = np.sin(phase) * np.hanning(m) * RNG.uniform(0.4, 0.9)
        end = min(n, start + m)
        sig[start:end] += chirp[:end - start]
    save('SFX_BIRDS', sig, 0.3)


rain_bed()
thunder()
door_creak()
candle()
sting()
birds()

# anchor-time hints for build_timeline (kept in one place)
hints = {
    'rain_start': 0.0,
    'thunder_S02': round(bnd['S02'][0] + 0.4, 3),
    'thunder_S08': round(bnd['S08'][0] + 0.6, 3),
    'door_S03': round(bnd['S03'][0] + 0.3, 3),
    'candle_S03': round(bnd['S03'][0] + 2.6, 3),
    'sting_S07': round(bnd['S07'][0] + 5.2, 3),
    'birds_S10': round(bnd['S10'][0] + 0.4, 3),
}
(PROJECT / '00_project' / 'sfx_times.json').write_text(
    json.dumps(hints, indent=2), encoding='utf-8')
print('hints:', hints)
