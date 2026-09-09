"""Generate TTS audio for all dialogue + inner voice using edge-tts.

Voice mapping:
- CEO (Gu Yanchuan): zh-CN-YunyangNeural (Professional, Reliable, 30s male)
- INTERN (Lin Xiaoyu): zh-CN-XiaoxiaoNeural (Warm, female)
- INNER_VOICE: Same as INTERN, with post-processing reverb + low-pass

Tone adjustments:
- CEO: rate -5%, pitch -3Hz (slower, deeper)
- INTERN: rate +3% (slightly nervous, normal speed)
- INNER_VOICE: rate -3%, pitch +2Hz, post-reverb added in mixer
"""
import asyncio
import sys
from pathlib import Path

import edge_tts

PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')


async def tts(text, voice, rate, pitch, output_path):
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_path))
    print(f'  saved: {output_path} ({output_path.stat().st_size/1024:.1f}KB)')


async def main():
    # Speaker configs
    ceo_voice = 'zh-CN-YunyangNeural'  # Professional, Reliable
    intern_voice = 'zh-CN-XiaoxiaoNeural'  # Warm

    # Dialogue JSON
    dialogue = [
        # (output_name, text, speaker, [extra_silence_ms])
        ('S01_DLG_CEO_intern_hands_report',  # opening line is from intern
         '顾总，这是您要的市场报告。',
         intern_voice, '+0%', '+0Hz'),

        ('S02_IV_INNER_six_five_four',
         '六……五……四……',
         intern_voice, '-3%', '+2Hz'),  # slower inner voice

        ('S04_IV_INNER_he_should_have_died',
         '他怎么没死？前七次明明都死在这里……',
         intern_voice, '-3%', '+2Hz'),

        ('S05_DLG_INTERN_coffee',
         '顾总，您的咖啡。',
         intern_voice, '+3%', '+0Hz'),

        ('S05_IV_INNER_peanut_allergy',
         '别喝啊！里面有花生酱，你不是严重过敏吗？',
         intern_voice, '-3%', '+2Hz'),

        ('S06_DLG_CEO_lin_xiaoyu',
         '林小雨。',
         ceo_voice, '-5%', '-3Hz'),  # CEO tone

        ('S06_DLG_INTERN_response',
         '顾……顾总？',
         intern_voice, '+8%', '+2Hz'),  # slightly nervous

        ('S06_DLG_CEO_who_are_you',
         '你到底是谁？',
         ceo_voice, '-5%', '-3Hz'),

        ('S06_DLG_INTERN_intern',
         '实习生啊……',
         intern_voice, '+3%', '+0Hz'),

        ('S06_IV_INNER_eighth_loop',
         '奇怪……第八次循环，他第一次活到了九点十七分。',
         intern_voice, '-3%', '+2Hz'),

        ('S08_IV_INNER_eighth_restart',
         '第八次循环……又开始了。',
         intern_voice, '-3%', '+2Hz'),

        ('S08_IV_INNER_this_time_me',
         '但是这一次……要死的人，好像是我。',
         intern_voice, '-5%', '+1Hz'),
    ]

    output_root = PROJECT / '05_audio'
    tasks = []
    for slug, text, voice, rate, pitch in dialogue:
        if 'IV_INNER' in slug or 'inner' in slug.lower():
            out_dir = output_root / 'INNER_VOICE'
        elif 'CEO' in slug:
            out_dir = output_root / 'CEO'
        else:
            out_dir = output_root / 'INTERN'
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f'{slug}.mp3'
        tasks.append(tts(text, voice, rate, pitch, out_path))

    await asyncio.gather(*tasks)
    print('\n=== TTS Generation Complete ===')


if __name__ == '__main__':
    asyncio.run(main())