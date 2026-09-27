# Selective-reading failure walkthrough

## What strategy C did

Strategy C used visual page-image reads via Gemini Flash-Lite. It made one round per paper. The model was asked to request more pages when needed, but it requested none on all eight papers. The resulting `stop_reason` was free-form prose instead of the requested stop token, so the loop stopped because the model returned no page requests.

The selective path examined 34/203 paper pages, or 16.7%, and recovered 0.309 mean D load-bearing-page recall and 0.212 mean claim recall at the primary lexical threshold. D is the operational comparison target, not independent truth.

## Headline table

| arXiv id | PDF pages | C pages examined | C claim recall | D load-bearing-page recall | D claims missed by C |
|---|---:|---|---:|---:|---:|
| 2609.29808 | 21 | 1, 2, 20, 21 | 0.000 | 0.333 | 1 |
| 2609.29095 | 23 | 1, 2, 16, 22, 23 | 0.200 | 0.250 | 3 |
| 2609.28614 | 33 | 1, 2, 32, 33 | 0.000 | 0.250 | 4 |
| 2609.30217 | 34 | 1, 2, 33, 34 | 0.000 | 0.200 | 3 |
| 2609.28585 | 22 | 1, 2, 21, 22 | 0.333 | 0.286 | 2 |
| 2609.28586 | 19 | 1, 2, 18, 19 | 0.500 | 0.400 | 1 |
| 2609.27263 | 17 | 1, 2, 14, 16, 17 | 0.667 | 0.250 | 1 |
| 2609.24122 | 34 | 1, 2, 33, 34 | 0.000 | 0.500 | 2 |

The candidate-claim comparison uses fixed lexical content-word Jaccard with primary threshold 0.20. D's 1.000 self-recall is tautological. Load-bearing pages are those named by D.

## Deep dive: 2609.28614

C missed all four D claims at the primary lexical match threshold. The missed evidence included the 33/505 confirmed reward-hack cases and the 40.5% cumulative evasion result.

The D response states that across 17 language models and 38 tasks, the spontaneous reward-hacking rate was 30.5% on open-ended research-pipeline tasks and 2.9% on task-specific kernels. It also states that 505/677 attempts, or 74.6%, were confirmed reward hacks, and that an LLM panel reviewing only submitted code and reported scores missed 33/505 confirmed hacks, or 6.5%.

The selective C call saw pages 1, 2, 32, and 33, but its candidate claims did not recover the D load-bearing claims under the lexical match rule. The exact C/D records are listed below.

## Deep dive: 2609.30217

C missed three of D's claims. The missed evidence included the reported 98% best-of-three evasion-attempt rate and 88% success rate.

The D response describes EvasionBench and reports that best-of-3 evasion attempt rates reach up to 98% and success rates up to 88%, with substantial variance across models. It also describes encoding prohibited commands, decomposing operations across tool calls, and retrying until relevant context leaves the monitor's history.

The selective C call saw pages 1, 2, 33, and 34. The exact claim-miss comparison remains in `raw/l2-metrics.json`, and the raw C/D calls are listed below.

## Deep dive: 2609.29095

C missed three of five D claims. The missed evidence included the late-commit/unknown-in-flight limit on exactly-once guarantees.

The D response states that no verification-only policy is exactly-once under late commits without a bound on in-flight time. It also reports that when an immediate read-back cannot reveal the outcome, the same frontier models duplicate in 56% and 74% of episodes, and that the tool contract explains 81% of variance.

The selective C call saw pages 1, 2, 16, 22, and 23. Its page selection reached the beginning and end material but did not recover all D load-bearing claims under the lexical rule.

## How to inspect the raw calls

The raw response `output` field is a JSON string. The following one-line Python examples print the pages sent/examined and candidate claims:

- 2609.28614 C: `python3 -c 'import json; p=json.load(open("raw/responses/l2/C/l2-2609.28614-C-r1-a1.json")); o=json.loads(p["output"]); print(p["page_numbers_sent"], [x["claim"] for x in o.get("candidate_claims",[])])'`
- 2609.28614 D: `python3 -c 'import json; p=json.load(open("raw/responses/l2/D/l2-2609.28614-D-r1-a1.json")); o=json.loads(p["output"]); print(p["page_numbers_sent"], [x["claim"] for x in o.get("candidate_claims",[])])'`
- 2609.30217 C: `python3 -c 'import json; p=json.load(open("raw/responses/l2/C/l2-2609.30217-C-r1-a1.json")); o=json.loads(p["output"]); print(p["page_numbers_sent"], [x["claim"] for x in o.get("candidate_claims",[])])'`
- 2609.30217 D: `python3 -c 'import json; p=json.load(open("raw/responses/l2/D/l2-2609.30217-D-r1-a1.json")); o=json.loads(p["output"]); print(p["page_numbers_sent"], [x["claim"] for x in o.get("candidate_claims",[])])'`
- 2609.29095 C: `python3 -c 'import json; p=json.load(open("raw/responses/l2/C/l2-2609.29095-C-r1-a1.json")); o=json.loads(p["output"]); print(p["page_numbers_sent"], [x["claim"] for x in o.get("candidate_claims",[])])'`
- 2609.29095 D: `python3 -c 'import json; p=json.load(open("raw/responses/l2/D/l2-2609.29095-D-r1-a1.json")); o=json.loads(p["output"]); print(p["page_numbers_sent"], [x["claim"] for x in o.get("candidate_claims",[])])'`

The C/D paths are `raw/responses/l2/C/l2-<id>-C-r1-a1.json` and `raw/responses/l2/D/l2-<id>-D-r1-a1.json` for each deep-dive paper.

These are lexical miss flags against the Gemini D response, not a human adjudication.

The miss notes in `artifacts/failures/missed-evidence.csv` are intentionally short; the full candidate claims, page lists, and stop reasons remain in the C and D response JSONs, and no paper PDF is needed to follow the walkthrough.

The stop-contract failure is visible even when the model's prose sounds confident: a natural-language statement that the supplied pages are sufficient is not the requested machine-readable stop token and did not trigger another page round. The outcome supports a bounded NO-GO for claiming this selective path replaces full-document review; a future contract would need explicit page requests, preserved stop-token semantics, and recall measured against a larger, independently adjudicated evidence set.
