"""Synthesize license-clean SFX + copy reusable EP01 SFX into the project.

Synthesized: message ping (double chime), short ping, UI click, end ding.
Reused from ceo_mindread_ep01 (same author, synthesized): low pulse,
reverse whoosh, impact.
"""
import shutil
import subprocess
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000
PROJECT = Path(r'E:/Minimax-H3/piyao_2026')
OUT = PROJECT / '05_audio' / 'SFX'
EP_SFX = Path(r'E:/Minimax-H3/ceo_mindread_ep01/05_audio/SFX')
RNG = np.random.default_rng(20260922)


def env_ar(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na > 0:
        e[:na] = np.linspace(0, 1, na)
    if nr > 0:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def save(name, sig, gain=0.5):
    peak = np.max(np.abs(sig)) or 1.0
    data = (sig / peak * gain * 32767).astype(np.int16)
    wav = OUT / f'{name}.wav'
    wavfile.write(str(wav), SR, data)
    m4a = OUT / f'{name}.m4a'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(wav),
                    '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', str(m4a)], check=True)
    wav.unlink()
    print(f'  {m4a.name}')


def tone(f0, dur, decay=6.0, partial2=0.3):
    n = int(dur * SR)
    t = np.arange(n) / SR
    v = np.sin(2 * np.pi * f0 * t) + partial2 * np.sin(2 * np.pi * f0 * 2.01 * t)
    return v * np.exp(-t * decay)


def msg_ping():
    a = tone(880.0, 0.45, decay=8)
    b = tone(1174.66, 0.7, decay=5)
    sig = np.zeros(int(1.0 * SR))
    sig[:len(a)] += a
    off = int(0.16 * SR)
    sig[off:off + len(b)] += b * 0.9
    save('SFX_MSG_PING', sig, 0.5)


def msg_ping_short():
    sig = tone(987.77, 0.35, decay=10)
    save('SFX_MSG_PING_SHORT', sig, 0.42)


def ui_click():
    n = int(0.09 * SR)
    noise = RNG.standard_normal(n) * np.exp(-np.arange(n) / SR * 160)
    b, a = signal.butter(2, [2400 / (SR / 2), 5200 / (SR / 2)], btype='band')
    save('SFX_UI_CLICK', signal.lfilter(b, a, noise), 0.35)


def end_ding():
    a = tone(523.25, 2.2, decay=1.8, partial2=0.15)   # C5
    b = tone(659.25, 2.2, decay=1.6, partial2=0.12)   # E5
    c = tone(783.99, 2.4, decay=1.4, partial2=0.10)   # G5
    sig = a * 0.6 + b * 0.45 + np.zeros(len(a))
    sig[:min(len(c), len(sig))] += c[:len(sig)] * 0.35
    save('SFX_END_DING', sig, 0.4)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print('synthesizing:')
    msg_ping()
    msg_ping_short()
    ui_click()
    end_ding()
    print('copying from EP01:')
    for name in ('SFX_LOW_PULSE.m4a', 'SFX_REVERSE_WHOOSH.m4a', 'SFX_IMPACT.m4a'):
        shutil.copy2(EP_SFX / name, OUT / name)
        print(f'  {name}')


if __name__ == '__main__':
    main()
