# Corpus manifest

The full frozen selection manifest is [raw/sampling.json](../../raw/sampling.json). It contains the fixed paper records, stratum fields, public metadata snapshot, KG-entry tags, PDF fetch outcomes, candidate IDs, and the L2/L3 subset IDs.

Per-PDF page, image, figure-reference, and table-reference facts are in [pdf-info.json](pdf-info.json). The public arXiv metadata snapshot is [raw/arxiv-abstracts.json](../../raw/arxiv-abstracts.json).

`sample-24.csv` is the compact, readable view. Each row retains the arXiv id and version, title, stratum, source-store label, categories, paper date, KG-entry tag, PDF outcome, page count, heavy-PDF flag, and the selection rationale.

The two upstream stores are private local systems and are **not** published. This tree publishes only the frozen 24-paper selection, public arXiv metadata, and derived facts.

Strata:

- `high_value_proxy`: 12 papers.
- `medium_adjacent`: 8 papers.
- `low_relevance_control`: 4 papers.

The sample is purposive, not random, and the labels are proxies rather than gold relevance judgments.

Downloaded rows include the byte count in `pdf_fetch`; not-attempted rows leave the page field blank. The `long_figure_or_table_heavy` flag is the frozen result of the page/image/figure/table rule, not a claim about paper quality.

`x_rationale` is the short corpus-table rationale used by the evaluation. It is intentionally separate from the much longer local digest notes in the full selection manifest.

The L2/L3 paper IDs are also recorded in `raw/sampling.json`; the compact CSV does not duplicate those subset columns.

The source-store labels in the compact CSV are functional labels only. They identify the selection family without publishing local database paths.

The arXiv URLs and IDs in the recovered manifest are public metadata references; they are not a redistribution of the excluded PDF media.
