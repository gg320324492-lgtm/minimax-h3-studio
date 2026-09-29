"""v2 narration with Qwen3-TTS-1.7B-CustomVoice (Apache-2.0).

说书人 = Uncle_Fu (低沉苍老男声) with per-line storytelling instructs;
娘子 = Serena (young female). Per-line speed fitted to the shot slot with
gentle ffmpeg atempo (clamped 0.85-1.15) after measuring raw duration.

Run with the dedicated venv: E:/tts/qwen3tts-venv/Scripts/python.exe
"""
import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(r'E:/Minimax-H3/liaozhai_demo')
OUT = PROJECT / '05_audio' / 'NARR_V2'
MODEL_DIR = r'E:/tts/models/Qwen3-TTS-1.7B-CustomVoice'
TOKENIZER_DIR = r'E:/tts/models/Qwen3-TTS-Tokenizer-12Hz'

NARR_INSTRUCT = ('用低沉苍老的嗓音，像老评书艺人讲鬼故事，吐字铿锵，语速缓慢，'
                 '抑扬顿挫，营造悬疑惊悚的氛围')
FEM_INSTRUCT = ('温柔清亮的年轻女子，语气柔弱胆怯，带着一丝小心翼翼的哀求')

CFG = json.loads((PROJECT / '00_project' / 'story.json').read_text(encoding='utf-8'))
SHOT_DUR = {sid: c['length'] / CFG['fps'] for sid, c in CFG['shots'].items()}


def adur(p):
    return float(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(p)]).decode().strip())


def main():
    import torch
    from qwen_tts import Qwen3TTSModel   # noqa: verify import name at runtime
    import soundfile as sf

    OUT.mkdir(parents=True, exist_ok=True)
    print('Loading Qwen3-TTS-1.7B-CustomVoice ...')
    tts = Qwen3TTSModel.from_pretrained(
        MODEL_DIR if Path(MODEL_DIR).exists() else 'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice',
        device_map='cuda:0', dtype=torch.bfloat16)
    print('ready')

    lines = [l for l in CFG['narration'] if not adur_skip(OUT, l['id'])]
    texts, speakers, instructs = [], [], []
    for l in lines:
        female = l.get('voice', '').startswith('zf')
        texts.append(l['text'])
        speakers.append('Serena' if female else 'Uncle_Fu')
        instructs.append(FEM_INSTRUCT if female else NARR_INSTRUCT)

    print(f'generating {len(texts)} lines ...')
    wavs, sr = tts.generate_custom_voice(
        text=texts, language=['Chinese'] * len(texts),
        speaker=speakers, instruct=instructs, max_new_tokens=2048)

    for l, wav in zip(lines, wavs):
        raw = OUT / f'{l["id"]}_raw.wav'
        sf.write(str(raw), wav, sr)
        raw_dur = adur(raw)
        # fit to slot: start offset 0.4 (or after-gap), keep 0.25s tail margin
        if 'after' in l:
            speed = 1.0
        else:
            slot = SHOT_DUR[l['shot']]
            speed = raw_dur / max(0.5, slot - 0.65)
            speed = min(1.3, max(0.8, speed))
        final = OUT / f'{l["id"]}.m4a'
        af = (f'silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,'
              f'areverse,silenceremove=start_periods=1:start_silence=0.08:start_threshold=-45dB,'
              f'areverse,atempo={speed:.4f},loudnorm=I=-16:TP=-1.5:LRA=11')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(raw),
                        '-af', af, '-ar', '48000', '-ac', '1',
                        '-c:a', 'aac', '-b:a', '192k', str(final)], check=True)
        raw.unlink()
        print(f'  {l["id"]} [{speakers[lines.index(l)]}] raw {raw_dur:.2f}s '
              f'-> {adur(final):.2f}s (speed {speed:.2f})')
    print('=== v2 narration done ===')


def adur_skip(out_dir, lid):
    f = out_dir / f'{lid}.m4a'
    if f.exists():
        print(f'  skip {lid} (exists)')
        return True
    return False


if __name__ == '__main__':
    main()
