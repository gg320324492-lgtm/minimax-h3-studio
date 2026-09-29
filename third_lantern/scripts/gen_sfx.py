"""License-clean SFX for third_lantern《第三盏灯》: wind, water drip, wind
chime, scissors snip, candle light, door knock (x3), door creak, coin clink,
soft footsteps, river bed, rain (flashback), lantern paper flutter, dawn
birds. All synthesized with numpy/scipy.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
PROJECT = Path(r'E:/Minimax-H3/third_lantern')
OUT = PROJECT / '05_audio' / 'SFX'
RNG = np.random.default_rng(410924)
CFG = json.loads((PROJECT / '00_project' / 'story.json').read_text(encoding='utf-8'))
FPS = CFG['fps']
TITLECARD = CFG['titlecard_duration_s']
ORDER = list(CFG['shots'].keys())

bnd = {}
t = TITLECARD
for sid in ORDER:
    dur = CFG['shots'][sid]['length'] / FPS
    bnd[sid] = (t, t + dur)
    t += dur

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


def bp_noise(n, lo, hi, order=2):
    noise = RNG.standard_normal(n)
    b, a = signal.butter(order, [lo / (SR / 2), hi / (SR / 2)], btype='band')
    return signal.lfilter(b, a, noise)


# night wind bed: low gusty noise with slow LFO (loopable 20s)
def wind_bed():
    n = 20 * SR
    body = bp_noise(n, 60, 420)
    b2, a2 = signal.butter(2, 700 / (SR / 2), btype='low')
    body = signal.lfilter(b2, a2, body)
    lfo = 0.55 + 0.45 * (0.6 * np.sin(2 * np.pi * 0.07 * np.arange(n) / SR + 1.3)
                         + 0.4 * np.sin(2 * np.pi * 0.023 * np.arange(n) / SR))
    body *= lfo
    fade = int(0.3 * SR)
    body[:fade] *= np.linspace(0, 1, fade)
    body[-fade:] *= np.linspace(1, 0, fade)
    save('SFX_WIND_BED', body, 0.45)


# single water drip: short sine chirp down + tick
def drip():
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    f = 1400 * np.exp(-t * 6) + 300
    phase = 2 * np.pi * np.cumsum(f) / SR
    v = np.sin(phase) * np.exp(-t * 26)
    v += 0.4 * RNG.standard_normal(n) * np.exp(-t * 300)
    save('SFX_DRIP', v, 0.4)


# wind chime: 3-4 inharmonic bell partials, gentle
def chime():
    sig = np.zeros(int(3.0 * SR))
    for i, (f0, at, g) in enumerate([(1244, 0.0, .8), (1661, 0.35, .6),
                                     (2093, 0.75, .5), (1568, 1.15, .45)]):
        n = int(2.0 * SR)
        t = np.arange(n) / SR
        tone = (np.sin(2 * np.pi * f0 * t) + 0.4 * np.sin(2 * np.pi * f0 * 2.76 * t)
                + 0.2 * np.sin(2 * np.pi * f0 * 5.4 * t))
        tone *= np.exp(-t * 2.2) * np.minimum(1, t * 200)
        i0 = int(at * SR)
        end = min(len(sig), i0 + n)
        sig[i0:end] += tone[:end - i0] * g
    save('SFX_CHIME', sig, 0.3)


# scissors snip: two metallic clicks
def scissors():
    sig = np.zeros(int(0.5 * SR))
    for at in (0.0, 0.18):
        n = int(0.05 * SR)
        click = RNG.standard_normal(n) * np.exp(-np.arange(n) / SR * 700)
        b, a = signal.butter(2, [2500 / (SR / 2), 8000 / (SR / 2)], btype='band')
        click = signal.lfilter(b, a, click)
        i0 = int(at * SR)
        sig[i0:i0 + n] += click
    save('SFX_SCISSORS', sig, 0.42)


# candle/bamboo lantern catch flame: soft puff + crackle
def candle():
    n = int(1.2 * SR)
    t = np.arange(n) / SR
    puff = bp_noise(n, 500, 2200) * np.exp(-((t - 0.25) ** 2) / 0.012)
    crackle = np.zeros(n)
    for _ in range(14):
        p = int(RNG.uniform(0.25, 1.0) * SR)
        m = int(0.004 * SR)
        crackle[p:p + m] += RNG.standard_normal(m) * np.exp(-np.arange(m) / SR * 1500)
    save('SFX_CANDLE_LIT', puff * 0.8 + crackle * 0.5, 0.4)


# three soft knocks on old wood
def knock3():
    sig = np.zeros(int(2.4 * SR))
    for i, at in enumerate((0.0, 0.55, 1.25)):
        n = int(0.16 * SR)
        t = np.arange(n) / SR
        f = 150 * (1 - 0.25 * t)
        phase = 2 * np.pi * np.cumsum(f) / SR
        thump = np.sin(phase) * np.exp(-t * 34)
        thump += 0.5 * RNG.standard_normal(n) * np.exp(-t * 220)
        i0 = int(at * SR)
        sig[i0:i0 + n] += thump * (0.9 - 0.12 * i)
    save('SFX_KNOCK3', sig, 0.6)


# door creak (reuse idea from previous film, new voice)
def door_creak():
    n = int(1.8 * SR)
    t = np.arange(n) / SR
    f = 260 * (1 + 0.45 * np.sin(2 * np.pi * 2.6 * t)) * np.exp(-t * 0.4)
    phase = 2 * np.pi * np.cumsum(f) / SR
    v = np.sin(phase) * (0.65 + 0.35 * signal.square(2 * np.pi * 19 * t) * 0.3)
    v += 0.3 * RNG.standard_normal(n) * np.exp(-t * 1.0)
    v *= np.hanning(n) ** 0.5
    b, a = signal.butter(2, [160 / (SR / 2), 2400 / (SR / 2)], btype='band')
    save('SFX_DOOR_CREAK', signal.lfilter(b, a, v), 0.45)


# old copper coin clink on wood: metallic ring
def coin():
    sig = np.zeros(int(1.2 * SR))
    for at, f0, g in ((0.0, 2450, 1.0), (0.02, 3150, 0.7), (0.11, 2450, 0.35)):
        n = int(0.9 * SR)
        t = np.arange(n) / SR
        tone = (np.sin(2 * np.pi * f0 * t) + 0.5 * np.sin(2 * np.pi * f0 * 1.62 * t))
        tone *= np.exp(-t * 9) * np.minimum(1, t * 400)
        i0 = int(at * SR)
        sig[i0:i0 + n] += tone * g
    save('SFX_COIN', sig, 0.4)


# soft footsteps on wet stone: 4 muted thuds with tick
def steps():
    sig = np.zeros(int(3.2 * SR))
    for i, at in enumerate(np.arange(0.0, 2.8, 0.7)):
        n = int(0.22 * SR)
        t = np.arange(n) / SR
        thud = np.sin(2 * np.pi * 95 * t) * np.exp(-t * 30)
        tick = bp_noise(n, 900, 3200) * np.exp(-t * 160) * 0.4
        i0 = int(at * SR)
        sig[i0:i0 + n] += (thud + tick) * RNG.uniform(0.7, 1.0)
    save('SFX_STEPS_WET', sig, 0.4)


# river bed: broad water noise, loopable 20s
def river_bed():
    n = 20 * SR
    body = bp_noise(n, 110, 1200)
    b2, a2 = signal.butter(2, 1500 / (SR / 2), btype='low')
    body = signal.lfilter(b2, a2, body)
    lfo = 0.8 + 0.2 * np.sin(2 * np.pi * 0.11 * np.arange(n) / SR + 0.7)
    body *= lfo
    fade = int(0.3 * SR)
    body[:fade] *= np.linspace(0, 1, fade)
    body[-fade:] *= np.linspace(1, 0, fade)
    save('SFX_RIVER_BED', body, 0.4)


# rain bed (flashback): hissier than v1 rain, loopable 20s
def rain_bed():
    n = 20 * SR
    body = bp_noise(n, 350, 3200)
    tb2, ta2 = signal.butter(2, 3600 / (SR / 2), btype='low')
    body = signal.lfilter(tb2, ta2, body)
    ticks = np.zeros(n)
    for _ in range(300):
        p = int(RNG.integers(0, n - 400))
        d = RNG.standard_normal(int(0.005 * SR)) * np.exp(-np.arange(int(0.005 * SR)) / SR * 1100)
        ticks[p:p + len(d)] += d * RNG.uniform(0.15, 0.6)
    tb, ta = signal.butter(2, [1800 / (SR / 2), 5200 / (SR / 2)], btype='band')
    ticks = signal.lfilter(tb, ta, ticks)
    sig = body * 0.75 + ticks * 0.3
    fade = int(0.25 * SR)
    sig[:fade] *= np.linspace(0, 1, fade)
    sig[-fade:] *= np.linspace(1, 0, fade)
    save('SFX_RAIN_BED', sig, 0.5)


# lantern paper flutter
def paper():
    n = int(1.4 * SR)
    t = np.arange(n) / SR
    v = bp_noise(n, 800, 4200) * (0.4 + 0.6 * np.abs(np.sin(2 * np.pi * 1.7 * t))) * np.hanning(n)
    save('SFX_PAPER_FLUTTER', v, 0.3)


# dawn birds (reuse style)
def birds():
    n = int(4.0 * SR)
    sig = np.zeros(n)
    for _ in range(6):
        start = int(RNG.uniform(0.2, 3.2) * SR)
        m = int(RNG.uniform(0.12, 0.28) * SR)
        t = np.arange(m) / SR
        f0 = RNG.uniform(2400, 3900)
        sweep = f0 * (1 + 0.3 * np.sin(2 * np.pi * RNG.uniform(6, 12) * t))
        chirp = np.sin(2 * np.pi * np.cumsum(sweep) / SR) * np.hanning(m) * RNG.uniform(0.35, 0.8)
        end = min(n, start + m)
        sig[start:end] += chirp[:end - start]
    save('SFX_BIRDS', sig, 0.26)


wind_bed()
drip()
chime()
scissors()
candle()
knock3()
door_creak()
coin()
steps()
river_bed()
rain_bed()
paper()
birds()

hints = {
    'wind_start': 0.0,
    'chime_S01': round(bnd['S01'][0] + 2.0, 3),
    'drip_S01': round(bnd['S01'][0] + 4.5, 3),
    'scissors_S02': round(bnd['S02'][0] + 1.2, 3),
    'candle_S02': round(bnd['S02'][0] + 4.0, 3),
    'door_S04': round(bnd['S04'][0] + 0.5, 3),
    'knock3_S06': round(bnd['S06'][0] + 4.2, 3),
    'door_S07': round(bnd['S07'][0] + 0.4, 3),
    'coin_S08': round(bnd['S08'][0] + 1.2, 3),
    'candle_S09': round(bnd['S09'][0] + 3.0, 3),
    'steps_S10': round(bnd['S10'][0] + 1.0, 3),
    'paper_S11': round(bnd['S11'][0] + 2.0, 3),
    'rain_S12': round(bnd['S12'][0], 3),
    'drip_S12': round(bnd['S12'][0] + 6.2, 3),
    'river_S13': round(bnd['S13'][0], 3),
    'paper_S14': round(bnd['S14'][0] + 4.0, 3),
    'river_S15': round(bnd['S15'][0], 3),
    'birds_S16': round(bnd['S16'][0] + 2.0, 3),
    'paper_S17': round(bnd['S17'][0] + 1.5, 3),
}
(PROJECT / '00_project' / 'sfx_times.json').write_text(
    json.dumps(hints, indent=2), encoding='utf-8')
print('hints written')
