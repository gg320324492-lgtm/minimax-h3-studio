"""Procedural 3-phase 志怪悬疑 score for liaozhai_demo《灯下无影》. License-clean.

Palette: low D drone + Karplus-Strong plucked pentatonic (guzheng-ish) +
heartbeat pulse for the tension phase + one dissonant-adjacent swell at the
S07 head-turn, resolving to an open fifth at dawn.

Boundaries mirror build_timeline.py exactly (titlecard + frame counts +
endcard), so this can run before the timeline exists.
"""
import json
from pathlib import Path

import numpy as np
from scipy.io import wavfile

SR = 48000
PROJECT = Path(r'E:/Minimax-H3/liaozhai_demo')
RNG = np.random.default_rng(20260924)

CFG = json.loads((PROJECT / '00_project' / 'story.json').read_text(encoding='utf-8'))
FPS = CFG['fps']
TITLECARD = CFG['titlecard_duration_s']
ENDCARD = CFG['endcard_duration_s']
ORDER = ['S01', 'S02', 'S03', 'S04', 'S05', 'S06', 'S07', 'S08', 'S09', 'S10']

# ---- deterministic shot boundaries (mirrors build_timeline.py) ----
bnd = {}
t = TITLECARD
for sid in ORDER:
    dur = CFG['shots'][sid]['length'] / FPS
    bnd[sid] = (t, t + dur)
    t += dur
TOTAL = round(t + ENDCARD, 3)
T_TENSE = bnd['S04'][0]      # the 娘子 appears -> tension palette
T_TURN = bnd['S07'][0] + 5.0  # head-turn moment -> sting swell
T_DAWN = bnd['S08'][0]       # flight -> dawn palette
print(f'sections: journey 0-{T_TENSE:.2f}  tense->{T_DAWN:.2f}  '
      f'dawn->{TOTAL:.2f}  (turn sting @{T_TURN:.2f})')

N = int(SR * (TOTAL + 0.7))
tt = np.arange(N) / SR
mixL = np.zeros(N)

NOTE = {n_: 440.0 * 2 ** ((i - 9) / 12) for i, n_ in enumerate(
    ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'])}


def freq(name):
    letter, octave = name[:-1], name[-1]
    return NOTE[letter] * 2 ** (int(octave) - 4)


def add(sig, at, gain=1.0):
    i0 = int(at * SR)
    i1 = min(N, i0 + len(sig))
    if i1 > i0:
        mixL[i0:i1] += sig[:i1 - i0] * gain


def pluck(f0, dur, bright=0.5, decay=4.0):
    """Karplus-Strong plucked string - guzheng/pipan flavour."""
    n = int(dur * SR)
    period = max(2, int(SR / f0))
    buf = RNG.uniform(-1, 1, period)
    blend = 0.5 - 0.28 * bright
    out = np.empty(n)
    for i in range(n):
        j = i % period
        out[i] = buf[j]
        buf[j] = blend * (buf[j] + buf[(j + 1) % period]) * 0.5
    out *= np.exp(-np.arange(n) / SR * decay)
    return out * 0.9


def drone(f0, dur, detune=0.4, lfo=0.08):
    n = int(dur * SR)
    t = np.arange(n) / SR
    swell = 0.75 + 0.25 * np.sin(2 * np.pi * lfo * t + RNG.uniform(0, 6))
    v = (np.sin(2 * np.pi * f0 * t)
         + 0.5 * np.sin(2 * np.pi * (f0 * 2 + detune) * t)
         + 0.25 * np.sin(2 * np.pi * (f0 * 3 - detune) * t))
    v *= swell * np.exp(-t * 0.05) * np.minimum(1, t * 4) * np.minimum(1, (dur - t) * 2)
    return v


# ---- phase palettes ----
# journey (title + S01-S03): low D drone + sparse dark plucks
add(drone(freq('D2'), T_TENSE + 1.0), 0, 0.30)
for at, note, g in [(4.0, 'D3', .30), (9.5, 'A2', .26), (15.0, 'F3', .24),
                    (19.5, 'D3', .26)]:
    add(pluck(freq(note), 3.5, bright=0.35, decay=2.2), at, g)

# tense (S04-S07): darker drone + D minor pentatonic plucks + heartbeat
add(drone(freq('D2') * 0.5, T_DAWN - T_TENSE + 1.0, detune=0.9), T_TENSE, 0.34)
pent = ['D3', 'F3', 'G3', 'A3', 'C4']
at = T_TENSE + 0.8
k = 0
while at < T_TURN - 0.8:
    note = pent[int(RNG.integers(0, len(pent)))]
    add(pluck(freq(note), 2.2, bright=0.55, decay=3.2), at, 0.20 + 0.05 * (k % 2))
    at += float(RNG.uniform(0.9, 1.7))
    k += 1

# heartbeat: enters mid-S06, accelerates into the turn
hb_start = bnd['S06'][0] + 3.0
beat = 0.95
tt_ = hb_start
while tt_ < T_TURN - 0.1:
    n = int(0.12 * SR)
    thump = np.sin(2 * np.pi * 55 * np.arange(n) / SR) * np.exp(-np.arange(n) / SR * 38)
    add(thump, tt_, 0.55)
    add(thump * 0.7, tt_ + 0.22, 0.45)
    tt_ += beat
    beat = max(0.55, beat - 0.035)

# the turn: dissonant swell + sub drop (mixed low; the dedicated SFX sting
# carries the accent, this is the musical body of it)
sw_n = int(2.6 * SR)
swt = np.arange(sw_n) / SR
swell = (np.sin(2 * np.pi * freq('D#3') * swt) + np.sin(2 * np.pi * freq('A3') * swt)
         + 0.6 * np.sin(2 * np.pi * freq('D4') * swt))
swell *= np.exp(-swt * 1.8) * np.minimum(1, swt * 8)
add(swell, T_TURN - 1.6, 0.30)
sub_n = int(1.4 * SR)
subt = np.arange(sub_n) / SR
sub = np.sin(2 * np.pi * 40 * subt * (1 - subt * 0.35)) * np.exp(-subt * 3.2)
add(sub, T_TURN - 0.1, 0.6)

# dawn (S08-end): lift to open fifth, warmer plucks, long fade
add(drone(freq('D3'), TOTAL - T_DAWN, detune=0.2), T_DAWN, 0.22)
add(drone(freq('A2'), TOTAL - T_DAWN), T_DAWN + 0.5, 0.18)
for i, (at, note, g) in enumerate([(T_DAWN + 1.2, 'D4', .20),
                                   (T_DAWN + 3.4, 'C4', .16),
                                   (T_DAWN + 5.6, 'A3', .16),
                                   (T_DAWN + 8.0, 'D4', .13)]):
    if at < TOTAL - 2:
        add(pluck(freq(note), 4.0, bright=0.3, decay=1.6), at, g)

# global fades: 0.4s in, 2.5s out
mixL[:int(0.4 * SR)] *= np.linspace(0, 1, int(0.4 * SR))
tail = int(2.5 * SR)
mixL[-tail:] *= np.linspace(1, 0, tail)

peak = np.max(np.abs(mixL)) or 1.0
data = (mixL / peak * 0.82 * 32767).astype(np.int16)
out = PROJECT / '05_audio' / 'BGM'
out.mkdir(parents=True, exist_ok=True)
wavfile.write(str(out / 'BGM_LIAOZHAI.wav'), SR, data.reshape(-1, 1))
print(f'written: {out / "BGM_LIAOZHAI.wav"}  {TOTAL:.2f}s')
