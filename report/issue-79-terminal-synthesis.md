## Benchmark synthesis — AI Papers Insights routing evaluation (recovered run, terminal)

Terminal deliverable for the bounded evaluation. **Recovery context:** the original execution froze in the 2026-09-25 host stall (disk-pressure episode) and was SIGKILLed by its 4-hour ceiling — see the recovery records above (audit + executed-recovery comments). The run was **resumed from its preserved checkpoint** (same codex session) at 2026-09-26 22:04Z and completed at 23:28:51Z, rc=0, with no re-paid L1 work and every outage-window failure retained as data.

**Run totals (all attempts):** 300 attempts / 275 unique call IDs · 1,965,663 input / 138,183 output tokens · **$0.5386 estimated** (6.7% of the $8 cap). Full raw evidence harvested to `~/.hermes/ops-cards/dq79-evidence/` (worktree copy at `~/.hermes/worktrees/delegation-queue/issue-79`, checksums in `raw/SHA256SUMS.txt`).

**Read this first:** the selective-reading hypothesis is **not supported** at the tested page budget (0.309 load-bearing-page recall; the reader requested no further pages on all eight papers). The only measured full pipeline meeting the structural/quality gates is full-document reference → GPT-6 Luna. Role recommendations, thresholds, and explicit uncertainty are inside — several judges/format findings are small-n and are flagged as such.

---

# AI Papers Insights routing evaluation — delegation-queue#79

Run started 2026-09-25 UTC. This is a bounded empirical evaluation in the issue-79 scratch worktree. Inputs are the read-only local paper stores/KG and public arXiv pages/PDFs; provider calls use only the specified endpoints. No host state, corpus database, service, scheduled job, or deployment is modified. Results and raw calls are retained under `raw/`.

## Setup and model identifiers
Models and paths were verified by live capability calls retained in `raw/capability-probes.json` and `raw/responses/probes/` (plus the documented Gemini selector correction). Provider ids are recorded exactly as sent.

| Candidate | Provider path | Sent id | Resolved id/version | Reasoning / structured output | Verification and usage mapping |
|---|---|---|---|---|---|
| DeepSeek Flash | Direct `https://api.deepseek.com/chat/completions` | `deepseek-flash` | `deepseek-flash` (response `model` echoed `deepseek-flash`) | `reasoning_effort:none`; response had no `reasoning_content` and no reasoning-token counter. `response_format: {"type":"json_object"}`. | HTTP 200; output `{"answer": 2}`. Usage: `usage.prompt_tokens`, `completion_tokens`, `prompt_cache_hit_tokens`; no reasoning channel observed. |
| Gemini Flash-Lite | Native `https://generativelanguage.googleapis.com/v1beta/models/{id}:generateContent` | Requested alias `gemini-3.5-flash-lite`; sent pinned `gemini-3.5-flash-lite` | Catalogue entry `models/gemini-3.5-flash-lite`, version `3.5-flash-lite-07-2026` (latest stable text Flash-Lite entry returned; TTS/image siblings excluded); generation responses echoed `modelVersion=gemini-3.5-flash-lite` without the dated suffix. | `thinkingConfig.thinkingLevel=low` accepted; `thinkingBudget=0` rejected HTTP 400. Structured JSON uses `responseMimeType: application/json`; one-page native PDF `inlineData` probe succeeded. | HTTP 200; returned `{"answer":2}` for text and PDF. Usage: `usageMetadata.promptTokenCount`, `candidatesTokenCount`, `cachedContentTokenCount`. `thoughtsTokenCount` absent in smoke response. |
| GPT-6 Luna | Direct `https://api.openai.com/v1/chat/completions` | `gpt-6-luna` | `gpt-6-luna` (response `model` echoed `gpt-6-luna`) | `reasoning_effort:none` produced numeric `reasoning_tokens=0`. `response_format: {"type":"json_schema","json_schema":{"name","strict":true,"schema"}}`. | HTTP 200; strict JSON output succeeded. Usage: `usage.prompt_tokens`, `completion_tokens`, `completion_tokens_details.reasoning_tokens`, `prompt_tokens_details.cached_tokens`. |
| JEV | Vercel AI Gateway evaluation v4 `https://ai-gateway.vercel.sh/v4/ai/evaluation-model` | Header `ai-model-id: typesafe-ai/jev` | `typesafe-ai/jev` (evaluation protocol accepted id; response carries typed answers, no separate resolved model field). | Typed bounded evaluation questions only; no reasoning channel. | HTTP 200; boolean probability answer returned. Usage: `usage.inputTokens`, `usage.outputTokens`. |

Runtime/tools: Python 3.13.5, uv 0.12.16, scratch-venv requests 2.34.2, PyMuPDF 1.28.2, pypdf 6.19.0. PDF extraction and rendering used PyMuPDF; package installation was limited to `venv-pdf` and `.uvcache` under this worktree. Provider endpoint calls use 120–300 second timeouts, with up to two retries on 429/5xx/timeout and persisted attempt records.

Applied rates per million tokens: GPT-6 Luna input $0.10, cached input $0.01, output $0.50; DeepSeek off-peak input/cached/output $0.15/$0.003/$0.60 and peak $0.30/$0.006/$1.20; Gemini input/cached/output $0.30/$0.30/$2.50; JEV input/output $0.042/$0. The GPT-6 Luna rates came from the [official model page](https://developers.openai.com/api/docs/models/gpt-6-luna) and the local prior-art comparison constants, reviewed 2026-09-24 UTC. DeepSeek rates came from [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/) plus prior-art `compare.ts`, reviewed 2026-09-24 UTC. Gemini rates came from the local `summarize_video.py` PRICING_PER_MILLION table, inspected 2026-09-25. JEV uses the `compare.ts` fallback table, reviewed 2026-09-24 UTC; a live JEV rate table was not queried. DeepSeek selects and records peak/off-peak from call-start UTC (peak Mon–Fri 01:00–04:00 and 06:00–10:00 UTC). Full per-call applied rates and costs are under `raw/responses/`.

Harness deviations: the initial Gemini catalogue selector chose `gemini-3.8-flash-lite-tts`; the first selection's three smoke attempts are reconstructed with missing status/latency where not recoverable and excluded from all aggregates. The corrected selector chose stable `gemini-3.5-flash-lite` and its text and PDF smoke checks succeeded. The first two L1 records are retained in `raw/l1-prompt-pilot.json` but excluded because the first prompt draft omitted exact output-key names; a corrected shared prompt passed a three-model pilot before the full L1 run. Those excluded probes/pilots are treated as harness failures, not model quality results.

## Sampled corpus
Selection is purposive and reproducible from fixed arXiv IDs written to `raw/sampling.json`. The rules deduplicate `papers.db` by arXiv id/newest digest, select high proxies from direct agenda sections/cues (`agents`, `mcp`, `infra`, `governance`), select adjacent LLM/RAG/prompt work, and choose non-agent domains from the full-abstract Kurate store as negative controls. Matching ids in `~/src/rmax-ai/knowledge-graph/sources/papers/*.md` tag already deeply processed items. It is not a random sample. The 12/8/4 class balance is artificial, and the low controls are older than the recent digest strata. Labels are proxies, not a gold relevance set.

| Stratum | n | Source and rule |
|---|---:|---|
| High-value proxy | 12 | `~/personal-hermes/papers.db`; direct agent reliability, evaluation, harness/runtime, MCP/governance, tool use, or workflow signal |
| Medium/adjacent | 8 | `~/personal-hermes/papers.db`; LLM/RAG/retrieval/prompt or structured-output work with plausible transfer but no direct agent runtime focus |
| Low-relevance control | 4 | `~/.hermes/cron/output/kurate/kurate.db`; non-agent optimization, state estimation, sensing, and AI labor-economics work |

Abstract metadata came from one `export.arxiv.org/api/query` request (HTTP 200, 64,174 bytes, 24 of 24 entries). The ten selected PDF candidates downloaded successfully (18,516,490 bytes total); six are at least 20 pages. The long/figure/table rule is measured as page count ≥20, or ≥6 embedded images / ≥4 explicit figure references, or ≥3 explicit table references; reference-count matches can overcount, so the page count is also shown. The L2/L3 set uses eight PDFs, with six 20+ page papers. PDF status/bytes/page/image/figure/table details and every per-paper rationale are in this table and `raw/sampling.json`.

| arXiv paper | Stratum | Source | Rationale | KG entry | PDF fetch |
|---|---|---|---|---|---|
| [/2609.27263v1](https://arxiv.org/abs/2609.27263v1) Specifying and Maintaining Agentic Workflows: An Empirical Study of GitHub Agentic Workflows | high_value_proxy | papers.db | Empirical study of agentic-workflow specifications and maintenance, a direct agent-workflow/evaluation signal. | yes | HTTP 200, 1,572,640 B, 17 pp; img 1, fig refs 19, table refs 0 |
| [/2609.28585v1](https://arxiv.org/abs/2609.28585v1) Persistent Billable State: Denial-of-Wallet Attacks and Defenses in Tool-Calling LLM Agents | high_value_proxy | papers.db | Studies tool-agent persistent billable state and runtime defenses, directly relevant to tool use and governance. | yes | HTTP 200, 971,756 B, 22 pp; img 2, fig refs 28, table refs 28 |
| [/2609.28586v1](https://arxiv.org/abs/2609.28586v1) Agent Approval Laundering: Transitive Effects Beyond the Approved Invocation | high_value_proxy | papers.db | Studies authorization records versus transitive workflow effects, directly relevant to agent action governance. | yes | HTTP 200, 1,249,606 B, 19 pp; img 0, fig refs 26, table refs 0 |
| [/2609.28614v1](https://arxiv.org/abs/2609.28614v1) Reward Hacking Challenges Oversight of Autonomous Research Agents | high_value_proxy | papers.db | Measures reward hacking in autonomous research agents, directly relevant to agent oversight and evaluation. | yes | HTTP 200, 11,495,738 B, 33 pp; img 100, fig refs 41, table refs 22 |
| [/2609.28693v1](https://arxiv.org/abs/2609.28693v1) Progressive Skill Discovery as Access Control for Tool-Using LLM Agents: Structural Governance through Role-Scoped Capability Delivery | high_value_proxy | papers.db | Studies role-scoped capability delivery for tool-using agents, directly relevant to tool governance. | yes | not attempted (bounded subset) |
| [/2609.28915v1](https://arxiv.org/abs/2609.28915v1) On the Effectiveness of Kernel-Level Evidence for Agent Security | high_value_proxy | papers.db | Examines kernel-level evidence for agent security, directly relevant to runtime assurance. | yes | not attempted (bounded subset) |
| [/2609.29095v1](https://arxiv.org/abs/2609.29095v1) Where Does Exactly-Once Live? Model, Harness, and Tool-Contract Effects on Duplicate Side Effects in LLM Agents | high_value_proxy | papers.db | Measures duplicate side effects across models, harnesses, and tool contracts, directly relevant to reliability. | yes | HTTP 200, 718,108 B, 23 pp; img 2, fig refs 10, table refs 28 |
| [/2609.30217v1](https://arxiv.org/abs/2609.30217v1) Instrumental Monitor Evasion Emerges Under Ordinary Task Pressure | high_value_proxy | papers.db | Empirically measures runtime-monitor evasion during ordinary agent task pressure. | yes | HTTP 200, 310,827 B, 34 pp; img 0, fig refs 57, table refs 20 |
| [/2609.30266v1](https://arxiv.org/abs/2609.30266v1) LLM Agents Can Easily Tamper With Their Own Traces | high_value_proxy | papers.db | Examines agents tampering with execution traces, directly relevant to audit and runtime assurance. | yes | not attempted (bounded subset) |
| [/2609.29808v1](https://arxiv.org/abs/2609.29808v1) Hard Stop: Kernel-Level Preemption and Containment for Rogue Agentic Execution | high_value_proxy | papers.db | Studies kernel-level preemption and containment of rogue agent execution. | yes | HTTP 200, 618,123 B, 21 pp; img 0, fig refs 4, table refs 0 |
| [/2609.23498v1](https://arxiv.org/abs/2609.23498v1) Runtime Authorization Consistency Checking for MCP-based Agentic Workflows | high_value_proxy | papers.db | Studies authorization consistency across MCP agent workflows. | yes | not attempted (bounded subset) |
| [/2609.24130v1](https://arxiv.org/abs/2609.24130v1) Self-Healing Harness for Runtime Oversight of Agent Self-Modification | high_value_proxy | papers.db | Studies harness-side runtime oversight of agent self-modification. | yes | not attempted (bounded subset) |
| [/2609.23742v1](https://arxiv.org/abs/2609.23742v1) Constrained Decoding Eliminates Structural Failures in Small LLMs but Reveals a Scale-Dependent Semantic Gap | medium_adjacent | papers.db | Structured-output reliability for small LLMs is adjacent to routing/evidence extraction, without directly evaluating agent workflows. | yes | HTTP 200, 219,981 B, 6 pp; img 2, fig refs 9, table refs 8 |
| [/2609.30009v1](https://arxiv.org/abs/2609.30009v1) Automated Regulatory Compliance Question Answering in Financial Services with Domain-Adapted Retrieval-Augmented Generation | medium_adjacent | papers.db | Domain-adapted RAG for financial compliance is an adjacent evidence-retrieval application, not a direct agent-runtime study. | yes | HTTP 200, 381,983 B, 15 pp; img 0, fig refs 6, table refs 18 |
| [/2609.24122v2](https://arxiv.org/abs/2609.24122v2) Re:CAP - Auditing Retrieval Coverage in Production RAG Pipelines | medium_adjacent | papers.db | Production RAG retrieval coverage auditing is adjacent to the evidence pipeline but does not focus on agent execution. | yes | HTTP 200, 977,728 B, 34 pp; img 1, fig refs 12, table refs 68 |
| [/2609.19710v1](https://arxiv.org/abs/2609.19710v1) A Closed-Loop Control Architecture for Reliable Constraint Satisfaction in LLM Text Generation | medium_adjacent | papers.db | Closed-loop constraint satisfaction in text generation is adjacent LLM reliability work, not agent routing/runtime evaluation. | yes | not attempted (bounded subset) |
| [/2609.14245v1](https://arxiv.org/abs/2609.14245v1) The Attribution-Compression Frontier in Retrieval-Augmented Generation | medium_adjacent | papers.db | RAG evidence compression and citation attribution are adjacent to selective reading and evidence packets. | yes | not attempted (bounded subset) |
| [/2609.03213v1](https://arxiv.org/abs/2609.03213v1) LLMs Learn Better In-Context from Rules than from Examples | medium_adjacent | papers.db | In-context rule learning is a general LLM method with possible transfer, not directly about agent systems. | yes | not attempted (bounded subset) |
| [/2609.15578v1](https://arxiv.org/abs/2609.15578v1) The Magnitude Mirage: Rethinking Confidence for Reasoning-Intensive Retrieval | medium_adjacent | papers.db | Retrieval confidence and abstention are adjacent to triage/calibration but not agent-specific. | yes | not attempted (bounded subset) |
| [/2609.22056v1](https://arxiv.org/abs/2609.22056v1) Predictable Failure in Multi-Hop Retrieval: Score-Distributional Confidence Scoring and Abstention | medium_adjacent | papers.db | Multi-hop retrieval confidence is adjacent to evidence sufficiency and escalation, not agent-specific. | yes | not attempted (bounded subset) |
| [/2606.01987v1](https://arxiv.org/abs/2606.01987v1) Graph Edit Distance Formulation for the Vehicle Routing Problem: Theory and Analysis | low_relevance_control | kurate.db | Vehicle-routing graph optimization has no agentic-AI agenda focus; negative domain control. | no | not attempted (bounded subset) |
| [/2606.30487v1](https://arxiv.org/abs/2606.30487v1) Discovering the Kalman-Bucy-Koopman Filter | low_relevance_control | kurate.db | Nonlinear state estimation/filtering has no agentic-AI agenda focus; technical control-domain negative control. | no | not attempted (bounded subset) |
| [/2603.21521v1](https://arxiv.org/abs/2603.21521v1) Ultrafast microwave sensing and automatic recognition of dynamic objects in open world using programmable surface plasmonic neural networks | low_relevance_control | kurate.db | Microwave sensing hardware and object recognition have no agentic-AI agenda focus; cross-domain negative control. | no | not attempted (bounded subset) |
| [/2606.15960v1](https://arxiv.org/abs/2606.15960v1) Chaining Tasks, Redefining Work: A Theory of AI Automation | low_relevance_control | kurate.db | Labor-economics theory about AI task bundling is adjacent to automation but has no agent reliability, runtime, or tool-use focus. | no | not attempted (bounded subset) |

## Layer 1: routing judgments
All 24 sampled papers received one logical call per judge (96 successful logical judgments); one JEV request returned HTTP 503 and succeeded on its first retry. The relevance outcome used for routing and calibration is the purposive stratum proxy: 12 high-value papers positive, 12 medium/low papers negative. It is not a natural-prevalence estimate or gold standard. At the default host threshold 0.50, every arm detected all 12 high-value proxies, so observed proxy false-negative rate was 0/12 for each; precision differed substantially. AUROC/AUPRC use the same balanced, stratified proxy labels.

| Judge | Proxy precision @0.50 | Recall | FNR | AUROC | AUPRC (AP) | Brier (relevance vs proxy) |
|---|---:|---:|---:|---:|---:|---:|
| JEV | 0.667 | 1.000 | 0.000 | 0.993 | 0.994 | 0.156 |
| DeepSeek Flash | 0.571 | 1.000 | 0.000 | 0.986 | 0.981 | 0.222 |
| Gemini 3.5 Flash-Lite | 0.857 | 1.000 | 0.000 | 0.969 | 0.942 | 0.075 |
| GPT-6 Luna | 0.600 | 1.000 | 0.000 | 0.889 | 0.824 | 0.292 |

Thresholds are applied in host analysis to P(relevant) at 0.30, 0.40, 0.50, 0.60, and 0.70. Models do not select thresholds. TP/FP/TN/FN and resulting rates:

| Threshold | Judge | TP / FP / TN / FN | Precision | Recall | FNR |
|---:|---|---:|---:|---:|---:|
| 0.30 | JEV | 12 / 11 / 1 / 0 | 0.522 | 1.000 | 0.000 |
| 0.30 | DeepSeek Flash | 12 / 9 / 3 / 0 | 0.571 | 1.000 | 0.000 |
| 0.30 | Gemini 3.5 Flash-Lite | 12 / 2 / 10 / 0 | 0.857 | 1.000 | 0.000 |
| 0.30 | GPT-6 Luna | 12 / 8 / 4 / 0 | 0.600 | 1.000 | 0.000 |
| 0.40 | JEV | 12 / 10 / 2 / 0 | 0.545 | 1.000 | 0.000 |
| 0.40 | DeepSeek Flash | 12 / 9 / 3 / 0 | 0.571 | 1.000 | 0.000 |
| 0.40 | Gemini 3.5 Flash-Lite | 12 / 2 / 10 / 0 | 0.857 | 1.000 | 0.000 |
| 0.40 | GPT-6 Luna | 12 / 8 / 4 / 0 | 0.600 | 1.000 | 0.000 |
| 0.50 | JEV | 12 / 6 / 6 / 0 | 0.667 | 1.000 | 0.000 |
| 0.50 | DeepSeek Flash | 12 / 9 / 3 / 0 | 0.571 | 1.000 | 0.000 |
| 0.50 | Gemini 3.5 Flash-Lite | 12 / 2 / 10 / 0 | 0.857 | 1.000 | 0.000 |
| 0.50 | GPT-6 Luna | 12 / 8 / 4 / 0 | 0.600 | 1.000 | 0.000 |
| 0.60 | JEV | 12 / 6 / 6 / 0 | 0.667 | 1.000 | 0.000 |
| 0.60 | DeepSeek Flash | 12 / 8 / 4 / 0 | 0.600 | 1.000 | 0.000 |
| 0.60 | Gemini 3.5 Flash-Lite | 12 / 2 / 10 / 0 | 0.857 | 1.000 | 0.000 |
| 0.60 | GPT-6 Luna | 12 / 8 / 4 / 0 | 0.600 | 1.000 | 0.000 |
| 0.70 | JEV | 12 / 2 / 10 / 0 | 0.857 | 1.000 | 0.000 |
| 0.70 | DeepSeek Flash | 12 / 7 / 5 / 0 | 0.632 | 1.000 | 0.000 |
| 0.70 | Gemini 3.5 Flash-Lite | 12 / 2 / 10 / 0 | 0.857 | 1.000 | 0.000 |
| 0.70 | GPT-6 Luna | 12 / 8 / 4 / 0 | 0.600 | 1.000 | 0.000 |

For calibration bins, entries are `n (mean probability / observed proxy-positive rate)`. Empty bins are shown as `0 (— / —)`.

| Judge | [0,.2) | [.2,.4) | [.4,.6) | [.6,.8) | [.8,1] |
|---|---|---|---|---|---|
| JEV | 0 (— / —) | 2 (0.29 / 0.00) | 5 (0.48 / 0.00) | 7 (0.68 / 0.14) | 11 (0.93 / 1.00) |
| DeepSeek Flash | 3 (0.08 / 0.00) | 0 (— / —) | 2 (0.57 / 0.00) | 4 (0.69 / 0.00) | 16 (0.93 / 0.75) |
| Gemini 3.5 Flash-Lite | 10 (0.07 / 0.00) | 0 (— / —) | 0 (— / —) | 0 (— / —) | 14 (0.95 / 0.86) |
| GPT-6 Luna | 4 (0.03 / 0.00) | 0 (— / —) | 0 (— / —) | 1 (0.79 / 0.00) | 19 (0.97 / 0.63) |

Abstract audit: all seven papers on which the four relevance decisions disagreed were read, plus one high-value proxy and one unanimous low control (n=9; one audited positive). The audit is deliberately disagreement-enriched. Gold labels and per-model Brier/P/R/FNR are in `raw/l1-audit.json` and `raw/l1-metrics.json`. For relevance, Gemini had 1/1 TP, 0 FP, 0 FN (Brier .007); JEV 1/1 TP, 4 FP (Brier .263); DeepSeek 1/1 TP, 7 FP (Brier .410); GPT-6 Luna 1/1 TP, 6 FP (Brier .562). These audit figures are not population estimates. All nine abstracts reported empirical evidence under the stated audit rule; empirical-evidence Brier was JEV .002, DeepSeek .013, Gemini .007, GPT-6 Luna .0001.

Pairwise agreement uses each Boolean probability thresholded by the host at 0.50, exact categorical agreement for topic, and an absolute difference ≤0.5 for the 0–4 implementation score. Each count is out of 24 when both outputs are valid.

| Judge pair | Relevant | Empirical | Topic | Escalate | Implementation score |
|---|---:|---:|---:|---:|---:|
| JEV vs DeepSeek Flash | 21/24 | 24/24 | 17/24 | 19/24 | 11/24 |
| JEV vs Gemini 3.5 Flash-Lite | 20/24 | 24/24 | 11/24 | 13/24 | 10/24 |
| JEV vs GPT-6 Luna | 22/24 | 24/24 | 13/24 | 16/24 | 11/24 |
| DeepSeek Flash vs Gemini 3.5 Flash-Lite | 17/24 | 24/24 | 10/24 | 18/24 | 12/24 |
| DeepSeek Flash vs GPT-6 Luna | 23/24 | 24/24 | 13/24 | 21/24 | 16/24 |
| Gemini 3.5 Flash-Lite vs GPT-6 Luna | 18/24 | 24/24 | 17/24 | 21/24 | 21/24 |


Arm latency and cost for the 24-paper routing pass (excluding setup pilots; full attempt detail is in raw/l1-metrics.json):

| Judge | Logical calls | Input / output tokens | Estimated cost | Median / p90 latency |
|---|---:|---:|---:|---:|
| JEV | 24 | 27,091 / 4,102 | $0.001138 | 344 / 503 ms |
| DeepSeek Flash | 24 | 21,731 / 1,441 | $0.002713 | 1,191 / 1,617 ms |
| Gemini Flash-Lite | 24 | 21,420 / 2,117 | $0.011719 | 23,815 / 25,153 ms |
| GPT-6 Luna | 24 | 23,764 / 1,581 | $0.003073 | 7,839 / 8,275 ms |

Observed output-shape/decision failures: the initial two-paper prompt pilot is excluded and retained at `raw/l1-prompt-pilot.json`; the exact-key correction pilot is `raw/l1-prompt-pilot-corrected.json`. In the measured 24-paper run all output schemas parsed and passed required-field/range checks. GPT-6 Luna returned Boolean/probability disagreements on relevance for 3/24 papers and escalation for 1/24; the host threshold uses the supplied probability. Topic and implementation-score disagreement remains material despite unanimous empirical-evidence Boolean decisions. The JEV 503/retry artifact pair for paper `2609.29808` is linked from `raw/l1-results.json`.

## Layer 2: PDF strategies
L2 is complete for all eight preselected long/figure/table-heavy papers. Every strategy used Gemini Flash-Lite. Strategy A was eight successful abstract+metadata calls, B eight successful whole-PDF native-document calls, C eight visual selective calls, and D eight page-labelled full-text reference calls. C made one round per paper; it requested no additional pages in any of the eight responses. Its `stop_reason` values were free-form natural-language sentences rather than the requested stop token, so the loop stopped because the model returned no page requests.

The reference D is an operational comparison target, not independent truth. The requested insight-recall comparison is operationalized as candidate-claim recall: fixed lexical content-word Jaccard against D claims (primary threshold 0.20; sensitivity at 0.15 and 0.25); it is not semantic evaluation. D’s 1.000 self-recall is tautological. Load-bearing pages are those named by D, and page recall measures whether the strategy saw those pages. L3 separately compares structured insight generation.

| Strategy | Input mechanism | Pages processed | Bytes processed/sent | Tokens in/out | Logical calls / attempts | Latency sum | Cost | Mean claim recall vs D (0.20) | Mean D load-bearing-page recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A. Abstract + metadata | Gemini Flash-Lite | 0 | 14,092 | 6,672 / 4,766 | 8 / 8 | 207.5s | $0.013917 | 0.554 | n/a |
| B. Full PDF inline to Gemini | Gemini Flash-Lite | 203 | 17,914,526 | 109,510 / 5,933 | 8 / 8 | 231.0s | $0.047685 | 0.631 | 1.000 |
| C. Selective PyMuPDF page images | Gemini Flash-Lite | 34 | 4,019,205 | 41,314 / 2,974 | 8 / 8 | 209.4s | $0.019829 | 0.212 | 0.309 |
| D. Full extracted text reference | Gemini Flash-Lite | 203 | 793,742 | 220,405 / 5,200 | 8 / 8 | 213.1s | $0.079121 | 1.000 | 1.000 |

Claim-recall threshold sensitivity (mean over eight papers):

| Strategy | Jaccard ≥0.15 | ≥0.20 | ≥0.25 |
|---|---:|---:|---:|
| A | 0.637 | 0.554 | 0.425 |
| B | 0.704 | 0.631 | 0.502 |
| C | 0.269 | 0.212 | 0.171 |
| D | 1.000 | 1.000 | 1.000 |

Selective-path detail and misses:

| arXiv id | PDF pages | C pages examined | C claim recall | D load-bearing-page recall | D load-bearing claims missed by C |
|---|---:|---|---:|---:|---:|
| 2609.29808 | 21 | 1, 2, 20, 21 | 0.000 | 0.333 | 1 |
| 2609.29095 | 23 | 1, 2, 16, 22, 23 | 0.200 | 0.250 | 3 |
| 2609.28614 | 33 | 1, 2, 32, 33 | 0.000 | 0.250 | 4 |
| 2609.30217 | 34 | 1, 2, 33, 34 | 0.000 | 0.200 | 3 |
| 2609.28585 | 22 | 1, 2, 21, 22 | 0.333 | 0.286 | 2 |
| 2609.28586 | 19 | 1, 2, 18, 19 | 0.500 | 0.400 | 1 |
| 2609.27263 | 17 | 1, 2, 14, 16, 17 | 0.667 | 0.250 | 1 |
| 2609.24122 | 34 | 1, 2, 33, 34 | 0.000 | 0.500 | 2 |

The selective path examined 34/203 paper pages (16.7%) and had mean evidence-page recall 0.309. It missed all four D claims on 2609.28614 at the primary lexical match threshold, including the 33/505 confirmed reward-hack cases and the 40.5% cumulative evasion result; see `raw/l2-metrics.json` and D/C call artifacts in `raw/responses/l2/`. On 2609.30217 it missed three D claims, including the reported 98% best-of-three evasion-attempt rate and 88% success rate. On 2609.29095 it missed three of five D claims, including the late-commit/unknown-in-flight limit on exactly-once guarantees. These are lexical miss flags against the Gemini D response, not a human adjudication.

B read all 203 pages from 17,914,526 PDF bytes and recovered 0.631 mean D-claim recall for $0.047686. D processed all 203 extracted pages (793,742 bytes, 220,405 input tokens) and cost $0.079122. Selective C cost $0.019829 and exposed only 34 rendered pages (4,019,205 PNG bytes), but its low page and claim recall rejects the tested stopping behavior as a reliable replacement at this page budget. A cost $0.013917 and claim recall was 0.554. Values and per-call usage are auditable in `raw/l2-metrics.json`, `raw/l2-results.json`, and `raw/responses/l2/{A,B,C,D}/`.

The three 2609.29095 strategy-B attempts made during the host degradation had null HTTP status and zero usage; they were retained as outage artifacts and excluded from the eight successful logical-call latency/token/cost measurements. A was reused from its valid saved HTTP-200 artifact. The clean recovery B call and C/D calls are in `raw/responses/l2/`.

## Layer 3: insight generation

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

## Layer 4: JEV post-generation

JEV evaluated the first insight from every eligible generated artifact: 47 candidates (23 full-reference, 24 selective; one full-reference Gemini generation had no output). All 47 returned valid typed boolean probabilities. These are bounded checks; JEV was not asked for open-ended novelty synthesis.

| Question | Host threshold | Mean probability | Positive decisions | Proxy comparison |
|---|---:|---:|---:|---|
| Supported by supplied evidence | 0.75 | 0.882 | 43/47 | Against candidate-specific exact quote containment: TP 24, FP 19, TN 2, FN 2; Brier 0.347, agreement 0.553. This is a string-match proxy, not semantic entailment. |
| Agenda relevant | 0.60 | 0.960 | 47/47 | Against high-value stratum label: TP 41, FP 6, TN 0, FN 0; Brier 0.114, agreement 0.872. Six proxy-negative candidate outputs all passed. |
| Duplicates supplied existing insight | 0.75 | 0.172 | 3/47 | No gold duplicate labels; no Brier or agreement estimate. |
| Has actionable implication | 0.60 | 0.897 | 47/47 | Against blind judge score ≥3: TP 31, FP 5, TN 0, FN 0 among 36 labeled; Brier 0.120 and agreement 0.861. Eleven candidates lacked a usable blind actionability score. |
| Escalate for deeper review | 0.65 | 0.476 | 5/47 | No gold escalation labels; no Brier or agreement estimate. |

On the eight full-reference GPT-6 Luna candidates used by matrix row 7, seven had exact quote containment; JEV marked six supported at P≥0.75 (TP 6, FP 0, TN 1, FN 1; Brier 0.047). This is promising only against a narrow lexical proxy on n=8. Across all candidates, raising support threshold to 0.95 improved exact-quote precision to 0.80 but reduced recall to 0.154; there is no balanced automatic acceptance threshold in this sample. Aggregate outputs, candidate-specific source checks, and probability records are in raw/l4-metrics.json and raw/l4-results.json. The 47 calls cost $0.004499, used 107,111 input and 5,358 output tokens, and totaled 17.8 seconds of request latency (median 337 ms).

## Generator x evaluator matrix

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

## Failure cases

All attempts with errors or malformed model output are preserved and treated as data, not silently discarded from cost totals.

- Host interruption/outage window: three 2609.29095 strategy-B attempts returned null HTTP status and zero usage. The clean resume call succeeded; prior valid A output was reused. See raw/responses/l2/B/l2-2609.29095-B-r1-a1.json, a2.json, a3.json and the resume artifact linked by raw/l2-results.json.
- Gemini model selection: the first catalogue selector chose the TTS sibling gemini-3.8-flash-lite-tts; three smoke attempts have unrecoverable status/latency and zero recorded usage. The selector was corrected to stable text model gemini-3.5-flash-lite, after which text and PDF probes passed. Raw selection/provenance is in raw/gemini-model-resolution.json and raw/capability-probes.json.
- L1: one JEV request returned 503 then succeeded on retry. The two-paper shared-prompt pilot was excluded because exact keys were omitted; the corrected prompt pilot and all 24 measured schemas are recorded under raw/l1-prompt-pilot*.json and raw/l1-results.json.
- L2 selective stop contract: all eight Gemini responses used free prose in stop_reason and requested no further pages. The harness made one selective round per paper; the resulting miss cases on 2609.28614, 2609.30217, and 2609.29095 are described in Layer 2 and raw/l2-metrics.json. This is a strategy failure, not a successful bounded iterative loop.
- L3 initial output format: one DeepSeek format pilot used an incompatible insight shape and was excluded; later DeepSeek JSON mode returned HTTP 400 until the prompt included lowercase json. The 2609.29808 DeepSeek and GPT outputs were truncated at earlier output limits and retried with shorter prompts/higher caps. Those responses remain in raw/responses/l3/ and links are indexed by raw/l3-results.json.
- L3 schema and judge failures: DeepSeek/Gemini emitted noncanonical shapes and usually failed normalized required-field checks. One full-reference Gemini generation had no parseable output. Of 36 judge calls, seven returned no usable dimension scores (including one null Gemini response); six other responses had incomplete/combined scores. Preference text was retained but not scored. See raw/l3-format-findings.json, raw/l3-metrics.json, and raw/responses/l3/judges/.
- L2 selective important misses: C missed all four D claims on 2609.28614, including 33/505 confirmed reward-hack cases and the 40.5% cumulative evasion result; three of D’s claims on 2609.30217, including 98% best-of-three evasion-attempt and 88% success results; and three of five on 2609.29095, including the late-commit/unknown-in-flight limitation on exactly-once guarantees. These are misses against the operational Gemini D reference and lexical match rule, not independent human adjudications.
- L4: all 47 calls returned typed answers; no transport failures. However, 19 of 43 candidates with JEV support P≥0.75 did not pass the candidate-specific exact quote-containment proxy, underscoring the semantic-verification gap.

## Cost and latency

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

## Recommended role-based routing and thresholds

Thresholds below are host policy candidates derived after observing this purposive sample; they are not model-selected and are not validated population guarantees.

- Paper triage: JEV at P(relevant) ≥0.70 is the cheapest measured candidate escalation threshold. It yielded proxy precision 0.857 and recall 1.000 (12/12 high-value labels) at about $0.000047 per call. Gemini at 0.70 had the same measured precision/recall and better Brier (0.075 vs JEV 0.156), but cost about ten times more and had much higher median latency. Use 0.50–0.69 as a review band; do not automatically discard lower scores in production on the strength of n=24. The abstract audit had one positive and was disagreement-enriched.
- Selective reading: no tested stop/request threshold is acceptable. C requested no additional page on all eight papers and saw only 0.309 of D load-bearing pages. Until a new evaluation shows ≥0.90 page and claim recall and a valid page-request/stop contract, use selective output only as an aid to navigation and fall back to a full-document reference whenever evidence completeness matters.
- Deep synthesis: GPT-6 Luna at reasoning_effort none is the strongest measured structured generator and the cheapest full-reference generator arm. Keep deterministic schema and citation gates; a failed gate should trigger rework or review, not durable storage. DeepSeek selective generation cost less than its full-reference run but still cost more than GPT-6 Luna on both input paths; its selective arm had 1/8 normalized schema passes.
- Post-generation verification: JEV at P(supported) ≥0.75 is not an automatic acceptance threshold: 19/43 predicted-supported candidates failed exact quote containment. At 0.95, proxy precision rose to 0.80 but recall fell to 0.154. Require resolvable evidence and independent review for storage decisions; JEV can prioritize checks. Duplicate and escalation thresholds have no gold labels in this run.

Quality-loss tolerance and MVP decision: the post-hoc limit is ≤0.5/4 loss on faithfulness/evidence support, ≥0.90 evidence-page and D-claim recall, and ≥0.95 normalized schema/page-reference validity. Only the full-reference D + GPT-6 Luna comparison cell met the structural/quality gates; no cheaper selective pipeline met the evidence-recall gate. **MVP go/no-go relative to delegation-queue#78: NO-GO for claiming selective PDF reading can replace full-document evidence review; conditional evaluation-only use is not a production-readiness result.**

## Implications for #78

Factual findings for the feasibility spec in delegation-queue#78:

- The eight-paper selective strategy failed to request pages and recovered 0.309 mean D load-bearing-page recall; an assumed selective-reading cost/quality advantage is not supported by this run.
- Whole-PDF inline Gemini recovered 0.631 lexical claim recall at $0.047686, while selective C recovered 0.212 at $0.019829 and reference D cost $0.079122. These are model-derived comparisons, not human gold.
- JEV was fast and inexpensive for typed triage, but its 0.70 proxy threshold was tested on 24 purposively balanced papers. Its post-generation support answers were overconfident against exact quote matching across mixed candidates.
- GPT-6 Luna was the only generator to emit the requested canonical schema on all eight outputs per path and passed normalized structural checks 8/8. DeepSeek and Gemini variants needed normalization and most normalized cells still failed checks.
- The measured best full-reference generator was GPT-6 Luna with reasoning off. The four-paper medium-effort sensitivity arm showed no qualitative score improvement in three scoreable pairs and mixed citation-string deltas.
- Blind rubric data have only 4–13 candidate ratings per dimension and seven of 36 judge calls with no usable scores; this evidence should narrow confidence claims and motivate a judge-format reliability check.
- L4 support verification achieved only 0.553 threshold agreement with a narrow exact-quote proxy over all candidates. Semantic evidence verification remains unestablished.

These are empirical deltas and uncertainty limits for #78 to incorporate; they do not specify a parallel architecture.

## Next implementation issues

1. Specify and test an exact selective-reader page-request/stop contract, including an explicit continuation condition; rerun the missed-evidence subset with a bounded page budget and record load-bearing-page recall.
2. Adjudicate a larger stratified routing set with blinded abstract readers, including real high-value false negatives and natural prevalence; estimate precision, recall, calibration, and escalation trade-offs.
3. Add strict output-shape conformance checks for DeepSeek and Gemini to the benchmark harness; measure provider-native constrained outputs separately from deterministic normalization.
4. Build a human-adjudicated evidence-support set linking each claim to page-level entailment, so quote containment can be separated from semantic support and L4 thresholds can be calibrated.
5. Re-run cross-vendor judge scoring with a hard response schema and balanced pair coverage; require every rubric dimension for both candidates and retain judge refusal/format failures as explicit outcomes.
6. Expand sensitivity testing only after the primary generator and page-source comparison is preregistered; current n=4 medium-effort evidence is inconclusive.
7. Refresh provider model IDs and rate cards on the next evaluation date; Gemini request IDs echoed only the stable catalogue name while its catalogue entry supplied the dated version.
