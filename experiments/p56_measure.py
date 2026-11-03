"""P56 measurement: one A/B video in, one JSON of facts out.

Per video:
  - ffprobe specs (codec / size / fps / frame count / audio)
  - freeze segments via ffmpeg freezedetect
  - adjacent-frame diff (pixels differing >8, the ab_field threshold) over
    evenly sampled frames, with the pct distribution and any frozen runs
  - three comparison frames (first / middle / last sampled) copied to
    out/p56/compare/{scene}_{side}_f{NNN}.png for the user's own eyes
  - four closed VLM questions per frame (subtitle words MEET and MAKER, the
    numeral 7, the roar) via studio/scripts/vlm_critic.py — an element counts
    as hit if any frame answers yes; --skip-vlm drops this leg

Usage: python p56_measure.py <video.mp4> <scene> <A|B> [--skip-vlm]
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(r'E:\Minimax-H3\studio\scripts')))
from vlm_critic import ask_vlm, parse_verdict  # noqa: E402

OUT56 = Path(r'E:\Minimax-H3\out\p56')
COMPARE = OUT56 / 'compare'
N_SAMPLES = 31
DIFF_THRESHOLD = 8  # ab_field's per-pixel delta threshold

QUESTIONS = {
    'subtitle_MEET': 'Does the image show the word "MEET" as large '
                     'comic-book lettering? Answer YES or NO.',
    'subtitle_MAKER': 'Does the image show the word "MAKER" as large '
                      'comic-book lettering? Answer YES or NO.',
    'numeral_7': 'Is the numeral 7 visible anywhere in the image? '
                 'Answer YES or NO.',
    'roar_jaws_open': 'Is the giant black creature roaring with its jaws '
                      'wide open? Answer YES or NO.',
}


def ffprobe_specs(path):
    out = subprocess.run(
        ['ffprobe', '-v', 'error', '-print_format', 'json',
         '-show_streams', str(path)],
        capture_output=True, text=True, check=True).stdout
    streams = json.loads(out)['streams']
    return {
        'video': [{k: s.get(k) for k in
                   ('codec_name', 'width', 'height', 'r_frame_rate',
                    'nb_frames', 'pix_fmt')}
                  for s in streams if s['codec_type'] == 'video'],
        'audio': [{k: s.get(k) for k in
                   ('codec_name', 'channels', 'sample_rate')}
                  for s in streams if s['codec_type'] == 'audio'],
    }


def freeze_segments(path):
    proc = subprocess.run(
        ['ffmpeg', '-hide_banner', '-nostats', '-i', str(path),
         '-vf', 'freezedetect=n=0.003:d=0.4', '-an', '-f', 'null', '-'],
        capture_output=True, text=True)
    segs = []
    start = None
    for line in proc.stderr.splitlines():
        m = re.search(r'freeze_start: ([\d.]+)', line)
        if m:
            start = float(m.group(1))
        m = re.search(r'freeze_duration: ([\d.]+)', line)
        if m and start is not None:
            segs.append({'start': start, 'duration': float(m.group(1))})
            start = None
    return segs


def sample_frames(path, tmpdir):
    """Extract N_SAMPLES evenly spaced frames; return sorted PNG paths."""
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
         '-print_format', 'json', '-show_streams', str(path)],
        capture_output=True, text=True, check=True).stdout
    n = int(json.loads(probe)['streams'][0].get('nb_read_frames')
            or json.loads(probe)['streams'][0].get('nb_frames') or 0)
    picks = sorted({round(i * (n - 1) / (N_SAMPLES - 1))
                    for i in range(N_SAMPLES)})
    for idx in picks:
        subprocess.run(
            ['ffmpeg', '-y', '-v', 'error', '-i', str(path),
             '-vf', f"select=eq(n\\,{idx})", '-vsync', '0', '-frames:v', '1',
             str(tmpdir / f'f{idx:03d}.png')], check=True)
    return n, sorted(tmpdir.glob('f*.png'))


def adjacent_diffs(frames):
    import numpy as np
    from PIL import Image
    pcts = []
    for a, b in zip(frames, frames[1:]):
        ia = np.asarray(Image.open(a).convert('RGB')).astype(np.int16)
        ib = np.asarray(Image.open(b).convert('RGB')).astype(np.int16)
        d = np.abs(ia - ib).max(axis=2)
        pcts.append(round(float((d > DIFF_THRESHOLD).mean() * 100), 4))
    return pcts


def vlm_leg(frames):
    """One closed question per element per frame; an element hits if any
    frame says yes. Raw answers are kept for the report."""
    matrix = {k: [] for k in QUESTIONS}
    for f in frames:
        for key, question in QUESTIONS.items():
            answer, why = ask_vlm(f, question)
            verdict = parse_verdict(answer) if answer else None
            matrix[key].append({'frame': f.name, 'answer': answer,
                                'verdict': verdict, 'why': why})
    return {k: {
        'hit': any(v['verdict'] for v in vs),
        'yes_frames': [v['frame'] for v in vs if v['verdict']],
        'answers': vs,
    } for k, vs in matrix.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video', type=Path)
    ap.add_argument('scene')
    ap.add_argument('side', choices=('A', 'B'))
    ap.add_argument('--skip-vlm', action='store_true')
    args = ap.parse_args()

    COMPARE.mkdir(parents=True, exist_ok=True)
    result = {'video': str(args.video), 'scene': args.scene,
              'side': args.side}
    result['specs'] = ffprobe_specs(args.video)
    result['freezes'] = freeze_segments(args.video)

    with tempfile.TemporaryDirectory(
            dir=str(OUT56)) as td:  # E drive only: the project must not
        # write to C:, and the default TEMP lives there
        tmpdir = Path(td)
        n, frames = sample_frames(args.video, tmpdir)
        result['frame_count'] = n
        pcts = adjacent_diffs(frames)
        result['adjacent_diff_pct'] = {
            'n_pairs': len(pcts), 'min': min(pcts), 'median': sorted(pcts)[
                len(pcts) // 2], 'max': max(pcts), 'per_pair': pcts}
        # a "frozen run": consecutive sampled gaps whose changed-pixel
        # fraction is near zero
        frozen = [p for p in pcts if p < 0.05]
        result['near_frozen_pairs'] = len(frozen)

        picks = [frames[0], frames[len(frames) // 2], frames[-1]]
        compare_names = []
        for f in picks:
            dst = COMPARE / f'{args.scene}_{args.side}_{f.stem}.png'
            shutil.copy2(f, dst)
            compare_names.append(str(dst))
        result['compare_frames'] = compare_names

        if not args.skip_vlm:
            result['vlm'] = vlm_leg(picks + [frames[len(frames) // 4],
                                             frames[3 * len(frames) // 4]])

    dst = OUT56 / f'measure_{args.scene}_{args.side}.json'
    dst.write_bytes(json.dumps(result, ensure_ascii=True,
                               indent=1).encode('utf-8'))
    print(json.dumps({k: v for k, v in result.items()
                      if k not in ('adjacent_diff_pct',)}, ensure_ascii=True,
                     indent=1)[:3000])
    print(f'[measure] full result -> {dst}')


if __name__ == '__main__':
    main()
