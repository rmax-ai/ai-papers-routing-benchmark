# DQ84 follow-up: one-pass GPT-6 Luna vs Gemini evidence extraction

This subtree is a follow-up benchmark in the same series as the DQ79 evaluation published at the root of this repository: a bounded, controlled comparison of two evidence pipelines for the AI Papers Insights program.

**Question** (source: [rmax-ai/delegation-queue#84](https://github.com/rmax-ai/delegation-queue/issues/84)): does a separate **Gemini Flash-Lite full-document evidence-extraction stage** improve evidence quality enough to justify its extra cost / latency / complexity, compared with giving the same full paper text directly to **GPT-6 Luna** in one pass?

**Design.** Both arms ran on the same eight-paper DQ79 subset, the same cached full-text extraction, the same canonical output schema and evidence requirements, and the same deterministic checks; the only variable is the evidence path:

- **Arm A** — full extracted paper text → GPT-6 Luna (one pass: evidence identification + PaperInsight synthesis).
- **Arm B** — full extracted paper text → Gemini Flash-Lite structured evidence packet → GPT-6 Luna synthesis from the packet.

**Outcome (summary).** One-pass Luna did not cede its place. B tripled measured cost per paper ($0.0109 vs $0.0036) and raised median serial latency (39.8s vs 15.4s), yet its final artifacts scored lower on load-bearing-page recall (0.273 vs 0.509), cited-quote containment (0.654 vs 0.804), unsupported-claim rate (43% vs 13%), and blind-judge dimensions (faithfulness 3.29 vs 4.00; evidence support 2.71 vs 4.00). B's only directional gain was lexical claim overlap against the DQ79 reference claims (0.652 vs 0.440 at Jaccard 0.20) — a measure confounded by the reference itself being Gemini-generated — and part of that gain was lost at the packet→synthesis hand-off (7 of 24 packet-matched claims). The run's own verdict: the data do not establish that the Gemini stage earns its added cost and latency; prefer the simpler one-pass architecture unless a targeted follow-up changes the evidence.

Full report with all tables, failure cases, and caveats: [`report.md`](report.md). Article-ready artifacts: [`comparison-table.md`](comparison-table.md), [`findings.md`](findings.md). Modeled escalation costs and throughput: [`scale-model.json`](scale-model.json).

**Provenance.** Executed 2026-09-27 UTC on the rmax-10 host as a single scoped Codex run (`gpt-6-luna`, max effort, direct rail; provider egress scoped to OpenAI/Gemini/DeepSeek for the run). Measured total spend **$0.188291** (cap $8), 36 persisted attempt artifacts. The run reused the DQ79 corpus subset, reference claims/pages, canonical schema, deterministic checks, and rate card; input compatibility was verified byte-for-byte (8/8 request-body SHA256 match, `report.md` → "Benchmark design and controls"). Run-harvest checksums live in the local evidence bundle; this subtree carries its own integrity manifest under `checksums/`. Paper PDFs and full extracted text are not redistributed (see [`../PROVENANCE.md`](../PROVENANCE.md)).

**Layout.**

```text
report.md               terminal report (all tables, failure cases, caveats)
comparison-table.md     article-ready architecture comparison table
findings.md             concise findings
metrics/                per-paper and aggregate measurements (JSON + CSV)
prompts/                canonical prompt templates + output schema + hashes
examples/               short representative output excerpts (≤25-word quotes)
harness/                benchmark harness used for this run
scale-model.json        modeled escalation costs and throughput under worker pools
checksums/              SHA256SUMS + MANIFEST.json for this subtree (repo-root-relative paths)
```

**Verification.** From the repository root:

```bash
sha256sum -c dq84-luna-vs-gemini/checksums/SHA256SUMS.txt
```

The DQ84 subtree does not modify any DQ79 artifact; the DQ79 release records in `checksums/` remain pinned to their original content.
