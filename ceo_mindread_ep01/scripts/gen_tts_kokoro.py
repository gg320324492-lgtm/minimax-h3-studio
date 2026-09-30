"""Regenerate ALL TTS using local Kokoro-82M high-quality TTS.

Voice assignments (Chinese):
- CEO (Gu Yanchuan, 30s male): zm_yunyang (Professional, Reliable)
- INTERN (Lin Xiaoyu, 23s female): zf_xiaoxiao (Warm)
- INNER VOICE: Same as INTERN with pitch/speed adjustment for eeriness
"""


# --- ffmpeg binary resolution -------------------------------------------------
# PATH `ffmpeg` on this machine is GNU Octave's bundled 4.2.11, not a normal
# install, so every encode silently depended on a third-party app. Resolve via
# ffmpeg_env (repo-bundled 7.1.1 by default; MINIMAX_FFMPEG_LEGACY=1 to pin the
# legacy PATH binary for byte-comparable re-runs).
import sys as _sys, os as _os  # noqa: E402
if r'E:\Minimax-H3' not in _sys.path:
    _sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import prepend_to_path as _prepend_ffmpeg  # noqa: E402
_prepend_ffmpeg()
# -----------------------------------------------------------------------------
import os
import sys
from pathlib import Path
import numpy as np
import subprocess

os.environ['HF_HUB_CACHE'] = 'E:/ComfyUI/models/tts'

PROJECT = Path(r'E:/Minimax-H3/ceo_mindread_ep01')

# Voice mapping
VOICE_CEO = 'zm_yunyang'  # Professional, Reliable male
VOICE_INTERN = 'zf_xiaoxiao'  # Warm female

# Dialogue lines from dialogue.json
LINES = [
    # (output_name, text, voice, speed)
    ('S01_DLG_CEO_intern_hands_report',
     '顾总，这是您要的市场报告。',
     VOICE_INTERN, 1.0),

    ('S02_IV_INNER_six_five_four',
     '六……五……四……',
     VOICE_INTERN, 0.85),  # Slower for inner voice

    ('S03_IV_INNER_three_two',
     '三……二……',
     VOICE_INTERN, 0.85),

    ('S04_IV_INNER_he_should_have_died',
     '他怎么没死？前七次明明都死在这里……',
     VOICE_INTERN, 0.85),

    ('S05_DLG_INTERN_coffee',
     '顾总，您的咖啡。',
     VOICE_INTERN, 1.05),  # Slightly nervous

    ('S05_IV_INNER_peanut_allergy',
     '别喝啊！里面有花生酱，你不是严重过敏吗？',
     VOICE_INTERN, 0.9),

    ('S06_DLG_CEO_lin_xiaoyu',
     '林小雨。',
     VOICE_CEO, 0.9),  # Slower for CEO

    ('S06_DLG_INTERN_response',
     '顾……顾总？',
     VOICE_INTERN, 1.15),  # Nervous

    ('S06_DLG_CEO_who_are_you',
     '你到底是谁？',
     VOICE_CEO, 0.85),  # Even slower for emphasis

    ('S06_DLG_INTERN_intern',
     '实习生啊……',
     VOICE_INTERN, 1.0),

    ('S06_IV_INNER_eighth_loop',
     '奇怪……第八次循环，他第一次活到了九点十七17分。',
     VOICE_INTERN, 0.85),

    ('S08_IV_INNER_eighth_restart',
     '第八次循环……又开始了。',
     VOICE_INTERN, 0.85),

    ('S08_IV_INNER_this_time_me',
     '但是这一次……要死的人，好像是我。',
     VOICE_INTERN, 0.8),

    # New: opening subtitle voice (just for S01 inner voice "完了……他还有七秒就要死了")
    ('S01_IV_INNER_completed',
     '完了……他还有七秒就要死了。',
     VOICE_INTERN, 0.85),
]


def convert_to_m4a(wav_path, m4a_path):
    """Convert wav to m4a using ffmpeg."""
    subprocess.run([
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(wav_path),
        '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
        str(m4a_path)
    ], check=True)


def main():
    from kokoro import KPipeline

    # Initialize pipeline once
    print('Loading Kokoro-82M model...')
    pipeline = KPipeline(lang_code='z', model=True, repo_id='hexgrad/Kokoro-82M')
    print('Pipeline ready\n')

    for slug, text, voice, speed in LINES:
        print(f'  Generating {slug}...')
        # Decide output directory
        if 'CEO' in slug and 'INNER' not in slug:
            out_dir = PROJECT / '05_audio/CEO'
        elif 'INNER' in slug:
            out_dir = PROJECT / '05_audio/INNER_VOICE'
        else:
            out_dir = PROJECT / '05_audio/INTERN'
        out_dir.mkdir(parents=True, exist_ok=True)

        wav_path = Path(f'C:/Users/pc/AppData/Local/Temp/kokoro_{slug}.wav')
        m4a_path = out_dir / f'{slug}.m4a'

        # Delete old file to ensure regeneration
        if m4a_path.exists():
            m4a_path.unlink()

        # Generate
        for gs, ps, audio in pipeline(text, voice=voice, speed=speed):
            if audio is not None and len(audio) > 0:
                # Save as WAV first
                import soundfile as sf
                sf.write(str(wav_path), audio, 24000)

                # Convert to M4A
                convert_to_m4a(wav_path, m4a_path)
                wav_path.unlink(missing_ok=True)
                size_kb = m4a_path.stat().st_size / 1024
                duration_s = len(audio) / 24000
                print(f'    -> {m4a_path.name} ({size_kb:.1f}KB, {duration_s:.2f}s)')
            else:
                print(f'    -> ERROR: no audio for "{text}"')
            break

    print('\n=== All TTS regenerated with Kokoro ===')


if __name__ == '__main__':
    main()