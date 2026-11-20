# 缺口清单 GAP_BACKLOG —— 2026-11-20 目录归位与清理的遗留项

> 背景：2026-11-20 对本项目做了 E 盘根归并（ComfyUI 迁入 `third_party/`）、
> 目录归位（成片项目收进 `成片项目/`、脚本收进 `脚本/`、杂项归入 `out/`）与一轮清理。
> 该轮**以整理为主**，凡是需要改代码修复的问题一律不在当轮处理，在此登记为缺口。
>
> 状态约定：`待办` / `待验证` / `已规避` / `已关闭`

---

## G-01 测试套件存在失败项 —— 待验证

目录归位后跑 `pytest tests/`，出现若干 E（error）与 F（failure）。

**已修（当轮）**：收集期报错的 2 个用例 —— `测试/test_p20_one_ruler.py`、
`测试/test_take_selection_behaviour.py`，根因是 `ffmpeg_env.py` 搬到 `脚本/` 后
`studio/scripts/take_ranker.py` 的 sys.path 没跟上（`ModuleNotFoundError: ffmpeg_env`）。
修后两个用例能正常收集。

**2026-11-20 补记**：tests/ 改名为 测试/ 时，暴露出**相对路径引用**也被迁移影响
（`ROOT / 'ceo_mindread_ep01' / 'scripts'` 这类不带 Minimimax-H3 前缀的写法，
前一轮只改了绝对路径，漏了这些）。已修 7 个文件（config/paths.py、
测试/test_p20_one_ruler.py、测试/test_p0_regressions.py、
测试/test_p16_reference_is_not_an_input_free_measurement.py、
测试/test_p2_prompt_contract.py、及 3 个生产脚本）。
修后 **801 个用例全部收集成功、0 收集错误**（改名前是 793 收集 + 1 错误）。

**未修（遗留）**：修完再跑，进度条上仍可见 **≥4 个 FAILURE**
（分布约在 35%、44%、53%、62% 处；此前 ≥6 个 ERROR 是上述收集错误连带造成的）。
具体用例名未捕获——该次 pytest 的输出被截断，只保留了进度点。

- 复现：`third_party/ComfyUI/venv/Scripts/python.exe -m pytest tests/ -q -rf --tb=no`
  （系统 python 3.10 **没有 pytest**，必须用 ComfyUI 的 venv）
- 建议下一步：加 `-rf --tb=no` 重跑取清单；再 `git stash` 回退到迁移前提交
  （8233b99）跑同一套作基线，区分「路径迁移引起」与「原本就红」
- 判定口径：只修前者，不动原本就红的用例

## G-09 sr_takes.py 指向的 shot_manifest 不存在 —— 待办

`成片项目/ceo_mindread_ep01/scripts/sr_takes.py:30` 读的是
`EP01 / '00_project' / 'shot_manifest.json'`，但该文件实际位于
`09_final/shot_manifest.json`（`09_final_v2/` 下另有一份）。

**这不是目录迁移造成的**：该行自最初的提交 9e96377 起就是这样写的，
`00_project/shot_manifest.json` 从未进过版本库（.gitignore 里也没有它），
只在磁盘上存在过；`私有备份/shot_manifest.before_takeranker.json` 就是它被
take_ranker 改动前的备份——说明后续某次运行把它挪走了，脚本没跟着改。

- 现象：`python sr_takes.py --help` 直接 FileNotFoundError
- 待办：确认 per-take SR 应该读 `09_final/shot_manifest.json` 还是
  `09_final_v2/shot_manifest.json`，再改这一行
- 影响面：只影响 EP01 的逐镜头超分，不影响其它工单

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
- 影响面：仅 `成片项目/water_renewal/scripts/generate_voice.py` 的重新生成旁白流程

## G-04 根目录成片项目联接 —— 已关闭

原 6 条联接（`ceo_mindread_ep01/` 等指向 `成片项目/`）已于 2026-11-20
随路径全量改写一并移除，项目根现在只剩真实目录。

- 121 处绝对路径引用改写完成（`E:\`、`E:/`、`/e/` 三种写法）
- 关联坑：git 切换分支会**透过联接写回真实文件**，切分支前需先拆联接；
  详见记忆 `project-directory-layout`
- 仍在的两条必要联接：`studio/public/jobs`（studio 的 staticFile 依赖）
  与 `.remotion/chrome-headless-shell`（Remotion 按此路径找浏览器）

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

## G-08 Remotion 浏览器位置 —— 已关闭

Remotion 认的浏览器位置是 `studio/node_modules/.remotion/chrome-headless-shell`，
而浏览器实体在 `third_party/chrome-headless-shell/`。两者用**目录联接**相连。

**起因**：2026-11-20 重装 `studio/node_modules` 时，Remotion 触发了浏览器下载，
该下载中断，只留下一个 32MB 的 zip 与 download.lock →
`测试/test_chart_type_defaults_are_real.py`（真跑 Remotion 渲染）先报 5 个 error 再卡死，
整个测试套件跑到 26% 就挂住。

**修法**：删掉未完成的下载目录，改建联接
`studio/node_modules/.remotion/chrome-headless-shell` → `third_party/chrome-headless-shell`。
修后该文件 **11 passed in 30.86s**，手工跑 `node studio/bin/still.mjs` 也正常出图。

**遗留**：`pnpm install` 重建 node_modules 后这个联接会没，届时需重跑
`out/工具脚本/link_chrome_nm.bat` 重建（不必重新下载 270MB）。

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
| `成片项目/ceo_mindread_ep01/_archive_20260910_rerun`（9 月重跑归档） | 398 MB |
| `studio/node_modules`（pnpm 硬链接重建） | 1.1 GB → 240 MB |
| **合计** | **约 13.5 GB** |

项目总体积 160G → 144G，E 盘可用 984G → 991G。
