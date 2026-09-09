"""Properly timed audio mix using -itsoffset for input timing.

Alternative simpler approach: use -itsoffset for each audio input.
"""
import subprocess
from pathlib import Path

PROJECT = Path(r'E:/Minimax-H3/ceo_mindread_ep01')
master = PROJECT / '07_edit/EP01_PICTURE_MASTER_1080P.mp4'

# Timeline: (start_seconds, end_seconds, audio_file, type)
timeline = [
    # S01
    (0.5, 4.0, '05_audio/CEO/S01_DLG_CEO_intern_hands_report.m4a', 'dialogue'),
    (3.0, 4.4, '05_audio/SFX/SFX_LOW_PULSE.m4a', 'sfx'),

    # S02
    (4.5, 8.5, '05_audio/INNER_VOICE/S01_IV_INNER_completed.m4a', 'inner'),
    (5.0, 9.0, '05_audio/INNER_VOICE/S02_IV_INNER_six_five_four.m4a', 'inner'),

    # S03
    (9.6, 11.5, '05_audio/INNER_VOICE/S03_IV_INNER_three_two.m4a', 'inner'),
    (12.0, 13.5, '05_audio/SFX/SFX_IMPACT.m4a', 'sfx'),

    # S04
    (13.5, 17.0, '05_audio/INNER_VOICE/S04_IV_INNER_he_should_have_died.m4a', 'inner'),

    # S05
    (18.0, 21.0, '05_audio/INTERN/S05_DLG_INTERN_coffee.m4a', 'dialogue'),
    (19.0, 21.5, '05_audio/INNER_VOICE/S05_IV_INNER_peanut_allergy.m4a', 'inner'),

    # S06
    (22.0, 23.0, '05_audio/CEO/S06_DLG_CEO_lin_xiaoyu.m4a', 'dialogue'),
    (23.0, 24.0, '05_audio/INTERN/S06_DLG_INTERN_response.m4a', 'dialogue'),
    (24.0, 25.0, '05_audio/CEO/S06_DLG_CEO_who_are_you.m4a', 'dialogue'),
    (25.0, 25.5, '05_audio/INTERN/S06_DLG_INTERN_intern.m4a', 'dialogue'),
    (25.0, 26.5, '05_audio/INNER_VOICE/S06_IV_INNER_eighth_loop.m4a', 'inner'),

    # S07
    (26.5, 27.5, '05_audio/SFX/SFX_REVERSE_WHOOSH.m4a', 'sfx'),

    # S08
    (28.7, 30.5, '05_audio/INNER_VOICE/S08_IV_INNER_eighth_restart.m4a', 'inner'),
    (30.5, 32.0, '05_audio/INNER_VOICE/S08_IV_INNER_this_time_me.m4a', 'inner'),
    (29.0, 32.0, '05_audio/SFX/SFX_HEARTBEAT.m4a', 'sfx'),

    # S09
    (33.0, 34.4, '05_audio/SFX/SFX_REVERSE_WHOOSH.m4a', 'sfx'),
]

# Get video duration
r = subprocess.check_output([
    'ffprobe', '-v', 'error',
    '-show_entries', 'format=duration',
    '-of', 'default=noprint_wrappers=1:nokey=1',
    str(master)
])
duration = float(r.decode().strip())
print(f'Duration: {duration:.2f}s')

# Build the command
# Format: ffmpeg -i video -i audio1 -i audio2 ... -itsoffset T1 -i audio1 -itsoffset T2 -i audio2 ...
# But we need to mix them all
# Simpler: use -ss in input to skip ahead

# Actually let's use a single filter_complex with concat/amix
# Build a filter that delays each audio to its proper start time, then mixes

# Strategy:
# - Each audio is pre-padded with silence to its start time
# - All padded audio are mixed together
# - BGM loops the entire duration

filter_parts = []

# Get unique audio files
unique_audio = {}  # path -> idx
audio_files = []

# Build inputs and indices
inputs = ['-i', str(master)]
next_idx = 1
unique_audio['__video__'] = 0

# BGM first
bgm_path = PROJECT / '05_audio/BGM/BGM_DARK_DRONE_60S.m4a'
if bgm_path.exists():
    inputs.extend(['-i', str(bgm_path)])
    unique_audio[str(bgm_path)] = next_idx
    next_idx += 1

# Other audio files
for start, end, audio_file, atype in timeline:
    full_path = PROJECT / audio_file
    if not full_path.exists():
        continue
    if str(full_path) not in unique_audio:
        inputs.extend(['-i', str(full_path)])
        unique_audio[str(full_path)] = next_idx
        next_idx += 1

# Build filter using apad + adelay to position audio
# BGM: loop entire duration
bgm_idx = unique_audio.get(str(bgm_path), -1)
if bgm_idx > 0:
    filter_parts.append(
        f'[{bgm_idx}:a]aloop=loop=-1:size=1e9,atrim=0:duration={duration},volume=0.25[bgmout]'
    )

# For each timeline audio
for start, end, audio_file, atype in timeline:
    full_path = PROJECT / audio_file
    if not full_path.exists():
        continue
    idx = unique_audio[str(full_path)]
    delay_ms = int(start * 1000)

    # Apply delay using adelay filter (in milliseconds)
    if atype == 'inner':
        filter_parts.append(
            f'[{idx}:a]volume=0.7,lowpass=f=4000,adelay={delay_ms}|{delay_ms}[a{idx}]'
        )
    elif atype == 'dialogue':
        filter_parts.append(
            f'[{idx}:a]volume=1.0,adelay={delay_ms}|{delay_ms}[a{idx}]'
        )
    else:  # sfx
        filter_parts.append(
            f'[{idx}:a]volume=0.7,adelay={delay_ms}|{delay_ms}[a{idx}]'
        )

# Collect all output labels
labels = ['[bgmout]'] if bgm_idx > 0 else []
for start, end, audio_file, atype in timeline:
    full_path = PROJECT / audio_file
    if not full_path.exists():
        continue
    idx = unique_audio[str(full_path)]
    labels.append(f'[a{idx}]')

# Mix all together
n_inputs = len(labels)
mix = ''.join(labels) + f'amix=inputs={n_inputs}:duration=longest:dropout_transition=0[mix];'
mix += '[mix]volume=0.85,alimiter=limit=0.97[mix_final]'

# Combine with semicolons
filter_complex = ';'.join(filter_parts) + ';' + mix

print(f'\nFilter ({len(filter_complex)} chars):')
print(filter_complex[:300] + '...')

cmd = ['ffmpeg', '-y', '-loglevel', 'error'] + inputs + [
    '-filter_complex', filter_complex,
    '-map', '0:v',
    '-map', '[mix_final]',
    '-c:v', 'copy',
    '-c:a', 'aac', '-b:a', '320k', '-ar', '48000',
    '-t', str(duration),
    str(PROJECT / '07_edit/EP01_WITH_AUDIO.mp4')
]

print(f'\nRunning ffmpeg with {n_inputs} audio sources...')
r = subprocess.run(cmd, capture_output=True)
if r.returncode != 0:
    print('STDERR:', r.stderr.decode()[:1500])
    raise RuntimeError('ffmpeg failed')
else:
    out = PROJECT / '07_edit/EP01_WITH_AUDIO.mp4'
    print(f'DONE: {out} ({out.stat().st_size/1024/1024:.1f}MB)')