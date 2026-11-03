# 执行指令 — P55：ComfyUI v0.34.0 → v0.43.2 升级 + 回归验证（**任何一条回归不过，就地回滚**）

> 给执行 agent。本文件**自包含**。你只负责执行与记录，**升级与否的最终裁定由指挥窗口做**。
> ⚠️ **本项是后续一切（Pika Flex 对比、ControlNet 验证）的地基。地基没验好，后面全白做。**

---

## 零、环境与对象

| 项 | 值 |
|---|---|
| 升级对象 | `E:\ComfyUI`（**独立 git 仓库**，不是 Minimax-H3 项目的一部分） |
| 当前版本 | v0.34.0（commit `12d52794`） |
| 目标版本 | **v0.43.2**（tag 已在本地，`git tag` 可见；与 HEAD 差 442 个提交） |
| python | `E:\ComfyUI\venv\Scripts\python.exe`（所有 pip 操作用这个 venv） |
| GPU | RTX 5090 32GB |
| 本项目仓库 | `E:\Minimax-H3`（工单、测试脚本、回归报告放这里） |

**⚠️ E:\ComfyUI 工作树里有几个已删除的占位文件**（`models/*/put_*_files_here`）——
那是装模型后删的 `.gitkeep`，**正常，不要恢复它们**。

**⚠️ 本项目工作树里有不属于你的在制工作**（`studio/src/Root.tsx` 已改、
`intro_video/`、`studio/public/audio/intro/`、`studio/src/templates/model-intro/`、
`tests/test_p48_reaccept.py` 已改）——**全部不要碰、不要提交、不要恢复。**

---

## 一、为什么升、升到哪、为什么是 0.43.2

- 官方 [H3 教程](https://docs.comfy.org/tutorials/video/minimax/minimax-h3) 的版本门槛：
  multiframe_reference 模板 **0.34.0+**（刚好够）、FastH3 **0.36.0+**、
  Fun ControlNet Union **0.35.0+**（**Union 2.0: 0.38.0+**）、
  Pika H3 Flex T2V 模板 **0.43.2+**。
- **⇒ 0.43.2 一次满足全部**，且它是当前最新 tag（`git tag --sort=-v:refname` 第一位）。

---

## 二、你要做的事（**严格按顺序**）

### 第 0 步：**先造回滚点，再动手**

1. `E:\ComfyUI` 里 `git tag local-pre-upgrade-0.34`（或记录 `12d52794`）；
2. `venv\Scripts\python.exe -m pip freeze > E:\Minimax-H3\out\p55\pip_freeze_0.34.txt`
   （⚠️ 输出目录先建好；**写到 E 盘**）；
3. 记录 `custom_nodes/` 清单（当前只有 `ComfyUI-FlashVSR_Ultra_Fast`）；
4. **跑一次升级前的基线生成**（见第 2 步的 r2v）——**没有基线，后面的"一致"无从判定**。

### 第 1 步：升级

```bash
cd /e/ComfyUI
git checkout v0.43.2
venv/Scripts/python.exe -m pip install -r requirements.txt
```

⚠️ **pip 输出里若有 major 版本变更的包**（torch、torchvision、xformers），
**先停下来报告**——torch 大版本变动可能破坏 FlashVSR 与超分路径，
**不要静默接受**。若 requirements 不强制，保持 torch 不动。

### 第 2 步：回归验证（**五条全过才算成功；任何一条不过 → 评估回滚**）

**① 启动无报错**：正常方式启动 ComfyUI，抓启动日志，列出新版本的
warning/error（区分"已知噪声"与"新出现的"）。

**② 三条工作流各跑一次**（本项目 `workflows/` 下的
`video_minimax_h3_t2v.json`、`video_minimax_h3_r2v.json`、`video_minimax_h3_fl2v.json`，
用 ComfyUI API 模式加载跑）：

| 验证 | 判据 |
|---|---|
| 能加载 | 模板在新版不报"未知节点/缺失输入" |
| 规格不变 | 输出 mp4：**17k+5 帧格、24fps、768p、原生立体声音轨**（ffprobe 实测） |
| 时长合理 | 与升级前同工作流的输出帧数一致 |

**③ r2v 升级前后一致性（本项的核心回归）**：
**同一个 prompt、同一个 seed**（工作流里把 seed 钉死），升级前后各渲一条，
对比：帧数一致 + 逐像素或近逐像素（编码噪声内）。
**⇒ 若画面变了，说明新版节点行为变了** ——**这是升级改变了生成结果，
必须定位到是哪个节点，并如实报告**（**不许说"看起来差不多"**，
用像素差 + VLM 读画面说清差在哪）。

**④ 超分节点存活**：`ComfyUI-FlashVSR_Ultra_Fast` 在新版下能加载、节点出现在节点列表。
**不要求跑完整超分**（那是 memory 里记录的独立管线），但节点必须能实例化。

**⑤ 本项目侧引用不破**：`grep -r "video_minimax_h3" E:/Minimax-H3 --include=*.py -l`
看有没有代码按节点名/文件名硬编码引用，有则逐个验证仍成立。

### 第 3 步：报告与提交

- 回归报告写到 `E:\Minimax-H3\docs\P55_COMFYUI_UPGRADE.md`（中文，`read_bytes`/`write_bytes`）；
- **E:\ComfyUI 的 checkout 不产生本项目提交**——你提交的是
  `E:\Minimax-H3` 里的报告 + 新增脚本（显式路径 `git add`，**不推送**）。

---

## 三、回滚方案（提前写清，用的时候不慌）

```bash
cd /e/ComfyUI && git checkout local-pre-upgrade-0.34   # 或 12d52794
venv/Scripts/python.exe -m pip install -r E:/Minimax-H3/out/p55/pip_freeze_0.34.txt
```

**回滚触发条件（任一）**：③ 生成结果改变且定位不到原因；② 任一工作流跑不起来且修复超过一次尝试；
④ FlashVSR 坏了且无修复路径。
**⇒ 回滚后照常交付报告**——**"回滚了，原因是 X，证据是 Y"是完整交付**，
**本项目已接受过十三次"实测说不出想要的结果"**。

---

## 四、验证协议

1. **先有基线再升级**——没有升级前的生成结果，第 2 步第 ③ 条无从判定；
2. **贴原始输出**（启动日志、ffprobe、像素差数字），不贴结论句；
3. ⚠️ **五条高频复发**：先证明被测对象存在再测量；**外推等于没测**；
   **写数字要么实测要么标注未测**；CRLF 用字节计数验；**别把长跑命令管道进 `tail`**；
4. ⚠️ **磁盘**：模型文件已就位，本项主要新增的是输出视频（每条约几十 MB），
   **放 `E:\out\p55\`，跑完留证据、删大文件**；
   ⚠️ **`studio/.remotion/water-renewal-bundle`（1.5 GB）不是你的，别删**；
5. ⚠️ **不要并发跑两个生成任务**（一块 GPU）；
6. ⚠️ **GBK 控制台会把非 ASCII 显示成替换字符——读非 ASCII 用字节判断**；
7. ⚠️ `tests/test_markdown_text_is_intact.py` 守着全仓 markdown 的 U+FFFD。

---

## 五、不要动的东西

- **本项目工作树里的在制工作**（见零节清单）——不碰
- `E:\ComfyUI\models/` 下所有已装模型——**不删不挪**（本项不下载新模型）
- `E:\ComfyUI/custom_nodes/ComfyUI-FlashVSR_Ultra_Fast`——只验证，不升级它
  （若它在新版 ComfyUI 下有兼容问题，报告，**不自行改它的代码**）
- `E:\Minimax-H3\docs\UPGRADE_PROGRESS.md`——**账本由指挥窗口写**
- `DiagOutputDir`——禁止触碰

---

## 六、交付

- 提交信息用**英文**，结尾加 `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- **提交但不推送**（只 stage 你自己的文件，显式路径）
- 交付时报告：
  - **升级是否成功**（或回滚 + 原因 + 证据）
  - **五条回归各自的实测结果**（②③④ 是重点，贴数字）
  - **③ 的一致性结论**：像素差是多少、VLM 读到的差异是什么、定位到哪个节点（若有）
  - **pip 依赖的变更清单**（torch 动没动）
  - **磁盘纪律**（造了什么、删了什么）
  - 改动的文件清单
- **如实报告你的操作失误比做出漂亮结果重要得多**

---

## 七、后续队列（供你了解上下文，不必处理）

- **P56（本项通过后派）**：拉取 Pika H3 Flex 两个 LoRA，r2v/fl2v/t2v 三场景
  同 seed 对比 turbo → 裁定去留；
- **P57**：拉取 Fun ControlNet Union 2.0，验证 5090 32GB 上能不能跑、多慢；
- **P53/P54**：上次会话中断的半成品（qa_layers 债 / bubble sizes），不阻塞本项。
