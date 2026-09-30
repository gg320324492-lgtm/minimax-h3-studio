"""Take selection + Picture Lock assembly for CEO Mindread EP01.

Strategy:
- For each shot, pick the best take (currently: T01 always wins as default)
- Concatenate all best takes with timing metadata
- Output a 720x1280 (or original 768x1344) rough cut

This is rough assembly - no audio, no transitions yet.
Final assembly with audio happens in `final_assembly.py`.
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
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')

# Quality of the 720p picture lock. The lock is an INTERMEDIATE, not a
# deliverable: it is the source every later stage reads (upscale -> audio ->
# subtitles), so loss here propagates into the master. It used to be encoded at
# crf 18, i.e. a second lossy generation on top of the ComfyUI takes, for no
# benefit -- nothing ships the lock. crf 12 is near-visually-lossless at ~2x the
# file size of an intermediate nobody distributes. Override with EP01_LOCK_CRF.
LOCK_CRF = str(_os.environ.get('EP01_LOCK_CRF', '12'))

# P1: shared take ranking engine (graceful: falls back to hard failure, never T01)
_RANKER = None
try:
    _sys.path.insert(0, r'E:\Minimax-H3\studio\scripts')
    import take_ranker as _RANKER  # noqa: E402
except Exception as _e:  # noqa: BLE001
    print(f'[select_takes] WARNING: take_ranker unavailable ({_e}); '
          f'auto-ranking disabled', file=_sys.stderr)


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


def _auto_rank(shot_id, raw_root):
    """Rank this shot's takes via the shared TakeRanker (studio/scripts)."""
    if _RANKER is None:
        return [], None, 'take_ranker unavailable (cannot import studio/scripts)'
    shot_dir = raw_root / shot_id
    if not shot_dir.exists():
        return [], None, f'no raw dir {shot_dir}'
    takes = sorted(p for p in shot_dir.glob('*.mp4') if p.is_file())
    if not takes:
        return [], None, f'no take files in {shot_dir}'
    metrics = [_RANKER.analyze(p) for p in takes]
    for i, a in enumerate(metrics):
        if a.hard_fail or a._sig is None:
            continue
        for b in metrics[:i]:
            if b.redundant_with or b._sig is None:
                continue
            if _RANKER.signature_distance(a._sig, b._sig) < 1.0:
                a.redundant_with = b.take_id
                break
    metrics.sort(key=lambda m: (m.hard_fail is not None, m.redundant_with is not None, -m.score))
    usable = [m for m in metrics if not m.hard_fail and not m.redundant_with]
    if not usable:
        return metrics, None, f'all {len(metrics)} takes failed or are duplicates'
    return metrics, usable[0].take_id, None


def main():
    # P1: automatic take ranking replaces the old "T01 always wins" default.
    #   no override  -> take_ranker analyzes every take and picks the winner
    #   override     -> human decision always wins
    # Usage: python select_takes.py [S02_T02 S05B_T02 ...]
    overrides = sys.argv[1:]
    overrides_map = {}
    for o in overrides:
        # Format: S01_T02 -> shot S01, take S01_T02
        parts = o.split('_T')
        if len(parts) == 2:
            overrides_map[parts[0]] = o
        else:
            log(f'WARN: ignoring malformed override {o!r} (want S01_T02)')

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
    failures = []
    for shot_id in shot_targets.keys():
        # Determine which take to use
        if shot_id in overrides_map:
            take = overrides_map[shot_id]
            log(f'{shot_id}: human override -> {take}')
        else:
            take = None

        src = raw_root / shot_id / f'{take}.mp4' if take else None
        if take is None:
            # auto-rank every take in this shot
            ranked, winner, err = _auto_rank(shot_id, raw_root)
            if err or winner is None:
                log(f'FAIL {shot_id}: {err}')
                failures.append(f'{shot_id}: {err}')
                continue
            log(f'{shot_id}: auto-ranked -> {winner} (of {len(ranked)} takes)')
            src = raw_root / shot_id / f'{winner}.mp4'

        if not src or not src.exists():
            log(f'FAIL {shot_id}: {src} does not exist!')
            failures.append(f'{shot_id}: missing {src}')
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
            # P1: `take` is None on the auto-rank path; src.stem is the real
            # take id in both paths (qa_final.py reads this field).
            'source_take': src.stem,
        }
        log(f'  {shot_id}: {src.stem} -> {dst.name} ({frames}f, {duration:.2f}s)')

    # Fail closed: a missing shot must not silently shorten the episode.
    # (The old code did `continue` on a missing take, so the shot vanished from
    #  the manifest and from the concat with a zero exit code.)
    if failures:
        log(f'\n=== FAILED: {len(failures)} shot(s) have no usable take ===')
        for f_ in failures:
            log(f'  ! {f_}')
        log('shot_manifest.json NOT written; fix the missing takes or pass an override.')
        sys.exit(1)

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
        '-c:v', 'libx264', '-preset', 'slow', '-crf', LOCK_CRF,
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