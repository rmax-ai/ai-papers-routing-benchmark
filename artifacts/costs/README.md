# Cost and latency

Every saved provider HTTP attempt was repriced from its recorded usage fields and applied rates. These are estimated charges, not provider invoice data. Stage aggregates include pilots, retries, invalid but billed responses, and zero-usage failures.

| Stage | Unique call IDs | Attempts | HTTP 200 / errors | Input / output tokens | Estimated cost | Request-latency sum |
|---|---:|---:|---:|---:|---:|---:|
| L1 | 96 | 110 | 109 / 1 | 106,085 / 10,579 | $0.021297 | 901.6 s |
| L2 | 34 | 36 | 33 / 3 | 378,737 / 19,436 | $0.162211 | 1,021.5 s |
| L3 | 88 | 97 | 95 / 2 | 1,372,808 / 102,755 | $0.350305 | 1,684.7 s |
| L4 | 47 | 47 | 47 / 0 | 107,111 / 5,358 | $0.004499 | 17.8 s |
| Capability probes | 10 | 10 | 6 / 4 | 922 / 55 | $0.000238 | 107.6 s |
| Total | 275 | 300 | 290 / 10 | 1,965,663 / 138,183 | $0.538550 | 3,733.3 s |

The applied per-million rates were GPT-6 Luna input $0.10, cached input $0.01, output $0.50; DeepSeek off-peak input/cached/output $0.15/$0.003/$0.60 and peak $0.30/$0.006/$1.20; Gemini input/cached/output $0.30/$0.30/$2.50; and JEV input/output $0.042/$0.

DeepSeek peak/off-peak handling was selected from call-start UTC. All recorded DeepSeek calls fell in the off-peak tier: $0.067903 off-peak and $0 peak.

The run was $0.538550 estimated, or 6.7% of the $8 cap. `raw/cost-report.json` reprices all 300 attempts, including failures, and retains stage, arm/provider, rate-source, and failed-attempt details.

The layer-specific comparison tables in `report/tables/` use raw milliseconds converted to seconds where the JSON records the latency sum. The report's displayed stage values are retained here for direct comparison.

The measured eight-paper matrix is a different accounting view: it excludes setup pilots and LLM judging, while full-reference cells include one shared D extraction pass. See `report/tables/l3-matrix.csv` for the report-sourced matrix rows.

Raw per-call costs retain provider rate sources, cached input treatment, and DeepSeek tier fields. Failed attempts remain present with zero usage when no provider response was recorded.

The total cost includes the four unsuccessful capability/setup attempts and the retry records. The all-run total is therefore not the sum of only successful response bodies.

Latency sums are provider round trips and exclude retry backoff and host waiting, matching the report's accounting convention.
