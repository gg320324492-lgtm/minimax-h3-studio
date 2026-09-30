# MiniMax-H3 Studio 升级总规划（Master Plan）

> 版本：v1.0（2026-09-30 立项）
> 状态：进行中 —— 逐 Phase 执行，见 [UPGRADE_PROGRESS.md](UPGRADE_PROGRESS.md)
> 前序阶段（Phase 0–7）已封版，记录见 [REMOTION_INTEGRATION_PROGRESS.md](REMOTION_INTEGRATION_PROGRESS.md)

---

## 0. 项目重新定义

本仓库不再是「MiniMax H3 视频生成工具」，而是：

> **一个本地 AI 视频导演与程序化 Motion Design 工作室。**

核心能力组合：

```
AI Director  +  Scene Graph  +  Remotion Motion Engine
             +  MiniMax H3 素材生成  +  Take Ranking
             +  Visual QA  +  Automatic Repair  +  Deterministic Rendering
```

**H3 是素材生成引擎。Remotion 是视觉合成引擎。Agent 是导演。Scene Graph 是系统的真正中心。**

---

## 1. 核心架构变更

### 现状

```
H3 生成画面 → Remotion 包装
```

### 目标

```
Brief / Script / Data / Reference
              │
              ▼
      Director / Planner
              │
              ▼
         Style Bible
              │
              ▼
          Scene Graph
        ┌─────┴─────┐
        │           │
        ▼           ▼
  H3 Assets    Remotion Graphics
  人物/场景      UI/数据/文字/2.5D
  B-roll
        └─────┬─────┘
              ▼
           Composer
              │
              ▼
        Visual Critic
              │
       ┌──────┴──────┐
       │             │
     PASS          REPAIR
       │             │
       │       Repair Planner
       │             │
       └──────◄──────┘
              │
              ▼
      Audio / Master / QA
              │
              ▼
           Delivery
```

### 职责划分（目标比例 80–90% 程序化视觉 / 10–20% H3）

| H3 负责 | Remotion 负责 |
|---|---|
| 人物、场景、cinematic B-roll | UI / Dashboard / 数据 / 图表 |
| 难以程序化的写实动态 | 数字 / 中文文字 / 表格 / Calendar |
| 情绪镜头、风格化素材 | Ranking / Browser Window / Card / Logo |
| | Brand Motion / Camera / 2.5D / Typography |

> **原则**：文字、数字、表格、UI 绝不交给 H3 生成——必须程序化渲染，100% 精准。

---

## 2. 执行铁律

1. **先审计再修改** —— P0 完成前不动生产代码。
2. **不破坏现有能力** —— DramaVertical / PsaWide / StoryAnimation / ReportVertical / CoverCard 与 timeline_v2 必须保持可运行。新体系一律「新增 schema / 模板 / pipeline / adapter」，不强制迁移旧项目。
3. **不随意删除** —— 已交付视频、archive、benchmark 原始结果、QA 报告、已验证脚本、用户项目数据默认不得删。废弃代码先标 `deprecated` + 进 production manifest，确认无依赖/有替代/可回滚后才归档。
4. **每个 Phase 独立可验收** —— 跑测试 + tsc + 真实渲染代表性样例 + 变更报告 + 遗留项。禁止「代码写了但没跑」。
5. **commit 但不自动 push** —— 除非用户明确授权。
6. **文档不 proliferate** —— 计划只维护 `UPGRADE_MASTER_PLAN.md` + `UPGRADE_PROGRESS.md` 两份，不产生互相矛盾的临时计划。

---

## 3. 视觉目标（最高优先级 benchmark）

参考视频 **第 24 秒以后**的视觉语言：

- Premium Fintech Product Film + Motion Design + Data Visualization + 2.5D UI Animation
- 超大 KPI 数字、极简背景、Dashboard 多窗口透视景深
- 巨大数字 + 立体柱阵、日历/数据卡/表格矩阵
- 黑卡 Quote + 极大留白、排名/slope graph、漂浮标签
- 3D 数据表面 + 蓝色柱体、图表快速轮换、窗口墙
- 金色 Logo Lockup、CTA 结尾
- 色系：黑 + 米白 + 金/橙点缀
- 约 59fps 的细腻运动

**高级感的来源是构图、字体、数据层级、空间运动、节奏 —— 且相当克制。** 不是特效多。

> **与现有 `ReportVertical` 分叉**：`ReportVertical` 保留为 `energetic`（抖音爆点）视觉体系；新建 `FinanceShowcaseWide` 为 `premium`（广告片）体系。两者不混用。

---

## 4. Phase 路线图（19 阶段，严格按序）

| Phase | 名称 | 核心产出 | 验收锚点 |
|---|---|---|---|
| **P0** | 全库审计与生产边界收敛 | `pipeline_manifest.yaml`、`config/`、审计报告 | 旧生产流程仍能启动 |
| **P1** | 自动选片 TakeRanker | `take_ranker.py` + 排名替换 T01 默认 | 真实 shot ≥3 takes 自动选优 |
| **P2** | H3 Atomic Shot + Prompt Compiler | `ShotSpec` schema、编译器、shot 级重试 | 一生成=一原子镜头 |
| **P3** | Showcase Scene Graph | `schemas/showcase-v1.ts` + 20 种 scene 类型 | Agent 生成 Scene JSON 而非 TSX |
| **P4** | FinanceShowcaseWide 模板 | 1920×1080@60fps，KPI/Dashboard/BigNumber/Calendar 四类代表 scene | 复刻参考片 24–40s 视觉结构 |
| **P5** | Motion Design Foundation | `motion/` + `components/` primitives、motionTokens | 组件不再自造 spring |
| **P6** | Design System | `design/` tokens：palette/typography/spacing/depth，premium-dark/light | 全 scene 统一品牌语言 |
| **P7** | 图表引擎 | 自研 SVG 图表集（Bar/Line/Area/Slope/Bubble/Heatmap/Rank/Sparkline/Volume） | 不依赖通用 chart 库默认样式 |
| **P8** | Format 数据驱动 | `calculateMetadata` 返回 width/height/fps/duration | 1080p60 / 竖屏60 / 4K60 schema 支持 |
| **P9** | Beat Grid + 高级音频同步 | `BeatGrid`（bar/beat/half/accent/phrase）、premium SFX profile | 动作绑定音乐化 |
| **P10** | Visual QA | `visual_qa.py`：deterministic 规则 + VLM critic | 技术 QA 与视觉 QA 分离 |
| **P11** | Auto Repair Loop | Repair Planner + patch props + scene 级重渲，MAX_REPAIR_ROUNDS=3 | 常见布局错误自动修复 |
| **P12** | Director Agent | Brief→StyleBible→Storyboard→SceneGraph→AssetPlan | Agent 不直接改 TSX |
| **P13** | Scene Cache / 增量构建 | `job_state.json` + hash 缓存 | 改一个 scene 不重跑全片 |
| **P14** | Render Worker / Fast Preview | 长驻 bundle + scene/draft/full 分级渲染 | repair loop 用 preview 非 full |
| **P15** | SR 路由升级 | SR Router：程序化内容免 SR，H3 走 SR，FlashVSR 仅纹理丰富镜头 | UI/文字绝不经过 Real-ESRGAN |
| **P16** | 参考视频 Benchmark | `reference_analysis.json` + 24–40s 复刻 → 40–82s 扩展 | 视觉语言对齐（不复制品牌内容） |
| **P17** | Showcase Demo | 全新 16:9 / 1920×1080 / 60fps / 45–60s 商业级 demo | 明显达到 premium product film |
| **P18** | 最终 QA（四类） | Technical / Layout / Motion / Visual 四层门禁 | 全过 |

### 每个 Phase 的固定报告格式

```markdown
## Phase X Result
### Implemented        ### Changed Files      ### Tests
### Real Render        ### Metrics            ### Problems Found
### Remaining Risks    ### Compatibility      ### Next Phase
```

---

## 5. 需要修复的现有问题（专项）

| 编号 | 问题 | 修复阶段 | 备注 |
|---|---|---|---|
| A | `select_takes.py` 实际无选片（T01 默认胜出） | P1 | **最高优先级**，取消 T01 默认 |
| B | `fit: fill` 造成几何变形 | P4 起 | 高品质 pipeline 改 cover/contain/controlled crop；`fill` 仅在源与目标严格同比例时保留（本项目 SR 链是 Lanczos 直拉，故 EP01 保留 fill 属已知例外） |
| C | timeline_v2 无限扩字段 | P3 | 短剧继续 v2，高级项目走 showcase-v1，不破坏 |
| D | `Root.tsx` 硬编码 fps/width/height | P8 | 新模板 metadata-driven，60fps |
| E | 技术 QA ≠ 视觉 QA | P10 | 两套分离 |
| F | H3 multi-shot prompt | P2 | 生产模式一生成=一原子镜头 |
| G | Agent 直接写视觉代码 | P12 | Agent 默认产出 Scene JSON，TSX 是稳定组件库 |

---

## 6. 目标代码组织

```
pipeline/
  director/ generation/ ranking/ visual_qa/ repair/ state/

studio/src/
  components/  charts/ data/ typography/ ui/ camera/
  motion/      design/  schemas/  templates/finance-showcase/
```

> 避免继续把所有东西堆进 `templates/common`。

**最终文档集**（逐阶段产出）：`ARCHITECTURE.md` `PIPELINE.md` `SHOWCASE_SCHEMA.md` `MOTION_SYSTEM.md` `VISUAL_QA.md` `AGENT_WORKFLOW.md`

---

## 7. 测试与性能要求

**测试**：每个新增核心模块必须有测试。`pnpm exec tsc --noEmit`；schema 三方一致（TS zod / JSON Schema / Python jsonschema）；Remotion renderStill + 短预览 + 代表性全片；Python 关键模块（TakeRanker / state hashing / manifest / visual QA 规则 / reference analyzer）加 pytest。

**性能**：benchmark `1080p60 / 30s / 代表性 showcase`，记录 bundle、render time、memory、output size，preview 与 final 分别测。重点检测渲染杀手：大 blur、backdrop-filter、SVG filters、Three.js、大 box-shadow、per-frame FFT、海量 DOM、motion blur samples。

**Three.js 边界**：默认 React + SVG + CSS 3D。仅 data-plane / 大规模 3D columns / 真 3D camera 场景引入 `@remotion/three`。Dashboard 用 Three.js 属错误架构。

---

## 8. 禁止事项

未经验证不得：大规模删除旧代码 · 强制迁移全部项目 · 自动 push · 修改用户交付目录 · 用 mtime 猜 ComfyUI 输出 · 用 AI 生成 UI 文字/数字替代程序化绘制 · 所有视频强行 FlashVSR · 每次 repair 重跑全片 H3 · 每个新视频生成独立 TSX · 引入多个重叠 chart 库 · 用大量 shake/flash/RGB split 冒充高级感。

---

## 9. 最终验收标准

升级成功不是看新增多少代码，而是至少满足：

1. 给一份数据 JSON，Agent 能生成高级数据产品宣传视频
2. 数字、中文、表格、UI 全部稳定无幻觉
3. H3 只用于合适的生成式内容
4. 一个 H3 镜头有真正自动选片
5. Scene 可单独重新生成、重新渲染
6. Scene 可以自动 Visual QA
7. 常见布局错误可以自动 repair
8. 参考视频 24 秒以后主要视觉语言基本能被当前组件系统表达
9. 整个视觉风格由统一 Style Bible 管理
10. 成片达到商业级 Premium Product Film，而非「AI 视频 + 字幕 + 特效」
