#!/usr/bin/env python3
"""Resumable structured insight generation benchmark."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from provider import DEEPSEEK_URL, GEMINI_BASE, MODELS, OPENAI_URL, assert_budget, chat_headers, gemini_headers, request_json, rolling_totals, write_json
from run_l1 import extract_json

ROOT = Path.cwd()

REF = {"type": "object", "additionalProperties": False,
       "properties": {"page": {"type": "integer", "minimum": 1},
                      "section": {"type": "string"}, "quote": {"type": "string"}},
       "required": ["page", "section", "quote"]}
REFS = {"type": "array", "items": REF}
OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "paper": {"type": "object", "additionalProperties": False, "properties": {
            "contribution": {"type": "string"},
            "key_claims": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {"claim": {"type": "string"}, "evidence_refs": REFS}, "required": ["claim", "evidence_refs"]}},
            "evidence": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {"claim": {"type": "string"}, "evidence_refs": REFS}, "required": ["claim", "evidence_refs"]}},
            "limitations": {"type": "array", "items": {"type": "string"}},
        }, "required": ["contribution", "key_claims", "evidence", "limitations"]},
        "insights": {"type": "array", "items": {"type": "object", "additionalProperties": False, "properties": {
            "insight": {"type": "string"}, "why_it_matters": {"type": "string"}, "evidence_refs": REFS,
            "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "novelty": {"type": "string"},
            "related_rmax_topics": {"type": "array", "items": {"type": "string"}}, "possible_action": {"type": "string"},
        }, "required": ["insight", "why_it_matters", "evidence_refs", "confidence", "novelty", "related_rmax_topics", "possible_action"]}},
        "connections": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "properties": {"prior_work_or_existing_rmax_insight": {"type": "string"}, "relationship": {"type": "string", "enum": ["supports", "contradicts", "extends", "reframes"]}},
            "required": ["prior_work_or_existing_rmax_insight", "relationship"]}},
        "followups": {"type": "object", "additionalProperties": False, "properties": {
            "experiments": {"type": "array", "items": {"type": "string"}},
            "implementation_ideas": {"type": "array", "items": {"type": "string"}},
            "research_questions": {"type": "array", "items": {"type": "string"}},
        }, "required": ["experiments", "implementation_ideas", "research_questions"]},
    }, "required": ["paper", "insights", "connections", "followups"],
}
SYSTEM = """Create a durable evidence-grounded insight artifact for this agenda: agent reliability, evaluation/assurance, harness/runtime, MCP/governance, tool use, long-running workflows. Use only supplied paper text and agenda context. Distinguish measured results from proposals; do not infer causality or novelty. Every key claim, evidence item, and insight must cite an in-range page and a short verbatim quote. If support is missing, state it as a limitation and keep confidence low. Produce at most 3 insights, 3 key claims, 3 evidence items, 4 limitations; one short sentence per field, ≤2 citations per insight, and ≤25 quoted words per citation. Target ≤1500 output tokens. Return JSON only. The required top level must contain exactly `paper`, `insights`, `connections`, and `followups`; paper must contain contribution/key_claims/evidence/limitations; each insight must contain insight/why_it_matters/evidence_refs/confidence/novelty/related_rmax_topics/possible_action. Citation objects have page/section/quote. Do not substitute fields such as title, id, agenda_fit, or measured_or_proposed; use exactly the field names shown. Empty arrays are valid."""
DIMENSIONS = ["faithfulness", "evidence_support", "insight_depth", "novelty_identification",
              "systems_relevance", "actionability", "compression_information_density",
              "uncertainty_calibration", "durable_memory_precision_proxy"]
JUDGE_SCHEMA: dict[str, Any] = {"type": "object", "additionalProperties": False, "properties": {
    "scores": {"type": "array", "items": {"type": "object", "additionalProperties": False,
        "properties": {"blind_label": {"type": "string", "enum": ["A", "B"]},
            **{d: {"type": "integer", "minimum": 0, "maximum": 4} for d in DIMENSIONS},
            "brief_reason": {"type": "string"}},
        "required": ["blind_label", *DIMENSIONS, "brief_reason"]}}}, "required": ["scores"]}
JUDGE_SYSTEM = """You are blind to generator identity; do not guess it. Score each supplied artifact against cited source excerpts and the agenda, independently from 0 (poor/unsupported) to 4 (strong). Faithfulness checks source agreement; evidence support checks citation support; depth checks synthesis beyond summary; novelty checks careful identification rather than unsupported novelty claims; systems relevance and actionability check agenda utility; compression rewards useful information per word; uncertainty calibration checks confidence against evidence; durable-memory precision asks whether this deserves storage in six months. Do not reward verbosity. Return only schema-compliant JSON."""


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


def response_text(provider: str, payload: dict | None) -> str:
    if not payload:
        return ""
    if provider in ("openai", "deepseek"):
        return str((((payload.get("choices") or [{}])[0].get("message") or {}).get("content")) or "")
    candidates = payload.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    return "".join(str(p.get("text") or "") for p in parts if isinstance(p, dict))


def canonicalize(raw: dict) -> tuple[dict, dict]:
    """Deterministically map valid-JSON variants; record every lossy/default mapping."""
    required_insight = {"insight", "why_it_matters", "evidence_refs", "confidence", "novelty", "related_rmax_topics", "possible_action"}
    paper = raw.get("paper") if isinstance(raw.get("paper"), dict) else {}
    strict_shape = (all(k in raw for k in ("paper", "insights", "connections", "followups"))
        and all(k in paper for k in ("contribution", "key_claims", "evidence", "limitations"))
        and isinstance(paper.get("key_claims"), list) and isinstance(paper.get("evidence"), list)
        and isinstance(raw.get("insights"), list)
        and all(isinstance(x, dict) and required_insight.issubset(x) and isinstance(x.get("confidence"), (int, float)) and isinstance(x.get("evidence_refs"), list) for x in raw.get("insights", []))
        and isinstance(raw.get("connections"), list) and isinstance(raw.get("followups"), dict))
    if strict_shape:
        return raw, {"used": False, "reason": "model returned requested schema field and type structure"}

    def refs_for(value: Any, hint: str = "") -> list[dict]:
        refs = value if isinstance(value, list) else []
        normalized_refs = []
        for ref in refs:
            if not isinstance(ref, dict):
                continue
            page = ref.get("page", ref.get("page_number"))
            try:
                page = int(page)
            except (TypeError, ValueError):
                continue
            quote = str(ref.get("quote") or ref.get("excerpt") or ref.get("citation") or "")
            normalized_refs.append({"page": page, "section": str(ref.get("section") or ""), "quote": quote})
        if normalized_refs:
            return normalized_refs
        # Some JSON-mode responses embed [PAGE n], "quote" citations in claim strings.
        match = re.search(r"\[PAGE\s*(\d+)\][^\"“]{0,100}[\"“]([^\"”]{8,300})[\"”]", hint, re.I)
        if match:
            return [{"page": int(match.group(1)), "section": "", "quote": match.group(2)}]
        return []

    def claim_items(items: Any) -> list[dict]:
        result = []
        for value in items if isinstance(items, list) else []:
            if isinstance(value, str):
                result.append({"claim": value, "evidence_refs": refs_for([], value)})
            elif isinstance(value, dict):
                claim = str(value.get("claim") or value.get("text") or value.get("statement") or value.get("title") or "")
                result.append({"claim": claim, "evidence_refs": refs_for(value.get("evidence_refs") or value.get("citations"), claim)})
        return result

    source_insights = raw.get("insights") if isinstance(raw.get("insights"), list) else []
    insights, inferred_evidence = [], []
    neutral_count = verbal_count = dropped_connection_count = 0
    for item in source_insights:
        if not isinstance(item, dict):
            continue
        insight_text = str(item.get("insight") or item.get("claim") or item.get("title") or "")
        refs = refs_for(item.get("evidence_refs") or item.get("citations"), insight_text)
        if not refs:
            page = item.get("page")
            quote = item.get("quote")
            if isinstance(page, int) and quote:
                refs = [{"page": page, "section": str(item.get("section") or ""), "quote": str(quote)}]
        confidence = item.get("confidence")
        if isinstance(confidence, str):
            verbal = {"very low": .1, "low": .25, "medium": .5, "moderate": .5, "high": .75, "very high": .9}
            mapped = verbal.get(confidence.lower())
            if mapped is not None:
                confidence, verbal_count = mapped, verbal_count + 1
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            confidence, neutral_count = .5, neutral_count + 1
        topics = item.get("related_rmax_topics") or item.get("related_topics") or item.get("agenda_fit") or []
        if isinstance(topics, str):
            topics = [topics]
        insight = {"insight": insight_text,
            "why_it_matters": str(item.get("why_it_matters") or item.get("why_matters") or ""),
            "evidence_refs": refs, "confidence": float(confidence),
            "novelty": str(item.get("novelty") or ""),
            "related_rmax_topics": [str(t) for t in topics if isinstance(t, (str, int, float))],
            "possible_action": str(item.get("possible_action") or "")}
        insights.append(insight)
        if refs:
            inferred_evidence.append({"claim": insight_text, "evidence_refs": refs})

    raw_paper = raw.get("paper") if isinstance(raw.get("paper"), dict) else {}
    key_claims = claim_items(raw_paper.get("key_claims", raw.get("key_claims", [])))
    old_evidence = raw_paper.get("evidence", raw.get("evidence", []))
    evidence = claim_items(old_evidence) if isinstance(old_evidence, list) else []
    if not evidence:
        evidence = inferred_evidence
    notes = raw.get("notes", raw_paper.get("limitations", []))
    limitations = [str(n) for n in notes] if isinstance(notes, list) else ([str(notes)] if notes else [])
    for item in source_insights:
        if isinstance(item, dict) and isinstance(item.get("limitations"), list):
            limitations.extend(str(v) for v in item["limitations"])
    connections = []
    for item in raw.get("connections", []) if isinstance(raw.get("connections"), list) else []:
        if isinstance(item, dict) and item.get("relationship") in {"supports", "contradicts", "extends", "reframes"}:
            connections.append({"prior_work_or_existing_rmax_insight": str(item.get("prior_work_or_existing_rmax_insight") or item.get("prior_work") or ""), "relationship": item["relationship"]})
        elif isinstance(item, dict):
            dropped_connection_count += 1
    old_followups = raw.get("followups") if isinstance(raw.get("followups"), dict) else {}
    def followup_values(*keys: str) -> list[str]:
        out = []
        for key in keys:
            values = old_followups.get(key, [])
            for value in values if isinstance(values, list) else []:
                if isinstance(value, str):
                    out.append(value)
                elif isinstance(value, dict):
                    text = value.get("question") or value.get("idea") or value.get("experiment") or value.get("text")
                    if text:
                        out.append(str(text))
        return out
    result = {"paper": {"contribution": str(raw_paper.get("contribution") or ""),
        "key_claims": key_claims, "evidence": evidence, "limitations": limitations},
        "insights": insights, "connections": connections,
        "followups": {"experiments": followup_values("experiments"),
            "implementation_ideas": followup_values("implementation_ideas", "actions"),
            "research_questions": followup_values("research_questions", "questions")}}
    return result, {"used": True, "reason": "valid JSON fields deterministically mapped to the canonical schema; missing text fields use empty values and unsupported connection types are dropped",
        "confidence_neutral_imputed_count": neutral_count, "confidence_verbal_mapping_count": verbal_count,
        "dropped_nonconforming_connections": dropped_connection_count,
        "claim_string_citations_parsed": sum(bool(item.get("evidence_refs")) for item in key_claims if not raw_paper.get("key_claims"))}


def paper_sources(paper: dict, l2: dict, text_map: dict, path: str) -> tuple[str, dict[int, str], str]:
    pid = paper["arxiv_id"]
    all_pages = {i + 1: text for i, text in enumerate(text_map[pid])}
    context_path = Path.home() / "src/rmax-ai/knowledge-graph/topics/ai-papers.md"
    agenda = context_path.read_text(encoding="utf-8")[:12000] if context_path.exists() else ""
    metadata = {"paper_id": pid, "title": paper.get("arxiv_title_differs_from_local") or paper["title"],
                "abstract": paper.get("abstract", ""), "rmax_topic_context": agenda}
    if path == "full_reference":
        pages = all_pages
        method = "strategy-D complete page-labelled PyMuPDF text extraction"
        source = "\n\n".join(f"[PAGE {n}]\n{t}" for n, t in pages.items())
    else:
        c = l2[pid]["strategies"]["C"]
        pages = {n: all_pages[n] for n in c.get("pages_examined", []) if n in all_pages}
        method = "strategy-C visually examined page text plus Gemini candidate-claim packet"
        source = json.dumps({"examined_pages": sorted(pages), "visual_reader_claims": c.get("candidate_claims", [])}, ensure_ascii=False) + "\n" + "\n\n".join(f"[PAGE {n}]\n{t}" for n, t in pages.items())
    return json.dumps(metadata, ensure_ascii=False) + f"\nSOURCE METHOD: {method}\nSOURCE:\n" + source, pages, method


def gen_request(provider: str, model_id: str, user_text: str) -> tuple[str, dict, dict, dict]:
    if provider == "deepseek":
        settings = {"reasoning_effort": "none", "structured_output": "json_object", "max_tokens": 4500, "prompt_revision": "concise-v4"}
        body = {"model": model_id, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Return a json object only and follow the artifact contract exactly.\n\n" + user_text}], "reasoning_effort": "none", "max_tokens": 4500, "response_format": {"type": "json_object"}}
        return DEEPSEEK_URL, settings, body, chat_headers(provider)
    if provider == "openai":
        settings = {"reasoning_effort": "none", "structured_output": "json_schema strict", "max_completion_tokens": 3600, "prompt_revision": "concise-v4"}
        body = {"model": model_id, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "Follow the artifact contract exactly.\n\n" + user_text}], "reasoning_effort": "none", "max_completion_tokens": 3600, "response_format": {"type": "json_schema", "json_schema": {"name": "paper_insight", "strict": True, "schema": OUTPUT_SCHEMA}}}
        return OPENAI_URL, settings, body, chat_headers(provider)
    thinking = json.loads((ROOT / "raw/capability-probes.json").read_text())["providers"]["gemini"]["primary_thinking_config"]
    settings = {"thinkingConfig": thinking, "responseMimeType": "application/json", "maxOutputTokens": 3000, "prompt_revision": "concise-v4"}
    body = {"systemInstruction": {"parts": [{"text": SYSTEM}]}, "contents": [{"role": "user", "parts": [{"text": "Follow the artifact contract exactly.\n\n" + user_text}]}], "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 3000, "thinkingConfig": thinking}}
    return f"{GEMINI_BASE}/models/{model_id}:generateContent", settings, body, gemini_headers()


def check_output(out: dict, pages: dict[int, str]) -> dict:
    refs = []
    groups = [("key_claims", (out.get("paper") or {}).get("key_claims", [])),
              ("evidence", (out.get("paper") or {}).get("evidence", [])),
              ("insights", out.get("insights", []))]
    for group, items in groups:
        for i, item in enumerate(items if isinstance(items, list) else []):
            raw_refs = item.get("evidence_refs", []) if isinstance(item, dict) else []
            for j, ref in enumerate(raw_refs if isinstance(raw_refs, list) else []):
                if not isinstance(ref, dict):
                    refs.append({"group": group, "item": i, "ref": j, "page": None,
                        "page_valid": False, "quote_nonempty": False,
                        "quote_contained_any_page": False, "quote_contained_cited_page": False})
                    continue
                page, quote = ref.get("page"), norm(str(ref.get("quote") or ""))
                refs.append({"group": group, "item": i, "ref": j, "page": page,
                    "page_valid": isinstance(page, int) and page in pages,
                    "quote_nonempty": bool(quote),
                    "quote_contained_any_page": bool(quote) and any(quote in norm(t) for t in pages.values()),
                    "quote_contained_cited_page": isinstance(page, int) and page in pages and bool(quote) and quote in norm(pages[page])})
    errors = []
    if not isinstance(out.get("paper"), dict):
        errors.append("paper must be an object")
    else:
        paper = out["paper"]
        for key in ("contribution", "limitations", "key_claims", "evidence"):
            if key not in paper:
                errors.append(f"paper.{key} missing")
        if not isinstance(paper.get("contribution"), str) or not isinstance(paper.get("limitations"), list):
            errors.append("paper contribution/limitations type mismatch")
        for key in ("key_claims", "evidence"):
            if not isinstance(paper.get(key), list):
                errors.append(f"paper.{key} must be an array")
            else:
                for i, item in enumerate(paper[key]):
                    if not isinstance(item, dict) or not isinstance(item.get("claim"), str) or not isinstance(item.get("evidence_refs"), list):
                        errors.append(f"paper.{key}[{i}] shape mismatch")
                    elif not item["evidence_refs"]:
                        errors.append(f"paper.{key}[{i}] has no evidence reference")
    if not isinstance(out.get("insights"), list):
        errors.append("insights must be an array")
    else:
        required = ("insight", "why_it_matters", "evidence_refs", "confidence", "novelty", "related_rmax_topics", "possible_action")
        for i, item in enumerate(out["insights"]):
            if not isinstance(item, dict) or any(k not in item for k in required):
                errors.append(f"insights[{i}] missing required field")
            elif not isinstance(item["confidence"], (int, float)) or not 0 <= item["confidence"] <= 1 or not isinstance(item["evidence_refs"], list):
                errors.append(f"insights[{i}] type/range mismatch")
            elif not item["evidence_refs"] or not isinstance(item["related_rmax_topics"], list):
                errors.append(f"insights[{i}] has no evidence reference or topic array")
    if not isinstance(out.get("connections"), list) or not isinstance(out.get("followups"), dict):
        errors.append("connections/followups shape mismatch")
    else:
        for i, connection in enumerate(out["connections"]):
            if not isinstance(connection, dict) or not isinstance(connection.get("prior_work_or_existing_rmax_insight"), str) or connection.get("relationship") not in {"supports", "contradicts", "extends", "reframes"}:
                errors.append(f"connections[{i}] shape mismatch")
        for key in ("experiments", "implementation_ideas", "research_questions"):
            if not isinstance(out["followups"].get(key), list) or any(not isinstance(value, str) for value in out["followups"].get(key, [])):
                errors.append(f"followups.{key} must be an array of strings")
    for ref in refs:
        if not ref["page_valid"] or not ref["quote_nonempty"]:
            errors.append(f"invalid citation at {ref['group']}[{ref['item']}].evidence_refs[{ref['ref']}]")
    return {"schema_shape_pass": not errors,
        "validation_errors": errors,
        "insight_count": len(out.get("insights", [])) if isinstance(out.get("insights"), list) else 0,
        "evidence_ref_count": len(refs), "evidence_refs": refs,
        "all_cited_pages_valid": all(r["page_valid"] for r in refs),
        "quote_containment_any_page_rate": sum(r["quote_contained_any_page"] for r in refs) / len(refs) if refs else None,
        "quote_containment_cited_page_rate": sum(r["quote_contained_cited_page"] for r in refs) / len(refs) if refs else None}


def generate(paper: dict, path: str, provider: str, model_id: str,
             user_text: str, pages: dict[int, str], effort: str = "none") -> dict:
    endpoint, settings, body, headers = gen_request(provider, model_id, user_text)
    if provider == "openai" and effort != "none":
        body["reasoning_effort"] = effort
        settings["reasoning_effort"] = effort
    input_blob = json.dumps(body, ensure_ascii=False, sort_keys=True)
    estimate = len(input_blob.encode()) / 3 * {"deepseek": .30, "gemini": .30, "openai": .10}[provider] / 1_000_000 + .015
    assert_budget(max(.03, estimate))
    call_id = f"l3-{paper['arxiv_id']}-{path}-{provider}"
    payload, history = request_json(provider=provider, call_id=call_id,
        arm_id=f"l3-{path}-{provider}", model_id=model_id, endpoint=endpoint,
        settings=settings, body=body, headers=headers, timeout=300,
        out_dir=f"l3/{path}/{provider}")
    result = {"paper_id": paper["arxiv_id"], "input_path": path, "provider": provider,
        "model_id_sent": model_id, "call_artifacts": [h["artifact"] for h in history],
        "reasoning_effort": effort,
        "prompt_revision": "concise-v4",
        "http_status": history[-1]["http_status"] if history else None,
        "latency_ms": sum(h["latency_ms"] for h in history),
        "input_sha256": hashlib.sha256(input_blob.encode()).hexdigest(),
        "input_chars": len(user_text), "input_bytes": len(user_text.encode()),
        "input_pages": sorted(pages), "usage": history[-1]["usage"] if history else None,
        "output": None, "parse_error": None}
    if payload:
        try:
            raw_output = extract_json(response_text(provider, payload))
            result["output"], result["host_normalization"] = canonicalize(raw_output)
            result["model_emitted_keys"] = list(raw_output.keys())
            result["model_emitted_canonical_shape"] = not result["host_normalization"]["used"]
            result["deterministic_checks"] = check_output(result["output"], pages)
            result["deterministic_checks"]["model_emitted_canonical_shape"] = result["model_emitted_canonical_shape"]
        except (ValueError, json.JSONDecodeError) as exc:
            result["parse_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    else:
        result["provider_error"] = json.loads((ROOT / history[-1]["artifact"]).read_text()).get("error") if history else "no response"
    return result


def cited_source(candidate: dict, page_text: dict[int, str]) -> list[dict]:
    refs = []
    obj = candidate.get("output") or {}
    groups = [(obj.get("paper") or {}).get("key_claims", []), (obj.get("paper") or {}).get("evidence", []), obj.get("insights", [])]
    for items in groups:
        for item in items if isinstance(items, list) else []:
            for ref in item.get("evidence_refs", []) if isinstance(item, dict) else []:
                n, quote = ref.get("page"), str(ref.get("quote") or "")
                source, match = page_text.get(n, "") if isinstance(n, int) else "", norm(quote)
                excerpt = source[:1200]
                pos = norm(source).find(match) if match else -1
                if pos >= 0:
                    excerpt = source[max(0, pos - 300):pos + len(quote) + 400]
                refs.append({"page": n, "quote": quote, "source_excerpt": excerpt})
    unique, seen = [], set()
    for ref in refs:
        key = (ref["page"], ref["quote"])
        if key not in seen:
            unique.append(ref)
            seen.add(key)
    return unique[:16]


def judge(provider: str, model_id: str, question: str, call_id: str) -> dict:
    if provider == "openai":
        endpoint = OPENAI_URL
        settings = {"reasoning_effort": "none", "structured_output": "json_schema strict", "max_completion_tokens": 1300, "blind": True}
        body = {"model": model_id, "messages": [{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": question}], "reasoning_effort": "none", "max_completion_tokens": 1300, "response_format": {"type": "json_schema", "json_schema": {"name": "blind_scores", "strict": True, "schema": JUDGE_SCHEMA}}}
        headers = chat_headers(provider)
    else:
        thinking = json.loads((ROOT / "raw/capability-probes.json").read_text())["providers"]["gemini"]["primary_thinking_config"]
        endpoint = f"{GEMINI_BASE}/models/{model_id}:generateContent"
        settings = {"thinkingConfig": thinking, "responseMimeType": "application/json", "maxOutputTokens": 1500, "blind": True}
        body = {"systemInstruction": {"parts": [{"text": JUDGE_SYSTEM}]}, "contents": [{"role": "user", "parts": [{"text": question}]}], "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 1500, "thinkingConfig": thinking}}
        headers = gemini_headers()
    assert_budget(len(json.dumps(body, ensure_ascii=False).encode()) / 3 * .30 / 1_000_000 + .01)
    payload, history = request_json(provider=provider, call_id=call_id,
        arm_id=f"l3-blind-judge-{provider}", model_id=model_id, endpoint=endpoint,
        settings=settings, body=body, headers=headers, timeout=240,
        out_dir=f"l3/judges/{provider}")
    result = {"judge_provider": provider, "judge_model_id": model_id,
        "call_artifacts": [h["artifact"] for h in history],
        "http_status": history[-1]["http_status"] if history else None,
        "latency_ms": sum(h["latency_ms"] for h in history), "output": None, "parse_error": None}
    if payload:
        try:
            result["output"] = extract_json(response_text(provider, payload))
        except (ValueError, json.JSONDecodeError) as exc:
            result["parse_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    else:
        result["provider_error"] = json.loads((ROOT / history[-1]["artifact"]).read_text()).get("error") if history else "no response"
    return result


def save(results: dict, target: int, status: str = "running") -> None:
    done = sum(all(k in row.get("generations", {}) for k in ("full_reference", "selective")) for row in results.values())
    write_json(ROOT / "raw/l3-results.json", {"schema_version": 1, "status": status,
        "papers_completed": done, "papers_target": target, "results": results})


def main() -> None:
    sample = json.loads((ROOT / "raw/sampling.json").read_text())
    l2 = json.loads((ROOT / "raw/l2-results.json").read_text())["results"]
    if not all(pid in l2 and all(k in l2[pid].get("strategies", {}) for k in ("C", "D")) for pid in sample["l3_paper_ids"]):
        raise SystemExit("L2 C/D strategies incomplete for L3 sample")
    l1 = json.loads((ROOT / "raw/l1-results.json").read_text())
    l1map = {r["paper_id"]: r for r in l1["results"]}
    paper_map = {p["arxiv_id"]: p for p in sample["papers"]}
    text_map = json.loads((ROOT / "scratch/pdf-text.json").read_text())
    gemini_id = json.loads((ROOT / "raw/capability-probes.json").read_text())["providers"]["gemini"]["model_id_sent"]
    model_ids = {"deepseek": MODELS["deepseek"], "gemini": gemini_id, "openai": MODELS["openai"]}
    result_path = ROOT / "raw/l3-results.json"
    results = json.loads(result_path.read_text()).get("results", {}) if result_path.exists() else {}
    target = len(sample["l3_paper_ids"])
    save(results, target)

    # Deterministic host-owned route: JEV P(relevant) >= 0.50.
    routed = []
    probs = {}
    for pid in sample["l3_paper_ids"]:
        ans = l1map[pid]["judgments"]["jev"].get("answers", {}).get("relevant", {})
        probability = ans.get("probability") if isinstance(ans, dict) else None
        probs[pid] = probability
        if probability is not None and float(probability) >= .50:
            routed.append(pid)
    write_json(ROOT / "raw/l3-routing-policy.json", {"threshold": .50,
        "input": "L1 JEV relevant probability", "probabilities": probs,
        "eligible_ids": sample["l3_paper_ids"], "routed_ids": routed,
        "not_routed_ids": [pid for pid in sample["l3_paper_ids"] if pid not in routed]})

    # Full-reference arms cover matrix 1-3. Routed selective arms cover rows 4-6.
    for pid in sample["l3_paper_ids"]:
        row = results.setdefault(pid, {"paper_id": pid, "inputs": {}, "generations": {}, "judges": {}})
        row.setdefault("inputs", {})
        row.setdefault("generations", {})
        for path in ("full_reference", "selective"):
            if path == "selective" and pid not in routed:
                row["inputs"][path] = {"skipped_by_host_policy": True, "threshold": .50}
                row["generations"].setdefault(path, {})
                save(results, target)
                continue
            user_text, pages, method = paper_sources(paper_map[pid], l2, text_map, path)
            row["inputs"][path] = {"source_method": method, "pages": sorted(pages),
                "input_chars": len(user_text), "sha256": hashlib.sha256(user_text.encode()).hexdigest()}
            cells = row["generations"].setdefault(path, {})
            for provider in ("deepseek", "gemini", "openai"):
                prior = cells.get(provider)
                needs_format_retry = bool(prior and (prior.get("parse_error") or prior.get("provider_error")) and prior.get("prompt_revision") != "concise-v4")
                if provider not in cells or needs_format_retry:
                    cells[provider] = generate(paper_map[pid], path, provider,
                        model_ids[provider], user_text, pages)
                    if prior:
                        cells[provider]["superseded_invalid_response_artifacts"] = prior.get("call_artifacts", [])
                        cells[provider]["superseded_parse_error"] = prior.get("parse_error")
                        cells[provider]["superseded_provider_error"] = prior.get("provider_error")
                    save(results, target)

    # One medium-reasoning OpenAI sensitivity pass on four fixed papers.
    sensitivity_ids = sample["l3_paper_ids"][:3] + [sample["l3_paper_ids"][-1]]
    for pid in sensitivity_ids:
        row = results[pid]
        if "openai_medium" in row:
            continue
        user_text, pages, _ = paper_sources(paper_map[pid], l2, text_map, "full_reference")
        res = generate(paper_map[pid], "full_reference-openai-medium", "openai",
                       model_ids["openai"], user_text, pages, effort="medium")
        row["openai_medium"] = res
        save(results, target)

    # Blind cross-vendor judge: OpenAI scores DeepSeek+Gemini; Gemini scores GPT+DeepSeek.
    unblind = {}
    for pid in sample["l3_paper_ids"]:
        for path in ("full_reference", "selective"):
            cells = results[pid]["generations"].get(path, {})
            if path == "selective" and pid not in routed:
                continue
            fullpages = {i + 1: t for i, t in enumerate(text_map[pid])}
            if path == "selective":
                chosen = set(l2[pid]["strategies"]["C"].get("pages_examined", []))
                judge_pages = {n: t for n, t in fullpages.items() if n in chosen}
            else:
                judge_pages = fullpages
            for judge_provider, candidates in (("openai", ["deepseek", "gemini"]), ("gemini", ["openai", "deepseek"])):
                jkey = f"{path}/{judge_provider}"
                if jkey in results[pid].setdefault("judges", {}):
                    continue
                available = [m for m in candidates if isinstance(cells.get(m, {}).get("output"), dict)]
                if not available:
                    continue
                salt = hashlib.sha256(f"{pid}/{path}/{judge_provider}".encode()).digest()[0]
                labels = ["A", "B"] if salt % 2 == 0 else ["B", "A"]
                mapping = dict(zip(labels, available))
                unblind[f"{pid}/{path}/{judge_provider}"] = mapping
                payloads = []
                for label, model in mapping.items():
                    payloads.append({"blind_label": label, "artifact": cells[model]["output"],
                        "cited_source_excerpts": cited_source(cells[model], judge_pages)})
                question = json.dumps({"paper_id": pid, "agenda": "agent reliability, evaluation/assurance, harness/runtime, MCP/governance, tool use, long-running workflows", "judge_note": "Some candidate fields may have been deterministically normalized; neutral confidence placeholders are not generator-reported calibration. If confidence provenance is unavailable, score uncertainty calibration as 2 (unobservable), not as calibrated or miscalibrated.", "blind_candidates": payloads}, ensure_ascii=False)
                model = model_ids[judge_provider]
                scored = judge(judge_provider, model, question, f"l3-judge-{pid}-{path}-{judge_provider}")
                scored["blind_to_generator_identity"] = True
                scored["same_vendor_candidate_models"] = [m for m in available if m == judge_provider]
                scored["label_to_model_internal"] = mapping
                results[pid]["judges"][jkey] = scored
                save(results, target)
    # The bounded reasoning sensitivity arm is judged against primary GPT-Luna by Gemini.
    for pid in sensitivity_ids:
        primary = results[pid]["generations"]["full_reference"].get("openai", {})
        medium = results[pid].get("openai_medium", {})
        if not isinstance(primary.get("output"), dict) or not isinstance(medium.get("output"), dict):
            continue
        jkey = "full_reference/sensitivity_gemini"
        if jkey in results[pid].setdefault("judges", {}):
            continue
        page_text = {i + 1: t for i, t in enumerate(text_map[pid])}
        blind_candidates = [{"blind_label": "A", "artifact": primary["output"], "cited_source_excerpts": cited_source(primary, page_text)},
            {"blind_label": "B", "artifact": medium["output"], "cited_source_excerpts": cited_source(medium, page_text)}]
        question = json.dumps({"paper_id": pid, "agenda": "agent reliability, evaluation/assurance, harness/runtime, MCP/governance, tool use, long-running workflows", "judge_note": "Some candidate fields may have been deterministically normalized; neutral confidence placeholders are not generator-reported calibration. If confidence provenance is unavailable, score uncertainty calibration as 2 (unobservable), not as calibrated or miscalibrated.", "blind_candidates": blind_candidates}, ensure_ascii=False)
        scored = judge("gemini", model_ids["gemini"], question, f"l3-judge-{pid}-full_reference-sensitivity-gemini")
        scored["blind_to_reasoning_setting"] = True
        scored["label_to_model_internal"] = {"A": "openai_none", "B": "openai_medium"}
        scored["same_vendor_candidate_models"] = []
        results[pid]["judges"][jkey] = scored
        save(results, target)
    write_json(ROOT / "raw/l3-judge-map.json", {"mappings": unblind, "dimensions": DIMENSIONS,
        "design": "Labels are permuted deterministically per paper/path/judge; vendor judge receives no model identity. Cross-vendor wherever possible."})
    save(results, target, "complete")
    print(json.dumps({"papers": target, "routed_ids": routed,
        "sensitivity_ids": sensitivity_ids, "usage_and_spend": rolling_totals()}, indent=2))


if __name__ == "__main__":
    main()
