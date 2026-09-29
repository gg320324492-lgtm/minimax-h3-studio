"""Standard output path constants for all video projects.

All new video generation tasks should use these paths.
Place all videos under C:/Users/pc/Desktop/MiniMax-H3-Outputs/
"""
from pathlib import Path

# Master output directory on desktop
OUTPUTS_ROOT = Path(r'C:/Users/pc/Desktop/MiniMax-H3-Outputs')

# Standard subfolder structure
SUBFOLDERS = {
    'ep01_final': 'EP01_CEO_Mindread/09_final',
    'ep01_raw': 'EP01_CEO_Mindread/03_video_raw',
    'ep01_selected': 'EP01_CEO_Mindread/04_video_selected',
    'ep01_audio': 'EP01_CEO_Mindread/05_audio',
    'lulu': 'Lulu_Animations',
    'benchmarks_768p': 'Video_Benchmarks/768p',
    'benchmarks_2k': 'Video_Benchmarks/2K',
    'benchmarks_4k': 'Video_Benchmarks/4K',
    'realesrgan_tests': 'Real_ESRGAN_Tests',
    'seedvr2_tests': 'SeedVR2_Tests',
}


def get_path(folder_key, filename=None):
    """Get a path under the outputs root.

    Usage:
        from outputs_paths import get_path
        ep01_path = get_path('ep01_final', 'EP01_DOUYIN_FINAL.mp4')
    """
    folder = OUTPUTS_ROOT / SUBFOLDERS[folder_key]
    folder.mkdir(parents=True, exist_ok=True)
    if filename:
        return folder / filename
    return folder


if __name__ == '__main__':
    print(f'Output root: {OUTPUTS_ROOT}')
    print('Available subfolders:')
    for key, path in SUBFOLDERS.items():
        full = OUTPUTS_ROOT / path
        exists = '[OK]' if full.exists() else '[ ]'
        print(f'  {exists} {key}: {path}')