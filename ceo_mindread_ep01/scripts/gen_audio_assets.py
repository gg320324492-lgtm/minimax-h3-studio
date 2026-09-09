"""Generate BGM and SFX for CEO Mindread EP01 using ffmpeg sine filters.

BGM Strategy:
- Suspense, dark corporate thriller
- Subtle pulse (low frequency drone)
- Slow tension build
- Use multiple sine layers with envelope

SFX Strategy:
- Heartbeat: 2-tone sine bursts
- Lamp crash: noise + envelope
- Glass breaking: noise burst
- Electric buzz: high sine with vibrato
- Reverse whoosh: filtered noise rising
"""
import os
import subprocess
from pathlib import Path

PROJECT = Path(r'E:\Minimax-H3\ceo_mindread_ep01')
BGM_DIR = PROJECT / '05_audio/BGM'
SFX_DIR = PROJECT / '05_audio/SFX'
BGM_DIR.mkdir(parents=True, exist_ok=True)
SFX_DIR.mkdir(parents=True, exist_ok=True)


def gen_bgm_drone(filename, duration_s, base_freq=55, secondary_freq=110, volume=0.15):
    """Generate dark suspenseful drone BGM with subtle pulse."""
    out = BGM_DIR / filename
    # Layer: base drone + harmonic + slow pulse
    filter_complex = (
        # Base low drone
        f"sine=frequency={base_freq}:duration={duration_s}:sample_rate=48000,"
        # Harmonic overtone
        f"sine=frequency={secondary_freq}:duration={duration_s}:sample_rate=48000,"
        # Slow pulse LFO
        f"sine=frequency=0.5:duration={duration_s}:sample_rate=48000,"
        f"amix=inputs=3:duration=longest"
    )
    # Use amix with proper volume scaling
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-f', 'lavfi',
        '-i', f'sine=frequency={base_freq}:duration={duration_s}:sample_rate=48000',
        '-f', 'lavfi',
        '-i', f'sine=frequency={secondary_freq}:duration={duration_s}:sample_rate=48000',
        '-f', 'lavfi',
        '-i', f'sine=frequency=0.5:duration={duration_s}:sample_rate=48000',
        '-filter_complex',
        f'[0:a]volume={volume}[a0];'
        f'[1:a]volume={volume*0.5}[a1];'
        f'[2:a]volume=0.4,tremolo=f=0.3:d=0.7[a2];'
        f'[a0][a1][a2]amix=inputs=3:duration=longest',
        '-c:a', 'aac', '-b:a', '192k',
        str(out)
    ]
    subprocess.run(cmd, check=True)
    print(f'  BGM: {out.name} ({out.stat().st_size/1024:.1f}KB)')


def gen_sfx_heartbeat(filename, duration_s=2.0):
    """Two-tone heartbeat SFX."""
    out = SFX_DIR / filename
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-f', 'lavfi',
        '-i', f'sine=frequency=60:duration=0.15:sample_rate=48000',
        '-f', 'lavfi',
        '-i', f'sine=frequency=80:duration=0.15:sample_rate=48000',
        '-f', 'lavfi',
        '-i', f'sine=frequency=60:duration=0.15:sample_rate=48000',
        '-f', 'lavfi',
        '-i', f'sine=frequency=80:duration=0.15:sample_rate=48000',
        '-filter_complex',
        '[0:a]volume=0.6[a0];'
        '[1:a]volume=0.4[a1];'
        '[2:a]volume=0.6[a2];'
        '[3:a]volume=0.4[a3];'
        '[a0][a1][a2][a3]concat=n=4:v=0:a=1,'
        'apad,'
        f'atrim=duration={duration_s}',
        '-c:a', 'aac', '-b:a', '192k',
        str(out)
    ]
    subprocess.run(cmd, check=True)
    print(f'  SFX: {out.name} ({out.stat().st_size/1024:.1f}KB)')


def gen_sfx_pulse(filename, duration_s=3.0, base_freq=40):
    """Low pulse SFX (sub bass heartbeat)."""
    out = SFX_DIR / filename
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-f', 'lavfi',
        '-i', f'sine=frequency={base_freq}:duration={duration_s}:sample_rate=48000',
        '-f', 'lavfi',
        '-i', f'sine=frequency=0.5:duration={duration_s}:sample_rate=48000',
        '-filter_complex',
        f'[0:a]volume=0.5[a0];'
        f'[1:a]volume=0.6,tremolo=f=0.5:d=0.7[a1];'
        f'[a0][a1]amix=inputs=2:duration=longest',
        '-c:a', 'aac', '-b:a', '192k',
        str(out)
    ]
    subprocess.run(cmd, check=True)
    print(f'  SFX: {out.name} ({out.stat().st_size/1024:.1f}KB)')


def gen_sfx_impact(filename, duration_s=2.0):
    """Low frequency impact / boom SFX."""
    out = SFX_DIR / filename
    # Combination of low sine burst with quick decay
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-f', 'lavfi',
        '-i', f'sine=frequency=40:duration=0.5:sample_rate=48000',
        '-f', 'lavfi',
        '-i', f'sine=frequency=120:duration=0.3:sample_rate=48000',
        '-filter_complex',
        f'[0:a]volume=0.7,afade=t=out:st=0:d=0.5[a0];'
        f'[1:a]volume=0.4,afade=t=out:st=0:d=0.3[a1];'
        f'[a0][a1]amix=inputs=2:duration=longest,'
        f'apad,atrim=duration={duration_s}',
        '-c:a', 'aac', '-b:a', '192k',
        str(out)
    ]
    subprocess.run(cmd, check=True)
    print(f'  SFX: {out.name} ({out.stat().st_size/1024:.1f}KB)')


def gen_sfx_buzz(filename, duration_s=2.0):
    """Electric buzz SFX."""
    out = SFX_DIR / filename
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-f', 'lavfi',
        '-i', f'sine=frequency=120:duration={duration_s}:sample_rate=48000',
        '-filter_complex',
        f'[0:a]volume=0.3,tremolo=f=4:d=0.9,'
        f'aecho=0.8:0.9:1000:0.3,'
        f'afade=t=in:st=0:d=0.2,afade=t=out:st={duration_s-0.3}:d=0.3',
        '-c:a', 'aac', '-b:a', '192k',
        str(out)
    ]
    subprocess.run(cmd, check=True)
    print(f'  SFX: {out.name} ({out.stat().st_size/1024:.1f}KB)')


def gen_sfx_whoosh(filename, duration_s=1.5):
    """Reverse whoosh / time reset sound."""
    out = SFX_DIR / filename
    cmd = [
        'ffmpeg', '-y', '-loglevel', 'error',
        '-f', 'lavfi',
        '-i', f'sine=frequency=200:duration={duration_s}:sample_rate=48000',
        '-f', 'lavfi',
        '-i', f'sine=frequency=400:duration={duration_s}:sample_rate=48000',
        '-filter_complex',
        f'[0:a]volume=0.4,aphaser=in_gain=0.4:out_gain=0.7:delay=3:decay=0.4:'
        f'speed=0.5,afade=t=in:st=0:d=0.1,afade=t=out:st={duration_s-0.2}:d=0.2[a0];'
        f'[1:a]volume=0.3,aphaser=in_gain=0.3:out_gain=0.5:delay=5:decay=0.3:'
        f'speed=0.7,afade=t=in:st=0:d=0.2,afade=t=out:st={duration_s-0.3}:d=0.3[a1];'
        f'[a0][a1]amix=inputs=2:duration=longest',
        '-c:a', 'aac', '-b:a', '192k',
        str(out)
    ]
    subprocess.run(cmd, check=True)
    print(f'  SFX: {out.name} ({out.stat().st_size/1024:.1f}KB)')


def main():
    print('=== Generating BGM ===')
    # Main BGM - 60s suspense
    gen_bgm_drone('BGM_DARK_DRONE_60S.m4a', duration_s=60)

    print('\n=== Generating SFX ===')
    gen_sfx_heartbeat('SFX_HEARTBEAT.m4a', duration_s=3.0)
    gen_sfx_pulse('SFX_LOW_PULSE.m4a', duration_s=4.0)
    gen_sfx_impact('SFX_IMPACT.m4a', duration_s=2.5)
    gen_sfx_buzz('SFX_ELECTRIC_BUZZ.m4a', duration_s=3.0)
    gen_sfx_whoosh('SFX_REVERSE_WHOOSH.m4a', duration_s=2.0)
    print('\n=== All audio assets generated ===')


if __name__ == '__main__':
    main()