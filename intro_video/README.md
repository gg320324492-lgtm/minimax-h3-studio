# model-intro —— MiniMax M3.1 自我介绍片

一支 50 秒的中文自我介绍片。**每一个像素都来自 React/Remotion 代码渲染，全程没有调用任何视频生成模型**（仓库里的 H3、ComfyUI 工作流一个都没碰）。旁白由本地 Kokoro-82M 合成，背景音乐与音效复用仓库既有资产。

## 产物

| 文件 | 说明 |
|---|---|
| `out/model_intro.mp4` | 成片（1920×1080 / 24fps / 1,198 帧 / 49.96 秒 / H.264 + AAC） |
| `narration.json` | 七段旁白文案（唯一文案来源，字幕从中派生） |
| `work/gen_tts.py` | 旁白合成脚本：Kokoro 出音 → ffmpeg 转 m4a → 写出带实测时长的 timeline.json |
| `work/patch_timeline.py` | 时间轴重排：算场景落点、字幕出入点、语音起止帧 |

## 复现步骤

```bash
# 1. 合成旁白（用 ComfyUI venv 的 Python，里面已装好 kokoro + misaki[zh]）
/e/ComfyUI/venv/Scripts/python.exe work/gen_tts.py

# 2. 重排时间轴（场景落点 + 字幕窗口）
/e/ComfyUI/venv/Scripts/python.exe work/patch_timeline.py

# 3. 渲染（在 studio 工程里）
cd ../studio
npx tsc --noEmit -p tsconfig.json
npx remotion render ModelIntro E:/Minimax-H3/intro_video/out/model_intro.mp4 \
  --browser-executable=E:/Minimax-H3/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe
```

第 2 步必须放在第 1 步之后：时间轴里每一场的语音起止帧都来自 Kokoro 实测时长，不是估的。

## 关键设计决策

**时间轴由语音驱动。** `gen_tts.py` 先合成每段旁白、用 `len(audio)/24000` 量出真实秒数写进 timeline.json，画面再按这个长度排布。字幕的出入点也由语音起止帧推出，所以音画不会漂。

**场景之间留 6 帧空档，用闪白过渡，而不是交叉溶解。** 试过 12 帧和 8 帧的叠化，两场的文字都会在半透明状态下同时在场，看着像渲染错误。改成「旧场淡出 → 空档 → 新场淡入」后，两场文字永不出现在同一帧。

**画面里的数字全部可核。** 82 个源文件 / 12,763 行是 `studio/src` 的实测值，11 个新文件 / 1,596 行是本片模板目录的实测值，1,198 帧 / 49.9 秒是本次渲染的实际产物。「本片调用视频生成模型 0 次」加了「本片」限定——仓库里确实存在其它视频模型调用脚本（`ceo_mindread_ep01/scripts/gen_keyframes_v3.py` 等），措辞得留边界。

**字幕提到顶层渲染。** 字幕与旁白不进场景 Sequence，而是各自挂在顶层、按场景时间开窗，这样转场空档里不会出现两条字幕打架。

## 源码位置

合成代码在 `../studio/src/templates/model-intro/`：

```
ModelIntro.tsx      顶层：场景序列、字幕/旁白/音效的时间窗
theme.ts            颜色与字体令牌
common/ui.tsx       Backdrop / Fade / CaptionBar / Typewriter / TransitionFlash
scenes/*.tsx        七个场景各一个文件
```
