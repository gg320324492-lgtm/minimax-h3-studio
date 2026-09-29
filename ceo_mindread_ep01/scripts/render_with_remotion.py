"""One-command Remotion render: stage -> render -> (optional) QA.

Replaces the old chain's concat+subtitle stages for EP01-style projects:
  timeline_v2.json -> stage_assets.py -> node bin/render.mjs -> MP4 -> qa_final.py

The old ffmpeg/PIL chain remains untouched as fallback; if this script fails,
run_post_chain.sh still produces a delivery the previous way.

Usage:
  E:/ComfyUI/venv/Scripts/python.exe ceo_mindread_ep01/scripts/render_with_remotion.py \
      --job ep01_v3 --out 07_edit/EP01_V3_REMOTION.mp4 [--qa]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')
EP01 = ROOT / 'ceo_mindread_ep01'
STUDIO = ROOT / 'studio'
VENV_PY = r'E:\ComfyUI\venv\Scripts\python.exe'


def run(cmd, **kw) -> int:
    print(f'+ {" ".join(str(c) for c in cmd)}', flush=True)
    return subprocess.run([str(c) for c in cmd], **kw).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--job', required=True)
    ap.add_argument('--timeline', default='00_project/timeline_v2.json')
    ap.add_argument('--comp', default='DramaVertical')
    ap.add_argument('--out', default='07_edit/EP01_V3_REMOTION.mp4')
    ap.add_argument('--concurrency', type=int, default=16)
    ap.add_argument('--crf', type=float, default=18)
    ap.add_argument('--qa', action='store_true', help='run qa_final.py on the output')
    ap.add_argument('--master', action='store_true',
                    help='master audio to -14 LUFS via studio/scripts/master_audio.py '
                         '(WAV 中转 loudnorm；drama 链混音已锁响度时不需要)')
    ap.add_argument('--karaoke', action='store_true',
                    help='word-level timestamps: transcribe premixed audio and inject into timeline before staging')
    args = ap.parse_args()

    # 0.5. optional karaoke: inject words into timeline sidecar (Phase 3.2)
    timeline_arg = args.timeline
    if args.karaoke:
        tl_path = EP01 / args.timeline
        words_out = tl_path.with_suffix('.words.json')
        if run([VENV_PY, ROOT / 'studio' / 'scripts' / 'word_timestamps.py',
                '--timeline', tl_path, '--audio', EP01 / '07_edit' / 'EP01_WITH_AUDIO.mp4']) != 0:
            print('word injection failed (continuing without karaoke)', file=sys.stderr)
        else:
            args.timeline = str(words_out.relative_to(EP01))

    # 1. stage
    if run([VENV_PY, EP01 / 'scripts' / 'stage_assets.py', '--job', args.job,
            '--timeline', args.timeline]) != 0:
        print('staging failed', file=sys.stderr)
        return 1
    props = STUDIO / 'public' / 'jobs' / args.job / 'props.json'

    # 2. render (Node API; 定稿参数见 studio/BENCHMARK_20260929.md)
    out_path = EP01 / args.out
    if run(['node', STUDIO / 'bin' / 'render.mjs',
            '--comp', args.comp, '--props', props, '--out', out_path,
            '--crf', args.crf, '--concurrency', args.concurrency]) != 0:
        print('render failed; 旧链仍可用：run_post_chain.sh（回退路径未受影响）', file=sys.stderr)
        return 1

    # 2.5. optional audio master (Phase 6.1)
    if args.master:
        if run([VENV_PY, ROOT / 'studio' / 'scripts' / 'master_audio.py', out_path]) != 0:
            print('audio master finished out of range (check levels)', file=sys.stderr)

    # 3. optional QA（qa_final 期望 <EP01_FINAL_DIR>/EP01_DOUYIN_FINAL.mp4）
    if args.qa:
        qa_dir = Path(tempfile.mkdtemp(prefix='ep01_qa_'))
        hard = qa_dir / 'EP01_DOUYIN_FINAL.mp4'
        try:
            os.link(out_path, hard)
        except OSError:
            import shutil
            shutil.copy2(out_path, hard)
        env = dict(os.environ, EP01_FINAL_DIR=str(qa_dir))
        rc = run([VENV_PY, EP01 / 'scripts' / 'qa_final.py'], cwd=EP01, env=env)
        print(f'qa rc={rc}, report at {qa_dir / "qa_report.md"}')
        return rc

    print(f'DONE: {out_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
