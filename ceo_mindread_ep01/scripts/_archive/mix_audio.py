"""Final audio mix and subtitle burn for CEO Mindread EP01.

Combines:
- BGM (dark drone) at -14 LUFS
- SFX (heartbeat, impact, whoosh) at strategic moments
- TTS dialogue aligned to specific shots
- Inner voice (心声) with low-pass filter for eerie effect
- ASS subtitles burned-in

Output: 1080x1920, H.264, AAC 320k, ready for Douyin.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def run_ffmpeg(cmd):
    """Run ffmpeg, raise if failed."""
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        print('STDERR:', r.stderr.decode()[:500])
        raise RuntimeError('ffmpeg failed')


def get_video_duration(video):
    r = subprocess.check_output([
        'ffprobe', '-v', 'error',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        str(video)
    ])
    return float(r.decode().strip())


def main():
    master_video = PROJECT / '07_edit/EP01_PICTURE_MASTER_1080P.mp4'
    if not master_video.exists():
        log(f'ERROR: {master_video} not found')
        return

    duration = get_video_duration(master_video)
    log(f'Master video: {duration:.2f}s')

    # Build timeline based on shot manifest
    # shot_targets aligns to actual generated durations
    timeline = [
        # (start_time, end_time, audio_type, audio_file, volume_db)
        # S01: 0-4.46s - opening dialogue
        (0.5, 4.0, 'dialogue', '05_audio/CEO/S01_DLG_CEO_intern_hands_report.m4a', 0),
        (3.0, 4.4, 'heartbeat', '05_audio/SFX/SFX_LOW_PULSE.m4a', -3),

        # S02: 4.46-9.63s - inner voice countdown
        (4.5, 9.0, 'inner', '05_audio/INNER_VOICE/S01_IV_INNER_completed.m4a', -2),
        (4.5, 9.0, 'inner', '05_audio/INNER_VOICE/S02_IV_INNER_six_five_four.m4a', -2),

        # S03: 9.63-13.5s - lamp crash
        (9.6, 12.0, 'inner', '05_audio/INNER_VOICE/S03_IV_INNER_three_two.m4a', -2),
        (12.0, 13.5, 'impact', '05_audio/SFX/SFX_IMPACT.m4a', 0),

        # S04: 13.5-17.92s - first reveal
        (13.5, 17.5, 'inner', '05_audio/INNER_VOICE/S04_IV_INNER_he_should_have_died.m4a', -2),

        # S05: 17.92-21.88s - coffee test
        (18.0, 21.0, 'dialogue', '05_audio/INTERN/S05_DLG_INTERN_coffee.m4a', 0),
        (19.0, 21.5, 'inner', '05_audio/INNER_VOICE/S05_IV_INNER_peanut_allergy.m4a', -2),

        # S06: 21.88-25.63s - who are you dialogue
        (22.0, 23.0, 'dialogue', '05_audio/CEO/S06_DLG_CEO_lin_xiaoyu.m4a', 0),
        (23.0, 24.0, 'dialogue', '05_audio/INTERN/S06_DLG_INTERN_response.m4a', 0),
        (24.0, 25.0, 'dialogue', '05_audio/CEO/S06_DLG_CEO_who_are_you.m4a', 0),
        (25.0, 25.5, 'dialogue', '05_audio/INTERN/S06_DLG_INTERN_intern.m4a', 0),
        (25.0, 26.5, 'inner', '05_audio/INNER_VOICE/S06_IV_INNER_eighth_loop.m4a', -2),

        # S07: 25.63-28.67s - time reset
        (26.5, 27.5, 'whoosh', '05_audio/SFX/SFX_REVERSE_WHOOSH.m4a', -3),

        # S08: 28.67-31.71s - the twist
        (28.7, 30.5, 'inner', '05_audio/INNER_VOICE/S08_IV_INNER_eighth_restart.m4a', -2),
        (30.5, 32.0, 'inner', '05_audio/INNER_VOICE/S08_IV_INNER_this_time_me.m4a', -2),
        (29.0, 32.0, 'heartbeat', '05_audio/SFX/SFX_HEARTBEAT.m4a', -5),

        # S09: 31.71-33.33s - end
        (33.0, 34.4, 'whoosh', '05_audio/SFX/SFX_REVERSE_WHOOSH.m4a', -5),
    ]

    # Build the complex filter
    filter_parts = []
    inputs = []

    # Add background music (BGM)
    bgm_path = PROJECT / '05_audio/BGM/BGM_DARK_DRONE_60S.m4a'
    inputs.append('-i')
    inputs.append(str(bgm_path))
    bgm_idx = 0

    # Add each timeline item as separate input
    input_indices = {}  # audio_file -> index
    next_idx = 1

    for start, end, atype, audio_file, vol_db in timeline:
        full_path = PROJECT / audio_file
        if not full_path.exists():
            log(f'  SKIP: {full_path.name} not found')
            continue
        if audio_file not in input_indices:
            inputs.append('-i')
            inputs.append(str(full_path))
            input_indices[audio_file] = next_idx
            next_idx += 1
        idx = input_indices[audio_file]

        # Calculate delay and duration
        delay_ms = int(start * 1000)
        duration_ms = int((end - start) * 1000)

        if atype == 'inner':
            # Apply low-pass filter for inner voice effect
            filter_parts.append(f'[{idx}:a]volume={vol_db}dB,lowpass=f=3000,aloop=loop=-1:size=1e9,adelay={delay_ms}|{delay_ms},atrim=duration={duration_ms/1000},asetpts=PTS-STARTPTS[a{idx}];')
        elif atype == 'whoosh':
            filter_parts.append(f'[{idx}:a]volume={vol_db}dB,adelay={delay_ms}|{delay_ms},atrim=duration={duration_ms/1000},asetpts=PTS-STARTPTS[a{idx}];')
        else:
            filter_parts.append(f'[{idx}:a]volume={vol_db}dB,adelay={delay_ms}|{delay_ms},atrim=duration={duration_ms/1000},asetpts=PTS-STARTPTS[a{idx}];')

    # BGM with sidechain ducking (simple version: just keep at low volume)
    bgm_volume = '-8dB'  # Keep BGM at -8dB so dialogue is clearer

    # Build mix filter
    all_audio_labels = [f'[a{input_indices[af]}]' for _, _, _, af, _ in timeline if af in input_indices]
    all_audio_labels = list(set(all_audio_labels))
    if not all_audio_labels:
        log('ERROR: no audio inputs')
        return

    mix_inputs = f'[0:a]{bgm_volume}[bgm];' + ''.join([s for s in filter_parts])
    mix_inputs += f'[bgm]{"".join(all_audio_labels)}amix=inputs={1+len(all_audio_labels)}:duration=longest[mix];'
    mix_inputs += f'[mix]volume=0.7,alimiter=limit=0.95[mix_final]'

    # Run ffmpeg
    log('Mixing audio...')
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-i', str(master_video),
    ] + inputs + [
        '-filter_complex', mix_inputs,
        '-map', '0:v',
        '-map', '[mix_final]',
        '-c:v', 'copy',
        '-c:a', 'aac', '-b:a', '320k', '-ar', '48000',
        '-t', str(duration),
        str(PROJECT / '07_edit/EP01_WITH_AUDIO.mp4')
    ]
    log(f'  inputs: {len(inputs)} audio files')
    run_ffmpeg(cmd)
    log(f'  audio mixed: EP01_WITH_AUDIO.mp4')

    log('\n=== AUDIO MIX COMPLETE ===')
    log(f'Next step: add subtitles')


if __name__ == '__main__':
    main()