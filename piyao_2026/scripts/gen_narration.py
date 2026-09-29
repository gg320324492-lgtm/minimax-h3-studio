"""Generate all narration lines with local Kokoro-82M (Chinese, male PSA voice).

- Voice: zm_yunyang (professional male), per-line speed from shots.json
- Head/tail silence trimmed (-45 dB, promo_video lesson: ~1.2 s per line)
- Output: 05_audio/NARR/<ID>.m4a (48 kHz mono, AAC)
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import os
os.environ['HF_HUB_CACHE'] = 'E:/ComfyUI/models/tts'

PROJECT = Path(r'E:/Minimax-H3/piyao_2026')
OUT = PROJECT / '05_audio' / 'NARR'
VOICE = 'zm_yunjian'  # deep / resolute male, more solemn than zm_yunyang

CFG = json.loads((PROJECT / '00_project' / 'shots.json').read_text(encoding='utf-8'))


def trim_to_m4a(wav_path, m4a_path):
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error', '-i', str(wav_path), '-af',
        'silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,'
        'areverse,'
        'silenceremove=start_periods=1:start_silence=0.08:start_threshold=-45dB,'
        'areverse',
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', str(m4a_path)], check=True)


def main():
    from kokoro import KPipeline
    import soundfile as sf

    OUT.mkdir(parents=True, exist_ok=True)
    print('Loading Kokoro-82M ...')
    pipeline = KPipeline(lang_code='z', model=True, repo_id='hexgrad/Kokoro-82M')
    print('Pipeline ready\n')

    tmp = Path(tempfile.gettempdir())
    for line in CFG['narration']:
        if line.get('skip'):
            continue
        m4a = OUT / f'{line["id"]}.m4a'
        text = line['text']
        speed = line.get('speed', 1.0)
        print(f'  {line["id"]} ({speed}x): {text}')
        audio = None
        for _, _, a in pipeline(text, voice=VOICE, speed=speed):
            if a is not None and len(a) > 0:
                audio = a
                break
        if audio is None:
            print(f'    ERROR: no audio for {line["id"]}')
            sys.exit(1)
        wav = tmp / f'kokoro_{line["id"]}.wav'
        sf.write(str(wav), audio, 24000)
        trim_to_m4a(wav, m4a)
        wav.unlink(missing_ok=True)
        dur = float(subprocess.check_output(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(m4a)]).decode().strip())
        print(f'    -> {m4a.name} {dur:.2f}s')
    print('\n=== narration done ===')


if __name__ == '__main__':
    main()
