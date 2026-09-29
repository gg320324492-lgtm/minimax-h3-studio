"""Audio mix for liaozhai_demo - timeline-driven (piyao's proven chain).

speech -> amix -> asplit: one branch ducks BGM via sidechaincompress;
rain bed looped under everything (fixed low level); sfx mixed separately;
final -> loudnorm -14 LUFS -> stereo 48k + measured static-gain correction.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import prepend_to_path  # noqa: E402
prepend_to_path()

PROJECT = Path(r'E:/Minimax-H3/liaozhai_demo')
OUTPUT = PROJECT / '07_edit' / 'LZ_WITH_AUDIO.mp4'


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def main():
    tl = json.loads((PROJECT / '00_project/timeline.json').read_text(encoding='utf-8'))
    total = tl['total_duration']

    master = Path(os.environ.get(
        'LZ_MASTER', str(PROJECT / '07_edit/LZ_MASTER_1080P.mp4')))
    if not master.exists():
        log(f'ERROR: {master} not found')
        sys.exit(1)
    log(f'picture master: {master.name}')

    inputs_list = ['-i', str(master)]      # index 0 = picture
    inputs_list += ['-i', str(PROJECT / tl['bgm']['file'])]  # index 1 = BGM

    file_index = {}
    next_idx = 2

    def idx_for(rel_path):
        nonlocal next_idx, inputs_list
        if rel_path not in file_index:
            p = PROJECT / rel_path
            if not p.exists():
                log(f'  WARN missing audio: {rel_path}')
                return None
            inputs_list += ['-i', str(p)]
            file_index[rel_path] = next_idx
            next_idx += 1
        return file_index[rel_path]

    for e in tl['audio_events'] + tl['sfx_events']:
        idx_for(e['file'])

    parts = []
    bgm_vol = tl['bgm']['volume']
    parts.append(
        f'[1:a]aloop=loop=-1:size=1e9,atrim=0:duration={total},'
        f'volume={bgm_vol},aformat=channel_layouts=stereo[bgm];'
    )

    amb = tl.get('ambience')
    amb_label = None
    if amb:
        idx = idx_for(amb['file'])
        if idx is not None:
            parts.append(
                f'[{idx}:a]aloop=loop=-1:size=1e9,atrim=0:duration={total},'
                f'volume={amb["volume"]},aformat=channel_layouts=stereo[amb];'
            )
            amb_label = '[amb]'

    speech_labels = []
    for e in tl['audio_events']:
        idx = file_index.get(e['file'])
        if idx is None:
            continue
        delay_ms = int(e['start'] * 1000)
        dur_s = max(0.1, e['end'] - e['start'])
        # trim FIRST, reset pts, THEN delay (the adelay/atrim lesson)
        parts.append(
            f'[{idx}:a]volume={e.get("volume", 1.0)},aformat=channel_layouts=stereo,'
            f'atrim=0:duration={dur_s},asetpts=PTS-STARTPTS,'
            f'adelay={delay_ms}|{delay_ms}[sp_{e["id"]}];'
        )
        speech_labels.append(f'[sp_{e["id"]}]')

    sfx_labels = []
    for e in tl['sfx_events']:
        idx = file_index.get(e['file'])
        if idx is None:
            continue
        delay_ms = int(e['start'] * 1000)
        dur_s = max(0.1, e['end'] - e['start'])
        parts.append(
            f'[{idx}:a]volume={e.get("volume", 0.8)},aformat=channel_layouts=stereo,'
            f'atrim=0:duration={dur_s},asetpts=PTS-STARTPTS,'
            f'adelay={delay_ms}|{delay_ms}[sfx_{e["id"]}];'
        )
        sfx_labels.append(f'[sfx_{e["id"]}]')

    if not speech_labels:
        log('ERROR: no speech events')
        sys.exit(1)
    parts.append(
        f'{"".join(speech_labels)}amix=inputs={len(speech_labels)}:duration=longest:dropout_transition=0,'
        f'aformat=channel_layouts=stereo[speech0];'
    )
    # sidechain must outlive the speech: apad the sidechain branch to total
    parts.append('[speech0]asplit=2[sc0][speech_mix];')
    parts.append(f'[sc0]apad=whole_dur={total}[speech_sc];')

    if tl['bgm'].get('duck', True):
        parts.append(
            '[bgm][speech_sc]sidechaincompress=threshold=0.015:ratio=8:attack=30:release=700[bgm_duck];')
        bgm_label = '[bgm_duck]'
    else:
        bgm_label = '[bgm]'

    beds = bgm_label + (amb_label or '')
    if sfx_labels:
        parts.append(
            f'{"".join(sfx_labels)}amix=inputs={len(sfx_labels)}:duration=longest:dropout_transition=0[sfxmix];')
        final_inputs = f'{beds}[speech_mix][sfxmix]'
        n_final = 2 + (1 if amb_label else 0) + 1
    else:
        final_inputs = f'{beds}[speech_mix]'
        n_final = 2 + (1 if amb_label else 0)

    parts.append(
        f'{final_inputs}amix=inputs={n_final}:duration=longest:dropout_transition=0,'
        f'loudnorm=I=-14:TP=-1.5:LRA=11,'
        f'aformat=sample_rates=48000:channel_layouts=stereo,'
        f'alimiter=limit=0.97[mix_final]'
    )

    fc_path = PROJECT / 'logs' / 'filter_mix.txt'
    fc_path.parent.mkdir(parents=True, exist_ok=True)
    fc_path.write_text(''.join(parts), encoding='utf-8')
    log(f'Filter graph written ({len("".join(parts))} chars)')

    cmd = ['ffmpeg', '-y', '-loglevel', 'error'] + inputs_list + [
        '-filter_complex_script', str(fc_path),
        '-map', '0:v', '-map', '[mix_final]',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '320k', '-ar', '48000',
        '-t', str(total),
        str(OUTPUT),
    ]
    log(f'Mixing {next_idx - 2} audio events, total {total:.2f}s ...')
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print('STDERR:', r.stderr.decode()[:2000])
        sys.exit(1)
    log(f'DONE: {OUTPUT} ({OUTPUT.stat().st_size/1024/1024:.1f}MB)')

    # measured static-gain correction loop
    for _ in range(3):
        r = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(OUTPUT),
                            '-map', '0:a', '-af', 'loudnorm=print_format=summary',
                            '-f', 'null', '-'], capture_output=True)
        integrated = None
        for line in r.stderr.decode(errors='ignore').split('\n'):
            if 'Input Integrated' in line:
                integrated = float(line.split(':')[1].replace('LUFS', '').strip())
        if integrated is None:
            log('WARN: could not measure loudness, skipping correction')
            return
        log(f'  measured integrated: {integrated:.2f} LUFS')
        if -14.5 <= integrated <= -13.5:
            log('  loudness OK')
            return
        gain = -14.0 - integrated
        fix_out = OUTPUT.with_suffix('.fix.mp4')
        r = subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(OUTPUT),
                            '-map', '0:v', '-map', '0:a', '-c:v', 'copy',
                            '-af', f'volume={gain:.2f}dB,alimiter=limit=0.97',
                            '-c:a', 'aac', '-b:a', '320k', '-ar', '48000',
                            str(fix_out)], capture_output=True)
        if r.returncode != 0:
            print('STDERR:', r.stderr.decode()[:2000])
            sys.exit(1)
        fix_out.replace(OUTPUT)
        log(f'  applied {gain:+.2f}dB correction')


if __name__ == '__main__':
    main()
