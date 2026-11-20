# experiments/ 目录分类清单（2026-11-21）

> 工单要求：只做分类报告与归位建议，不删除、不移动任何文件。
> 判据：文件名或内容在 `docs/*.md`、`pipeline_manifest.yaml`、`productions/*/scripts/`（含
> `scripts/`、`tests/`、`studio/`）中被提及 → 有存档价值；否则视为历史残留候选。
> 引用检索范围：docs/、pipeline_manifest.yaml、productions/、scripts/、tests/、studio/、config/
> （grep 文件名，排除 experiments/ 自身）。

## 一、结论摘要

- experiments/ 合计 **0.84 MB**（43 个顶层脚本 + `_ref_analysis/` 5 个文件），无异常体量目录。
- **保留（有明确引用/登记）：37 项**；**待定（仅 manifest 登记为 superseded/archive，或属证据目录成员）：11 项**；**可删：0 项**。
- `_ref_analysis/` 已从缺口文档记载的 151 MB 清理到 **615 KB**，未复生；目录整体作为 P16
  参照基准测量证据被 `docs/P16_REFERENCE_BENCHMARK.md`、`docs/WORKORDER_P37_REFERENCE_REANALYSIS.md`、
  `docs/GAP_BACKLOG_20261120.md` 和守护测试 `tests/test_p16_reference_is_not_an_input_free_measurement.py` 引用，**建议整目录保留**。
- `pipeline_manifest.yaml` 已把全部 43 个顶层脚本登记在四类之一
  （experimental_approved / benchmark_only / forbidden / superseded / archive_candidates），
  其中 forbidden 类（6 个）是"Agent 调用即事故"的风险证据，删除会破坏登记完整性，均建议保留。

## 二、分类清单

| 文件 | 体积 | 被谁引用 | 建议 |
|---|---|---|---|
| _ref_analysis/ab_h3_720p.py | 5.0 KB | 无直接引用（属 P16 证据目录成员） | 待定（随目录保留） |
| _ref_analysis/cuts.txt | 0.8 KB | docs/P16_REFERENCE_BENCHMARK.md、docs/UPGRADE_PROGRESS.md、docs/WORKORDER_P37_REFERENCE_REANALYSIS.md、tests/test_p16_reference_is_not_an_input_free_measurement.py | 保留 |
| _ref_analysis/hist2.json | 266 KB | tests/test_p16_reference_is_not_an_input_free_measurement.py | 保留 |
| _ref_analysis/probe_liaozhai.py | 8.2 KB | docs/P16_REFERENCE_BENCHMARK.md、tests/test_p16_reference_is_not_an_input_free_measurement.py | 保留 |
| _ref_analysis/tts_smoke.wav | 349 KB | 无直接引用（属 P16 证据目录成员） | 待定（随目录保留） |
| bench.py | 6.3 KB | docs/ARCHITECTURE_AUDIT_20260930.md、docs/P55_COMFYUI_UPGRADE.md、pipeline_manifest.yaml（benchmark_only"唯一干净 poller"）、productions/ceo_mindread_ep01/scripts/comfy_utils.py:100（deadline 模式出处） | 保留 |
| bench_4k_chain.py | 4.2 KB | docs/OPTIMAL_PIPELINE_REPORT.md、pipeline_manifest.yaml（"结论仍被 flashvsr_upscale 引用"） | 保留 |
| bench_dtype.py | 4.8 KB | docs/OPTIMAL_PIPELINE_REPORT.md、pipeline_manifest.yaml | 保留 |
| bench_log.py | 4.7 KB | pipeline_manifest.yaml（benchmark_only"唯一 VRAM 探针"） | 保留 |
| bench_real_esrgan.py | 5.9 KB | docs/OPTIMAL_PIPELINE_REPORT.md、pipeline_manifest.yaml | 保留 |
| convert_seedvr2.py | 1.3 KB | docs/OPTIMAL_PIPELINE_REPORT.md、pipeline_manifest.yaml（archive_candidates；SeedVR2 权重前缀转换的唯一记录） | 保留 |
| download_models.py | 3.8 KB | docs/UPGRADE_PROGRESS.md（作为风险证据点名）、pipeline_manifest.yaml（forbidden：硬编码代理+误删 20GB 部分下载） | 保留（禁用≠删除，forbidden 登记需在场） |
| fix_combine.py | 1.3 KB | pipeline_manifest.yaml（archive_candidates） | 待定（可归档） |
| flashvsr_upscale.py | 15.3 KB | docs/ARCHITECTURE_AUDIT_20260930.md、docs/UPGRADE_REPORT_20260919.md、pipeline_manifest.yaml（experimental_approved：P15 SR 路由候选实现） | 保留 |
| flicker_test.py | 3.2 KB | docs/OPTIMAL_PIPELINE_REPORT.md、docs/UPGRADE_REPORT_20260919.md、pipeline_manifest.yaml（superseded：被 quality_compare.py 取代） | 待定（已被取代，文档引用过可归档） |
| full_pipeline.py | 4.7 KB | docs/UPGRADE_REPORT_20260919.md、pipeline_manifest.yaml（forbidden：import _deprecated 崩溃）、scripts/sr_pipeline_v2.py:4（v2 取代链） | 保留 |
| gen_lulu.py | 8.3 KB | docs/UPGRADE_REPORT_20260919.md、pipeline_manifest.yaml（superseded） | 待定（可归档） |
| gen_remaining.py | 7.2 KB | docs/UPGRADE_REPORT_20260919.md、pipeline_manifest.yaml（superseded） | 待定（可归档） |
| gen_round_a.py | 7.8 KB | docs/UPGRADE_REPORT_20260919.md、pipeline_manifest.yaml（forbidden：删仓库根文件+无 deadline） | 保留（forbidden 证据） |
| generate_4.py | 9.7 KB | docs/UPGRADE_REPORT_20260919.md、pipeline_manifest.yaml（superseded） | 待定（可归档） |
| motion_analysis.py | 1.8 KB | docs/P16_REFERENCE_BENCHMARK.md、pipeline_manifest.yaml（archive_candidates） | 保留 |
| multi_bench.py | 3.7 KB | pipeline_manifest.yaml（benchmark_only） | 保留 |
| outputs_paths.py | 1.4 KB | pipeline_manifest.yaml（archive_candidates："无人 import"；输出路径常量原始定义） | 待定（可归档） |
| p55_compare.py | 3.5 KB | docs/P55_COMFYUI_UPGRADE.md、pipeline_manifest.yaml | 保留 |
| p55_runner.py | 11.1 KB | docs/P55_COMFYUI_UPGRADE.md、pipeline_manifest.yaml | 保留 |
| p56_build_workflows.py | 18.8 KB | docs/P56_PIKA_FLEX_COMPARISON.md、pipeline_manifest.yaml | 保留 |
| p56_measure.py | 7.1 KB | pipeline_manifest.yaml（benchmark_only，P56 对比读数） | 保留 |
| p56_runner.py | 10.5 KB | docs/P56_PIKA_FLEX_COMPARISON.md、pipeline_manifest.yaml | 保留 |
| p57_build_workflows.py | 7.0 KB | docs/P57_CONTROLNET_UNION_VERDICT.md、pipeline_manifest.yaml | 保留 |
| p57_compare.py | 4.0 KB | docs/P57_CONTROLNET_UNION_VERDICT.md、pipeline_manifest.yaml | 保留 |
| p57_control_assets.py | 5.7 KB | docs/P57_CONTROLNET_UNION_VERDICT.md、docs/UPGRADE_PROGRESS.md、pipeline_manifest.yaml | 保留 |
| p57_measure.py | 2.6 KB | docs/P57_CONTROLNET_UNION_VERDICT.md、pipeline_manifest.yaml | 保留 |
| p57_runner.py | 5.3 KB | docs/P57_CONTROLNET_UNION_VERDICT.md、pipeline_manifest.yaml | 保留 |
| p58_build_workflows.py | 6.6 KB | docs/P58_REAL_EXTRACTION.md、pipeline_manifest.yaml | 保留 |
| p58_extract.py | 7.7 KB | docs/P58_REAL_EXTRACTION.md、pipeline_manifest.yaml | 保留 |
| p58_measure.py | 6.4 KB | docs/P58_REAL_EXTRACTION.md、pipeline_manifest.yaml | 保留 |
| p58_measure_extract.py | 5.5 KB | docs/P58_REAL_EXTRACTION.md、pipeline_manifest.yaml | 保留 |
| p58_runner.py | 5.0 KB | docs/P58_REAL_EXTRACTION.md、pipeline_manifest.yaml | 保留 |
| pipe_4k.py | 4.2 KB | docs/ARCHITECTURE_AUDIT_20260930.md、docs/OPTIMAL_PIPELINE_REPORT.md、pipeline_manifest.yaml（forbidden：无 __main__ 守卫） | 保留 |
| pipe_4k_fast.py | 5.0 KB | docs/ARCHITECTURE_AUDIT_20260930.md、docs/OPTIMAL_PIPELINE_REPORT.md、docs/TEST_REPORT_20260910.md、docs/UPGRADE_REPORT_20260919.md、productions/ceo_mindread_ep01/scripts/finalize.py:199、productions/ceo_mindread_ep01/09_final/render_report.md、productions/ceo_mindread_ep01/RESUME_STATE.md、scripts/sr_pipeline_v2.py:34、pipeline_manifest.yaml（forbidden） | 保留 |
| pipe_fast.py | 4.8 KB | docs/OPTIMAL_PIPELINE_REPORT.md、docs/TEST_REPORT_20260910.md、docs/UPGRADE_REPORT_20260919.md、scripts/sr_pipeline_v2.py:4、pipeline_manifest.yaml（forbidden） | 保留 |
| quality_compare.py | 5.7 KB | docs/HANDOFF_VERIFIER_20261001.md、docs/OPTIMAL_PIPELINE_REPORT.md、docs/UPGRADE_PROGRESS.md、docs/UPGRADE_REPORT_20260919.md、pipeline_manifest.yaml（benchmark_only，flicker_test 的严格超集） | 保留 |
| test_seedvr2.py | 4.9 KB | docs/OPTIMAL_PIPELINE_REPORT.md、pipeline_manifest.yaml（forbidden：mtime 唯一主路径） | 保留 |
| upscale_a1.py | 5.1 KB | pipeline_manifest.yaml（superseded） | 待定（可归档） |
| upscale_fix.py | 5.0 KB | pipeline_manifest.yaml（superseded） | 待定（可归档） |
| upscale_generic.py | 4.2 KB | pipeline_manifest.yaml（superseded） | 待定（可归档） |
| upscale_to_4k.py | 4.7 KB | docs/UPGRADE_REPORT_20260919.md（弃用表）、pipeline_manifest.yaml（forbidden） | 保留 |
| upscale_x4v3.py | 5.2 KB | docs/TEST_REPORT_20260910.md、docs/UPGRADE_REPORT_20260919.md、pipeline_manifest.yaml（forbidden） | 保留 |

## 三、异常体量产物目录检查

- `_ref_analysis/`：现存 5 个文件共 615 KB（ab_h3_720p.py 5.0K、cuts.txt 0.8K、hist2.json 266K、
  probe_liaozhai.py 8.2K、tts_smoke.wav 349K）。缺口文档 `docs/GAP_BACKLOG_20261120.md` 记载清理前
  为 151 MB，现已清干净且**未复生**，无大文件残留。
- experiments/ 顶层无其他子目录；全部 43 个脚本均为 <19 KB 的纯文本脚本。
- 全目录合计 0.84 MB，无异常体量。

## 四、归位建议（本工单不执行，仅供参考）

1. **保留类**（37 项）原地不动；其中 forbidden 6 项是 manifest 风险登记的实物证据，
   建议与 manifest 同步保留。
2. **待定类**（11 项）：`flicker_test.py`、`gen_lulu.py`、`gen_remaining.py`、`generate_4.py`、
   `upscale_a1.py`、`upscale_fix.py`、`upscale_generic.py`、`fix_combine.py`、`outputs_paths.py`
   可移入归档目录（如 `experiments/_archive/`，并同步更新 pipeline_manifest.yaml 里的路径）；
   `_ref_analysis/ab_h3_720p.py`、`tts_smoke.wav` 随 P16 证据目录整体保留。
3. 若做归档移动，需同步改 `pipeline_manifest.yaml` 中 12 处 `experiments/...` 路径引用，
   并跑 `tests/` 守护测试确认无路径断链（P16 测试直接引用 `experiments/_ref_analysis/` 内文件）。
