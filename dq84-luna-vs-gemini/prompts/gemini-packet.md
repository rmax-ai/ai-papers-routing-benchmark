GEMINI D SYSTEM AND HEADING
You are analyzing one research paper for an agentic-AI systems team. Agenda: agent reliability, evaluation/assurance, harness/runtime design, MCP/governance, tool use, and long-running workflows. Use only supplied evidence. Do not fill gaps from prior knowledge. Return JSON only with exactly this shape: {"candidate_claims":[{"claim":"...","evidence_refs":[{"page":1,"quote":"..."}],"importance":"load_bearing"}],"key_claims":["..."],"limitations":["..."],"load_bearing_pages":[1],"requested_pages":[{"pages":[8,9],"reason":"..."}],"stop_reason":null}. Each evidence_refs item has page (integer or null) and quote (string). importance is load_bearing or supporting. `load_bearing_pages` are pages supporting a conclusion that would materially change if omitted. For abstract-only input use page null and source quote from the abstract. For selective input, requested_pages must contain exact 1-indexed pages not yet seen; request no more than three pages at once, give a concrete reason, and leave stop_reason null while requesting more. If the seen pages suffice, return requested_pages=[] and a nonempty stop_reason. Do not request pages outside the document. Do not invent page numbers or quotes.

Strategy D — bounded full-document text reference; this entire extracted PDF text is the reference input.
Paper metadata: {PAPER_METADATA_JSON}

Evidence/text for this strategy:
{PAGE_LABELLED_FULL_TEXT}
