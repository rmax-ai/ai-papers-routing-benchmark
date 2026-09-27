# Benchmark methodology

## Experiment question

The experiment asks whether cheaper routing and selective PDF reading can replace full-document evidence review for paper-insight generation.

The hypothesis under test was that JEV or a small-model triage pass could identify the useful papers, and that a model-directed selective reader could inspect a small page budget while preserving enough evidence for reliable insight generation. The benchmark treats that as an empirical question rather than an architectural assumption.

The evaluation is bounded. It compares measured routing, evidence, generation, and typed post-check behavior on a purposive corpus. It does not claim a population estimate, human-gold semantic support, or production readiness.

## Corpus construction

The corpus has 24 papers in three purposive strata: 12 `high_value_proxy`, 8 `medium_adjacent`, and 4 `low_relevance_control`.

The high and medium selections came from a private local paper store of digested arXiv papers. The control selection came from a private local full-abstract store. Those upstream stores are not published.

Selection rules match the source evaluation:

1. Deduplicate the paper store by arXiv id, keeping the newest digest date.
2. Select high-value proxies from direct agenda sections and cues covering agents, MCP, infrastructure, and governance, prioritizing empirical, reliability, evaluation, tool, and runtime studies.
3. Select adjacent medium papers covering LLM, retrieval-augmented generation, prompt, or related application and evaluation work without direct agent-routing or runtime-reliability focus.
4. Select negative controls from distinct non-agent AI, optimization, sensing, control, and labor-economics domains.
5. Mark the KG entry when a matching arXiv id exists in the local deep-processing index; this is a secondary tag, not the relevance label.

The exact selection is frozen in `raw/sampling.json`. Public arXiv abstract metadata is frozen in `raw/arxiv-abstracts.json`, and the readable selection table is `benchmark/corpus/sample-24.csv`.

The PDF candidate rule is page count ≥20 or ≥6 embedded images or ≥4 explicit figure references or ≥3 explicit table references. Reference-count matches can overcount. Ten PDF candidates were downloaded. The L2/L3 subset contains eight papers selected from that bounded PDF set; six of those eight are 20+ page papers.

## Layer 1: routing judgments

L1 uses one shared question pack and four judges: JEV, DeepSeek Flash, Gemini Flash-Lite, and GPT-6 Luna.

The routing label is a purposive proxy: the 12 high-value papers are positive, and the 12 medium/low papers are negative. It is not a gold relevance set and does not represent natural prevalence.

The host applies probability thresholds at 0.30, 0.40, 0.50, 0.60, and 0.70. Models do not select the thresholds. The default routing comparison uses the supplied relevance probability at 0.50; the proposed escalation line uses JEV at 0.70.

Every measured model output is checked for the shared required fields and valid ranges. The audit subset contains the seven disagreement papers plus one high-value proxy and one unanimous low control, for nine abstracts. It is deliberately disagreement-enriched, so its figures are not population estimates.

Pairwise agreement is measured with Boolean probabilities thresholded by the host at 0.50, exact categorical agreement for topic, and an absolute difference ≤0.5 for the 0–4 implementation score. Counts are reported only where both outputs are valid.

## Layer 2: PDF strategies

L2 compares four evidence inputs, all evaluated with Gemini Flash-Lite:

- **A, abstract-only:** abstract and metadata without PDF pages.
- **B, whole-PDF native:** the complete PDF supplied as a native document.
- **C, selective page-image reads:** PyMuPDF-rendered page images, with model-directed follow-up pages for one round.
- **D, full extracted-text reference:** all extracted pages with page labels, used as the operational comparison target.

The selective reader is asked to request additional pages or stop. In the recorded run it requested no additional page on any of the eight papers, and its stop reason was free-form prose rather than the requested stop token. The observed behavior is therefore a tested stopping behavior, not a successful bounded iterative contract.

D is an operational comparison target, not independent truth. Candidate-claim recall is computed with fixed lexical content-word Jaccard against D claims, with a primary threshold of 0.20 and sensitivity thresholds of 0.15 and 0.25. This is not semantic evaluation.

Load-bearing pages are the pages named by D. Evidence-page recall measures whether another strategy saw those pages. D's 1.000 self-recall is tautological. The selective miss table and direct-inspection walkthrough are in `artifacts/failures/selective-reading.md`.

## Layer 3: insight generation

L3 crosses two evidence paths, full-reference and selective, with three generators: DeepSeek Flash, Gemini Flash-Lite, and GPT-6 Luna. Full-reference arms receive D's extracted-text reference. Selective arms receive C's examined-page text and visual-reader candidate-claim packet.

All eight L2/L3 papers pass the host JEV relevance threshold used for this subset. This is not a missed-paper stress test.

The canonical output schema contains structured insights, evidence references, quotes, confidence, and the required insight fields. Deterministic checks examine canonical artifact shape, normalized schema shape, page-range validity, nonempty citations, and exact case/whitespace-normalized quote containment against supplied page text. Quote containment checks strings, not semantic entailment.

Native model-emitted canonical shape and host-normalized schema validity are reported separately. DeepSeek and Gemini variants can be normalized, but normalization does not convert a failed required-field check into a quality pass.

The blind judge is cross-vendor where possible and receives shuffled A/B labels. The rubric keeps faithfulness, evidence support, insight depth, novelty identification, systems relevance, actionability, compression/information density, uncertainty calibration, and durable-memory precision proxy as separate dimensions. Missing or combined dimensions remain format failures; preference text is not converted into scores.

A small GPT-6 Luna sensitivity arm compares reasoning effort `none` and `medium` on four fixed papers. It is descriptive and does not establish a reasoning-effort effect.

## Layer 4: JEV post-generation checks

L4 asks five typed JEV questions of the first insight from every eligible generated artifact:

1. Supported by supplied evidence.
2. Agenda relevant.
3. Duplicates supplied existing insight.
4. Has actionable implication.
5. Escalate for deeper review.

The host thresholds are 0.75, 0.60, 0.75, 0.60, and 0.65 in that order. Support is compared with candidate-specific exact quote containment, agenda relevance with the high-value proxy label, and actionability with the blind judge actionability score. Duplicate and escalation have no gold labels.

These are bounded typed checks. They prioritize review and do not establish semantic evidence support. The exact-quote comparison is a string-match proxy, and a positive JEV probability is not an automatic acceptance decision.

## Pipeline matrix

The matrix combines a shared D extraction pass with each full-reference generator, or a JEV subset triage pass, C selective reading, and each selective generator. The seven cells use direct inference costs for the eight-paper comparison. LLM judging and setup pilots are excluded from those cell costs.

The matrix is evaluated against a post-hoc tolerance of at most 0.5/4 loss in faithfulness and evidence support, at least 0.90 evidence-page and D-claim recall, and at least 0.95 normalized schema/page-reference validity. These thresholds were not preregistered.

## Limitations

The sample is purposive rather than random. The 12/8/4 balance is artificial, and the low controls are older than the recent digest strata. Proxy labels do not stand in for blinded human relevance labels.

Judge coverage is uneven and several cells have only 4-13 ratings per dimension. Seven of 36 blind judge calls had no usable dimension scores, so the qualitative means are descriptive rather than statistically powered rankings.

Quote containment is a deterministic string match. It does not test whether a cited quote semantically entails a claim. L4 therefore measures agreement with a narrow lexical proxy, not independent evidence adjudication.

Thresholds and tolerances were selected after observing the run rather than preregistered. The reported policy candidates are not validated population guarantees.

Each measured cell was run once. Provider outages, retries, malformed outputs, and setup failures are retained, but a single run cannot characterize provider variance.

Costs are estimates from recorded usage and applied rate tables, not provider invoices. DeepSeek peak/off-peak handling and cached-token treatment are recorded in the raw per-attempt artifacts.

The selective reader's free-form stop behavior is a contract failure. The result rejects the tested replacement behavior at this page budget; it does not prove that every possible selective reader design will fail.

## Reproducibility checklist

The following commands describe the original harness order. They require the private stores only for corpus acquisition and selection; later analysis consumes the frozen raw JSONs.

- Capability setup: `python3 benchmark/harness/run_probes.py` → `raw/capability-probes.json` and probe responses.
- Prompt pilots: `python3 benchmark/harness/prompt_pilot.py` → the layer pilot JSON artifacts.
- L1 calls: `python3 benchmark/harness/run_l1.py` → `raw/l1-results.json`; metrics: `python3 benchmark/harness/l1_metrics.py` → `raw/l1-metrics.json`.
- Corpus and PDF selection: `python3 benchmark/harness/fetch_corpus.py` and `python3 benchmark/harness/select_sample.py` → the frozen selection and PDF facts.
- L2 calls: `python3 benchmark/harness/run_l2.py` → `raw/l2-results.json`; metrics: `python3 benchmark/harness/l2_metrics.py` → `raw/l2-metrics.json`.
- L3 calls: `python3 benchmark/harness/run_l3.py` → `raw/l3-results.json`; format audit and metrics use `l3_format_audit.py` and `l3_metrics.py`.
- L4 calls and metrics: `python3 benchmark/harness/run_l4.py` and `python3 benchmark/harness/l4_metrics.py` → `raw/l4-results.json` and `raw/l4-metrics.json`.
- Accounting and report stages: `cost_report.py`, `report_writer.py`, `finish_report.py`, and `finalize_artifacts.py` write the corresponding recovered artifacts.
- Offline publication tables: `python3 benchmark/harness/make_tables.py` regenerates `report/tables/*.csv` from published JSONs without provider calls.

This repository publishes the frozen output. It does not re-run the provider pipeline.

## Measurement conventions

A logical call is the benchmark's unit of work; an attempt is a persisted provider request, including retries. The cost report counts every attempt, while layer metric tables describe the successful logical comparisons and retain failure links.

Page counts refer to the downloaded candidate PDFs. Rendered image bytes and extracted-text bytes are tracked separately because they represent different input mechanisms. Token fields use the provider usage mappings recorded in `benchmark/harness/provider.py` and the raw attempt records.

For L1, a host threshold turns a probability into a decision. For L2, page recall is computed against the pages selected by D, and claim recall is computed against D's candidate claims. For L3, structural checks are deterministic and blind scores are available-score summaries. For L4, each typed answer remains tied to its candidate artifact and response path.

The benchmark keeps setup deviations visible. The Gemini selector correction, excluded pilot records, L2 outage attempts, selective stop-contract behavior, L3 malformed outputs, and L4 proxy limits are all retained in raw files and described in the failure artifacts.

## Interpretation boundary

The result supports the narrow conclusion that the tested selective behavior did not replace full-document evidence review at the tested page budget. It does not support an extrapolation to untested prompts, models, page budgets, or a different selective continuation contract.

The result also supports a practical separation of roles: use typed triage to prioritize work, use deterministic checks to reject malformed artifacts, and treat evidence completeness and semantic support as separate review obligations. This separation is a design interpretation of the measured layers, not a new benchmark claim.

The public table generator is not part of the provider experiment. It is an offline reporting utility that preserves source JSON precision where practical and uses the report only for the matrix strings that cannot be reconstructed from the public arm aggregates.

A rerun of the provider pipeline would be a new experiment. It would need fresh provider identifiers, rate cards, and a new provenance record rather than overwriting these artifacts.

## What the benchmark does not measure

It does not measure human reading time, provider invoice reconciliation, population-level routing prevalence, or semantic entailment by independent adjudicators. Those questions require a different study design.

It does not treat the operational D response as ground truth. D supplies the comparison pages and claims used by the fixed lexical metrics. This makes the measurement auditable while retaining the stated reference limitation.

It does not infer that a low-cost cell is acceptable from cost alone. The matrix combines cost with page recall, claim recall, schema validity, citation containment, and available blind scores.

It does not treat a malformed or incomplete model response as a hidden success. Native shape, normalized shape, judge-format failures, and provider retries are separate records.

## Publication boundary

The public corpus file is a derived view of the frozen manifest. The response records are copies of the original per-call artifacts. The report files are terminal artifacts. The checksums cover all of these public outputs together.
