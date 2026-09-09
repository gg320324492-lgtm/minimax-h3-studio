"""Audio mix v4 - timeline-driven, loudness-normalized, stereo, BGM ducking.

Reads 00_project/timeline.json (built by build_timeline.py).

Signal chain:
  1. each dialogue/inner event: volume -> (lowpass for inner) -> adelay
  2. each sfx event: volume -> adelay
  3. speech = amix(dialogue+inner), sfxmix = amix(sfx)
  4. bgm: aloop -> atrim -> volume -> sidechaincompress(key=speech)
  5. final = amix(bgm_ducked, speech, sfx) -> loudnorm(-14 LUFS) -> aformat 48k stereo
"""
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')
OUTPUT = PROJECT / '07_edit' / 'EP01_WITH_AUDIO.mp4'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def main():
    tl = json.loads((PROJECT / '00_project/timeline.json').read_text(encoding='utf-8'))
    total = tl['total_duration']

    master = PROJECT / '07_edit/EP01_PICTURE_MASTER_1080P.mp4'
    if not master.exists():
        log(f'ERROR: {master} not found')
        sys.exit(1)

    # ---- Collect input files (video + bgm + unique event files) ----
    inputs = ['-i', str(master)]          # index 0
    inputs += ['-i', str(PROJECT / tl['bgm']['file'])]  # index 1 = BGM

    event_files = []   # (abs_path, idx)
    file_index = {}
    next_idx = 2

    def idx_for(rel_path):
        nonlocal next_idx, inputs
        if rel_path not in file_index:
            p = PROJECT / rel_path
            if not p.exists():
                log(f'  WARN missing audio: {rel_path}')
                return None
            inputs += ['-i', str(p)]
            file_index[rel_path] = next_idx
            next_idx += 1
        return file_index[rel_path]

    # Collect all files first so indices are stable
    for e in tl['audio_events'] + tl['sfx_events']:
        idx_for(e['file'])

    # ---- Filter graph ----
    parts = []

    # BGM: loop to full duration, base volume
    bgm_vol = tl['bgm']['volume']
    parts.append(
        f'[1:a]aloop=loop=-1:size=1e9,atrim=0:duration={total},'
        f'volume={bgm_vol},aformat=channel_layouts=stereo[bgm];'
    )

    # Dialogue + inner voice events
    speech_labels = []
    for e in tl['audio_events']:
        idx = file_index.get(e['file'])
        if idx is None:
            continue
        delay_ms = int(e['start'] * 1000)
        dur_s = max(0.1, e['end'] - e['start'])
        if e['type'] == 'inner':
            chain = f'volume=0.75,lowpass=f=4000'
        else:
            chain = f'volume=1.0'
        parts.append(
            f'[{idx}:a]{chain},aformat=channel_layouts=stereo,'
            f'adelay={delay_ms}|{delay_ms},atrim=0:duration={dur_s},'
            f'asetpts=PTS-STARTPTS[sp_{e["id"]}];'
        )
        speech_labels.append(f'[sp_{e["id"]}]')

    # SFX events
    sfx_labels = []
    for e in tl['sfx_events']:
        idx = file_index.get(e['file'])
        if idx is None:
            continue
        delay_ms = int(e['start'] * 1000)
        dur_s = max(0.1, e['end'] - e['start'])
        parts.append(
            f'[{idx}:a]volume={e.get("volume", 0.8)},aformat=channel_layouts=stereo,'
            f'adelay={delay_ms}|{delay_ms},atrim=0:duration={dur_s},'
            f'asetpts=PTS-STARTPTS[sfx_{e["id"]}];'
        )
        sfx_labels.append(f'[sfx_{e["id"]}]')

    # Mix speech
    n_sp = len(speech_labels)
    if n_sp == 0:
        log('ERROR: no speech events')
        sys.exit(1)
    parts.append(
        f'{"".join(speech_labels)}amix=inputs={n_sp}:duration=longest:dropout_transition=0,'
        f'aformat=channel_layouts=stereo[speech0];'
    )
    # split: one branch feeds sidechain, other feeds final mix (labels consumed once only)
    parts.append('[speech0]asplit=2[speech_sc][speech_mix];')

    # BGM ducking via sidechaincompress (threshold low so speech ducks bgm)
    if tl['bgm'].get('duck', True):
        parts.append(
            '[bgm][speech_sc]sidechaincompress=threshold=0.02:ratio=6:attack=80:release=500[bgm_duck];'
        )
        bgm_label = '[bgm_duck]'
    else:
        bgm_label = '[bgm]'

    # SFX mix (if any)
    if sfx_labels:
        n_sfx = len(sfx_labels)
        parts.append(
            f'{"".join(sfx_labels)}amix=inputs={n_sfx}:duration=longest:dropout_transition=0[sfxmix];'
        )
        final_inputs = f'{bgm_label}[speech_mix][sfxmix]'
        n_final = 3
    else:
        final_inputs = f'{bgm_label}[speech_mix]'
        n_final = 2

    # Final mix: sum -> loudness normalize to -14 LUFS -> stereo 48k
    parts.append(
        f'{final_inputs}amix=inputs={n_final}:duration=longest:dropout_transition=0,'
        f'loudnorm=I=-14:TP=-1.5:LRA=11,'
        f'aformat=sample_rates=48000:channel_layouts=stereo,'
        f'alimiter=limit=0.97[mix_final]'
    )

    filter_complex = ''.join(parts)

    fc_path = PROJECT / 'logs' / 'filter_v4.txt'
    fc_path.parent.mkdir(parents=True, exist_ok=True)
    fc_path.write_text(filter_complex, encoding='utf-8')
    log(f'Filter graph written to {fc_path} ({len(filter_complex)} chars)')

    cmd = ['ffmpeg', '-y', '-loglevel', 'error'] + inputs + [
        '-filter_complex_script', str(fc_path),
        '-map', '0:v', '-map', '[mix_final]',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '320k', '-ar', '48000',
        '-t', str(total),
        str(OUTPUT),
    ]
    log(f'Mixing {next_idx - 2} audio events, total {total:.2f}s...')
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print('STDERR:', r.stderr.decode()[:2000])
        sys.exit(1)
    log(f'DONE: {OUTPUT} ({OUTPUT.stat().st_size/1024/1024:.1f}MB)')


if __name__ == '__main__':
    main()
