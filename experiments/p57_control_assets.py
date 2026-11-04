"""P57 control-video assets: five preprocessed control sequences
(Pose / Canny / Depth / HED / MLSD) at 124 frames @ 24 fps, 864x480.

Why generated instead of extracted: the official template's pose chain needs
sdpose_wholebody + rt_detr models that are not on disk, and the work order
explicitly allows the control video to be a simple programmatic input
("control video is input, not output; a drawn stick figure is fine").
All five paths share one synthetic source scene (a walking humanoid + ball +
horizon, moving LEFT->RIGHT over 5.2 s) so the only thing that varies between
runs is the control STYLE.
"""
import json
import math
import os

import numpy as np
import cv2

W, H, N, FPS = 864, 480, 124, 24
OUT = r"E:\Minimax-H3\out\p57\controls"
DEST = r"E:\ComfyUI\input"
os.makedirs(OUT, exist_ok=True)


def scene(i):
    """Return RGB frame i of the base scene + its depth map (float32, 0..255)."""
    t = i / (N - 1)                     # 0..1 over the clip
    x = int(W * (0.18 + 0.64 * t))      # humanoid walks left -> right
    bob = int(10 * math.sin(t * 2 * math.pi * 4))
    depth = np.zeros((H, W), np.float32)
    depth[:] = 60.0                     # far background
    horizon = int(H * 0.62)
    depth[horizon:, :] = 120.0          # ground plane nearer
    rgb = np.full((H, W, 3), 40, np.uint8)
    rgb[horizon:, :] = (60, 70, 90)     # ground
    rgb[:int(H * 0.35), :] = (200, 205, 210)  # bright sky
    # humanoid (torso + head + limbs), medium distance
    cv2.rectangle(rgb, (x - 28, 180 + bob), (x + 28, 330 + bob), (220, 220, 230), -1)
    cv2.circle(rgb, (x, 150 + bob), 30, (230, 225, 220), -1)
    cv2.rectangle(depth, (x - 28, 180 + bob), (x + 28, 330 + bob), 210.0, -1)
    cv2.circle(depth, (x, 150 + bob), 30, 210.0, -1)
    # ball bouncing near the right edge, closer to camera
    bx = int(W * (0.78 + 0.05 * math.sin(t * 2 * math.pi)))
    by = int(360 + 60 * abs(math.sin(t * 2 * math.pi * 3)))
    r = 40
    yy, xx = np.ogrid[:H, :W]
    m = (xx - bx) ** 2 + (yy - by) ** 2 <= r * r
    rgb[m] = (30, 30, 230)
    depth[m] = 250.0                    # brightest = nearest
    return rgb, depth


def hed_like(edges):
    """Cheap HED-style sketch: multi-scale soft edges on white background."""
    e = cv2.dilate(edges, np.ones((2, 2), np.uint8))
    paper = np.full_like(e, 255)
    paper[e > 0] = 0
    return paper


def mlsd_like(rgb):
    """Cheap MLSD-style straight-line segments (HoughLinesP on Canny)."""
    edges = cv2.Canny(cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY), 60, 140)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, 60, minLineLength=45, maxLineGap=6)
    canvas = np.zeros((H, W), np.uint8)
    if lines is not None:
        for x1, y1, x2, y2 in lines[:, 0]:
            cv2.line(canvas, (x1, y1), (x2, y2), 255, 2)
    return canvas


def pose_skeleton(i):
    """SDPose-like whole-body skeleton: colored lines on black, same motion."""
    t = i / (N - 1)
    x = int(W * (0.18 + 0.64 * t))
    bob = int(10 * math.sin(t * 2 * math.pi * 4))
    sw = math.sin(t * 2 * math.pi * 4) * 28      # leg swing
    img = np.zeros((H, W, 3), np.uint8)
    head = (x, 150 + bob)
    neck = (x, 185 + bob)
    hip = (x, 265 + bob)
    cv2.circle(img, head, 26, (255, 255, 255), 2)
    cv2.line(img, neck, hip, (255, 0, 0), 3)                      # torso (blue)
    cv2.line(img, neck, (x - 60 - int(sw), 215 + bob), (0, 0, 255), 3)
    cv2.line(img, neck, (x + 60 + int(sw), 215 + bob), (0, 0, 255), 3)   # arms red
    cv2.line(img, hip, (x - 20 - int(sw), 350), (0, 255, 0), 3)
    cv2.line(img, hip, (x + 20 + int(sw), 350), (0, 255, 0), 3)   # legs green
    cv2.line(img, (x - 60 - int(sw), 215 + bob), (x - 75 - int(sw), 190 + bob), (0, 0, 255), 2)
    cv2.line(img, (x + 60 + int(sw), 215 + bob), (x + 75 + int(sw), 190 + bob), (0, 0, 255), 2)
    return img


def write_video(path, frames):
    """Encode as h264 yuv420p via ffmpeg (mp4v part-2 is fragile for decoders)."""
    import subprocess
    tmp = path + ".frames"
    os.makedirs(tmp, exist_ok=True)
    for i, f in enumerate(frames):
        cv2.imwrite(os.path.join(tmp, f"{i:04d}.png"), f)
    cmd = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", os.path.join(tmp, "%04d.png"),
           "-pix_fmt", "yuv420p", "-c:v", "libx264", "-preset", "fast", path]
    subprocess.run(cmd, check=True, capture_output=True)
    for fn in os.listdir(tmp):
        os.remove(os.path.join(tmp, fn))
    os.rmdir(tmp)


def main():
    rgbs, depths = [], []
    for i in range(N):
        rgb, depth = scene(i)
        rgbs.append(rgb)
        depths.append(np.clip(depth, 0, 255).astype(np.uint8))

    canny = [cv2.Canny(g, 50, 150) for g in rgbs]
    hed = [hed_like(c) for c in canny]
    mlsd = [mlsd_like(g) for g in rgbs]
    pose = [pose_skeleton(i) for i in range(N)]
    depth3 = [cv2.cvtColor(d, cv2.COLOR_GRAY2BGR) for d in depths]

    write_video(os.path.join(OUT, "p57_pose.mp4"), pose)
    write_video(os.path.join(OUT, "p57_canny.mp4"), [cv2.cvtColor(c, cv2.COLOR_GRAY2BGR) for c in canny])
    write_video(os.path.join(OUT, "p57_depth.mp4"), depth3)
    write_video(os.path.join(OUT, "p57_hed.mp4"), [cv2.cvtColor(h, cv2.COLOR_GRAY2BGR) for h in hed])
    write_video(os.path.join(OUT, "p57_mlsd.mp4"), [cv2.cvtColor(m, cv2.COLOR_GRAY2BGR) for m in mlsd])

    for name in ("p57_pose.mp4", "p57_canny.mp4", "p57_depth.mp4", "p57_hed.mp4", "p57_mlsd.mp4"):
        src = os.path.join(OUT, name)
        dst = os.path.join(DEST, name)
        with open(src, "rb") as a, open(dst, "wb") as b:
            b.write(a.read())
    print("wrote 5 control videos:", [f for f in os.listdir(OUT) if f.endswith(".mp4")])


if __name__ == "__main__":
    main()
