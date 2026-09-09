"""Take selection + Picture Lock assembly for CEO Mindread EP01.

Strategy:
- For each shot, pick the best take (currently: T01 always wins as default)
- Concatenate all best takes with timing metadata
- Output a 720x1280 (or original 768x1344) rough cut

This is rough assembly - no audio, no transitions yet.
Final assembly with audio happens in `final_assembly.py`.
"""
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')


def log(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', flush=True)


def get_video_info(video_path):
    """Get fps and frame count of video."""
    out = subprocess.check_output([
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=avg_frame_rate,nb_frames,duration',
        '-of', 'json',
        str(video_path)
    ]).decode()
    info = json.loads(out)
    stream = info['streams'][0]
    fps_parts = stream['avg_frame_rate'].split('/')
    fps = float(fps_parts[0]) / float(fps_parts[1]) if float(fps_parts[1]) > 0 else 24
    nb_frames = int(stream.get('nb_frames', 0))
    duration = float(stream.get('duration', 0))
    return fps, nb_frames, duration


def main():
    # Default: pick T01 for each shot
    # User can override with: python select_takes.py S02_T02 S05B_T02
    overrides = sys.argv[1:]
    overrides_map = {}
    for o in overrides:
        # Format: S01_T02 -> shot S01, take T02
        parts = o.split('_T')
        if len(parts) == 2:
            overrides_map[parts[0]] = o

    # Shot definitions with target durations
    shot_targets = {
        'S01': 4.5,   # 4.5s
        'S02': 5.2,   # 5.2s
        'S03A': 1.6,  # 1.6s
        'S03B': 1.6,  # 1.6s
        'S03C': 1.6,  # 1.6s
        'S04': 4.5,   # 4.5s
        'S05A': 0.9,  # 0.9s
        'S05B': 3.8,  # 3.8s
        'S06': 5.2,   # 5.2s
        'S07': 3.8,   # 3.8s
        'S08': 3.8,   # 3.8s
        'S09': 2.3,   # 2.3s
    }

    raw_root = PROJECT / '03_video_raw'
    sel_root = PROJECT / '04_video_selected'
    sel_root.mkdir(parents=True, exist_ok=True)

    selections = {}
    for shot_id in shot_targets.keys():
        # Determine which take to use
        if shot_id in overrides_map:
            take = overrides_map[shot_id]
        else:
            take = f'{shot_id}_T01'

        src = raw_root / shot_id / f'{take}.mp4'
        if not src.exists():
            log(f'WARN: {src} does not exist!')
            continue
        dst = sel_root / f'{shot_id}.mp4'
        shutil.copy2(str(src), str(dst))
        fps, frames, duration = get_video_info(dst)
        selections[shot_id] = {
            'file': str(dst.relative_to(PROJECT)),
            'fps': fps,
            'frames': frames,
            'duration_s': duration,
            'target_s': shot_targets[shot_id],
            'source_take': take,
        }
        log(f'  {shot_id}: {take} -> {dst.name} ({frames}f, {duration:.2f}s)')

    # Write shot_manifest.json
    manifest = {
        'project': 'ceo_mindread_ep01',
        'created_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'selections': selections,
        'total_duration_s': sum(s['duration_s'] for s in selections.values()),
    }
    with open(PROJECT / '00_project/shot_manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    log(f'\nWritten: 00_project/shot_manifest.json')
    log(f'Total duration: {manifest["total_duration_s"]:.2f}s')

    # Concatenate into rough cut
    log('\n--- Concatenating rough cut ---')
    concat_list = sel_root / 'concat_list.txt'
    with open(concat_list, 'w', encoding='utf-8') as f:
        for shot_id in shot_targets.keys():
            if shot_id in selections:
                f.write(f"file '{sel_root / shot_id}.mp4'\n")

    rough_cut = PROJECT / '07_edit/EP01_PICTURE_LOCK_720P.mp4'
    rough_cut.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-f', 'concat', '-safe', '0',
        '-i', str(concat_list),
        '-c:v', 'libx264', '-preset', 'slow', '-crf', '18',
        '-pix_fmt', 'yuv420p',
        str(rough_cut)
    ]
    log(f'  cmd: {" ".join(cmd)}')
    subprocess.run(cmd, check=True)
    log(f'\n=== ROUGH CUT SAVED ===')
    log(f'  {rough_cut}')
    log(f'  size: {rough_cut.stat().st_size/1024/1024:.1f}MB')


if __name__ == '__main__':
    main()