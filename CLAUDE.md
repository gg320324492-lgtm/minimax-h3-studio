# Minimax-H3 项目规定

## 文件系统纪律（用户明令，2026-11-04 补充并于 2026-11-20 加严）

- **不要在 E 盘根目录创建文件夹**。历次 agent 会话已在 E:\ 根部留下大量杂物文件夹；
  今后一切新文件、新文件夹只创建在本项目 `E:\Minimax-H3\` 内部。
- **本项目的任何文件都不得写入 C 盘**（用户 2026-11-20 加严：不再是"模型和工具"，
  而是**任何文件**——源码、缓存、临时文件、模型、数据集、日志、安装包、解压产物、
  测试产物、渲染中间件，一律不许落在 C 盘）。C 盘是系统盘且长期吃紧，
  本项目对它只有**读取**权限，没有**写入**权限。

  具体红线：
  - 下载模型、数据集、工具的存储一律指到 E 盘项目内路径
    （如 HuggingFace 设 `HF_HOME`，ollama 设 `OLLAMA_MODELS`，pip 设 `PIP_CACHE_DIR`，
    npm 设 `npm_config_cache`，临时目录设 `TEMP`/`TMP`）；
  - 安装新工具前先确认其默认落盘位置，凡默认进 C 盘（`%LOCALAPPDATA%`、`%USERPROFILE%`、
    `%TEMP%`）的，先改配置再装；
  - 跑命令前先确认它会不会顺手写 C 盘（`npx` 会往 npm 缓存装包、`pip` 会写缓存、
    `huggingface_hub` 会写 `~/.cache`、`matplotlib` 会写字体缓存、
    某些 CLI 会往 `%TEMP%` 扔中间件）；
  - **唯一的例外**：Claude Code 框架自身的固定目录
    （`C:\Users\pc\.claude\` 下的记忆与会话记录）——它由框架管理，不归项目控制；
  - 例外之外若发现本项目已在 C 盘落了文件，**当场迁走**（不是留着）。
- 临时产物、测量证据、生成输出放 `out/` 下按工单命名的子目录（如 `out/p55/`）；
  `out/` 已被 gitignore，不会误入版本库。
- 工单若指定了 E:\ 外部路径（历史工单曾有 `E:\out\...`），按本规定改放项目内，
  并同步更新工单与报告里的路径引用。
- 大文件（视频、抽帧 PNG）跑完按工单要求留证据、删大文件，不要长期占据磁盘。

### C 盘零写入的执行办法

- **环境变量先行**（已设成用户级，任何新终端都生效）：
  `HF_HOME=E:\Minimax-H3\third_party\hf-cache`、
  `XDG_CACHE_HOME=E:\Minimax-H3\third_party\xdg-cache`、
  `PIP_CACHE_DIR=E:\Minimax-H3\third_party\pip-cache`、
  `npm_config_cache=E:\Minimax-H3\third_party\npm-cache`、
  `UV_CACHE_DIR=E:\Minimax-H3\third_party\uv-cache`、
  `TEMP=TMP=E:\Minimax-H3\third_party\tmp`。
- **守卫脚本**：`python tools/check_c_drive.py` 检查环境变量是否仍指向 E 盘，
  并比对本项目在 C 盘的占用与基线（`tools/.c_drive_baseline.json`），
  有新增就报错。**收工前跑一次**，或在任何可能写盘的命令前跑。
- 路径里出现 `C:\` 且不是框架目录，就是 bug——写脚本时路径一律由
  `Path(__file__).resolve().parents[n]` 推出来，不写死盘符。

## 目录命名

- **目录名一律用英文**（2026-11-20 定稿）。本日一度改成中文（`成片项目/`、`测试/`…），
  当天改回：中文目录名会让 `git ls-files` 输出八进制转义、`subprocess` 按 GBK 解码出乱码、
  守护测试的路径正则全部失效，且每条绝对路径都要跟着改、漏一处就断。
- 中文只出现在**文档正文与注释**里，不进路径。
