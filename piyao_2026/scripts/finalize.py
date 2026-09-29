"""Finalize piyao_2026: copy the delivery into 09_final/, extract a cover frame,
mirror to the desktop, and write a delivery manifest (seeds + timings).
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

if r'E:\Minimax-H3' not in sys.path:
    sys.path.insert(0, r'E:\Minimax-H3')
from ffmpeg_env import prepend_to_path  # noqa: E402
prepend_to_path()

PROJECT = Path(r'E:/Minimax-H3/piyao_2026')
FINAL = PROJECT / '09_final'
DESKTOP = Path(r'C:/Users/pc/Desktop/MiniMax-H3-Outputs/piyao_2026/09_final')
SRC = PROJECT / '07_edit/PIYAO_WITH_SUBTITLES.mp4'
NAME = '它只是换了一个地名_参赛版_1080P.mp4'

CFG = json.loads((PROJECT / '00_project/shots.json').read_text(encoding='utf-8'))


def main():
    if not SRC.exists():
        print(f'ERROR: {SRC} not found')
        sys.exit(1)
    FINAL.mkdir(parents=True, exist_ok=True)
    dst = FINAL / NAME
    shutil.copy2(SRC, dst)
    print(f'delivery: {dst}')

    tl = json.loads((PROJECT / '00_project/timeline.json').read_text(encoding='utf-8'))
    cover_at = tl['shot_boundaries']['S12']['start'] + 5.0
    cover = FINAL / '封面_麦田.jpg'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(cover_at),
                    '-i', str(dst), '-frames:v', '1', '-q:v', '2', str(cover)], check=True)
    print(f'cover: {cover} (t={cover_at:.2f}s)')

    seeds = json.loads((PROJECT / '00_project/seed_manifest.json').read_text(encoding='utf-8'))
    manifest = {
        'project': CFG['project'],
        'title': CFG['title'],
        'theme': CFG['theme'],
        'delivered_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'file': NAME,
        'duration_s': tl['total_duration'],
        'resolution': f"{CFG['out_width']}x{CFG['out_height']}",
        'fps': CFG['fps'],
        'audio': 'AAC 48kHz stereo, loudnorm -14 LUFS',
        'ai_label': '本内容经AI技术辅助生成（角标持续显示 + 片尾卡）',
        'shots': seeds.get('shots', {}),
    }
    (FINAL / 'delivery_manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')

    if DESKTOP.parent.exists():
        DESKTOP.mkdir(parents=True, exist_ok=True)
        for f in (dst, cover, FINAL / 'delivery_manifest.json'):
            shutil.copy2(f, DESKTOP / f.name)
        print(f'desktop mirror: {DESKTOP}')
    else:
        print(f'desktop dir not found, skipped: {DESKTOP.parent}')


if __name__ == '__main__':
    main()
