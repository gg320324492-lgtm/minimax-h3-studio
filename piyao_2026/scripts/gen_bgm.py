"""Procedural 3-phase PSA score for piyao_2026. License-clean (synthesized).

Sections are derived from shots.json so the music lands on the picture
boundaries (clip frame counts are deterministic, so this runs before the
timeline exists):

  S01-S03  hook & reveal      dark Dm drone, filtered, sparse low pulse
  S04-S06  spread             anxious tick pulse + soft kick enters
  S07-S11  fact-check         cooler/brighter pad, gentle arpeggio, no drums
  S12-end  warm resolve       F major lift, piano-like plucks, swell, fade

Run with the ComfyUI venv python (needs numpy+scipy).
"""
import json
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
PROJECT = Path(r'E:/Minimax-H3/piyao_2026')
RNG = np.random.default_rng(20260922)

CFG = json.loads((PROJECT / '00_project' / 'shots.json').read_text(encoding='utf-8'))
FPS = CFG['fps']
FREEZE = CFG.get('s02_freeze_extra_s', 2.0)
ENDCARD = CFG.get('endcard_duration_s', 4.5)

ORDER = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08',
         'S09', 'S10', 'S11', 'S12', 'S13', 'S14']

# ---- deterministic shot boundaries (mirrors build_timeline.py) ----
bnd = {}
t = 0.0
for sid in ORDER:
    dur = CFG['shots'][sid]['length'] / FPS + (FREEZE if sid == 'S02' else 0.0)
    bnd[sid] = (t, t + dur)
    t += dur
TOTAL = round(t + ENDCARD, 3)
N = int(SR * (TOTAL + 0.7))
tt = np.arange(N) / SR

S_P3 = bnd['S07'][0]        # rational section
S_P4 = bnd['S12'][0]        # warm section
S_END = TOTAL - ENDCARD     # end card
print(f'sections: tense 0-{bnd["S04"][0]:.2f}  spread->{S_P3:.2f}  '
      f'rational->{S_P4:.2f}  warm->{TOTAL:.2f}')

F = {n_: 440.0 * 2 ** ((i - 9) / 12) for i, n_ in enumerate(
    ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'])}


def freq(name):
    letter, octave = name[:-1], name[-1]
    if letter.endswith('b'):
        letter = {'B': 'A', 'E': 'D', 'A': 'G', 'D': 'C'}[letter[0]] + '#'
    return F[letter] * 2 ** (int(octave) - 4)


# (t0, dur, bass, pad notes)
CHORDS = [
    (0.0,                     bnd['S02'][0] - 0.0, 'D2',  ['D3', 'A3', 'D4']),
    (bnd['S02'][0],           bnd['S04'][0] - bnd['S02'][0], 'Bb1', ['Bb2', 'F3', 'Bb3', 'D4']),
    (bnd['S04'][0],           8.0,  'D2',  ['D3', 'F3', 'A3', 'D4']),
    (bnd['S05'][0],           8.0,  'Bb1', ['Bb2', 'D3', 'F3', 'Bb3']),
    (bnd['S06'][0],           bnd['S07'][0] - bnd['S06'][0], 'G1', ['G2', 'Bb2', 'D3', 'G3']),
    (bnd['S07'][0],           bnd['S08'][0] - bnd['S07'][0], 'A1', ['A2', 'C3', 'E3', 'A3']),
    (bnd['S08'][0],           bnd['S09'][0] - bnd['S08'][0], 'F2', ['F3', 'A3', 'C4']),
    (bnd['S09'][0],           bnd['S10'][0] - bnd['S09'][0], 'C2', ['C3', 'G3', 'C4', 'E4']),
    (bnd['S10'][0],           bnd['S11'][0] - bnd['S10'][0], 'A2', ['A2', 'C3', 'E3', 'A3']),
    (bnd['S11'][0],           bnd['S12'][0] - bnd['S11'][0], 'Bb2', ['Bb2', 'D3', 'F3', 'Bb3']),
    (bnd['S12'][0],           bnd['S13'][0] - bnd['S12'][0], 'F2', ['F3', 'A3', 'C4', 'F4']),
    (bnd['S13'][0],           bnd['S14'][0] - bnd['S13'][0], 'C3', ['C3', 'G3', 'C4', 'E4']),
    (bnd['S14'][0],           S_END - bnd['S14'][0], 'Bb2', ['Bb2', 'D3', 'F3', 'Bb3', 'D4']),
    (S_END,                   ENDCARD + 0.7, 'F2', ['F2', 'F3', 'A3', 'C4', 'F4']),
]


def env_ar(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na > 0:
        e[:na] = np.linspace(0, 1, na)
    if nr > 0:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def place(buf, sig, at):
    i = int(at * SR)
    j = min(N, i + len(sig))
    if i < N and j > i:
        buf[i:j] += sig[:j - i]


def spec_lp(x, cutoff):
    Xf = np.fft.rfft(x, axis=0)
    fr = np.fft.rfftfreq(x.shape[0], 1 / SR)
    g = 1.0 / (1.0 + (fr / cutoff) ** 2.2)
    return np.fft.irfft(Xf * g[:, None], n=x.shape[0], axis=0)


# ---------- pad ----------
DET = 0.0012
padL = np.zeros(N)
padR = np.zeros(N)
for (t0, dur, bass, notes) in CHORDS:
    n = int(dur * SR)
    if n <= 0:
        continue
    tseg = np.arange(n) / SR
    e = env_ar(n, min(1.6, dur * 0.3), min(2.4, dur * 0.4))
    warm = t0 >= S_P4 - 0.01
    for k, note in enumerate(notes):
        f0 = freq(note)
        lvl = 1.0 / (1 + 0.35 * k)
        for (det, pan) in ((1 - DET, 0.35), (1 + DET, 0.65)):
            ph = RNG.uniform(0, 2 * np.pi)
            v = np.sin(2 * np.pi * f0 * det * tseg + ph)
            if f0 < 700:
                v += 0.38 * np.sin(2 * np.pi * f0 * 2 * det * tseg + ph * 1.7)
            if warm:
                v += 0.16 * np.sin(2 * np.pi * f0 * 3 * det * tseg + ph * 2.3)
            v *= lvl * e
            vl = v * ((0.55 + pan) if pan < 0.5 else (0.45 + 0.2 * (1 - pan)))
            vr = v * ((0.45 + 0.2 * pan) if pan < 0.5 else (0.55 + (1 - pan)))
            place(padL, vl, t0)
            place(padR, vr, t0)
pad = np.stack([padL, padR], 1)

# piecewise spectral lowpass (tense -> cool -> warm/open)
pad_f = np.zeros_like(pad)
SEGS = [(0.0, bnd['S04'][0], 1300), (bnd['S04'][0], S_P4, 2400),
        (S_P4, TOTAL + 0.7, 3800)]
for (a, b, cut) in SEGS:
    i0, i1 = int(a * SR), min(N, int(b * SR))
    if i1 > i0:
        pad_f[i0:i1] = spec_lp(pad[i0:i1], cut)
# soften seams
for seam in (SEGS[0][1], SEGS[1][1]):
    i0 = max(0, int((seam - 1.0) * SR))
    i1 = min(N, int((seam + 1.0) * SR))
    w = np.linspace(0, 1, i1 - i0)[:, None]
    pad_f[i0:i1] = pad_f[i0:i1] * w + spec_lp(pad[i0:i1], 1300) * (1 - w)
pad_f *= 0.9

# ---------- sub drone ----------
sub = np.zeros(N)
for (t0, dur, bass, notes) in CHORDS:
    f0 = freq(bass)
    n = int(min(dur, TOTAL - t0) * SR)
    if n <= 0:
        continue
    tseg = np.arange(n) / SR
    v = (np.sin(2 * np.pi * f0 * tseg) + 0.5 * np.sin(2 * np.pi * f0 * 2 * tseg)) * env_ar(n, 0.8, 0.8)
    place(sub, v * 0.8, t0)
subL = sub * 0.5 + np.roll(sub, 220) * 0.5
subR = sub * 0.5 + np.roll(sub, 440) * 0.5

# ---------- low heartbeat pulse (S01-S03 only) ----------
heart = np.zeros(N)
hb = 0.0
while hb < bnd['S04'][0] - 1.0:
    n = int(0.5 * SR)
    tseg = np.arange(n) / SR
    fdrop = 82 * np.exp(-tseg * 18) + 44
    v = np.sin(2 * np.pi * np.cumsum(fdrop) / SR) * np.exp(-tseg * 11)
    lvl = 0.16 if hb < bnd['S02'][0] else 0.22
    place(heart, v * lvl, hb)
    place(heart, v * lvl * 0.6, hb + 0.28)
    hb += 2.4

# ---------- anxious tick + soft kick (spread section) ----------
pluck = np.zeros(N)
kick = np.zeros(N)
BEAT = 0.62
sec = bnd['S04'][0]
while sec < S_P3 - 0.05:
    cur = CHORDS[0]
    for ch in CHORDS:
        if ch[0] <= sec + 1e-9:
            cur = ch
    f0 = freq(cur[3][0]) * 2
    n = int(0.4 * SR)
    tseg = np.arange(n) / SR
    v = (np.sin(2 * np.pi * f0 * tseg) + 0.3 * np.sin(2 * np.pi * f0 * 2 * tseg)) * np.exp(-tseg * 10)
    place(pluck, v * 0.11, sec)
    n = int(0.28 * SR)
    tseg = np.arange(n) / SR
    fdrop = 100 * np.exp(-tseg * 22) + 46
    kv = np.sin(2 * np.pi * np.cumsum(fdrop) / SR) * np.exp(-tseg * 14)
    place(kick, kv * 0.24, sec)
    sec += BEAT * 2

# ---------- cool arpeggio (rational section, 8ths, higher) ----------
arp = np.zeros(N)
sec = S_P3
step = BEAT / 2
idx = 0
while sec < S_P4 - 0.05:
    cur = CHORDS[0]
    for ch in CHORDS:
        if ch[0] <= sec + 1e-9:
            cur = ch
    note = cur[3][idx % len(cur[3])]
    f0 = freq(note) * 2
    n = int(0.35 * SR)
    tseg = np.arange(n) / SR
    v = (np.sin(2 * np.pi * f0 * tseg) + 0.25 * np.sin(2 * np.pi * f0 * 2 * tseg)) * np.exp(-tseg * 12)
    place(arp, v * 0.075, sec)
    idx += 1
    sec += step

# ---------- warm piano-ish plucks (S12 -> end) ----------
piano = np.zeros(N)
for (t0, dur, bass, notes) in CHORDS:
    if t0 < S_P4 - 0.01:
        continue
    for j, note in enumerate(notes[1:]):
        f0 = freq(note) * 2
        n = int(1.8 * SR)
        tseg = np.arange(n) / SR
        v = (np.sin(2 * np.pi * f0 * tseg) + 0.4 * np.sin(2 * np.pi * f0 * 2 * tseg)
             + 0.15 * np.sin(2 * np.pi * f0 * 3.01 * tseg)) * np.exp(-tseg * 3.2)
        place(piano, v * (0.10 - 0.015 * j), t0 + 0.12 * j)

# ---------- risers: into S03 reveal and into S12 warm turn ----------
def riser(a, b, lvl):
    n = int((b - a) * SR)
    noise = RNG.standard_normal(n)
    bb, aa = signal.butter(2, 900 / (SR / 2), btype='low')
    noise = signal.lfilter(bb, aa, noise)
    sw = np.linspace(0, 1, n) ** 2.4
    out = np.zeros(N)
    i0 = int(a * SR)
    out[i0:i0 + n] += noise * sw * lvl
    return out


ris = riser(bnd['S03'][0] - 2.2, bnd['S03'][0] + 0.3, 0.10)
ris += riser(S_P4 - 2.5, S_P4 + 0.4, 0.12)

# ---------- intensity envelope ----------
xs = [0, bnd['S02'][0], bnd['S02'][1], bnd['S04'][0], bnd['S07'][0], bnd['S11'][0],
      bnd['S12'][0], bnd['S12'][0] + 2, S_END - 1, S_END, TOTAL - 1.0, TOTAL]
ys = [0.52, 0.60, 0.66, 0.72, 0.60, 0.66,
      0.55, 0.88, 0.88, 0.80, 0.62, 0.30]
gain = np.interp(tt, xs, ys)
k = np.hanning(int(2.5 * SR))
k /= k.sum()
gb = np.stack([np.convolve(gain, k, 'same')] * 2, 1)
pad_f *= gb
subL *= gb[:, 0]
subR *= gb[:, 1]
heart *= gain ** 0.5
pluck *= gain ** 0.5
kick *= gain ** 0.5
arp *= np.interp(tt, xs, ys) ** 0.5
piano *= gain ** 0.5

# ---------- mix ----------
mixL = pad_f[:, 0] + subL + heart + pluck + kick * 0.9 + arp + piano + ris
mixR = pad_f[:, 1] + subR + heart + pluck + kick * 0.9 + arp + piano + ris
mix = np.stack([mixL, mixR], 1)

fade_in = int(1.2 * SR)
mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
# fade must land on zero BEFORE the video ends at TOTAL (the mix trims at
# TOTAL; a fade window past the end gets chopped mid-level and clicks)
i0 = int((TOTAL - 2.5) * SR)
i1 = int((TOTAL - 0.2) * SR)
mix[i0:i1] *= np.linspace(1, 0, i1 - i0)[:, None] ** 1.3
mix[i1:] = 0.0

peak = np.max(np.abs(mix))
mix *= (0.5 / peak)
wavfile.write(str(PROJECT / '05_audio' / 'BGM' / 'BGM_PIYAO.wav'), SR,
              (mix * 32767).astype(np.int16))
print(f'BGM written: {TOTAL + 0.7:.1f}s, peak {float(peak):.3f} -> 0.5')
