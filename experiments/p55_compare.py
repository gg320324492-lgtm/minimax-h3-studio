"""P55: compare two generated videos for the pixel-identity regression check.

Usage: python p55_compare.py <baseline.mp4> <candidate.mp4> <out.json>

Checks, in order of strictness:
  1. ffprobe specs (codec, resolution, fps, frame count, audio streams)
  2. per-stream MD5 of the decoded elementary streams (video, each audio)
  3. if the video MD5s differ: PSNR of every frame pair (encoding noise >=
     50 dB; anything lower is a real pixel change and the report must say so)

ffmpeg is pinned to the repo-bundled 7.1.1 build by absolute path because the
worktree has no tools/ directory and PATH's ffmpeg is Octave's 4.2.11.
"""
import json
import subprocess
import sys
from pathlib import Path

FFMPEG = r'E:\Minimax-H3\tools\ffmpeg-7.1.1-full_build\bin\ffmpeg.exe'
FFPROBE = r'E:\Minimax-H3\tools\ffmpeg-7.1.1-full_build\bin\ffprobe.exe'


def probe(path):
    r = subprocess.run([FFPROBE, '-v', 'error', '-show_streams', '-show_format',
                        '-of', 'json', path], capture_output=True)
    return json.loads(r.stdout.decode('utf-8', 'replace'))


def specs(path):
    p = probe(path)
    out = {'video': [], 'audio': []}
    for s in p.get('streams', []):
        if s['codec_type'] == 'video':
            out['video'].append({
                'codec': s.get('codec_name'),
                'width': s.get('width'), 'height': s.get('height'),
                'r_frame_rate': s.get('r_frame_rate'),
                'nb_frames': s.get('nb_frames'),
                'pix_fmt': s.get('pix_fmt'),
            })
        elif s['codec_type'] == 'audio':
            out['audio'].append({
                'codec': s.get('codec_name'),
                'channels': s.get('channels'),
                'channel_layout': s.get('channel_layout'),
                'sample_rate': s.get('sample_rate'),
            })
    return out


def stream_md5(path, stream_spec):
    r = subprocess.run([FFMPEG, '-v', 'error', '-i', path, '-map', stream_spec,
                        '-f', 'md5', '-'], capture_output=True)
    text = r.stdout.decode('ascii', 'replace').strip()
    return text.split('=', 1)[-1] or ('ERROR: ' + text)


def psnr(a, b):
    r = subprocess.run([FFMPEG, '-v', 'info', '-i', a, '-i', b, '-lavfi', 'psnr',
                        '-f', 'null', '-'], capture_output=True)
    text = r.stderr.decode('utf-8', 'replace')
    for line in text.splitlines():
        if 'PSNR' in line and 'average' in line:
            return line.strip()
    return 'PSNR line not found; stderr tail: ' + text[-400:]


def main():
    a_path, b_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    report = {
        'baseline': a_path, 'candidate': b_path,
        'baseline_specs': specs(a_path), 'candidate_specs': specs(b_path),
    }
    # md5 per elementary stream: video first, then every audio stream
    for tag in ('0:v:0', '0:a:0', '0:a:1'):
        try:
            report[f'md5_baseline_{tag}'] = stream_md5(a_path, tag)
            report[f'md5_candidate_{tag}'] = stream_md5(b_path, tag)
        except Exception as e:
            report[f'md5_{tag}'] = f'UNAVAILABLE: {e}'
    v_same = report.get('md5_baseline_0:v:0') == report.get('md5_candidate_0:v:0')
    report['video_md5_identical'] = v_same
    if not v_same:
        report['psnr'] = psnr(a_path, b_path)
    Path(out_path).write_bytes(
        json.dumps(report, indent=2, ensure_ascii=False).encode('utf-8'))
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
