# Failure cases

All attempts with errors or malformed model output were preserved and treated as data, not silently discarded from cost totals.

## Host outage artifacts

Three 2609.29095 strategy-B attempts returned null HTTP status and zero usage during the host interruption. The clean resume call succeeded; prior valid A output was reused. The outage records are `raw/responses/l2/B/l2-2609.29095-B-r1-a1.json`, `raw/responses/l2/B/l2-2609.29095-B-r1-a2.json`, and `raw/responses/l2/B/l2-2609.29095-B-r1-a3.json`. The clean recovery is `raw/responses/l2/B/l2-2609.29095-B-r1-resume1-a1.json`, linked by `raw/l2-results.json`.

## Gemini model-selection misresolve

The first catalogue selector chose the TTS sibling `gemini-3.8-flash-lite-tts`. Three smoke attempts have unrecoverable status/latency and zero recorded usage. The selector was corrected to stable text model `gemini-3.5-flash-lite`, after which text and PDF probes passed. See `raw/gemini-model-resolution.json`, `raw/capability-probes.json`, and `raw/responses/probes/`.

## L1 pilot exclusions and retry

The two-paper shared-prompt pilot was excluded because exact keys were omitted. The corrected prompt pilot and all 24 measured schemas are recorded in `raw/l1-prompt-pilot.json`, `raw/l1-prompt-pilot-corrected.json`, and `raw/l1-results.json`.

One JEV request for paper 2609.29808 returned 503 and succeeded on retry. The paired artifacts are `raw/responses/l1/jev/l1-2609.29808-jev-a1.json` and `raw/responses/l1/jev/l1-2609.29808-jev-a2.json`.

## L2 selective stop-contract failure

All eight Gemini selective responses used free prose in `stop_reason` and requested no further pages. The harness made one selective round per paper. The miss cases on 2609.28614, 2609.30217, and 2609.29095 are described in `artifacts/failures/selective-reading.md` and `raw/l2-metrics.json`.

This is a strategy failure, not a successful bounded iterative loop. The direct calls remain under `raw/responses/l2/C/` and `raw/responses/l2/D/`.

## L3 format, schema, and judge failures

One DeepSeek format pilot used an incompatible insight shape and was excluded. Later DeepSeek JSON mode returned HTTP 400 until the prompt included lowercase json. The 2609.29808 DeepSeek and GPT outputs were truncated at earlier output limits and retried with shorter prompts/higher caps. Those responses remain under `raw/responses/l3/`, with links indexed by `raw/l3-results.json`.

DeepSeek and Gemini emitted noncanonical shapes and usually failed normalized required-field checks. One full-reference Gemini generation had no parseable output. Of 36 judge calls, seven returned no usable dimension scores, including one null Gemini response; six other responses had incomplete or combined scores. Preference text was retained but not scored. See `raw/l3-format-findings.json`, `raw/l3-metrics.json`, `raw/l3-judge-map.json`, and `raw/responses/l3/judges/`.

C missed all four D claims on 2609.28614, including 33/505 confirmed reward-hack cases and the 40.5% cumulative evasion result; three of D's claims on 2609.30217, including 98% best-of-three evasion-attempt and 88% success results; and three of five on 2609.29095, including the late-commit/unknown-in-flight limitation on exactly-once guarantees. These are misses against the operational Gemini D reference and lexical match rule, not independent human adjudications. See `raw/l2-metrics.json` and `artifacts/failures/missed-evidence.csv`.

## L4 semantic-verification gap

All 47 calls returned typed answers; there were no transport failures. However, 19 of 43 candidates with JEV support P≥0.75 did not pass the candidate-specific exact quote-containment proxy. This underscores the semantic-verification gap. See `raw/l4-metrics.json`, `raw/l4-results.json`, and the L4 response records under `raw/responses/l4/jev/`.

The failure artifacts link into the raw records rather than replacing them. Keep the classes separate: the host stall, model-selection correction, and L1 retry are harness or transport events, while the selective stop issue and the L3 schema issues affect measured quality or structure. The raw L3 total includes 52 generation cells, 36 blind-judge calls, retries, and billed invalid responses; the all-run cost includes $0.000238 of capability probes, and network-latency sums exclude backoff and host waiting. The report and raw JSONs remain authoritative for exact numeric fields; this index is a navigation aid.
