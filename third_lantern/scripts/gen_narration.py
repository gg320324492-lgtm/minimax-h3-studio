"""Narration + dialogue for third_lantern《第三盏灯》(Qwen3-TTS).

- 阿宁 first-person narration + her soft lines: CustomVoice 'Serena' with
  quiet, restrained-sad instructs.
- 小满 (child): VoiceDesign model, described as a 8-10 y.o. Chinese boy,
  clear soft timid voice.

Run with E:/tts/qwen3tts-venv/Scripts/python.exe
"""
import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(r'E:/Minimax-H3/third_lantern')
OUT = PROJECT / '05_audio' / 'NARR'
CUSTOM_DIR = r'E:/tts/models/Qwen3-TTS-1.7B-CustomVoice'
DESIGN_DIR = r'E:/tts/models/Qwen3-TTS-1.7B-VoiceDesign'

NARR_INSTRUCT = ('年轻女子，声音安静低缓，清冷中带着隐忍的哀伤，像在心里讲一件藏了很多年的事，'
                 '语速缓慢，吐字轻，悬念处微微压低')
SOFT_INSTRUCT = ('年轻女子，声音很轻很软，颤抖着克制悲伤，像忍着泪在告别，语速缓慢')
CHILD_INSTRUCT = ('八到十岁的中国小男孩，声音清亮柔软，干净没有杂音，胆怯安静，'
                  '带着一点朦胧空灵和抱歉的语气，语速缓慢轻柔，像怕吵到谁')

CFG = json.loads((PROJECT / '00_project' / 'story.json').read_text(encoding='utf-8'))
SHOT_DUR = {sid: c['length'] / CFG['fps'] for sid, c in CFG['shots'].items()}


def adur(p):
    return float(subprocess.check_output(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(p)]).decode().strip())


def finish(raw, final, speed):
    af = ('silenceremove=start_periods=1:start_silence=0.05:start_threshold=-45dB,'
          'areverse,silenceremove=start_periods=1:start_silence=0.08:start_threshold=-45dB,'
          'areverse,atempo={:.4f},loudnorm=I=-16:TP=-1.5:LRA=11'.format(speed))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(raw),
                    '-af', af, '-ar', '48000', '-ac', '1',
                    '-c:a', 'aac', '-b:a', '192k', str(final)], check=True)


def main():
    import torch
    from qwen_tts import Qwen3TTSModel
    import soundfile as sf

    OUT.mkdir(parents=True, exist_ok=True)
    todo = [l for l in CFG['narration']
            if not (OUT / f'{l["id"]}.m4a').exists()]
    if not todo:
        print('all lines exist')
        return

    need_custom = [l for l in todo if l['voice'] in ('female', 'female_soft')]
    need_child = [l for l in todo if l['voice'] == 'child']

    if need_custom:
        tts = Qwen3TTSModel.from_pretrained(CUSTOM_DIR, device_map='cuda:0',
                                            dtype=torch.bfloat16)
        texts, instructs = [], []
        for l in need_custom:
            texts.append(l['text'])
            instructs.append(SOFT_INSTRUCT if l['voice'] == 'female_soft' else NARR_INSTRUCT)
        wavs, sr = tts.generate_custom_voice(
            text=texts, language=['Chinese'] * len(texts),
            speaker=['Serena'] * len(texts), instruct=instructs, max_new_tokens=2048)
        for l, wav in zip(need_custom, wavs):
            raw = OUT / f'{l["id"]}_raw.wav'
            sf.write(str(raw), wav, sr)
            raw_dur = adur(raw)
            if 'after' in l:
                speed = 1.0
            else:
                slot = SHOT_DUR[l['shot']]
                speed = min(1.3, max(0.8, raw_dur / max(0.5, slot - 0.7)))
            final = OUT / f'{l["id"]}.m4a'
            finish(raw, final, speed)
            raw.unlink()
            print(f'  {l["id"]} [Serena] raw {raw_dur:.2f}s -> {adur(final):.2f}s (x{speed:.2f})')
        del tts
        torch.cuda.empty_cache()

    if need_child:
        tts = Qwen3TTSModel.from_pretrained(DESIGN_DIR, device_map='cuda:0',
                                            dtype=torch.bfloat16)
        texts = [l['text'] for l in need_child]
        instructs = [CHILD_INSTRUCT] * len(texts)
        wavs, sr = tts.generate_voice_design(
            text=texts, instruct=instructs, language=['Chinese'] * len(texts),
            max_new_tokens=2048)
        for l, wav in zip(need_child, wavs):
            raw = OUT / f'{l["id"]}_raw.wav'
            sf.write(str(raw), wav, sr)
            final = OUT / f'{l["id"]}.m4a'
            finish(raw, final, 1.0)
            raw.unlink()
            print(f'  {l["id"]} [child-design] raw {adur(final):.2f}s')
    print('=== narration v3 done ===')


if __name__ == '__main__':
    main()
