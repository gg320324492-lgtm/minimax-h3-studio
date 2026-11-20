# 缺口清单 GAP_BACKLOG —— 2026-11-20 目录归位与清理的遗留项

> 背景：2026-11-20 对本项目做了 E 盘根归并（ComfyUI 迁入 `third_party/`）、
> 目录归位（成片项目收进 `成片项目/`、脚本收进 `脚本/`、杂项归入 `out/`）与一轮清理。
> 该轮**以整理为主**，凡是需要改代码修复的问题一律不在当轮处理，在此登记为缺口。
>
> 状态约定：`待办` / `待验证` / `已规避` / `已关闭`

---

## G-01 测试套件存在失败项 —— 待验证

目录归位后跑 `pytest tests/`，出现若干 E（error）与 F（failure）。

**已修（当轮）**：收集期报错的 2 个用例 —— `tests/test_p20_one_ruler.py`、
`tests/test_take_selection_behaviour.py`，根因是 `ffmpeg_env.py` 搬到 `脚本/` 后
`studio/scripts/take_ranker.py` 的 sys.path 没跟上（`ModuleNotFoundError: ffmpeg_env`）。
修后两个用例能正常收集。

**未修（遗留）**：修完再跑，进度条上仍可见 **≥6 个 ERROR、≥4 个 FAILURE**
（分布约在 17%、26%、35%、44%、53%、62% 处）。
具体用例名未捕获——该次 pytest 的输出被截断，只保留了进度点。

- 复现：`third_party/ComfyUI/venv/Scripts/python.exe -m pytest tests/ -q -rf --tb=no`
  （系统 python 3.10 **没有 pytest**，必须用 ComfyUI 的 venv）
- 建议下一步：加 `-rf --tb=no` 重跑取清单；再 `git stash` 回退到迁移前提交
  （8233b99）跑同一套作基线，区分「路径迁移引起」与「原本就红」
- 判定口径：只修前者，不动原本就红的用例

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
- 影响面：仅 `water_renewal/scripts/generate_voice.py` 的重新生成旁白流程

## G-04 根目录的 6 个成片项目联接不可删 —— 已规避

`ceo_mindread_ep01/` `liaozhai_demo/` `piyao_2026/` `third_lantern/` `water_renewal/`
`intro_video/` 现在是**目录联接**，指向 `成片项目/` 下的实体。

- 作用：老脚本里的 `E:/Minimax-H3/water_renewal/...` 绝对路径仍可解析
- 风险：**删掉联接 = 断掉所有旧路径引用**
- 已加 `.gitignore` 规则忽略这 6 条联接路径，避免 git 在两处各登记一份内容
- 待办：若将来要把绝对路径全部改写为 `成片项目/...`，改完才能删联接

## G-05 H3_local_private/repo_backup 仍是旧路径 —— 已规避

`H3_local_private/repo_backup/` 里的备份脚本仍写 `E:\Minimax-H3` 与旧目录名。
该目录整体被 `.gitignore` 忽略（历史上因路径深度不匹配差点泄露到公开仓库），是**只读备份**。

- 待办：若要把备份升级为当前结构，需要单独一轮操作（不急）

## G-06 Remotion 每次渲染会重新拷贝 jobs —— 已规避

`studio/public/jobs` 现在是联接 → `out/工作室渲染/`（911M）。
Remotion 打包时会把 `public/` 整目录拷进 `studio/.remotion/*-bundle/`
（实测上次打包产出 1.5G 的 jobs 拷贝，本轮已清掉）。

- 代价：每次渲染前会多出一次 1.5G 的临时拷贝
- 已缓解：`out/工作室渲染/` 里 5 个 `ep01_*` 的视频已用 NTFS 硬链接去重（320MB 零占用），
  且 3 个 `PREMIXED.mp4` 已剥离无用视频轨（375MB → 8.4MB）
- 待办：若渲染变慢，可考虑把 `public/jobs` 改回实体目录、只把归档产物放 out/

## G-07 studio 依赖重装后未做端到端渲染 —— 待验证

`studio/node_modules` 已用 pnpm 重装（store 指到 `third_party/.pnpm-store`，
node_modules 由 1.1G 降到 240M）。已验证 remotion CLI 可用、Node 能透过联接读取素材，
但**没有跑一次完整渲染**。

- 待办：`cd studio && pnpm run dev` 起 studio，确认各模板仍能正常预览/渲染

## G-08 .remotion/chrome-headless-shell 保留 —— 已规避

270M 的 headless Chrome 是渲染必需，删了会重新下载且默认落 C 盘。
本轮**未删除**。若将来要删，需先设环境变量把下载位置指到 E 盘。

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
| `ceo_mindread_ep01/_archive_20260910_rerun`（9 月重跑归档） | 398 MB |
| `studio/node_modules`（pnpm 硬链接重建） | 1.1 GB → 240 MB |
| **合计** | **约 13.5 GB** |

项目总体积 160G → 144G，E 盘可用 984G → 991G。
