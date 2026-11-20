# 缺口清单 GAP_BACKLOG —— 2026-11-20 目录归位与清理的遗留项

> 背景：2026-11-20 对本项目做了 E 盘根归并（ComfyUI 迁入 `third_party/`）、
> 目录归位（成片项目收进 `productions/`、脚本收进 `scripts/`、杂项归入 `out/`）与一轮清理。
> 该轮**以整理为主**，凡是需要改代码修复的问题一律不在当轮处理，在此登记为缺口。
>
> 状态约定：`待办` / `待验证` / `已规避` / `已关闭`

---

## G-10 目录命名 —— 已关闭（2026-11-20 改回英文）

本日一度把成片目录改成中文（成片项目/ 测试/ 脚本/ 私有备份/ 等），**当天已全部改回英文**：

    productions/   6 个成片项目
    tests/         测试套件
    scripts/       ffmpeg_env.py、sr_pipeline_v2.py
    私有备份/   私有备份
    out/工作流/ out/日志/ out/渲染素材/ out/工具/

**为什么改回**：中文目录名在四处在持续制造问题，每一处都会静默出错——
1. `git ls-files` 默认把非 ASCII 路径输出成八进制转义（`"æ..."`），
   测试拿这个输出去开文件必然失败；
2. `subprocess.run(..., text=True)` 按系统 locale（本机 GBK）解码 git 的 UTF-8 输出，
   中文路径变乱码；
3. 守护测试里的路径正则只认 `tests|studio|pipeline|docs|tools`，改名就得逐个改；
4. 每一条绝对路径、每一个 manifest 条目都要跟着改，改漏一处就断。

**结论**：本项目的目录名保持英文。中文只用在**文档正文与注释**里，不进路径。

---

## G-01 测试套件 —— 已关闭（2026-11-20）

**最终状态：789 passed / 12 skipped / 0 failed，10 分 34 秒。**

这条缺口从 15 failed 一路降到 0，过程中揭出的问题分三类：

1. **目录迁移的漏改**（绝大多数）——绝对路径改了，相对写法漏了：
   `ROOT / 'tests' / 'x.py'`（引号带空格）、元组里的 `'tests'`、
   `Minimax-H3	ests`（反斜杠）、`skip_dirs` 里的旧目录名。
2. **静默 skip 的假绿**——`tests/test_visual_qa.py` 的 `from ffmpeg_env import`
   包在 try/except 里，导入失败就 skip，于是"单独跑绿、全跑红"。补上路径后
   那两条时长守卫从 skip 变成真跑并通过（38 passed 而非 36 passed + 5 skipped）。
3. **一个环境问题**——`tests/test_p41_vlm_critic.py` 靠 `npx tsx` 从 registry
   临时装包，陈旧的 npx 缓存会以 EPERM 失败。改用 studio 本地安装的 tsx。

另有一处**文件真的丢了**并已找回：`productions/ceo_mindread_ep01/scripts/`
下的 `gen_office.py` 与 `gen_references.py`——它们在本轮起点前被 git 跟踪、
后来才被 .gitignore 排除，切分支时被 git 从磁盘删除且 git 也恢复不了
（ignore 规则使其不再进入索引）。已从 8233b99 恢复并施加同样的路径修复。

复现：`third_party/ComfyUI/venv/Scripts/python.exe -m pytest tests/ -q`
（系统 python 没有 pytest；用 ComfyUI 的 venv）。

## G-09 sr_takes.py 指向的 shot_manifest 不存在 —— 已关闭（2026-11-20）

根因：目录归位时 `shot_manifest.json` 被移到 `09_final/`，但 `sr_takes.py` 等
6 处引用仍指旧位置。两批提交修复：

1. **0867d5e**：`sr_takes.py` 读取的 `shot_manifest.json` 改指实际存在的
   `09_final/` 目录。
2. **18d11c0（同根因 5 处）**：shot_manifest.json 的权威位置统一改为
   `productions/ceo_mindread_ep01/09_final/shot_manifest.json`——
   - `select_takes.py`：写入改到 `09_final/`（并确保目录存在）；
   - `finalize.py`：删除 `00_project` -> `09_final` 的复制，
     读取改读 `09_final/`；
   - `qa_final.py`：读取改读 `09_final/`；
   - `studio/scripts/rank_takes.py`：读取改读 `09_final/`。

tests/test_p0_regressions.py 与 tests/test_p20_one_ruler.py 复跑通过。

## G-11 water_renewal 脚本的子目录结构需逐个适配 —— 待收尾（2026-11-21）

2026-11-20 把 `from_e_root/黑臭水体治理宣传片剪辑` 并入 `productions/water_renewal/` 时，
这批脚本的根路径已全部重映射到项目内（不再指向已不存在的 `E:/promo_video`、
也不再写 C 盘桌面），但**脚本内部期待的子目录结构仍是旧的**，需要逐文件适配：

| 脚本 | 仍期待 | 修复后指向 |
|---|---|---|
| `build_video.py` | `A=ROOT/'assets'`、`W=ROOT/'work'/'build'`、`OUT=ROOT/'output'` | `A=05_audio/music/`、`W=07_edit/build/`、`OUT=09_final/`；H3 素材读 `01_reference/h3_clips/`、narration manifest 读 `01_reference/narration_manifest.json` |
| `gen_h3_clips.py` | `PROJECT/'assets'/'h3'` | `01_reference/h3_clips/` |
| `gen_narration.py` | `OUT=PROJECT/'assets'/'narration'` | `05_audio/narration/`；manifest 写 `01_reference/narration_manifest.json`、临时 wav 落 `05_audio/tmp/` |
| `gen_cover.py` | `OUT=.../assets/cover` | `01_reference/cover/`（重映射时已改对，本轮核对无误） |

- 之所以不在归位轮直接改：这几条路径各自对应哪一版产物需要按成片实际内容判断，
  猜错会让脚本把素材写到错误的目录——属于"修复任务"，按约定登记为缺口。
- 影响面：只影响 water_renewal 的重跑（成片已交付，`09_final/` 在位）。
- **2026-11-21 修复一：根路径重映射（commit 1bf84b1）**：归位当天先做了把
  `E:/promo_video` 等 E 盘外部根重映射到项目内路径的工作，4 个脚本已不再指向
  已不存在的 `E:/promo_video`、也不再写 C 盘桌面。
- **2026-11-21 修复二：原始素材归位**：原始素材（C 盘桌面旧目录）已不存在，故把仍在的
  素材副本归位到项目内——8 个第一批视频从 `studio/public/jobs/water-renewal/`
  （prepare_media.py 的转码副本）拷回 `01_reference/videos/`（保持 `_raw.mp4`
  原文件名，V 表只需改相对路径）；24 张第一批照片 `01_reference/A09..A32.jpg`
  （640×480，EXIF 已转正，与微信导出图同源同分辨率）按 P 表 fid 顺序拷入
  `01_reference/photos/p01..p24.jpg`，`norm_photos()` 改读该目录。4 个脚本
  均已用 ComfyUI venv ast.parse 验证通过。
- **2026-11-21 遗留**：脚本内部子目录常量的运行时适配（上表"修复后指向"所列）
  正在另一会话处理，完成后此处更新为已关闭。

---

## G-12 仓库测试套件的「账务化」—— 待决策

73 个测试文件 / 29188 行。逐文件断言对象分类后：**账务类 29 个 / 639 行（14 用例）**、
中间 1 个、**产出类 69 个 / 28369 行（691 用例）**。

- 账务类（护仓库自身的路径/哈希/引用/清单）：`test_manifest_freshness`、
  `test_tautology_criterion`、`test_brand_lock_comment_honesty`，
  加上产出类里实际在钉仓库文本的约 26 个（引用解析、行号引用落点、docstring 计数、
  qa_layers/visual_qa 的哈希 pin、p0 的 ls-files 检查等）。
- 产出类（真正护画面/管线行为）：图表几何与基线、转场非冻结、camera move、
  depth cue、visual acceptance 可复现、schema 严格性、渲染入口守卫等。

待决策：账务类是否裁掉。裁掉后 789 用例约降到 350；可能漏掉个别真护产出的
（判定脚本 out/工具/classify_tests.py 可重跑，删除前逐个过一遍更稳）。

---

## G-02 本机网络出口受限 —— 已规避

2026-11-20 实测：

| 站点 | 状态 | 替代 |
|---|---|---|
| `pypi.org` / `files.pythonhosted.org` | 000（SSL EOF） | `mirrors.aliyun.com/pypi/simple` |
| `huggingface.co` | 000 | `www.modelscope.cn` |
| `github.com` | 000 | — （**无法 push**，本地分支暂只能留本地） |
| `mirrors.tuna.tsinghua.edu.cn` / `ustc` | 000 | 阿里云可用 |
| `modelscope.cn` / `baidu.com` | 200 | — |

- 影响：HF 上的模型要改走 ModelScope；新分支推不上去
- 待办：确认 GitHub 是否长期不可达；若恢复，`git push origin chore/comfyui-into-project`

## G-03 Qwen3-TTS 缺 flash-attn —— 待办

`third_party/tts/venv` 加载 Qwen3TTSModel 时告警 `flash-attn is not installed`，
当前跑的是手动 PyTorch 实现，功能正常但推理慢。

- 待办：`pip install flash-attn`（需与 torch 2.11.0+cu128 匹配，编译可能失败）
- 影响面：仅 `productions/water_renewal/scripts/generate_voice.py` 的重新生成旁白流程

## G-04 根目录成片项目联接 —— 已关闭

原 6 条联接（`ceo_mindread_ep01/` 等指向 `productions/`）已于 2026-11-20
随路径全量改写一并移除，项目根现在只剩真实目录。

- 121 处绝对路径引用改写完成（`E:\`、`E:/`、`/e/` 三种写法）
- 关联坑：git 切换分支会**透过联接写回真实文件**，切分支前需先拆联接；
  详见记忆 `project-directory-layout`
- 仍在的两条必要联接：`studio/public/jobs`（studio 的 staticFile 依赖）
  与 `.remotion/chrome-headless-shell`（Remotion 按此路径找浏览器）

## G-05 私有备份/repo_backup 仍是旧路径 —— 已规避

`私有备份/repo_backup/` 里的备份脚本仍写 `E:\Minimax-H3` 与旧目录名。
该目录整体被 `.gitignore` 忽略（历史上因路径深度不匹配差点泄露到公开仓库），是**只读备份**。

- 待办：若要把备份升级为当前结构，需要单独一轮操作（不急）

## G-06 Remotion 每次渲染会重新拷贝 jobs —— 已规避

`studio/public/jobs` 现在是联接 → `out/渲染素材/`（911M）。
Remotion 打包时会把 `public/` 整目录拷进 `studio/.remotion/*-bundle/`
（实测上次打包产出 1.5G 的 jobs 拷贝，本轮已清掉）。

- 代价：每次渲染前会多出一次 1.5G 的临时拷贝
- 已缓解：`out/渲染素材/` 里 5 个 `ep01_*` 的视频已用 NTFS 硬链接去重（320MB 零占用），
  且 3 个 `PREMIXED.mp4` 已剥离无用视频轨（375MB → 8.4MB）
- 待办：若渲染变慢，可考虑把 `public/jobs` 改回实体目录、只把归档产物放 out/

## G-07 studio 依赖重装后未做端到端渲染 —— 已关闭（2026-11-20）

端到端验证完成：`pnpm exec remotion --version` = @remotion/cli 4.0.529；
`node studio/bin/still.mjs --comp FinanceShowcaseWide` 真实出图
（1920×1080 PNG，452KB，证据 out/工具/审计/g07_verify/frame.png）；
渲染相关守护测试 58 passed / 3 skipped / 0 failed。
studio 依赖重装后链路完好。

## G-08 Remotion 浏览器位置 —— 已关闭

Remotion 认的浏览器位置是 `studio/node_modules/.remotion/chrome-headless-shell`，
而浏览器实体在 `third_party/chrome-headless-shell/`。两者用**目录联接**相连。

**起因**：2026-11-20 重装 `studio/node_modules` 时，Remotion 触发了浏览器下载，
该下载中断，只留下一个 32MB 的 zip 与 download.lock →
`tests/test_chart_type_defaults_are_real.py`（真跑 Remotion 渲染）先报 5 个 error 再卡死，
整个测试套件跑到 26% 就挂住。

**修法**：删掉未完成的下载目录，改建联接
`studio/node_modules/.remotion/chrome-headless-shell` → `third_party/chrome-headless-shell`。
修后该文件 **11 passed in 30.86s**，手工跑 `node studio/bin/still.mjs` 也正常出图。

**遗留**：`pnpm install` 重建 node_modules 后这个联接会没，届时需重跑
`out/工具/link_chrome_nm.bat` 重建（不必重新下载 270MB）。

---

## 附：本轮清理账目

| 项目 | 释放 |
|---|---|
| `studio/.remotion/water-renewal-bundle`（构建缓存） | 1.5 GB |
| `third_party/ollama`（本地推理栈，未再使用） | 8.7 GB |
| 3 个 `PREMIXED.mp4` 剥离视频轨 | 375 MB |
| `experiments/_ref_analysis` | 151 MB |
| `out/_legacy`（35 个历史杂散目录归拢处） | 43 MB |
| ComfyUI `output/` + `input/` | 1.3 GB |
| `productions/ceo_mindread_ep01/_archive_20260910_rerun`（9 月重跑归档） | 398 MB |
| `studio/node_modules`（pnpm 硬链接重建） | 1.1 GB → 240 MB |
| **合计** | **约 13.5 GB** |

项目总体积 160G → 144G，E 盘可用 984G → 991G。
