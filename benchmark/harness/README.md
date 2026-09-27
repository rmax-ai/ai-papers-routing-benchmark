# Benchmark harness

## Runtime

The original run used Python 3.13.5 and uv 0.12.16.

Recorded runtime dependencies were requests 2.34.2, PyMuPDF 1.28.2, and pypdf 6.19.0. The harness scripts use provider-specific structured-output and PDF handling recorded in `raw/`.

## Environment

Provider credentials are read only from the process environment by `provider.py` and are never stored in this repository:

- `DEEPSEEK_API_KEY`
- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `AI_GATEWAY_API_KEY`

The exact provider endpoints, model identifiers, timeouts, retry behavior, applied rates, and response usage mappings are recorded in the report and raw response artifacts.

## Execution order

The original order was:

```text
run_probes
prompt_pilot
run_l1
l1_metrics
run_l2
l2_metrics
run_l3
l3_format_audit + l3_metrics
run_l4
l4_metrics
cost_report
report_writer / finish_report
finalize_artifacts
```

The published provider and pipeline scripts are historical reproduction tools. Do not run them against a live provider as part of validating this publication.

## Inputs and outputs

`run_probes.py` uses the configured provider environment and writes capability probes plus per-call probe records. `prompt_pilot.py` writes the saved pilot records.

`fetch_corpus.py` and `select_sample.py` require the two private local paper stores used by the original run. Their frozen selection output is published as `raw/sampling.json`; their PDF facts are published as `benchmark/corpus/pdf-info.json`. The private stores themselves are not included.

`run_l1.py` reads the frozen sample and question pack and writes `raw/l1-results.json` and L1 response records. `l1_metrics.py` writes `raw/l1-metrics.json`.

`run_l2.py` reads the selected PDF/text inputs and writes `raw/l2-results.json` and L2 response records. `l2_metrics.py` writes `raw/l2-metrics.json`.

`run_l3.py` reads L2 outputs and routing policy inputs and writes `raw/l3-results.json` and generator/judge response records. `l3_format_audit.py` writes `raw/l3-format-findings.json`; `l3_metrics.py` writes `raw/l3-metrics.json`.

`run_l4.py` reads generated insight artifacts and writes `raw/l4-results.json` and typed JEV response records. `l4_metrics.py` writes `raw/l4-metrics.json`.

`cost_report.py` reprices all saved attempts into `raw/cost-report.json`. The report-writing and artifact-finalization scripts correspond to the recovered report and indexes.

## Offline table regeneration

The published raw bundle is the frozen output of the original run. `make_tables.py` is the only harness script that must be run to regenerate the publication tables from the published JSONs.

Run it from the repository root:

```bash
python3 benchmark/harness/make_tables.py
```

It uses only the Python standard library, reads paths relative to the repository root, touches no network, and writes the eight CSVs under `report/tables/`.

The seven matrix cost cells are **report-sourced** because the report's accounting intentionally differs from some per-arm metric aggregates. The matrix values are copied from the report's Generator x evaluator matrix; the supporting evidence strings are likewise report-sourced. Other table values are derived directly from the published JSONs where the JSON contains the field.

All CSVs are UTF-8 with LF line endings, a header row, and standard comma quoting.
