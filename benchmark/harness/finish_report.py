#!/usr/bin/env python3
"""Replace interim report bodies with measured results, preserving required H2 anchors."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from report_writer import replace_section

ROOT = Path.cwd()
REPORT = ROOT / "dq79-ai-papers-routing-eval.md"

L1_COST = """
Arm latency and cost for the 24-paper routing pass (excluding setup pilots; full attempt detail is in raw/l1-metrics.json):

| Judge | Logical calls | Input / output tokens | Estimated cost | Median / p90 latency |
|---|---:|---:|---:|---:|
| JEV | 24 | 27,091 / 4,102 | $0.001138 | 344 / 503 ms |
| DeepSeek Flash | 24 | 21,731 / 1,441 | $0.002713 | 1,191 / 1,617 ms |
| Gemini Flash-Lite | 24 | 21,420 / 2,117 | $0.011719 | 23,815 / 25,153 ms |
| GPT-6 Luna | 24 | 23,764 / 1,581 | $0.003073 | 7,839 / 8,275 ms |
"""

L3 = """
The eight-paper generation comparison uses strategy-D full extracted text for full-reference arms. Routed selective arms receive only the strategy-C examined-page text and its visual-reader candidate-claim packet. All eight papers passed the host JEV relevance threshold of 0.50; this is a purposive subset, not a missed-paper stress test. GPT-6 Luna also has one reasoning-effort medium sensitivity output on four fixed papers. Primary settings were DeepSeek reasoning_effort none, Gemini thinkingLevel low, and GPT-6 Luna reasoning_effort none.

Before judging, deterministic checks examined the canonical artifact shape, page range, nonempty citations, and exact case/whitespace-normalized quote containment against the supplied page text. Exact quote containment checks reference strings, not semantic entailment. Model-emitted canonical shape is reported separately from normalized host shape. The blind judge was cross-vendor where possible, with shuffled A/B labels. It produced at least one numeric rubric score in 29/36 calls and 55 candidate score records; seven calls omitted usable dimension scores and one of those returned a null output. Six score-bearing calls had at least one incomplete or combined rubric dimension. Unusable answers remain format failures; preference text was not converted into scores. See raw/l3-metrics.json, raw/l3-format-findings.json, raw/l3-judge-map.json, and raw/responses/l3/judges/.

Generator output and input-path measurements:

| Input / model | Output objects | Native canonical | Normalized schema pass | Exact quote containment on citations | Input / output tokens across attempts | Cost | Latency sum |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full reference / DeepSeek | 8/8 | 0/8 | 2/8 | 0.744 | 300,659 / 20,224 | $0.049839 | 91.5 s |
| Full reference / Gemini | 7/8 | 0/8 | 1/7 | 0.262 | 251,138 / 11,468 | $0.104011 | 230.7 s |
| Full reference / GPT-6 Luna | 8/8 | 8/8 | 8/8 | 0.776 | 248,085 / 16,748 | $0.033183 | 179.4 s |
| Selective / DeepSeek | 8/8 | 0/8 | 1/8 | 0.700 | 69,598 / 13,854 | $0.014725 | 60.6 s |
| Selective / Gemini | 8/8 | 0/8 | 1/8 | 0.325 | 78,338 / 10,740 | $0.050351 | 251.1 s |
| Selective / GPT-6 Luna | 8/8 | 8/8 | 8/8 | 0.851 | 62,865 / 11,052 | $0.011813 | 137.4 s |

Costs and tokens above include every saved attempt assigned to each generation arm, including billed invalid/truncated responses and retries. Quote-containment rates average all key-claim, evidence, and insight citation references. They do not establish that a claim is entailed by its cited page. GPT-6 Luna alone emitted the requested canonical shape on all outputs; DeepSeek and Gemini emitted JSON variants that needed deterministic normalization, and most normalized outputs still failed one or more required fields. One full-reference Gemini response had no parseable output. Per-paper checks and raw attempts are retained.

Blind qualitative scores, 0–4 with available numeric candidate ratings shown as n in parentheses. Each dimension remains separate. DeepSeek was scored by both judge vendors where possible; Gemini was scored by OpenAI and GPT-6 Luna by Gemini, so n differs and cross-vendor coverage is uneven. Means are descriptive, not a statistically powered ranking.

| Input / generator | Faithfulness | Evidence support | Insight depth | Novelty identification | Systems relevance | Actionability | Compression / density | Uncertainty calibration | Durable-memory precision proxy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full reference / DeepSeek | 3.36 (11) | 3.00 (11) | 3.09 (11) | 2.91 (11) | 3.90 (10) | 3.70 (10) | 3.27 (11) | 2.00 (11) | 3.18 (11) |
| Full reference / Gemini | 2.86 (7) | 2.71 (7) | 2.14 (7) | 1.71 (7) | 2.86 (7) | 2.71 (7) | 3.00 (7) | 2.00 (7) | 2.43 (7) |
| Full reference / GPT-6 Luna | 4.00 (4) | 4.00 (4) | 3.75 (4) | 2.75 (4) | 4.00 (3) | 4.00 (3) | 3.50 (4) | 2.00 (4) | 3.75 (4) |
| Selective / DeepSeek | 3.54 (13) | 2.77 (13) | 2.85 (13) | 2.85 (13) | 3.70 (10) | 3.40 (10) | 3.23 (13) | 2.00 (13) | 2.92 (13) |
| Selective / Gemini | 3.12 (8) | 2.88 (8) | 2.00 (8) | 2.00 (8) | 3.12 (8) | 2.62 (8) | 3.12 (8) | 2.00 (8) | 2.50 (8) |
| Selective / GPT-6 Luna | 4.00 (5) | 4.00 (5) | 3.20 (5) | 3.00 (5) | 4.00 (2) | 4.00 (2) | 3.20 (5) | 2.00 (5) | 3.20 (5) |

Uncertainty calibration was scored 2 (unobservable) wherever the judge had no outcome series to compare with model confidence. It is not evidence that confidence is calibrated. Durable-memory precision is an expert-judged six-month-storage proxy, not a longitudinal test.

Sensitivity arm: four full-reference GPT-6 Luna outputs at reasoning_effort medium all passed schema/page checks and emitted three insights each, as did the paired none outputs. Mean exact quote containment was 0.667 at medium versus 0.725 at none (mixed per-paper direction). In the three paired judge calls with numeric scores for both outputs, all separated rubric dimensions were equal; the fourth judge response scored only the none candidate, so its medium score is missing. This small arm shows no measured quality gain. The medium calls used 116,147 input and 9,603 output tokens, cost $0.016416, and took 84.7 seconds of summed request latency. Details are in raw/l3-metrics.json.

Representative outputs:

- Strongest observed artifact, GPT-6 Luna full-reference on 2609.28614: “Assurance should verify the scientific claim independently, not merely inspect the agent’s final artifact or reproduce its reported score.” The canonical schema passed, exact citations all matched in this output, and available blind scores were 4/4 for faithfulness and evidence support. Raw output: raw/responses/l3/full_reference/openai/l3-2609.28614-full_reference-openai-a1.json.
- Weak selective example, Gemini on 2609.28614: “standard software monitoring is too slow” to handle thousands of automated actions. This overstates what its supplied abstract citation establishes; the cell failed normalized schema checks, and only 0.25 of all cited references in the output matched their cited pages. Raw output: raw/responses/l3/selective/gemini/l3-2609.28614-selective-gemini-a1.json.
"""

L4 = """
JEV evaluated the first insight from every eligible generated artifact: 47 candidates (23 full-reference, 24 selective; one full-reference Gemini generation had no output). All 47 returned valid typed boolean probabilities. These are bounded checks; JEV was not asked for open-ended novelty synthesis.

| Question | Host threshold | Mean probability | Positive decisions | Proxy comparison |
|---|---:|---:|---:|---|
| Supported by supplied evidence | 0.75 | 0.882 | 43/47 | Against candidate-specific exact quote containment: TP 24, FP 19, TN 2, FN 2; Brier 0.347, agreement 0.553. This is a string-match proxy, not semantic entailment. |
| Agenda relevant | 0.60 | 0.960 | 47/47 | Against high-value stratum label: TP 41, FP 6, TN 0, FN 0; Brier 0.114, agreement 0.872. Six proxy-negative candidate outputs all passed. |
| Duplicates supplied existing insight | 0.75 | 0.172 | 3/47 | No gold duplicate labels; no Brier or agreement estimate. |
| Has actionable implication | 0.60 | 0.897 | 47/47 | Against blind judge score ≥3: TP 31, FP 5 among 36 labeled; Brier 0.120 and agreement 0.861. Eleven candidates lacked a usable blind actionability score. |
| Escalate for deeper review | 0.65 | 0.476 | 5/47 | No gold escalation labels; no Brier or agreement estimate. |

On the eight full-reference GPT-6 Luna candidates used by matrix row 7, seven had exact quote containment; JEV marked six supported at P≥0.75 (TP 6, FP 0, TN 1, FN 1; Brier 0.047). This is promising only against a narrow lexical proxy on n=8. Across all candidates, raising support threshold to 0.95 improved exact-quote precision to 0.80 but reduced recall to 0.154; there is no balanced automatic acceptance threshold in this sample. Aggregate outputs, candidate-specific source checks, and probability records are in raw/l4-metrics.json and raw/l4-results.json. The 47 calls cost $0.004499, used 107,111 input and 5,358 output tokens, and totaled 17.8 seconds of request latency (median 337 ms).
"""

MATRIX = """
Matrix costs are direct inference costs for the measured eight-paper set. Full-document rows include one shared strategy-D extraction pass; selective rows include the strategy-C reader plus the JEV triage calls for those eight papers. LLM judging and setup pilots are excluded. Quality evidence is from L2 and L3; it does not include a production-scale loss guarantee.

| Pipeline cell | Cost for 8 papers | Evidence and measured fit |
|---|---:|---|
| 1. Full-document D → DeepSeek Flash | $0.128960 | D extraction $0.079122 plus DeepSeek full-reference generation $0.049839. Citation quote containment 0.744; normalized schema passed 2/8. Blind ratings: faithfulness 3.36/4 and evidence support 3.00/4, with 11 available ratings per dimension. Lower generator cost than Gemini, but it is not the cheapest full-reference arm and schema reliability is weak. |
| 2. Full-document D → Gemini Flash-Lite | $0.183133 | D $0.079122 plus generation $0.104011. Quote containment 0.262; normalized schema passed 1/7 parsed outputs. Blind means were 2.86 faithfulness, 2.71 evidence support, and 2.14 depth, n=7. Slowest and highest-cost full-reference generator. |
| 3. Full-document D → GPT-6 Luna | $0.112304 | D $0.079122 plus generation $0.033183. Canonical schema passed 8/8; quote containment 0.776; available blind means 4.00 faithfulness/evidence, n=4, depth 3.75/4, n=4. Cheapest of the three full-reference pipelines and strongest measured structured-output/quality result, with small judge coverage. |
| 4. JEV triage → Gemini selective C → DeepSeek | $0.034955 | Subset triage $0.000401, C $0.019829, selective DeepSeek $0.014725. All eight routed at P≥0.50. C page recall 0.309 and claim recall 0.212; DeepSeek normalized schema passed 1/8; quote containment 0.700. Low cost does not compensate for missed evidence. |
| 5. JEV triage → Gemini selective C → Gemini | $0.070581 | Same triage/C plus selective Gemini $0.050351. C recall unchanged; generator quote containment 0.325 and schema pass 1/8. No measured advantage over the other selective generators. |
| 6. JEV triage → Gemini selective C → GPT-6 Luna | $0.032042 | Subset triage $0.000401, C $0.019829, selective GPT $0.011813. GPT schema passed 8/8 and quote containment was 0.851; available judge depth was 3.20 versus 3.75 full-reference. Despite its low apparent inference cost, C saw only 30.9% of D load-bearing pages and missed important results. |
| 7. Best measured generator GPT-6 Luna → JEV post-check | $0.113075 | Full-reference pipeline 3 plus eight GPT full-reference post-checks ($0.000771). On n=8, JEV support decisions matched the exact-quote proxy in 7/8; across all 47 candidates, support precision was only 24/43 at threshold 0.75. Typed checks are cheap, but not sufficient to accept evidence semantically. |

For decisions against the strongest measured reference, we set a post-hoc tolerance of at most 0.5/4 loss in faithfulness and evidence support, at least 0.90 evidence-page and D-claim recall, and at least 0.95 normalized schema/page-reference validity. This tolerance was not preregistered. No selective pipeline met it: C averaged 0.309 evidence-page recall and 0.212 claim recall. D + GPT-6 Luna is the only measured cell that met its own reference quality and structural gates; there is no cheaper measured pipeline shown to remain within tolerance.
"""

FAILURES = """
All attempts with errors or malformed model output are preserved and treated as data, not silently discarded from cost totals.

- Host interruption/outage window: three 2609.29095 strategy-B attempts returned null HTTP status and zero usage. The clean resume call succeeded; prior valid A output was reused. See raw/responses/l2/B/l2-2609.29095-B-r1-a1.json, a2.json, a3.json and the resume artifact linked by raw/l2-results.json.
- Gemini model selection: the first catalogue selector chose the TTS sibling gemini-3.8-flash-lite-tts; three smoke attempts have unrecoverable status/latency and zero recorded usage. The selector was corrected to stable text model gemini-3.5-flash-lite, after which text and PDF probes passed. Raw selection/provenance is in raw/gemini-model-resolution.json and raw/capability-probes.json.
- L1: one JEV request returned 503 then succeeded on retry. The two-paper shared-prompt pilot was excluded because exact keys were omitted; the corrected prompt pilot and all 24 measured schemas are recorded under raw/l1-prompt-pilot*.json and raw/l1-results.json.
- L2 selective stop contract: all eight Gemini responses used free prose in stop_reason and requested no further pages. The harness made one selective round per paper; the resulting miss cases on 2609.28614, 2609.30217, and 2609.29095 are described in Layer 2 and raw/l2-metrics.json. This is a strategy failure, not a successful bounded iterative loop.
- L3 initial output format: one DeepSeek format pilot used an incompatible insight shape and was excluded; later DeepSeek JSON mode returned HTTP 400 until the prompt included lowercase json. The 2609.29808 DeepSeek and GPT outputs were truncated at earlier output limits and retried with shorter prompts/higher caps. Those responses remain in raw/responses/l3/ and links are indexed by raw/l3-results.json.
- L3 schema and judge failures: DeepSeek/Gemini emitted noncanonical shapes and usually failed normalized required-field checks. One full-reference Gemini generation had no parseable output. Of 36 judge calls, seven returned no usable dimension scores (including one null Gemini response); six other responses had incomplete/combined scores. Preference text was retained but not scored. See raw/l3-format-findings.json, raw/l3-metrics.json, and raw/responses/l3/judges/.
- L2 selective important misses: C missed all four D claims on 2609.28614, including 33/505 confirmed reward-hack cases and the 40.5% cumulative evasion result; three of D’s claims on 2609.30217, including 98% best-of-three evasion-attempt and 88% success results; and three of five on 2609.29095, including the late-commit/unknown-in-flight limitation on exactly-once guarantees. These are misses against the operational Gemini D reference and lexical match rule, not independent human adjudications.
- L4: all 47 calls returned typed answers; no transport failures. However, 19 of 43 candidates with JEV support P≥0.75 did not pass the candidate-specific exact quote-containment proxy, underscoring the semantic-verification gap.
"""

COST = """
Every saved provider HTTP attempt was repriced from its recorded usage fields and rates_used. These are estimated charges, not provider invoice data. Stage aggregates include pilots, retries, invalid but billed responses, and zero-usage failures. Network-latency sums exclude backoff and host waiting.

| Stage | Unique call IDs | Attempts | HTTP 200 / errors | Input / output tokens | Estimated cost | Request-latency sum |
|---|---:|---:|---:|---:|---:|---:|
| L1 | 96 | 110 | 109 / 1 | 106,085 / 10,579 | $0.021297 | 901.6 s |
| L2 | 34 | 36 | 33 / 3 | 378,737 / 19,436 | $0.162211 | 1,021.5 s |
| L3 | 88 | 97 | 95 / 2 | 1,372,808 / 102,755 | $0.350305 | 1,684.7 s |
| L4 | 47 | 47 | 47 / 0 | 107,111 / 5,358 | $0.004499 | 17.8 s |
| Capability probes | 10 | 10 | 6 / 4 | 922 / 55 | $0.000238 | 107.6 s |
| Total | 275 | 300 | 290 / 10 | 1,965,663 / 138,183 | $0.538550 | 3,733.3 s |

Cached input tokens were 88,727 and reasoning tokens 5,257. DeepSeek calls all fell in the recorded off-peak tier: $0.067903 off-peak, $0 peak. Total estimated spend is 6.7% of the $8 cap. The L3 blind judge used $0.069967 in total, below its $1 sub-budget. Stage, arm/provider, source-rate strings, failed-attempt pointers, medians, and p90 latency are in raw/cost-report.json; every response attempt is under raw/responses/.

The layer-specific A/B/C/D, generator, sensitivity, and post-check unit comparisons appear above. The raw all-attempt L2 spend ($0.162211) includes the A prompt pilot and three outage attempts; the eight measured A/B/C/D arms themselves cost $0.160553. The raw L3 total includes 52 generation cells, 36 blind-judge calls, retries, and billed invalid responses. The all-run cost includes $0.000238 of capability probes, including four unsuccessful setup attempts.
"""

RECOMMENDATIONS = """
Thresholds below are host policy candidates derived after observing this purposive sample; they are not model-selected and are not validated population guarantees.

- Paper triage: JEV at P(relevant) ≥0.70 is the cheapest measured candidate escalation threshold. It yielded proxy precision 0.857 and recall 1.000 (12/12 high-value labels) at about $0.000047 per call. Gemini at 0.70 had the same measured precision/recall and better Brier (0.075 vs JEV 0.156), but cost about ten times more and had much higher median latency. Use 0.50–0.69 as a review band; do not automatically discard lower scores in production on the strength of n=24. The abstract audit had one positive and was disagreement-enriched.
- Selective reading: no tested stop/request threshold is acceptable. C requested no additional page on all eight papers and saw only 0.309 of D load-bearing pages. Until a new evaluation shows ≥0.90 page and claim recall and a valid page-request/stop contract, use selective output only as an aid to navigation and fall back to a full-document reference whenever evidence completeness matters.
- Deep synthesis: GPT-6 Luna at reasoning_effort none is the strongest measured structured generator and the cheapest full-reference generator arm. Keep deterministic schema and citation gates; a failed gate should trigger rework or review, not durable storage. DeepSeek was cheaper only on selective short input and had 1/8 normalized schema passes there; full-reference arm cost exceeded GPT-6 Luna.
- Post-generation verification: JEV at P(supported) ≥0.75 is not an automatic acceptance threshold: 19/43 predicted-supported candidates failed exact quote containment. At 0.95, proxy precision rose to 0.80 but recall fell to 0.154. Require resolvable evidence and independent review for storage decisions; JEV can prioritize checks. Duplicate and escalation thresholds have no gold labels in this run.

Quality-loss tolerance and MVP decision: the post-hoc limit is ≤0.5/4 loss on faithfulness/evidence support, ≥0.90 evidence-page and D-claim recall, and ≥0.95 normalized schema/page-reference validity. Only the full-reference D + GPT-6 Luna comparison cell met the structural/quality gates; no cheaper selective pipeline met the evidence-recall gate. **MVP go/no-go relative to delegation-queue#78: NO-GO for claiming selective PDF reading can replace full-document evidence review; conditional evaluation-only use is not a production-readiness result.**
"""

IMPLICATIONS = """
Factual findings for the feasibility spec in delegation-queue#78:

- The eight-paper selective strategy failed to request pages and recovered 0.309 mean D load-bearing-page recall; an assumed selective-reading cost/quality advantage is not supported by this run.
- Whole-PDF inline Gemini recovered 0.631 lexical claim recall at $0.047686, while selective C recovered 0.212 at $0.019829 and reference D cost $0.079122. These are model-derived comparisons, not human gold.
- JEV was fast and inexpensive for typed triage, but its 0.70 proxy threshold was tested on 24 purposively balanced papers. Its post-generation support answers were overconfident against exact quote matching across mixed candidates.
- GPT-6 Luna was the only generator to emit the requested canonical schema on all eight outputs per path and passed normalized structural checks 8/8. DeepSeek and Gemini variants needed normalization and most normalized cells still failed checks.
- The measured best full-reference generator was GPT-6 Luna with reasoning off. The four-paper medium-effort sensitivity arm showed no qualitative score improvement in three scoreable pairs and mixed citation-string deltas.
- Blind rubric data have only 4–13 candidate ratings per dimension and seven of 36 judge calls with no usable scores; this evidence should narrow confidence claims and motivate a judge-format reliability check.
- L4 support verification achieved only 0.553 threshold agreement with a narrow exact-quote proxy over all candidates. Semantic evidence verification remains unestablished.

These are empirical deltas and uncertainty limits for #78 to incorporate; they do not specify a parallel architecture.
"""

NEXT = """
1. Specify and test an exact selective-reader page-request/stop contract, including an explicit continuation condition; rerun the missed-evidence subset with a bounded page budget and record load-bearing-page recall.
2. Adjudicate a larger stratified routing set with blinded abstract readers, including real high-value false negatives and natural prevalence; estimate precision, recall, calibration, and escalation trade-offs.
3. Add strict output-shape conformance checks for DeepSeek and Gemini to the benchmark harness; measure provider-native constrained outputs separately from deterministic normalization.
4. Build a human-adjudicated evidence-support set linking each claim to page-level entailment, so quote containment can be separated from semantic support and L4 thresholds can be calibrated.
5. Re-run cross-vendor judge scoring with a hard response schema and balanced pair coverage; require every rubric dimension for both candidates and retain judge refusal/format failures as explicit outcomes.
6. Expand sensitivity testing only after the primary generator and page-source comparison is preregistered; current n=4 medium-effort evidence is inconclusive.
7. Refresh provider model IDs and rate cards on the next evaluation date; Gemini request IDs echoed only the stable catalogue name while its catalogue entry supplied the dated version.
"""


def main() -> None:
    text = REPORT.read_text(encoding="utf-8")
    marker = "Observed output-shape/decision failures:"
    if "Arm latency and cost for the 24-paper routing pass" not in text:
        text = text.replace(marker, L1_COST + chr(10) + marker, 1)
        REPORT.write_text(text, encoding="utf-8")
    replace_section("Layer 3: insight generation", L3)
    replace_section("Layer 4: JEV post-generation", L4)
    replace_section("Generator x evaluator matrix", MATRIX)
    replace_section("Failure cases", FAILURES)
    replace_section("Cost and latency", COST)
    replace_section("Recommended role-based routing and thresholds", RECOMMENDATIONS)
    replace_section("Implications for #78", IMPLICATIONS)
    replace_section("Next implementation issues", NEXT)
    print("Updated report sections; exact H2 anchors retained.")


if __name__ == "__main__":
    main()
