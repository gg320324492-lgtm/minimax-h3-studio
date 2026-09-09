"""Properly timed audio mix for CEO Mindread EP01.

Uses ffmpeg's adelay filter to position each audio clip at the correct time.
"""
import subprocess
from pathlib import Path

PROJECT = Path(r'E:/Minimax-H3/ceo_mindread_ep01')
master = PROJECT / '07_edit/EP01_PICTURE_MASTER_1080P.mp4'

# Timeline: (start_seconds, end_seconds, audio_path, type)
timeline = [
    # S01
    (0.5, 4.0, '05_audio/CEO/S01_DLG_CEO_intern_hands_report.m4a', 'dialogue'),
    (3.0, 4.4, '05_audio/SFX/SFX_LOW_PULSE.m4a', 'sfx'),

    # S02 - inner voice countdown
    (4.5, 8.5, '05_audio/INNER_VOICE/S01_IV_INNER_completed.m4a', 'inner'),
    (5.0, 9.0, '05_audio/INNER_VOICE/S02_IV_INNER_six_five_four.m4a', 'inner'),

    # S03 - lamp crash
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

# BGM with loop
bgm_path = PROJECT / '05_audio/BGM/BGM_DARK_DRONE_60S.m4a'

# Collect unique audio files and assign indices
audio_files = [(bgm_path, 'bgm')]  # index 1
audio_indices = {}  # path -> index

for start, end, audio_file, atype in timeline:
    full_path = PROJECT / audio_file
    if full_path.exists() and str(full_path) not in audio_indices:
        audio_indices[str(full_path)] = len(audio_files) + 1  # +1 for video
        audio_files.append((full_path, atype))

# Build inputs
inputs = ['-i', str(master)]
for path, _ in audio_files:
    inputs.extend(['-i', str(path)])

# Build filter
filter_parts = []

# BGM: loop to video duration, volume 0.25
bgm_idx = 1  # First audio (after video at 0)
filter_parts.append(
    f'[{bgm_idx}:a]aloop=loop=-1:size=1e9,'
    f'atrim=duration={duration},'
    f'volume=0.25[bgm];'
)

# All timeline audio
for start, end, audio_file, atype in timeline:
    full_path = PROJECT / audio_file
    if not full_path.exists():
        continue
    idx = audio_indices[str(full_path)]
    delay_ms = int(start * 1000)
    dur_s = end - start

    # Inner voice gets low-pass + slight volume reduce
    if atype == 'inner':
        filter_parts.append(
            f'[{idx}:a]volume=0.7,lowpass=f=4000,'
            f'adelay={delay_ms}|{delay_ms},'
            f'atrim=duration={dur_s},'
            f'asetpts=PTS-STARTPTS[a{idx}];'
        )
    elif atype == 'dialogue':
        filter_parts.append(
            f'[{idx}:a]volume=1.0,'
            f'adelay={delay_ms}|{delay_ms},'
            f'atrim=duration={dur_s},'
            f'asetpts=PTS-STARTPTS[a{idx}];'
        )
    else:  # sfx
        filter_parts.append(
            f'[{idx}:a]volume=0.7,'
            f'adelay={delay_ms}|{delay_ms},'
            f'atrim=duration={dur_s},'
            f'asetpts=PTS-STARTPTS[a{idx}];'
        )

# Collect all unique audio labels
audio_labels = set()
audio_labels.add('[bgm]')
for start, end, audio_file, atype in timeline:
    full_path = PROJECT / audio_file
    if not full_path.exists():
        continue
    idx = audio_indices[str(full_path)]
    audio_labels.add(f'[a{idx}]')

n_inputs = len(audio_labels)
mix = ''.join(audio_labels) + f'amix=inputs={n_inputs}:duration=longest[mix];'
mix += '[mix]volume=0.85,alimiter=limit=0.97[mix_final]'

# Combine
filter_complex = ''.join(filter_parts) + mix

# Run ffmpeg
cmd = [
    'ffmpeg', '-y', '-loglevel', 'error',
] + inputs + [
    '-filter_complex', filter_complex,
    '-map', '0:v',
    '-map', '[mix_final]',
    '-c:v', 'copy',
    '-c:a', 'aac', '-b:a', '320k', '-ar', '48000',
    '-t', str(duration),
    str(PROJECT / '07_edit/EP01_WITH_AUDIO.mp4')
]

print(f'Running ffmpeg with {n_inputs} audio sources, duration {duration:.1f}s...')
print(f'Filter ({len(filter_complex)} chars): {filter_complex[:200]}...')
r = subprocess.run(cmd, capture_output=True)
if r.returncode != 0:
    print('STDERR:', r.stderr.decode()[:1500])
    raise RuntimeError('ffmpeg failed')
else:
    out = PROJECT / '07_edit/EP01_WITH_AUDIO.mp4'
    print(f'DONE: {out} ({out.stat().st_size/1024/1024:.1f}MB)')