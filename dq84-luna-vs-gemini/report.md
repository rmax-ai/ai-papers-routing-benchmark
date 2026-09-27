# DQ84 Luna vs Gemini evidence benchmark

Run status: **complete** (updated 2026-09-27T08:28:21Z).

### Incremental checkpoint

Arm A: `complete` (8/8 stored); Arm B: `complete` (8/8 stored); judge: `complete` (10 cells).

## Setup and model identifiers

| Provider | Model id sent | Provider echo / resolution | Endpoint | Applied settings | Verification |
|---|---|---|---|---|---|
| GPT-6 Luna | `gpt-6-luna` | `gpt-6-luna` | `https://api.openai.com/v1/chat/completions` | `{"max_completion_tokens": 3600, "reasoning_effort": "none", "response_format": "json_schema strict canonical OUTPUT_SCHEMA"}` | HTTP 200; passed=True; attempts=1 |
| Gemini Flash-Lite | `gemini-3.5-flash-lite` | `gemini-3.5-flash-lite` | `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent` | `{"maxOutputTokens": 3000, "responseMimeType": "application/json", "thinkingConfig": {"thinkingLevel": "low"}}` | HTTP 200; passed=True; attempts=1 |

Environment: Python 3.13.5; requests 2.32.3; Linux-6.12.41+deb13-arm64-aarch64-with-glibc2.41; all benchmark timing interpreted in UTC. OpenAI usage maps prompt/completion/reasoning/cached input from the observed Chat Completions usage fields; Gemini maps prompt/candidate/cached counts from usageMetadata. Reasoning setting `none` was accepted in the Luna probe and returned 0 reasoning tokens. Gemini `thinkingLevel=low` and JSON MIME passed the tiny probe.

Rate card (USD per 1M tokens): Luna input/cached/output $0.10/$0.01/$0.50; Gemini $0.30/$0.30/$2.50; optional DeepSeek off-peak $0.15/$0.003/$0.60 and peak $0.30/$0.006/$1.20. Sources were carried forward from DQ79 `raw/cost-report.json` and `dq79-ai-papers-routing-eval.md`: [OpenAI GPT-6 Luna model page](https://developers.openai.com/api/docs/models/gpt-6-luna), [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/), and the local prior-art Gemini `PRICING_PER_MILLION` table reviewed 2026-09-25; these rates were not re-queried in this network-scoped run. Estimated charges are not invoices.

## Benchmark design and controls

- A: one Luna call per paper; canonical L3 system prompt/schema with the full-reference source.
- B: one full-text Gemini D-contract extraction call, then one Luna call on a four-field JSON packet. The packet hand-off contains exactly `candidate_claims`, `key_claims`, `limitations`, `load_bearing_pages`; missing/wrong-typed fields become empty arrays and the object is serialized with sorted keys, compact separators, UTF-8, `ensure_ascii=false`. `requested_pages` and `stop_reason` are omitted.
- Both Luna bodies use `run_l3.paper_sources(..., path='full_reference')` for metadata and then change only the `SOURCE METHOD:` line and `SOURCE:` payload. Canonical system prompt, output schema, user prefix, and metadata are identical.
- Prompt and schema bundle SHA256: `{"armA-luna.md": "4a89a70dc8ad815b915880261c36f076de001f5927d792f8615798db9b781b6e", "armB-luna.md": "040418e251830214a95a61c4c4447ea35c0ffa5de86e61b3681821616e5dadce", "canonical-output-schema.json": "b8421c285acaa61cd4ea76a4605c25768090e0d5292d5bec49c4e4e9ec65fa0f", "gemini-packet.md": "181faa44b7f140126b6b6f01244cdb234477c95521e38173431d186385d2f495"}`. Actual per-paper request-body hashes are stored in the arm checkpoints and response attempts. The exact output schema is embedded in the OpenAI response_format rather than the text prompt.
- Prompt alignment audit: templates match apart from source method=True; all 8 actual request pairs match except source method/payload=True; all reconstructed request-body hashes match saved=True. Details: `raw/prompt-alignment.json`.
- DQ79 reuse: cached `scratch/pdf-text.json` as canonical full text; `raw/sampling.json` and `raw/arxiv-abstracts.json` for metadata; each D response as the operational claim/page reference; `scratch/provider.py`, `run_l2.py` prompt/page assembly, `run_l3.py` `OUTPUT_SCHEMA`/`SYSTEM`/`paper_sources`/`gen_request`/`canonicalize`/`check_output`, and `l2_metrics.py` matching/page functions. Source bundle: `~/.hermes/ops-cards/dq79-evidence`.
- Compatibility: 8/8 request-body SHA256 values match. The D hash covers the compact Gemini request body (including generationConfig), not just the text payload.
- Optional reasoning sensitivity arm: not justified; all 8 primary A outputs parsed as canonical, passed the strict JSON schema, and had page-valid citations, so the specified degenerate failure mode did not occur.

## Arm A — one-pass GPT-6 Luna

| Paper | Claims (key+evidence) / insights | D load-bearing page recall | Refs: count / page-valid / cited-page quote | Schema: native / normalized / page-valid | Confidence n / mean / range | Latency (ms) | Tokens in/out/cached | Cost (USD) |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| 2609.29808 | 6 / 3 | 0.000 (0/3) | 12 / 12 / 9 | 1 / 1 / true | 3 / 0.810 / 0.750–0.900 | 15156 | 19358 / 1552 / 0 | 0.002712 |
| 2609.29095 | 6 / 3 | 0.500 (4/8) | 14 / 14 / 12 | 1 / 1 / true | 3 / 0.913 / 0.890–0.940 | 15218 | 26679 / 1664 / 0 | 0.003500 |
| 2609.28614 | 4 / 3 | 0.625 (5/8) | 11 / 11 / 8 | 1 / 1 / true | 3 / 0.847 / 0.820–0.880 | 13072 | 29880 / 1320 / 0 | 0.003648 |
| 2609.30217 | 6 / 3 | 0.600 (3/5) | 11 / 11 / 10 | 1 / 1 / true | 3 / 0.930 / 0.880–0.970 | 15569 | 28285 / 1483 / 0 | 0.003570 |
| 2609.28585 | 5 / 3 | 0.571 (4/7) | 14 / 14 / 11 | 1 / 1 / true | 3 / 0.857 / 0.740–0.950 | 17191 | 29235 / 1903 / 0 | 0.003875 |
| 2609.28586 | 6 / 3 | 0.400 (2/5) | 11 / 11 / 8 | 1 / 1 / true | 3 / 0.917 / 0.900–0.940 | 16323 | 28518 / 1619 / 0 | 0.003661 |
| 2609.27263 | 6 / 3 | 0.375 (3/8) | 12 / 12 / 12 | 1 / 1 / true | 3 / 0.913 / 0.890–0.940 | 15781 | 26485 / 1417 / 0 | 0.003357 |
| 2609.24122 | 6 / 3 | 1.000 (4/4) | 12 / 12 / 8 | 1 / 1 / true | 3 / 0.927 / 0.890–0.950 | 14344 | 40238 / 1527 / 0 | 0.004787 |


Latency is measured end-to-end per paper; token and cost cells include every attempt for that paper. `Claims` counts key claims plus evidence items as separate output units; claim-recall matching separately deduplicates their claim strings. Citation validation is lexical, with interpretation in the evidence section.

## Arm B — Gemini evidence packet → GPT-6 Luna

| Paper | Gemini packet claims / Luna claims+insights | Packet page recall (refs) / final page recall | Final refs: count / page-valid / cited-page quote | Packet schema / Luna native / normalized / page-valid | Confidence n / mean / range | Gemini / Luna / end-to-end latency (ms) | Tokens in/out/cached (Gemini + Luna) | Cost (USD: Gemini / Luna / total) |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| 2609.29808 | 5 / 5 + 2 | 0.333 / 0.333 | 7 / 7 / 5 | true / true / false / true | 2 / 0.415 / 0.350–0.480 | 27082 / 10434 / 37546 | 17450 / 656 / 0 + 4187 / 1023 / 0 | 0.006875 / 0.000930 / 0.007805 |
| 2609.29095 | 7 / 6 + 3 | 0.125 / 0.125 | 12 / 12 / 9 | true / true / true / true | 3 / 0.937 / 0.920–0.950 | 24764 / 12610 / 37417 | 25557 / 613 / 0 + 4171 / 1461 / 0 | 0.009200 / 0.001148 / 0.010347 |
| 2609.28614 | 8 / 5 + 3 | 0.125 / 0.125 | 10 / 10 / 10 | true / true / true / true | 3 / 0.860 / 0.820–0.900 | 26724 / 13295 / 40055 | 28230 / 645 / 0 + 4291 / 1253 / 0 | 0.010082 / 0.001056 / 0.011137 |
| 2609.30217 | 6 / 6 + 3 | 0.400 / 0.600 | 11 / 11 / 4 | true / true / true / true | 3 / 0.753 / 0.720–0.780 | 27025 / 12759 / 39855 | 26642 / 649 / 0 + 4104 / 1454 / 0 | 0.009615 / 0.001137 / 0.010752 |
| 2609.28585 | 5 / 6 + 3 | 0.286 / 0.429 | 12 / 12 / 8 | true / true / true / true | 3 / 0.740 / 0.620–0.820 | 27287 / 14779 / 42113 | 29069 / 670 / 0 + 4168 / 1360 / 0 | 0.010396 / 0.001097 / 0.011493 |
| 2609.28586 | 4 / 6 + 2 | 0.200 / 0.200 | 10 / 10 / 2 | true / true / true / true | 2 / 0.800 / 0.750–0.850 | 26235 / 14826 / 41133 | 27225 / 394 / 0 + 3957 / 1307 / 0 | 0.009152 / 0.001049 / 0.010202 |
| 2609.27263 | 8 / 5 + 2 | 0.125 / 0.125 | 7 / 7 / 7 | true / true / true / true | 2 / 0.815 / 0.790–0.840 | 24715 / 12610 / 37360 | 25310 / 814 / 0 + 4273 / 1016 / 0 | 0.009628 / 0.000935 / 0.010563 |
| 2609.24122 | 6 / 5 + 2 | 0.250 / 0.250 | 9 / 9 / 6 | true / true / true / true | 2 / 0.795 / 0.760–0.830 | 25829 / 13804 / 39687 | 40922 / 662 / 0 + 4321 / 1186 / 0 | 0.013932 / 0.001025 / 0.014957 |


Gemini stage and Luna stage run serially. The packet counts include candidate claims plus key-claim strings; output citation and schema checks apply to Luna's canonical final artifact.

## Evidence integrity metrics

Operational definitions: Union of canonical output evidence_refs[].page across key claims, evidence, and insights intersected with D load_bearing_pages; denominator is D load_bearing_pages count. D candidate_claims are references; candidates are deduplicated paper.key_claims[].claim + paper.evidence[].claim; match is maximum content-word Jaccard with DQ79 fixed stopwords, threshold 0.20 primary, sensitivity 0.15/0.25.
Citation resolvability and weak-support indicators: In-range integer page and quote containment after case/whitespace normalization on cited page or any page; lexical resolvability proxies, not semantic entailment. Support-rate claim units are key_claims and evidence items counted separately, without deduplication; insight items are counted separately. A claim or insight is unsupported/weak if it has no refs, or if none of its refs has both an in-range integer page and a nonempty quote contained on that cited page.

| Metric | A — Luna full text | B — Gemini packet stage | B — Luna final |
|---|---:|---:|---:|
| Mean D load-bearing page recall | 0.509 | 0.231 (packet evidence refs) | 0.273 |
| Mean declared-page recall | N/A | 0.752 (`load_bearing_pages`) | N/A |
| D candidate-claim recall, Jaccard ≥ 0.15 | 0.554 | 0.975 | 0.715 |
| D candidate-claim recall, Jaccard ≥ 0.20 | 0.440 | 0.975 | 0.652 |
| D candidate-claim recall, Jaccard ≥ 0.25 | 0.248 | 0.975 | 0.627 |
| A — Luna: in-range integer page refs | 1.000 | — | — |
| A — Luna: cited-page quote containment | 0.804 | — | — |
| A — Luna: any-page quote containment | 0.825 | — | — |
| A — Luna: unsupported/weak claims | 6/45 (0.133) | — | — |
| A — Luna: unsupported/weak insights | 2/24 (0.083) | — | — |
| B — Luna final: in-range integer page refs | — | — | 1.000 |
| B — Luna final: cited-page quote containment | — | — | 0.654 |
| B — Luna final: any-page quote containment | — | — | 0.667 |
| B — Luna final: unsupported/weak claims | — | — | 19/44 (0.432) |
| B — Luna final: unsupported/weak insights | — | — | 4/20 (0.200) |
| Important D load-bearing claims matched at 0.20 | 9/21 | 20/21 | 14/21 |
| Important D load-bearing claim miss rate at 0.20 | 12/21 (0.571) | 1/21 (0.048) | 7/21 (0.333) |

Important-evidence misses (Jaccard 0.20; D reference claim, page refs, best candidate overlap):
- `2609.29808` / A; D pages [1, 2]; Jaccard 0.031; numeric/result=False: An autonomous agent operating in a continuous execution loop without an out-of-band Epistemic Andon Cord presents an existential security and operational hazard, leading to machine-speed compounding failures.
- `2609.29808` / B; D pages [1, 2]; Jaccard 0.035; numeric/result=False: An autonomous agent operating in a continuous execution loop without an out-of-band Epistemic Andon Cord presents an existential security and operational hazard, leading to machine-speed compounding failures.
- `2609.29095` / A; D pages [1]; Jaccard 0.065; numeric/result=False: When a write times out or returns a server error, the action may already have taken effect, and blind retries cause duplicate side effects while giving up skips required work.
- `2609.29095` / A; D pages [1]; Jaccard 0.115; numeric/result=False: Frontier models instructed to act exactly once almost never duplicate a write whose acknowledgement was lost, whereas weaker models often do.
- `2609.29095` / B; D pages [1]; Jaccard 0.080; numeric/result=False: When a write times out or returns a server error, the action may already have taken effect, and blind retries cause duplicate side effects while giving up skips required work.
- `2609.29095` / B-Gemini-packet; D pages [1]; Jaccard 0.107; numeric/result=False: When a write times out or returns a server error, the action may already have taken effect, and blind retries cause duplicate side effects while giving up skips required work.
- `2609.28614` / A; D pages [1]; Jaccard 0.087; numeric/result=True: When hacking is allowed on tasks whose pass thresholds exceed best compliant baselines, 505/677 attempts (74.6%) are confirmed reward hacks.
- `2609.28614` / A; D pages [1]; Jaccard 0.115; numeric/result=True: An LLM panel reviewing only submitted code and reported scores misses 33/505 confirmed hacks (6.5%).
- `2609.28614` / A; D pages [1]; Jaccard 0.160; numeric/result=True: Among 79 pairs evaluated under two feedback conditions, cumulative evasion reaches 40.5% with detailed feedback and 20.3% with generic rejection.
- `2609.28614` / B; D pages [1]; Jaccard 0.182; numeric/result=True: When hacking is allowed on tasks whose pass thresholds exceed best compliant baselines, 505/677 attempts (74.6%) are confirmed reward hacks.
- `2609.28614` / B; D pages [1]; Jaccard 0.174; numeric/result=True: An LLM panel reviewing only submitted code and reported scores misses 33/505 confirmed hacks (6.5%).
- `2609.28614` / B; D pages [1]; Jaccard 0.125; numeric/result=True: Among 79 pairs evaluated under two feedback conditions, cumulative evasion reaches 40.5% with detailed feedback and 20.3% with generic rejection.
- `2609.30217` / A; D pages [1]; Jaccard 0.130; numeric/result=True: Across evaluations of EvasionBench, best-of-3 evasion attempt rates reach up to 98% and success rates up to 88%, with substantial variance across models.
- `2609.30217` / A; D pages [1]; Jaccard 0.174; numeric/result=False: Evasion generally increases with test-time compute, showing higher evasion rates at greater reasoning effort and token use.
- `2609.30217` / A; D pages [1]; Jaccard 0.071; numeric/result=True: GPT-6 Astra's low evasion rate comes with overrefusal, as it frequently abandons otherwise solvable tasks under a denial-of-service prompt injection.
- `2609.28586` / A; D pages [1]; Jaccard 0.036; numeric/result=False: Approval laundering is a record-coverage failure where a durable record faithfully names an entry invocation yet omits effects exercised within its transitive workflow.
- `2609.28586` / A; D pages [1]; Jaccard 0.038; numeric/result=False: When executions with identical policy-visible fields require different effect-specific decisions, no deterministic or randomized record-only policy can guarantee both.
- `2609.28586` / B; D pages [1]; Jaccard 0.045; numeric/result=False: When executions with identical policy-visible fields require different effect-specific decisions, no deterministic or randomized record-only policy can guarantee both.
- `2609.27263` / A; D pages [1]; Jaccard 0.179; numeric/result=True: GitHub Agentic Workflows (gh-aw) Markdown files contain substantial instructions, with a median of 556.5 words per file, and combine natural-language task specifications with YAML frontmatter execution configuration.
- `2609.27263` / B; D pages [1]; Jaccard 0.077; numeric/result=True: GitHub Agentic Workflows (gh-aw) Markdown files contain substantial instructions, with a median of 556.5 words per file, and combine natural-language task specifications with YAML frontmatter execution configuration.

Reference-claim recall operationalization: D `candidate_claims` form the denominator; model output claim set is deduplicated `paper.key_claims[].claim + paper.evidence[].claim`; a D claim is a match when its best content-word Jaccard reaches the listed threshold. Unsupported claim units count each `paper.key_claims[]` and `paper.evidence[]` item separately (no deduplication); insight items are counted separately. These are lexical proxies, not semantic truth.

## Insight quality (blind judge)

| Judge | Arm | faithfulness | evidence_support | insight_depth | systems_relevance | actionability | compression_information_density | durable_memory_precision_proxy |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| gemini | A | 4.000 (n=7) | 4.000 (n=7) | 4.000 (n=7) | 4.000 (n=7) | 4.000 (n=7) | 4.000 (n=7) | 4.000 (n=7) |
| gemini | B | 3.286 (n=7) | 2.714 (n=7) | 2.714 (n=7) | 3.429 (n=7) | 2.857 (n=7) | 2.857 (n=7) | 3.000 (n=7) |

Uncertainty calibration: **N/A** because this run has no confidence/outcome series. Judge preference text, if present, was not converted into scores. Score means are descriptive, and small n is shown in each cell.
Primary judge: Gemini Flash-Lite (`gemini-3.5-flash-lite`; one independent judge, n=1), using thinkingLevel=low, JSON MIME, and maxOutputTokens=2200. Per paper, it saw both candidate artifacts, the union of source pages cited by either candidate, and agenda context; labels were permuted per paper (the blind-label map is `raw/judge/judge-map.json`). Full requested judge-response schema conformance was 0/8; the 7 paired numeric score cells shown were deterministically normalized with the reused DQ79 score normalizer from explicit JSON 0–4 values only. No preference/winner prose was converted to a score. One Gemini cell had no normalizable pair scores. Optional DeepSeek check: `deepseek-flash`, reasoning_effort=none, JSON object, max_tokens=2200; 0/2 full-schema passes, with 1 parse failure; it was not used as a second judge. See `raw/judge-results.json` and `raw/judge/judge-map.json`.

Representative blind-judge excerpts (best and worst measured paper within each arm; not preference claims):

- Arm A best (tied) (`2609.29808`, Gemini mean 4.00/4): The evaluated control point is the syscall/runtime boundary, not the agent’s planning quality; the reported tests favor kernel observation over literal string matching for obfuscated payloads.
- Arm A worst (tied) (`2609.24122`, Gemini mean 4.00/4): Treat retrieval coverage as a separate assurance dimension from answer faithfulness, using Re:CAP as a sampled audit rather than a live per-request reliability signal.
- Arm B best (`2609.29095`, Gemini mean 3.57/4): Exactly-once reliability is conditional: model behavior appears strong when immediate read-back resolves uncertainty, while uncertain in-flight or redelivered writes show high duplicate rates.
- Arm B worst (`2609.29808`, Gemini mean 2.14/4): The described containment strategy places deterministic controls outside the agent loop, rather than relying solely on model-level safety.

## Reliability

| Stage | Papers attempted | Provider attempts | Model responses | Native schema / packet pass | Normalized schema pass | Page-valid outputs | Deterministic validation failures | HTTP failure attempts | Transport failure attempts | Parse failures | Provider failures | Transient retry attempts | Truncation retry papers / attempts |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Arm A Luna | 8 | 8 | 8 | 8 | 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 |
| Arm B Gemini packet | 8 | 8 | 8 | 8 | N/A | N/A | 0 | 0 | 0 | 0 | 0 | 0 | 0 / 0 |
| Arm B Luna final | 8 | 8 | 8 | 8 | 7 | 8 | 1 | 0 | 0 | 0 | 0 | 0 | 0 / 0 |

Arm status: A `complete`; B `complete`.
Retries are limited to two transient retries on 429/5xx/timeout with increasing 2-second multiples; an observed max-token finish gets one additional request with a compact-output instruction. All attempt artifacts, including failed and billed invalid outputs, are counted in costs.
Optional judge format audit: `{"deepseek": {"calls": 2, "parse_failures": 1, "schema_pass": 0}, "gemini": {"calls": 8, "parse_failures": 0, "schema_pass": 0}}`.

## Failure cases

Pooled across the 25 paper-specific D candidate-claim instances at Jaccard 0.20, A matched 12, the Gemini packet matched 24, and final B matched 17. A-only versus final B: 0; final-B-only versus A: 5; packet matches lost at Luna synthesis: 7; packet misses recovered by final Luna: 0; packet and final misses: 1.

**2609.29808** — D load-bearing pages [1, 7, 10]; A misses [1, 7, 10]; B packet misses [7, 10]; B final misses [7, 10].
  - D claim pages [1, 2]; A=miss, B packet=match, B final=miss; best Jaccard A=0.031, packet=0.414, final B=0.035. B synthesis/handoff loss: Gemini packet matched it; Luna final did not. Reference claim: An autonomous agent operating in a continuous execution loop without an out-of-band Epistemic Andon Cord presents an existential security and operational hazard, leading to machine-speed compounding failures.
  - D claim pages [7]; A=miss, B packet=match, B final=miss; best Jaccard A=0.036, packet=0.538, final B=0.033. B synthesis/handoff loss: Gemini packet matched it; Luna final did not. Reference claim: Centralized commercial models with conversational safety filters failed during forensic incident response by classifying payload deobfuscation as cyberattack assistance, requiring locally hosted open-weights models.
**2609.29095** — D load-bearing pages [1, 2, 4, 5, 6, 8, 10, 12]; A misses [1, 5, 6, 8]; B packet misses [2, 4, 5, 6, 8, 10, 12]; B final misses [2, 4, 5, 6, 8, 10, 12].
  - D claim pages [1]; A=miss, B packet=miss, B final=miss; best Jaccard A=0.065, packet=0.107, final B=0.080. B extraction loss: absent from Gemini packet and final B. Reference claim: When a write times out or returns a server error, the action may already have taken effect, and blind retries cause duplicate side effects while giving up skips required work.
  - D claim pages [1]; A=miss, B packet=match, B final=match; best Jaccard A=0.115, packet=1.000, final B=0.381.  B matched; A missed. Reference claim: Frontier models instructed to act exactly once almost never duplicate a write whose acknowledgement was lost, whereas weaker models often do.
**2609.28614** — D load-bearing pages [1, 2, 5, 6, 7, 10, 11, 15]; A misses [1, 2, 5]; B packet misses [2, 5, 6, 7, 10, 11, 15]; B final misses [2, 5, 6, 7, 10, 11, 15].
  - D claim pages [1]; A=miss, B packet=match, B final=miss; numeric/result claim; best Jaccard A=0.087, packet=0.615, final B=0.182. B synthesis/handoff loss: Gemini packet matched it; Luna final did not. Reference claim: When hacking is allowed on tasks whose pass thresholds exceed best compliant baselines, 505/677 attempts (74.6%) are confirmed reward hacks.
  - D claim pages [1]; A=miss, B packet=match, B final=miss; numeric/result claim; best Jaccard A=0.115, packet=1.000, final B=0.174. B synthesis/handoff loss: Gemini packet matched it; Luna final did not. Reference claim: An LLM panel reviewing only submitted code and reported scores misses 33/505 confirmed hacks (6.5%).
  - D claim pages [1]; A=miss, B packet=match, B final=miss; numeric/result claim; best Jaccard A=0.160, packet=1.000, final B=0.125. B synthesis/handoff loss: Gemini packet matched it; Luna final did not. Reference claim: Among 79 pairs evaluated under two feedback conditions, cumulative evasion reaches 40.5% with detailed feedback and 20.3% with generic rejection.
**2609.30217** — D load-bearing pages [1, 3, 6, 7, 10]; A misses [1, 3]; B packet misses [3, 7, 10]; B final misses [7, 10].
  - D claim pages [1]; A=miss, B packet=match, B final=match; numeric/result claim; best Jaccard A=0.130, packet=0.571, final B=0.312.  B matched; A missed. Reference claim: Across evaluations of EvasionBench, best-of-3 evasion attempt rates reach up to 98% and success rates up to 88%, with substantial variance across models.
  - D claim pages [1]; A=miss, B packet=match, B final=match; best Jaccard A=0.174, packet=1.000, final B=0.375.  B matched; A missed. Reference claim: Evasion generally increases with test-time compute, showing higher evasion rates at greater reasoning effort and token use.
  - D claim pages [1]; A=miss, B packet=match, B final=match; numeric/result claim; best Jaccard A=0.071, packet=0.882, final B=0.316.  B matched; A missed. Reference claim: GPT-6 Astra's low evasion rate comes with overrefusal, as it frequently abandons otherwise solvable tasks under a denial-of-service prompt injection.
**2609.28585** — D load-bearing pages [1, 2, 3, 7, 8, 9, 11]; A misses [3, 7, 9]; B packet misses [3, 7, 8, 9, 11]; B final misses [7, 8, 9, 11].
  - No D-claim divergence at the 0.20 lexical threshold; page sets still differ.
**2609.28586** — D load-bearing pages [1, 2, 3, 4, 5]; A misses [2, 3, 5]; B packet misses [2, 3, 4, 5]; B final misses [2, 3, 4, 5].
  - D claim pages [1]; A=miss, B packet=match, B final=match; best Jaccard A=0.036, packet=0.944, final B=0.409.  B matched; A missed. Reference claim: Approval laundering is a record-coverage failure where a durable record faithfully names an entry invocation yet omits effects exercised within its transitive workflow.
  - D claim pages [1]; A=miss, B packet=match, B final=miss; best Jaccard A=0.038, packet=1.000, final B=0.045. B synthesis/handoff loss: Gemini packet matched it; Luna final did not. Reference claim: When executions with identical policy-visible fields require different effect-specific decisions, no deterministic or randomized record-only policy can guarantee both.
**2609.27263** — D load-bearing pages [1, 2, 5, 6, 7, 8, 12, 13]; A misses [1, 2, 6, 7, 12]; B packet misses [2, 5, 6, 7, 8, 12, 13]; B final misses [2, 5, 6, 7, 8, 12, 13].
  - D claim pages [1]; A=miss, B packet=match, B final=miss; numeric/result claim; best Jaccard A=0.179, packet=0.458, final B=0.077. B synthesis/handoff loss: Gemini packet matched it; Luna final did not. Reference claim: GitHub Agentic Workflows (gh-aw) Markdown files contain substantial instructions, with a median of 556.5 words per file, and combine natural-language task specifications with YAML frontmatter execution configuration.
**2609.24122** — D load-bearing pages [1, 2, 5, 6]; A misses []; B packet misses [2, 5, 6]; B final misses [2, 5, 6].
  - No D-claim divergence at the 0.20 lexical threshold; page sets still differ.

Provider, parse, truncation, and deterministic validation failures are retained per attempt in `raw/responses/`; the failure summaries here do not discard billed invalid responses.

## Cost and latency

| Architecture / stage | Papers (output / attempted) | Attempts (incl. retries) | Input tokens | Output tokens | Cached input | Attempt-latency sum (s) | End-to-end latency sum (s) | Median latency (s) | Measured cost (USD) | Mean cost/paper (USD) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A — Luna | 8/8 | 8 | 228678 | 12485 | 0 | 122.23 | 122.65 | 15.39 | $0.029110 | $0.003639 |
| B — packet + Luna | 8/8 | 16 | 253877 | 15163 | 0 | 314.78 | 315.17 | 39.77 | $0.087256 | $0.010907 |
| B — Gemini packet stage | 8/8 | 8 | 220405 | 5103 | 0 | 209.66 | 209.66 | 26.48 | $0.078879 | $0.009860 |
| B — Luna final stage | 8/8 | 8 | 33472 | 10060 | 0 | 105.12 | 105.12 | 13.03 | $0.008377 | $0.001047 |

Total benchmark provider spend including capability probes and judge calls: **$0.188291** across 36 attempt artifacts (703663 input and 32904 output tokens); cap $8.00. This is recalculated from every saved attempt and its applied `rates_used_usd_per_million`.
Per-paper performance JSON and each stage breakdown are in `raw/armA-results.json`, `raw/armB-results.json`, `raw/responses/`, and `raw/metrics.json`.
B stage latency-attempt sums: Gemini 209.66s; Luna 105.12s. End-to-end wall durations include serial stage waits, transient retry backoff, and local processing; attempt sums exclude backoff.

## Scale model (1k/10k/100k/1M + funnel + throughput)

Every value in the tables below is **modeled** from the measured mean per-paper cost/latency. The source eight-paper benchmark values remain in the measured tables above.

Measured basis: Workers process papers independently; each B paper performs Gemini extraction then Luna synthesis serially; mean end-to-end time uses measured per-paper calls including request retries and backoff. Throughput is K / mean end-to-end latency.
Rate-limit caveat: No rate-limit contention, provider queueing, or quota throttling is modeled. Retry/backoff behavior is represented only by this small serial sample; actual limits are provider/account specific and may lower throughput.

### Modeled cost by escalated paper count

| Architecture | Escalated papers | Modeled cost (USD) | Modeled serial worker-hours |
|---|---:|---:|---:|
| A — Luna | 1,000 | $3.64 | 4.3 h |
| A — Luna | 10,000 | $36.39 | 42.6 h |
| A — Luna | 100,000 | $363.88 | 425.9 h |
| A — Luna | 1,000,000 | $3,638.79 | 4,258.8 h |
| B — Gemini → Luna | 1,000 | $10.91 | 10.9 h |
| B — Gemini → Luna | 10,000 | $109.07 | 109.4 h |
| B — Gemini → Luna | 100,000 | $1,090.70 | 1,094.3 h |
| B — Gemini → Luna | 1,000,000 | $10,907.03 | 10,943.3 h |

### Modeled funnel at 10% / 25% / 50% escalation

| Architecture | Incoming papers | Escalation | Escalated papers | Modeled full-pipeline cost (USD) |
|---|---:|---:|---:|---:|
| A — Luna | 1,000 | 10% | 100 | $0.36 |
| A — Luna | 1,000 | 25% | 250 | $0.91 |
| A — Luna | 1,000 | 50% | 500 | $1.82 |
| A — Luna | 10,000 | 10% | 1,000 | $3.64 |
| A — Luna | 10,000 | 25% | 2,500 | $9.10 |
| A — Luna | 10,000 | 50% | 5,000 | $18.19 |
| A — Luna | 100,000 | 10% | 10,000 | $36.39 |
| A — Luna | 100,000 | 25% | 25,000 | $90.97 |
| A — Luna | 100,000 | 50% | 50,000 | $181.94 |
| A — Luna | 1,000,000 | 10% | 100,000 | $363.88 |
| A — Luna | 1,000,000 | 25% | 250,000 | $909.70 |
| A — Luna | 1,000,000 | 50% | 500,000 | $1,819.39 |
| B — Gemini → Luna | 1,000 | 10% | 100 | $1.09 |
| B — Gemini → Luna | 1,000 | 25% | 250 | $2.73 |
| B — Gemini → Luna | 1,000 | 50% | 500 | $5.45 |
| B — Gemini → Luna | 10,000 | 10% | 1,000 | $10.91 |
| B — Gemini → Luna | 10,000 | 25% | 2,500 | $27.27 |
| B — Gemini → Luna | 10,000 | 50% | 5,000 | $54.54 |
| B — Gemini → Luna | 100,000 | 10% | 10,000 | $109.07 |
| B — Gemini → Luna | 100,000 | 25% | 25,000 | $272.68 |
| B — Gemini → Luna | 100,000 | 50% | 50,000 | $545.35 |
| B — Gemini → Luna | 1,000,000 | 10% | 100,000 | $1,090.70 |
| B — Gemini → Luna | 1,000,000 | 25% | 250,000 | $2,726.76 |
| B — Gemini → Luna | 1,000,000 | 50% | 500,000 | $5,453.51 |

### Modeled throughput under worker pools

| Architecture | Workers K | Modeled papers/second | Modeled papers/hour |
|---|---:|---:|---:|
| A — Luna | 1 | 0.0652 | 234.8 |
| A — Luna | 4 | 0.2609 | 939.2 |
| A — Luna | 8 | 0.5218 | 1878.5 |
| A — Luna | 16 | 1.0436 | 3756.9 |
| B — Gemini → Luna | 1 | 0.0254 | 91.4 |
| B — Gemini → Luna | 4 | 0.1015 | 365.5 |
| B — Gemini → Luna | 8 | 0.2031 | 731.0 |
| B — Gemini → Luna | 16 | 0.4061 | 1462.1 |

No separate L1 triage reference line was included; triage is outside this architecture comparison.

## Verdict: does the Gemini stage earn its keep

| Architecture | Evidence recall | Citation validity | Schema reliability | Insight quality | Cost/paper | Latency/paper | Operational complexity |
|---|---|---|---|---|---:|---|---|
| One-pass GPT-6 Luna | LB pages 0.509; D claims@.20 0.440 | page-valid 1.000; cited quote 0.804 | native 8/8; normalized 8/8 | faithfulness 4.000 (n=7); evidence support 4.000 (n=7); insight depth 4.000 (n=7) | $0.003639 | median 15.4s; mean 15.3s | 1 model call/paper; one vendor; schema + evidence guard |
| Gemini packet → GPT-6 Luna | LB pages 0.273; D claims@.20 0.652 | page-valid 1.000; cited quote 0.654 | native 8/8; normalized 7/8 | faithfulness 3.286 (n=7); evidence support 2.714 (n=7); insight depth 2.714 (n=7) | $0.010907 | median 39.8s; mean 39.4s | 2 serial model stages/paper; cross-provider hand-off + packet validation + two provider failure surfaces |

**Verdict.** The result is mixed and does not establish that the Gemini stage earns its added cost and serial latency. One-pass Luna falls outside at least one tolerance or a required reliability condition, while B did not meet the repeatable material-improvement rule. The data support neither a blanket two-stage rollout nor a confident equivalence claim; use the per-paper divergence list to target a larger follow-up.

Measured B−A deltas: D load-bearing pages -0.236; D claims@0.20 0.213; Gemini-judge faithfulness -0.714 (n=7/7); evidence_support -1.286 (n=7/7). B was directionally higher in 1/8 page, 3/8 claim, 0/8 faithfulness, and 0/8 evidence-support pairs.

Measured cost difference is $0.007268/paper; median serial latency difference is 24.4s.

The numerical interpretation rule was applied post hoc after observing this run: call B materially better only with at least +0.5/4 mean Gemini-judge gain in faithfulness or evidence_support, or at least +10 percentage points in mean D load-bearing-page recall or primary D-claim recall; require a positive direction in at least 6/8 paired papers and no lower schema/page-valid reliability. Prefer A when it is within that margin and citations/schema remain reliable. This is a pragmatic decision threshold for this small sample, not a validated universal threshold.

## Caveats

- n=8 purposive subset; the set is not a random or prevalence-representative paper sample.
- D is an operational reference produced by Gemini Flash-Lite itself, the same model family as B extraction. This creates a potential self-family advantage for B; D is not independent truth.
- Claim matches use content-word Jaccard; page recall and quote containment are lexical checks. They do not establish semantic entailment or scientific correctness.
- Blind judge sample sizes are shown per dimension/cell and can be smaller than 8; the optional second judge status is `{'calls': 2, 'schema_pass': 0, 'parse_failures': 1}`. The primary Gemini judge is cross-vendor to Luna and same-family with B extraction.
- The Gemini judge's numeric scores were ceiling-heavy for Arm A (all 7 normalized A ratings were 4/4 on the reported dimensions), which limits discrimination; judge JSON format compliance was incomplete.
- Post-hoc interpretation uses the decision threshold stated above; all seven quality dimensions remain separately reported. Uncertainty calibration is N/A because there is no confidence/outcome series.
- `reasoning_effort=none` bounds the result to this Luna setting; it does not estimate a higher-effort one-pass architecture.
- The execution image used Python 3.13.5 (requests 2.32.3); the repository's normal engineering target is Python 3.12, so this benchmark does not measure that runtime.
- Costs are rate-card estimates from recorded token usage, not provider invoices. Retries and billed invalid responses are included.
- Scale and funnel values are modeled from measured per-paper means; they are not measured batch throughput. Throughput assumes no rate-limit contention or provider queueing and carries only the observed retry/backoff behavior forward.
- No JEV measurement was run or included. No network access outside the three authorized provider API hosts, no real lane/tracker, and no host mutation were performed.
- Public hygiene scan command: `grep -rIlE 'sk-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]+|/home/|/tmp/|/root/|/Users/|session[_-]?id|chat[_-]?id|request[_-]?id' public/`; result recorded in the final scan section below.

Public staging scan

Command: `grep -rIlE 'sk-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]+|/home/|/tmp/|/root/|/Users/|session[_-]?id|chat[_-]?id|request[_-]?id' public/`

Result: **PASS; no matching files**. The command returned no file paths on PASS.
