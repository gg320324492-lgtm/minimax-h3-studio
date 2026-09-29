"""Inject word-level timestamps into timeline_v2.json subtitles (Phase 3 karaoke).

Transcribes the premixed audio with faster-whisper (word_timestamps=True), then for
each subtitle event collects ASR words whose midpoint falls inside the event window
and writes event['words'] = [{w, t, d}, ...]. Karaoke rendering uses the ASR word
surfaces (they may differ cosmetically from the TTS source text).

Usage:
  E:/ComfyUI/venv/Scripts/python.exe studio/scripts/word_timestamps.py \
      --timeline ceo_mindread_ep01/00_project/timeline_v2.json \
      --audio ceo_mindread_ep01/07_edit/EP01_WITH_AUDIO.mp4 \
      [--model small] [--in-place]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(r'E:\Minimax-H3')
sys.path.insert(0, str(ROOT))
from ffmpeg_env import FFMPEG  # noqa: E402


def to_wav16k(src: Path) -> Path:
    dst = Path(tempfile.mkdtemp(prefix='asr16k_')) / 'a.wav'
    subprocess.run(
        [FFMPEG, '-y', '-v', 'error', '-i', str(src),
         '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(dst)],
        check=True,
    )
    return dst


import re


def norm_text(s: str) -> str:
    return re.sub(r'[^\w]', '', s, flags=re.UNICODE)


def similar(asr_concat: str, event_text: str, threshold: float = 0.5) -> bool:
    """ASR 词面与字幕文本的字符重合率——钩子/结束卡等叠字图形卡片的音频
    念的不是卡片文字，卡拉OK高亮会指错字，必须拒绝匹配（回退静态/打字机）。"""
    a = set(norm_text(asr_concat))
    e = set(norm_text(event_text))
    if not e:
        return False
    return len(a & e) / len(e) >= threshold


def is_content(ch: str) -> bool:
    return bool(re.match(r'[\w一-鿿]', ch))


def align_to_source(event_text: str, words: list) -> list:
    """把 ASR 词时间戳映射回已知原文：文字用原文（标点/省略号原样保留），
    时间用 ASR 词边界。ASR 词面仅充当对齐标尺——这样卡拉OK高亮的是正确文本。"""
    out = []
    ti = 0
    text = event_text
    for w in words:
        wn = norm_text(w['w'])
        if not wn:
            continue
        seg = ''
        while ti < len(text) and not is_content(text[ti]):
            seg += text[ti]
            ti += 1
        taken = 0
        while ti < len(text) and taken < len(wn):
            seg += text[ti]
            if is_content(text[ti]):
                taken += 1
            ti += 1
        while ti < len(text) and not is_content(text[ti]):
            seg += text[ti]
            ti += 1
        out.append({'w': seg or w['w'], 't': w['t'], 'd': w['d']})
    if out and ti < len(text):
        out[-1]['w'] += text[ti:]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--timeline', required=True)
    ap.add_argument('--audio', required=True)
    ap.add_argument('--model', default='small', choices=['base', 'small', 'medium'])
    ap.add_argument('--language', default='zh')
    ap.add_argument('--in-place', action='store_true', help='write words back into the timeline file')
    args = ap.parse_args()

    from faster_whisper import WhisperModel

    tl_path = Path(args.timeline)
    tl = json.loads(tl_path.read_text(encoding='utf-8'))
    events = tl['subtitles']
    if not events:
        print('no subtitles in timeline')
        return 0

    wav = to_wav16k(Path(args.audio))
    with wave.open(str(wav), 'rb') as w:
        audio_dur = w.getnframes() / w.getframerate()
    print(f'audio {audio_dur:.2f}s, model={args.model}')

    model = WhisperModel(args.model, device='cpu', compute_type='int8')
    segments, info = model.transcribe(
        str(wav), language=args.language, word_timestamps=True,
        vad_filter=True, vad_parameters={'min_silence_duration_ms': 400},
    )

    words_all = []
    for seg in segments:
        for w in seg.words:
            words_all.append({'w': w.word, 't': round(w.start, 3), 'd': round(w.end - w.start, 3)})
    print(f'ASR words: {len(words_all)}')
    for wa in words_all:
        wa['_mid'] = wa['t'] + wa['d'] / 2

    matched = 0
    rejected = 0
    for ev in events:
        lo, hi = ev['start'] - 0.05, ev['end'] + 0.15
        inside = [w for w in words_all if lo <= w['_mid'] <= hi]
        if inside and similar(''.join(w['w'] for w in inside), ev['text']):
            ev['words'] = align_to_source(ev['text'], inside)
            matched += 1
        else:
            if inside:
                rejected += 1
            ev.pop('words', None)

    for w in words_all:
        w.pop('_mid')

    out_path = tl_path if args.in_place else tl_path.with_suffix('.words.json')
    out_path.write_text(json.dumps(tl, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'matched {matched}/{len(events)} events ({rejected} rejected: audio text != caption text) -> {out_path}')
    return 0 if matched else 1


if __name__ == '__main__':
    sys.exit(main())
