"""Take selection with real ranking (P1) — replaces the T01-always default.

    03_video_raw/<SHOT>/*.mp4
        -> cheap metrics (take_ranker.analyze)
        -> near-duplicate detection (same-seed wastes are flagged redundant)
        -> ranking
        -> human override wins, always
        -> winner copied to 04_video_selected/<SHOT>.mp4
        -> report written to 00_project/take_ranking.json + 00_project/take_report.md

Fail-closed: a shot with no usable take is an ERROR (the old code silently
dropped it with `continue`, shortening the episode without a non-zero exit).

Usage:
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/rank_takes.py --project ceo_mindread_ep01
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/rank_takes.py --project ceo_mindread_ep01 --dry-run
  ... --override S06=S06_T02 --override S05A=S05A_v1
"""

from __future__ import annotations

import argparse
import json
import shutil

import cv2
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from take_ranker import TakeMetrics, analyze, signature_distance  # noqa: E402

ROOT = Path(r'E:\Minimax-H3')
# Same-seed reruns are pixel-identical (mean abs diff == 0.000 measured on
# EP01 S06_T01 vs S06_T02). Real generations are far away: the measured
# distribution over 9 real take pairs was {0.000} ∪ [34.5, 67.2] — nothing in
# between — so 0.5 sits on the true duplicate with ~34x margin.
#
# KNOWN LIMIT (recorded 2026-09-30 after review): this catches *exact*
# duplicates only. A rerun with a non-deterministic sampler would land at a
# small-but-nonzero distance and slip through. Revisit the threshold (and the
# sample size — n=1 real duplicate so far) whenever more multi-take shots land.
#
# P20 re-measured on the WHOLE corpus (2026-10-03, all 16 takes -> 120 pairs,
# not just same-shot ones): still {0.000} ∪ [31.264, 105.839], and the
# within-shot pairs the rule can actually see are {0.000} ∪ [34.543, 62.820].
# So the gap P1 recorded is real and 0.5 still sits ~63x below the nearest
# genuine pair. Note WHAT the measurement does NOT pin down: 0.5 is not
# derived from this distribution, it is merely inside the gap. Anything in
# (0.0, 34.543) gives the same verdict on every pair that exists, so the corpus
# cannot choose a number here. `select_takes.py` used 1.0 for the same question
# over the same population — that second literal is gone (P20); it is imported
# below rather than retyped.
DUP_THRESHOLD = 0.5


def find_takes(raw_dir: Path) -> list[Path]:
    """All take files for a shot. Accepts T01-style and legacy v1/v2 names."""
    files = sorted(p for p in raw_dir.glob('*.mp4') if p.is_file())
    return files


def rank_shot(shot_id: str, raw_dir: Path) -> tuple[list[TakeMetrics], str | None, str | None]:
    """Returns (metrics sorted best-first, winner_id, hard_error)."""
    takes = find_takes(raw_dir)
    if not takes:
        return [], None, f'{shot_id}: no take files in {raw_dir}'

    metrics = [analyze(p) for p in takes]

    # near-duplicate marking: same seed => pixel-identical => ranking is noise
    for i, a in enumerate(metrics):
        if a.hard_fail or a._sig is None:
            continue
        for b in metrics[:i]:
            if b.redundant_with or b._sig is None:
                continue
            if signature_distance(a._sig, b._sig) < DUP_THRESHOLD:
                a.redundant_with = b.take_id
                a.notes.append(f'pixel-identical to {b.take_id} (same seed — generation wasted)')
                break

    def sort_key(m: TakeMetrics):
        return (m.hard_fail is not None, m.redundant_with is not None, -m.score)

    metrics.sort(key=sort_key)
    usable = [m for m in metrics if not m.hard_fail and not m.redundant_with]
    if not usable:
        return metrics, None, f'{shot_id}: every take failed or is redundant ({len(metrics)} files)'
    return metrics, usable[0].take_id, None


def write_contact_sheet(proj: Path, report: dict, out_html: Path) -> None:
    """One row per take, 4 sampled frames each — the human tie-breaker surface."""
    import base64
    from take_ranker import read_probe_frames

    css = ('body{font:14px/1.5 system-ui;margin:24px;background:#111;color:#eee}'
           'h2{margin:28px 0 8px}table{border-collapse:collapse}'
           'td,th{padding:6px 10px;vertical-align:top;text-align:left}'
           'img{width:110px;border-radius:3px;display:block}'
           '.win{outline:2px solid #FFD866}.fail{color:#ff7676}.dup{color:#888}')
    rows = [f'<h1>Take 联系表 — {proj.name}</h1>',
            '<p>人工复核用：<b>黄框</b>=自动选中，<span class="fail">红字</span>=硬失败，'
            '<span class="dup">灰字</span>=与前者像素相同（同 seed 浪费）。</p>']
    for sid, rep in report.items():
        if 'winner' not in rep:
            continue
        rows.append(f'<h2>{sid} → {rep["winner"]}'
                    f'{"（人工指定）" if rep["overridden"] else ""}</h2><table><tr><th>take</th><th>score</th><th>帧</th></tr>')
        for t in rep['takes']:
            cells = []
            for img in read_probe_frames(Path(t['path']), max_frames=4):
                b = base64.b64encode(cv2.imencode('.jpg', img)[1].tobytes()).decode()
                cells.append(f'<img src="data:image/jpeg;base64,{b}">')
            cls = ' class="win"' if t['take_id'] == rep['winner'] else ''
            name = t['take_id']
            if t['hard_fail']:
                name += f' <span class="fail">({t["hard_fail"]})</span>'
            elif t['redundant_with']:
                name += f' <span class="dup">(= {t["redundant_with"]})</span>'
            rows.append(f'<tr{cls}><td><b>{name}</b></td><td>{t["score"]:.3f}</td><td>{"".join(cells)}</td></tr>')
        rows.append('</table>')
    out_html.write_text('<meta charset="utf-8">' + ''.join(rows), encoding='utf-8')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--project', default='ceo_mindread_ep01')
    ap.add_argument('--override', action='append', default=[],
                    help='SHOT=TAKE_ID — always wins over the ranking')
    ap.add_argument('--dry-run', action='store_true', help='rank and report, copy nothing')
    ap.add_argument('--min-margin', type=float, default=0.0,
                    help='require winner to beat runner-up by this much, else flag for review')
    ap.add_argument('--contact-sheet', action='store_true',
                    help='write 00_project/contact_sheet.html (frames per take) for human review')
    args = ap.parse_args()

    proj = ROOT / args.project
    raw_root = proj / '03_video_raw'
    out_root = proj / '04_video_selected'
    manifest_path = proj / '00_project' / 'shot_manifest.json'
    if not raw_root.exists():
        print(f'no raw dir: {raw_root}', file=sys.stderr)
        return 1

    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {}
    shot_ids = list(manifest.get('selections', {}).keys()) or sorted(
        d.name for d in raw_root.iterdir() if d.is_dir())

    overrides = {}
    for o in args.override:
        if '=' not in o:
            print(f'bad --override {o!r} (want SHOT=TAKE)', file=sys.stderr)
            return 2
        k, v = o.split('=', 1)
        overrides[k.strip()] = v.strip()

    report: dict[str, dict] = {}
    errors: list[str] = []
    changed: list[str] = []
    out_root.mkdir(parents=True, exist_ok=True)

    for sid in shot_ids:
        metrics, winner, err = rank_shot(sid, raw_root / sid)
        if err:
            errors.append(err)
            report[sid] = {'error': err, 'takes': [m.to_dict() for m in metrics]}
            print(f'  [FAIL] {sid}: {err}')
            continue

        override = overrides.get(sid)
        if override:
            if any(m.take_id == override for m in metrics):
                if override != winner:
                    changed.append(f'{sid}: override {winner} -> {override}')
                winner = override
            else:
                errors.append(f'{sid}: override {override} not among takes')
                print(f'  [FAIL] {sid}: override {override} not found')
                continue

        runner = next((m for m in metrics if m.take_id == winner and not m.redundant_with), None)
        margin = (runner.score - metrics[0].score) if (runner and metrics[0].take_id != winner) else 0.0
        top = metrics[0]
        needs_review = (not override) and len([m for m in metrics if not m.hard_fail and not m.redundant_with]) > 1 \
            and (top.score - max((m.score for m in metrics[1:] if not m.hard_fail and not m.redundant_with), default=0)) < 0.02

        prev = manifest.get('selections', {}).get(sid, {}).get('source_take')
        if not override and prev and prev != winner:
            changed.append(f'{sid}: auto-ranked {prev} -> {winner}')

        src = raw_root / sid / f'{winner}.mp4'
        dst = out_root / f'{sid}.mp4'
        if not args.dry_run and src.exists():
            shutil.copy2(src, dst)

        report[sid] = {
            'winner': winner,
            'previous': prev,
            'overridden': bool(override),
            'margin_vs_auto_top': round(margin, 4),
            'needs_human_review': needs_review,
            'n_takes': len(metrics),
            'n_redundant': sum(1 for m in metrics if m.redundant_with),
            'takes': [m.to_dict() for m in metrics],
        }
        flag = ' (review: top-2 too close)' if needs_review else ''
        dup = f" [{sum(1 for m in metrics if m.redundant_with)} redundant]" if any(m.redundant_with for m in metrics) else ''
        print(f'  {sid}: {winner} (score {top.score:.3f}, {len(metrics)} takes){dup}{flag}')

    # manifest update
    if not args.dry_run and not errors:
        for sid, rep in report.items():
            if 'winner' not in rep:
                continue
            m = next((x for x in rep['takes'] if x['take_id'] == rep['winner']), None)
            entry = manifest.setdefault('selections', {}).setdefault(sid, {})
            entry['source_take'] = rep['winner']
            if m:
                entry['duration_s'] = m['duration_s']
                entry['frames'] = m['frames']
                entry['ranking_score'] = m['score']
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')

        rank_path = proj / '00_project' / 'take_ranking.json'
        rank_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')

        md = [f'# Take 排名报告（{"dry-run" if args.dry_run else "applied"}）', '']
        for sid, rep in report.items():
            if 'winner' not in rep:
                md += [f'## {sid} — 失败', rep.get('error', ''), '']
                continue
            md += [f'## {sid}  →  **{rep["winner"]}**  (score {next((t["score"] for t in rep["takes"] if t["take_id"] == rep["winner"]), 0):.3f})',
                   f'- 变更：{rep["previous"]} → {rep["winner"]}' + ('  【人工指定】' if rep["overridden"] else ''),
                   f'- take 数：{rep["n_takes"]}（冗余 {rep["n_redundant"]}）', '',
                   '| take | score | 锐度 | 曝光 | 运动 | 稳定 | 主体一致 | 备注 |',
                   '|---|---|---|---|---|---|---|---|']
            for t in rep['takes']:
                mark = ' ✅' if t['take_id'] == rep['winner'] else ''
                note = t['hard_fail'] or ('; '.join(t['notes']) or '—')
                md.append(f'| `{t["take_id"]}`{mark} | {t["score"]:.3f} | {t["sharpness"]:.2f} | '
                          f'{t["exposure"]:.2f} | {t["motion"]:.2f} | {t["stability"]:.2f} | '
                          f'{t["subject_consistency"]:.2f} | {note} |')
            md.append('')
        (proj / '00_project' / 'take_report.md').write_text('\n'.join(md), encoding='utf-8')

        if args.contact_sheet:
            try:
                write_contact_sheet(proj, report, proj / '00_project' / 'contact_sheet.html')
                print(f'联系表: {proj / "00_project" / "contact_sheet.html"}')
            except Exception as e:
                print(f'联系表生成失败（不影响选片结果）: {e}', file=sys.stderr)

    print()
    if changed:
        print('变更：')
        for c in changed:
            print(f'  - {c}')
    if errors:
        print(f'\n错误 {len(errors)}：')
        for e in errors:
            print(f'  ! {e}')
        return 1
    print('OK' + ('（dry-run，未复制文件）' if args.dry_run else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
