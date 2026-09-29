"""Import real BGM/SFX assets into the studio audio library (Phase 6 asset channel).

Replaces the synthesized fallbacks with licensed real recordings:
  - BGM: librosa beat grid (bpm/beats/bass) + per-frame pump envelope + peak-normalized m4a
  - SFX: peak-normalized to -6 dBFS each (relative levels are set template-side)
  - manifest.json: license audit trail (source URL + license + download date)

All files stay under studio/public/audio/; synth originals keep their *_synth names.
Optionally patches a props JSON: narration.src/pumpEnvelope + project bpm.

Usage:
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/import_real_assets.py \
      --bgm /tmp/mixtrack_Digital_Clouds.mp3 \
      --sfx whoosh=/tmp/mixkit_1492.mp3 impact=/tmp/mixkit_1143.mp3 \
            coin=/tmp/mixkit_216.mp3 pop=/tmp/kenney/Audio/click_001.ogg \
            ding=/tmp/kenney/Audio/confirmation_001.ogg \
      [--props studio/public/jobs/report_demo/props_meta.json]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import warnings
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(r'E:\Minimax-H3')
sys.path.insert(0, str(ROOT))
from ffmpeg_env import FFMPEG  # noqa: E402

OUT = ROOT / 'studio' / 'public' / 'audio'
SR_ANALYSIS = 22050
FPS = 24

MANIFEST_ENTRIES = [
    ('bgm_main', 'Mixkit "Digital Clouds" (mixkit.co/free-stock-music/tag/technology)', 'Mixkit Stock Music Free License', 'no attribution; no standalone redistribution'),
    ('sfx_whoosh', 'Mixkit #1492 "Cinematic whoosh fast transition"', 'Mixkit Sound Effects Free License', 'no attribution'),
    ('sfx_impact', 'Mixkit #1143 "Cinematic whoosh deep impact"', 'Mixkit Sound Effects Free License', 'no attribution'),
    ('sfx_coin', 'Mixkit #216 "Arcade game jump coin"', 'Mixkit Sound Effects Free License', 'no attribution'),
    ('sfx_pop', 'Kenney Interface Sounds click_001 (kenney.nl)', 'CC0', 'no restrictions'),
    ('sfx_ding', 'Kenney Interface Sounds confirmation_001 (kenney.nl)', 'CC0', 'no restrictions'),
    ('sfx_riser', 'synthesized (make_audio_assets.py) — kept, no real riser imported', 'studio-original', '-'),
]


def ffmpeg_run(cmd: list[str]) -> None:
    r = subprocess.run([FFMPEG, '-y', '-v', 'error'] + cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f'ffmpeg failed: {r.stderr[-400:]}')


def peak_normalize(src: Path, out_m4a: Path, target_dbfs: float = -6.0) -> float:
    """Peak-normalize to target and encode 48k AAC. Returns applied gain dB."""
    r = subprocess.run([FFMPEG, '-i', src, '-af', 'volumedetect', '-f', 'null', '-'],
                       capture_output=True, text=True)
    m = None
    for line in r.stderr.splitlines():
        if 'max_volume' in line:
            m = float(line.split('max_volume:')[1].replace('dB', '').strip())
    gain = target_dbfs - (m if m is not None else 0)
    ffmpeg_run(['-i', src, '-af', f'volume={gain:.2f}dB', '-ar', '48000',
                '-c:a', 'aac', '-b:a', '192k', out_m4a])
    return gain


def main() -> int:
    warnings.filterwarnings('ignore')
    ap = argparse.ArgumentParser()
    ap.add_argument('--bgm', required=True)
    ap.add_argument('--sfx', nargs='+', required=True, help='name=path pairs')
    ap.add_argument('--props', default=None, help='props JSON to patch (bpm/narration)')
    args = ap.parse_args()

    import librosa

    # ---- BGM: decode → beat grid → pump envelope → normalized m4a ----
    y, sr = librosa.load(args.bgm, sr=SR_ANALYSIS, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time', start_bpm=120, tightness=100)
    bpm = float(np.atleast_1d(tempo)[0])
    while bpm > 150:
        bpm /= 2
    while bpm < 70:
        bpm *= 2
    beats = np.array([b for b in beats if b < len(y) / sr - 0.1])

    n_fft = 2048
    hop = int(sr / FPS)
    win = np.hanning(n_fft)
    freqs = np.fft.rfftfreq(n_fft, 1 / sr)
    band = (freqs >= 20) & (freqs <= 150)
    vals = []
    for i in range(0, max(len(y) - n_fft, 1), hop):
        spec = np.abs(np.fft.rfft(y[i:i + n_fft] * win))
        vals.append(float(spec[band].mean()))
    v = np.array(vals)
    v = v / max(v.max(), 1e-9)
    v = np.convolve(v, np.ones(3) / 3, mode='same')
    envelope = {'fps': FPS, 'values': [round(float(x), 4) for x in v]}

    times = librosa.frames_to_time(np.arange(len(v)), sr=sr)
    bass_per_beat = []
    for t in beats:
        i0, i1 = np.searchsorted(times, [t - 0.05, t + 0.15])
        bass_per_beat.append(round(float(v[i0:i1].mean() if i1 > i0 else 0), 4))

    beat_grid = {
        'bpm': round(bpm, 2),
        'beat_interval': round(60 / bpm, 4),
        'source': Path(args.bgm).name,
        'beats': [{'t': round(float(t), 3), 'bass': b} for t, b in zip(beats, bass_per_beat)],
    }

    # BGM peak-normalize to -6 dBFS (headroom; final loudness handled by master_audio)
    src_peak = float(np.abs(y).max())
    gain = -6 - (20 * np.log10(max(src_peak, 1e-9)))
    y_out = y * (10 ** (gain / 20))
    bgm_48k = librosa.resample(y_out, orig_sr=sr, target_sr=48000)
    tmp_wav = OUT / '_import.wav'
    import wave
    data = (np.clip(np.stack([bgm_48k, bgm_48k], 1), -1, 1) * 32767).astype('<i2')
    with wave.open(str(tmp_wav), 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(data.tobytes())
    ffmpeg_run(['-i', tmp_wav, '-c:a', 'aac', '-b:a', '192k', str(OUT / 'bgm_main.m4a')])
    tmp_wav.unlink()
    (OUT / 'pump_envelope.json').write_text(json.dumps(envelope), encoding='utf-8')
    (OUT / 'bgm_beats.json').write_text(json.dumps(beat_grid, indent=1), encoding='utf-8')

    # ---- SFX: peak-normalize each to -6 dBFS ----
    for pair in args.sfx:
        name, src = pair.split('=', 1)
        out_m4a = OUT / f'sfx_{name}.m4a'
        g = peak_normalize(Path(src), out_m4a)
        print(f'sfx_{name}: gain {g:+.1f}dB -> {out_m4a.name}')

    # ---- manifest ----
    manifest = {
        'generated': date.today().isoformat(),
        'note': 'all files commercial-use, no attribution required; do not redistribute standalone',
        'files': [
            {'file': f'{key}.m4a', 'source': src, 'license': lic, 'terms': terms}
            for key, src, lic, terms in MANIFEST_ENTRIES
        ],
    }
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')

    # ---- optional props patch ----
    if args.props:
        pp = Path(args.props)
        props = json.loads(pp.read_text(encoding='utf-8'))
        props['bpm'] = round(bpm, 1)
        props['narration']['src'] = 'audio/bgm_main.m4a'
        props['narration']['pumpEnvelope'] = envelope
        pp.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'props patched: bpm={bpm:.1f}, narration=audio/bgm_main.m4a, envelope {len(envelope["values"])}f')

    print(f'\nBGM: {bpm:.1f} BPM, {len(y) / sr:.0f}s -> bgm_main.m4a')
    print('beat grid + pump envelope regenerated for the real track')
    return 0


if __name__ == '__main__':
    sys.exit(main())
