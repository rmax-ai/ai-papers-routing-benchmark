# Metrics artifacts

The raw JSONs are the machine-readable record. This index points to the metric artifact that answers each question.

| File | What it answers | Source script |
|---|---|---|
| `raw/l1-metrics.json` | Routing judge discrimination, thresholds, calibration, and agreement inputs | `l1_metrics.py` |
| `raw/l2-metrics.json` | PDF-strategy page, claim, usage, and selective-miss measurements | `l2_metrics.py` |
| `raw/l3-metrics.json` | Generator schema, citation, sensitivity, and blind-judge summaries | `l3_metrics.py` |
| `raw/l4-metrics.json` | Typed post-generation probabilities and proxy comparisons | `l4_metrics.py` |
| `raw/l1-audit.json` | Disagreement-enriched abstract audit | `run_l1.py` / audit stage |
| `raw/l3-format-findings.json` | L3 output and judge-format failures | `l3_format_audit.py` |
| `raw/l3-judge-map.json` | Blind-label to generator mapping | `run_l3.py` |
| `raw/capability-probes.json` | Provider capability and setup checks | `run_probes.py` |
| `raw/gemini-model-resolution.json` | Gemini selector correction and resolved catalogue entry | `run_probes.py` |

Headline metrics from the report:

- L1 AUROCs: JEV 0.993, DeepSeek 0.986, Gemini 0.969, GPT-6 Luna 0.889.
- L2 mean claim recall/cost: A 0.554/$0.013917, B 0.631/$0.047685, C 0.212/$0.019829, D 1.000/$0.079121.
- L2 selective mean load-bearing-page recall: 0.309.
- L3 GPT-6 Luna normalized schema: 8/8 on full-reference and 8/8 on selective; DeepSeek and Gemini were 0/8 native canonical on both paths.
- L4 support agreement was 0.553; actionability agreement was 0.861.
- Total estimated run cost was $0.538550.

These figures are bounded observations from the purposive run. The raw files retain the full precision and per-call evidence.
