SYSTEM
Create a durable evidence-grounded insight artifact for this agenda: agent reliability, evaluation/assurance, harness/runtime, MCP/governance, tool use, long-running workflows. Use only supplied paper text and agenda context. Distinguish measured results from proposals; do not infer causality or novelty. Every key claim, evidence item, and insight must cite an in-range page and a short verbatim quote. If support is missing, state it as a limitation and keep confidence low. Produce at most 3 insights, 3 key claims, 3 evidence items, 4 limitations; one short sentence per field, ≤2 citations per insight, and ≤25 quoted words per citation. Target ≤1500 output tokens. Return JSON only. The required top level must contain exactly `paper`, `insights`, `connections`, and `followups`; paper must contain contribution/key_claims/evidence/limitations; each insight must contain insight/why_it_matters/evidence_refs/confidence/novelty/related_rmax_topics/possible_action. Citation objects have page/section/quote. Do not substitute fields such as title, id, agenda_fit, or measured_or_proposed; use exactly the field names shown. Empty arrays are valid.

USER CONTENT TEMPLATE
Follow the artifact contract exactly.

{METADATA_JSON}
SOURCE METHOD: strategy-D complete page-labelled PyMuPDF text extraction
SOURCE:
{SOURCE_PAYLOAD}
