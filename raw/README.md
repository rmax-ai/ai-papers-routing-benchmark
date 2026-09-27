# Raw evidence mirror

`raw/` is a sanitized mirror of the recovered DQ79 raw-evidence bundle. Filenames, JSON shapes, response paths, and recorded attempt records are preserved.

## Inventory

- Result JSONs: `l1-results.json`, `l2-results.json`, `l3-results.json`, and `l4-results.json`.
- Metric JSONs: `l1-metrics.json`, `l2-metrics.json`, `l3-metrics.json`, and `l4-metrics.json`.
- Audit, format, judge-map, and routing-policy JSONs: `l1-audit.json`, `l3-format-findings.json`, `l3-judge-map.json`, and `l3-routing-policy.json`.
- Prompt pilots: the L1, L2, L3, and judge pilot JSONs.
- Probes and model resolution: `capability-probes.json` and `gemini-model-resolution.json`.
- Manifest and original checksums: `manifest.json` and `SHA256SUMS.txt`.
- Supporting snapshots and packs: sampling, arXiv abstracts, cost report, prompt template, and question packs.
- `responses/` contains 300 per-call records organized by layer and provider, including retries, failures, and probe artifacts.

The response records retain the applied usage and cost fields used by the cost report. They are evidence records, not a second execution.

## Why some references appear dangling

First, references to `raw/pdfs/<id>.pdf` inside results, the manifest, and the original checksum file point to files intentionally not published here. The paper PDFs are excluded; arXiv IDs, URLs, public metadata, and page facts are published in `benchmark/corpus/` and `raw/sampling.json`.

Second, `raw/SHA256SUMS.txt` and `raw/manifest.json` describe the **full original bundle**, including those excluded files. They are preserved verbatim for traceability. `checksums/SHA256SUMS.txt` covers this public tree instead.

Sanitization collapsed absolute local paths to `~`; nothing else was changed in the copied raw artifacts. No credentials or account data are included.

`raw/capability-probe.pdf` is an 881-byte synthetic fixture used by the capability probe. It is the only PDF kept in this public tree.

The run's paper PDFs and extracted full text remain excluded. Their absence is intentional and does not invalidate the original-bundle references.

The result JSONs link each logical cell to its response artifacts. The metric JSONs summarize those links without removing the underlying attempts.

The pilot files explain prompt-shape corrections and setup exclusions. The question packs and routing policy preserve the exact typed questions and host-applied policy inputs.

The cost report is an all-attempt accounting record. It should not be confused with the L2 arm-only or L3 generator-arm views in the metric files.

The raw mirror is intentionally verbose so an auditor can move from a headline in `report/report.md` to a metric, then to the response file named by that metric.

The public checksum directory is generated after all authored files and copied responses are in place. It is separate from the recovered checksum file because the recovered file describes the larger original bundle.

Use `raw/manifest.json` and `raw/SHA256SUMS.txt` only as recovered-bundle traceability records; use `checksums/` to verify this repository.

The manifest's excluded PDF entries are expected dangling references in this mirror. They document the original input bundle, while the public corpus files document what remains available here.

The raw mirror includes the only published PDF, the synthetic capability fixture. It does not include paper PDFs or the extracted full-text scratch file.

The source response paths use the original layer/provider organization, which is also used by the representative-output index and selective-reading walkthrough.
