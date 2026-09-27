# Provenance

## Source run

This publication is the recovered output of [rmax-ai/delegation-queue#79](https://github.com/rmax-ai/delegation-queue/issues/79), with related feasibility work in [#78](https://github.com/rmax-ai/delegation-queue/issues/78).

The run started on **2026-09-25 UTC**. A host stall interrupted the first execution. It resumed from the preserved checkpoint on **2026-09-26 22:04Z** and completed at **23:28:51Z**, with `rc=0`.

The terminal synthesis records the all-attempt totals:

- 300 attempts / 275 unique call IDs.
- 1,965,663 input tokens / 138,183 output tokens.
- $0.538550 estimated total cost.
- 6.7% of the $8 cap.

## Preserved evidence

The public tree preserves the recovered `raw/` mirror, the terminal `report/`, the reproduction `benchmark/harness/`, the frozen corpus manifests, and selected representative response artifacts.

`report/report.md` is the benchmark report copied from the source evaluation. `report/issue-79-terminal-synthesis.md` is the terminal synthesis comment copied from the source issue. Neither has been shortened or restructured.

The response archive retains every recovered per-call record, including retries, failed attempts, malformed outputs, and zero-usage outage records. The public archive therefore keeps operational failures as data rather than silently discarding them.

## Intentional exclusions

The ten paper PDFs under the recovered bundle's `pdfs/` directory are intentionally excluded. ArXiv IDs, URLs, public metadata, page facts, and derived artifacts remain published, but the paper media is not redistributed here.

The extracted full paper text is also excluded. It is represented by the published metrics and by the evidence paths recorded in the raw results.

The private local corpus stores whose sampled metadata seeded the corpus are not published. Only the frozen 24-paper selection, public arXiv metadata, and derived artifacts are included.

Delegation-queue worktree files, including design, plan, source, tests, operations, skills, documentation, and repository configuration files, are not part of this publication tree.

## Sanitization

Absolute local paths were collapsed to `~` in terminal artifacts where required. No credentials, keys, or account data are present in the published evidence; the source issue records the corresponding scans.

The raw top-level JSON files and response records were copied without content changes. The original raw manifest and checksum file intentionally retain references to the full recovered bundle, including excluded paper PDFs.

## Checksums policy

`checksums/SHA256SUMS.txt` covers this public tree, excluding itself and the `.git/` directory. `checksums/MANIFEST.json` records the same public file inventory and byte counts.

`raw/SHA256SUMS.txt` is the recovered bundle's original checksum file. It also covers files not published here, by design, including the excluded paper PDFs. `raw/manifest.json` has the same full-bundle scope and is preserved verbatim for traceability.

## Path mapping

The terminal report cites evidence as `raw/<name>`. Those paths refer to this repository's `raw/` mirror, which preserves the recovered bundle's filenames and response layout.

The run is not re-executed in this repository. The only regeneration step is the offline `benchmark/harness/make_tables.py` script, which reads the frozen public JSONs.

## Accounting and traceability

The total includes capability probes, pilots, retries, invalid but billed responses, and zero-usage failures; the raw response archive is the lowest-level evidence for the attempt totals, and the cost report is the normalized accounting view. The report's matrix prices the measured eight-paper cells separately from the all-attempt stage totals, so the public table generator keeps matrix costs report-sourced while deriving stage and arm fields from JSON where possible.

The publication build performs no provider calls, corpus-store reads, or benchmark pipeline stages: the raw bundle, report, and selected artifacts are a frozen record of the earlier run. The recovery header in the terminal synthesis is retained because the host stall and checkpoint resume explain why outage-window artifacts appear alongside successful records.

This repository's checksums are generated last, after the table CSVs and authored documentation are complete; they are the verification boundary for the publication tree.

## Follow-up run (DQ84)

A second, controlled benchmark was added on 2026-09-27 atop release `8fdc741` under `dq84-luna-vs-gemini/`: one-pass GPT-6 Luna versus a Gemini Flash-Lite evidence-extraction stage feeding the same GPT-6 Luna synthesis (source: [rmax-ai/delegation-queue#84](https://github.com/rmax-ai/delegation-queue/issues/84)). It reused this tree's eight-paper subset, reference claims/pages, canonical schema and checks, and rate card, with byte-exact input compatibility (8/8 request-body SHA256 match) and a measured spend of $0.188291. Its integrity records live under `dq84-luna-vs-gemini/checksums/` (SHA256SUMS.txt, MANIFEST.json). The DQ79 release records in the root `checksums/` remain pinned to their original content and are not re-issued by this addition.
