# AI Papers Insights routing benchmark

A recovered, public publication tree for the bounded DQ79 evaluation of routing, PDF evidence strategies, insight generation, and post-generation checks.

## Key finding

The selective-reading hypothesis is **not supported** at the tested page budget. Selective reading (strategy C) recovered only **0.309 mean load-bearing-page recall** and requested no further pages on all eight papers. The only measured pipeline meeting the benchmark's structural/quality gates was full-document reference (strategy D) → GPT-6 Luna. The overall run cost was **$0.538550 estimated**, or **6.7% of an $8 cap**.

## The experiment

The question was: can cheaper routing (JEV / small-model triage) plus selective PDF reading replace full-document evidence review for paper-insight generation?

The benchmark has four layers:

1. **L1 routing judges:** compare JEV, DeepSeek Flash, Gemini Flash-Lite, and GPT-6 Luna on purposive proxy labels.
2. **L2 PDF strategies:** compare abstract-only, whole-PDF native, selective page-image, and full extracted-text reference inputs.
3. **L3 insight generation matrix:** compare generators on full-reference and selective evidence paths, with structural checks and blind judging.
4. **L4 JEV post-generation checks:** evaluate evidence support, agenda relevance, duplication, actionability, and escalation signals.

## The routing matrix

The seven measured pipeline cells had these direct inference costs for eight papers:

| Pipeline cell | Cost for 8 papers |
|---|---:|
| Full-document D → DeepSeek Flash | $0.128960 |
| Full-document D → Gemini Flash-Lite | $0.183133 |
| Full-document D → GPT-6 Luna | $0.112304 |
| JEV triage → Gemini selective C → DeepSeek | $0.034955 |
| JEV triage → Gemini selective C → Gemini | $0.070581 |
| JEV triage → Gemini selective C → GPT-6 Luna | $0.032042 |
| Best measured generator GPT-6 Luna → JEV post-check | $0.113075 |

The L1 judge line was JEV at P(relevant) ≥0.70: precision **0.857** and recall **1.000** on the purposive proxy labels.

## Caveats

1. The sample is purposive: 24 papers, with 12/8/4 strata, not a random sample; labels are proxies, not gold.
2. Several judge cells have small-n coverage, with 4-13 ratings per dimension.
3. Quote containment is a string match, not semantic entailment.
4. Thresholds and tolerances were post-hoc, not preregistered.
5. Cells were run once.
6. Cost figures are estimates from recorded usage, not provider invoices.

## Repository map

```text
benchmark/       standalone methodology, corpus manifest, and reproduction harness
report/          terminal report, synthesis comment, and generated tables
artifacts/       metric, cost, failure, and representative-output indexes
raw/             sanitized frozen evidence mirror, including 300 response records
checksums/       checksums and manifest for this public tree
```

## Reproduction

Read [benchmark/methodology.md](benchmark/methodology.md) and [benchmark/harness/README.md](benchmark/harness/README.md) first. The original run used these exact model and provider identifiers:

| Role | Identifier and path |
|---|---|
| DeepSeek | `deepseek-flash` — `https://api.deepseek.com/chat/completions` |
| Gemini | `gemini-3.5-flash-lite` — generativelanguage v1beta `generateContent` |
| OpenAI | `gpt-6-luna` — `https://api.openai.com/v1/chat/completions` |
| JEV | `typesafe-ai/jev` — Vercel AI Gateway evaluation v4 |

The public repository does not re-execute the provider run. `benchmark/harness/make_tables.py` regenerates the published CSV tables from the frozen JSON evidence without network access.

## Provenance

This is a recovered run from [rmax-ai/delegation-queue#79](https://github.com/rmax-ai/delegation-queue/issues/79), with the terminal synthesis and report preserved under `report/`; see [PROVENANCE.md](PROVENANCE.md).

The evidence is preserved as a sanitized bundle. The run is **not** re-executed in this repository.

## License

The code is MIT licensed; see [LICENSE](LICENSE). Documentation and artifacts are published for research traceability under the same permissive terms, with upstream provider and arXiv sources retained in the evidence records.

## Notes on scope

- The L2 comparison uses the operational Gemini D response as the reference. Strategy A is abstract + metadata; B sends the whole PDF natively; C sends rendered page images; D sends extracted text with page labels. The lexical claim-recall rule and its sensitivity values are explained in the report.
- The L3 output checks separate native canonical emission from host normalization, verify cited pages, and test exact quote containment. Blind rubric dimensions are reported with their available rating counts; incomplete judge output is never converted into a score.
- The L4 checks are typed probability questions. Support and actionability have proxy comparisons; duplicate and escalation have no gold labels. A positive post-check is a review signal, not permission to store an insight without evidence inspection.
- The negative result is inspectable: [artifacts/failures/selective-reading.md](artifacts/failures/selective-reading.md) links the C and D calls per missed paper, [artifacts/failures/failure-cases.md](artifacts/failures/failure-cases.md) indexes the retries and malformed outputs, and [raw/README.md](raw/README.md) explains the intentionally absent PDFs and extracted text.
- The selected corpus is a frozen manifest, not a live feed: public arXiv metadata and derived PDF facts make the selection auditable without releasing the private stores that seeded it.
- To audit: start with the report, follow its `raw/` paths into the frozen mirror, inspect the selected response artifact, then verify the tree with `sha256sum -c checksums/SHA256SUMS.txt`.

The evaluation's recorded decision is a bounded NO-GO for the tested selective-replacement claim, with conditional evaluation-only use described in the source report.
