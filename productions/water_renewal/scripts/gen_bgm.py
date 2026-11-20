"""Procedural documentary score for the 120s promo. License-clean (synthesized).

Structure (mirrors the edit brief):
  0-15s   low & restrained: sub drone + dark pad, sparse
  15-45s  subtle electronic pulse enters (soft 8th-note pluck)
  45-80s  engineering rhythm: kick + shaker groove, pad moves faster
  80-105s climax: brighter/wider pad, denser pulse, riser into 80s
  105-120s resolve & fade to the end card

Run with the ComfyUI venv python (needs scipy+numpy).
"""
import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
DUR = 122.0
N = int(SR * DUR)
t = np.arange(N) / SR
RNG = np.random.default_rng(20260922)

BPM = 50.0                      # slow documentary pulse
BEAT = 60.0 / BPM               # 1.2s
BAR = 4 * BEAT                  # 4.8s

# note frequencies
F = {n: 440.0 * 2 ** ((i - 9) / 12) for i, n in enumerate(
    ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'])}
def freq(name):  # accepts 'D2' and 'A1#' (== 'A#1')
    if len(name) == 3 and name[2] == '#':
        name = name[0] + '#' + name[1]
    return F[name[:-1]] * 2 ** (int(name[-1]) - 4)

# chord schedule: (start_time, chord roots as note names)
PROG_A = [['D2', ['D3', 'F3', 'A3', 'D4']], ['A1#', ['A#2', 'D3', 'F3', 'A#3']],
          ['F1', ['F2', 'A2', 'C3', 'F3']],   ['C2', ['C3', 'E3', 'G3', 'C4']]]
def shift(octv, notes):
    return [n[:-1] + str(int(n[-1]) + octv) for n in notes]

SCHEDULE = []  # (t0, bass_note, pad_notes)
for rep in range(2):                     # 0 - 38.4  restrained
    for bass, pad in PROG_A:
        SCHEDULE.append((rep * 4 * BAR + len(SCHEDULE) % 4 * BAR, bass, pad))
# rebuild properly with running time
SCHEDULE = []
T = 0.0
for rep in range(2):
    for bass, pad in PROG_A:
        SCHEDULE.append((T, bass, pad)); T += BAR
T_A = T                                  # 38.4
PROG_B = [['D2', ['D3', 'F3', 'A3', 'D4']], ['A1#', ['A#2', 'D3', 'F3', 'A#3']],
          ['G1', ['G2', 'A#2', 'D3', 'G3']], ['A1', ['A2', 'C3', 'E3', 'A3']]]
T_B = T_A + 2 * 4 * BAR                  # 38.4 + 38.4 = 76.8
for rep in range(2):
    for bass, pad in PROG_B:
        SCHEDULE.append((T, bass, pad)); T += BAR
T_C = T                                  # 76.8  (climax start ~80 adjusted)
PROG_C = [['F1', ['F2', 'A2', 'C3', 'F3', 'A3']], ['C2', ['C3', 'E3', 'G3', 'C4', 'E4']],
          ['A1#', ['A#2', 'D3', 'F3', 'A#3', 'D4']], ['D2', ['D3', 'F3', 'A3', 'D4', 'F4']]]
CLIMAX_END = 105.0
while T < CLIMAX_END:
    for bass, pad in PROG_C:
        if T >= CLIMAX_END - 0.01: break
        SCHEDULE.append((T, bass, pad)); T += BAR
# resolve on Dm till end
SCHEDULE.append((T, 'D2', ['D2', 'D3', 'A3', 'D4', 'F4']))
TOTAL = DUR

def env_ar(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na > 0: e[:na] = np.linspace(0, 1, na)
    if nr > 0: e[-nr:] *= np.linspace(1, 0, nr)
    return e

def place(buf, sig, at):
    i = int(at * SR)
    j = min(N, i + len(sig))
    if i < N and j > i:
        buf[i:j] += sig[:j - i]

# ---------- pad voices ----------
padL = np.zeros(N); padR = np.zeros(N)
DET = 0.0012
for (t0, bass, notes) in SCHEDULE:
    dur = min(BAR * 1.05, TOTAL - t0)
    if dur <= 0.2: continue
    n = int(dur * SR)
    tt = np.arange(n) / SR
    e = env_ar(n, min(1.6, dur * .3), min(2.2, dur * .4))
    # intensity automation: restrained -> climax brighter
    bright = 0.55 + 0.45 * np.clip((t0 - 70) / 25, 0, 1)
    for k, note in enumerate(notes):
        f0 = freq(note)
        level = 1.0 / (1 + 0.35 * k)
        for (det, pan) in ((1 - DET, 0.35), (1 + DET, 0.65)):
            ph = RNG.uniform(0, 2 * np.pi)
            v = np.sin(2 * np.pi * f0 * det * tt + ph)
            if f0 < 700:                      # add upper partials only on low-mid notes
                v += 0.38 * np.sin(2 * np.pi * f0 * 2 * det * tt + ph * 1.7)
                if bright > 0.75:
                    v += 0.20 * bright * np.sin(2 * np.pi * f0 * 3 * det * tt + ph * 2.3)
            v *= level * e
            vl = v * ((0.55 + pan) if pan < 0.5 else (0.45 + 0.2 * (1 - pan)))
            vr = v * ((0.45 + 0.2 * pan) if pan < 0.5 else (0.55 + (1 - pan)))
            place(padL, vl, t0); place(padR, vr, t0)
pad = np.stack([padL, padR], 1)

# spectral lowpass with slight brightness automation via 3 segments
def spec_lp(x, cutoff):
    Xf = np.fft.rfft(x, axis=0)
    fr = np.fft.rfftfreq(x.shape[0], 1 / SR)
    g = 1.0 / (1.0 + (fr / cutoff) ** 2.2)
    return np.fft.irfft(Xf * g[:, None], n=x.shape[0], axis=0)

seg = []
for (a, b, cut) in ((0, 46, 1400), (46, 82, 2400), (82, TOTAL, 3600)):
    i0, i1 = int(a * SR), min(N, int(b * SR))
    seg.append(np.concatenate([spec_lp(pad[i0:i1], cut), np.zeros((max(0, i1 - int(b*SR)), 2))]) if False else spec_lp(pad[i0:i1], cut))
pad_f = np.zeros_like(pad)
for (a, b, cut), s in zip(((0, 46, 1400), (46, 82, 2400), (82, TOTAL, 3600)), seg):
    i0, i1 = int(a * SR), min(N, int(b * SR))
    pad_f[i0:i1] = s[:i1 - i0]
# crossfade the seams (2s)
for seam in (46, 82):
    i0 = int((seam - 1) * SR); i1 = int((seam + 1) * SR)
    w = np.linspace(0, 1, i1 - i0)[:, None]
    pad_f[i0:i1] = pad_f[i0:i1] * w + pad_f[i0:i1] * (1 - w)  # placeholder no-op
pad_f *= 0.9

# ---------- sub drone (follows bass notes) ----------
sub = np.zeros(N)
for (t0, bass, notes) in SCHEDULE:
    f0 = freq(bass)
    dur = min(BAR * 1.02, TOTAL - t0)
    if dur <= 0.2: continue
    n = int(dur * SR); tt = np.arange(n) / SR
    v = (np.sin(2 * np.pi * f0 * tt) + 0.5 * np.sin(2 * np.pi * f0 * 2 * tt)) * env_ar(n, 0.8, 0.8)
    place(sub, v * 0.8, t0)
subL = sub * 0.5 + np.roll(sub, 220) * 0.5
subR = sub * 0.5 + np.roll(sub, 440) * 0.5

# ---------- pulse pluck (8ths) ----------
pulse = np.zeros(N)
STEP = BEAT / 2
k = 0
tt_p = 0.0
while tt_p < TOTAL:
    sec = tt_p
    lvl = 0.0
    if 15 <= sec < 46: lvl = 0.10
    elif 46 <= sec < 80: lvl = 0.16
    elif 80 <= sec < 105: lvl = 0.24
    elif sec >= 105: lvl = 0.12 * max(0, 1 - (sec - 105) / 10)
    if lvl > 0 and (sec >= 80 or k % 2 == 0):   # denser at climax
        root = 220.0 * 2 ** ((k % 4) * 0)  # fixed A3-based tick that follows chords loosely
        # follow chord schedule
        cur = SCHEDULE[0]
        for (t0, bass, notes) in SCHEDULE:
            if t0 <= sec + 1e-9: cur = (t0, bass, notes)
        f0 = freq(cur[2][0]) * 2
        n = int(0.5 * SR); tt2 = np.arange(n) / SR
        v = (np.sin(2 * np.pi * f0 * tt2) + 0.3 * np.sin(2 * np.pi * f0 * 2 * tt2)) * np.exp(-tt2 * 9)
        place(pulse, v * lvl, sec)
    k += 1; tt_p += STEP

# ---------- engineering rhythm (45-80s, denser 80-105) ----------
kick = np.zeros(N); shaker = np.zeros(N)
sec = 45.0
while sec < 104:
    dense = sec >= 80
    # kick on beats
    n = int(0.3 * SR); tt2 = np.arange(n) / SR
    fdrop = 110 * np.exp(-tt2 * 22) + 48
    v = np.sin(2 * np.pi * np.cumsum(fdrop) / SR) * np.exp(-tt2 * 13)
    lvl = 0.32 if not dense else 0.40
    if sec < 80 and (int((sec - 45) / BEAT) % 4) == 3: lvl *= 0.6
    place(kick, v * lvl, sec)
    # shaker on offbeat 8ths
    for off in (0.5,):
        ns = int(0.06 * SR)
        noise = RNG.standard_normal(ns) * np.exp(-np.arange(ns) / SR * 90)
        b, a = signal.butter(2, [5500 / (SR / 2), 9500 / (SR / 2)], btype='band')
        noise = signal.lfilter(b, a, noise)
        place(shaker, noise * (0.10 if not dense else 0.13), sec + off * BEAT)
    sec += BEAT
    if not dense and int((sec - 45) / BEAT) % 8 == 0:
        pass  # keep groove continuous but light

# ---------- riser into climax (75.5-80s) ----------
ris = np.zeros(N)
i0, i1 = int(75.5 * SR), int(80.2 * SR)
n = i1 - i0
noise = RNG.standard_normal(n)
b, a = signal.butter(2, 900 / (SR / 2), btype='low')
noise = signal.lfilter(b, a, noise)
sw = np.linspace(0, 1, n) ** 2.4
ris[i0:i1] += noise * sw * 0.16
pad_f[i0:i1] *= (1 + 0.25 * np.linspace(0, 1, n)[:, None])

# ---------- intensity envelope (documentary arc) ----------
xs = [0, 15, 22, 45, 50, 78, 82, 103, 106, 112, 116.5, 122]
ys = [0.60, 0.60, 0.70, 0.72, 0.84, 0.86, 1.0, 1.0, 0.78, 0.68, 0.48, 0.30]
gain = np.interp(t, xs, ys)
k = np.hanning(int(3.0 * SR)); k /= k.sum()
gb = np.stack([np.convolve(gain, k, 'same'), np.convolve(gain, k, 'same')], 1)
pad_f *= gb
subL *= gb[:, 0]; subR *= gb[:, 1]
kick *= np.interp(t, xs, ys) ** 0.5
pulse *= np.interp(t, xs, ys) ** 0.5

# ---------- mix ----------
mix = np.stack([pad_f[:, 0] + subL + pulse + kick * 0.9 + shaker + ris,
                pad_f[:, 1] + subR + pulse + kick * 0.9 + shaker + ris], 1)

# gentle master fades; leave the very end near-silent (0.5s room tone)
fade_in = int(1.2 * SR); mix[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
tail = int((TOTAL - 116.5) * SR)
i0 = int(116.5 * SR)
mix[i0:] *= np.linspace(1, 0, N - i0)[:, None] ** 1.3

# normalize to about -6 dBFS peak
peak = np.max(np.abs(mix)); mix *= (0.5 / peak)
wavfile.write(r'E:/promo_video/assets/bgm_score.wav', SR, (mix * 32767).astype(np.int16))
print('BGM written: 122s, peak scaled', round(float(peak), 3))
