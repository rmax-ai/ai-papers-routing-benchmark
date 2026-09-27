#!/usr/bin/env python3
"""Compare abstract, full-PDF, selective visual, and full-text reference input."""

from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any

import pymupdf

from provider import GEMINI_BASE, MODELS, assert_budget, gemini_headers, request_json, write_json
from run_l1 import extract_json

ROOT = Path.cwd()
SYSTEM = """You are analyzing one research paper for an agentic-AI systems team. Agenda: agent reliability, evaluation/assurance, harness/runtime design, MCP/governance, tool use, and long-running workflows. Use only supplied evidence. Do not fill gaps from prior knowledge. Return JSON only with exactly this shape: {\"candidate_claims\":[{\"claim\":\"...\",\"evidence_refs\":[{\"page\":1,\"quote\":\"...\"}],\"importance\":\"load_bearing\"}],\"key_claims\":[\"...\"],\"limitations\":[\"...\"],\"load_bearing_pages\":[1],\"requested_pages\":[{\"pages\":[8,9],\"reason\":\"...\"}],\"stop_reason\":null}. Each evidence_refs item has page (integer or null) and quote (string). importance is load_bearing or supporting. `load_bearing_pages` are pages supporting a conclusion that would materially change if omitted. For abstract-only input use page null and source quote from the abstract. For selective input, requested_pages must contain exact 1-indexed pages not yet seen; request no more than three pages at once, give a concrete reason, and leave stop_reason null while requesting more. If the seen pages suffice, return requested_pages=[] and a nonempty stop_reason. Do not request pages outside the document. Do not invent page numbers or quotes."""


def add_meta(history: list[dict], metadata: dict) -> None:
    for call in history:
        path = ROOT / call["artifact"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload.update(metadata)
        write_json(path, payload)


def extract_gemini(payload: dict | None) -> str:
    if not payload:
        return ""
    candidates = payload.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    return "".join(str(part.get("text") or "") for part in parts)


def gemini_call(*, paper: dict, strategy: str, round_no: int, model_id: str,
                text: str, parts: list[dict] | None = None, pages: list[int] | None = None,
                timeout: int = 240, estimated_cost: float = 0.05,
                call_tag: str | None = None) -> dict:
    endpoint = f"{GEMINI_BASE}/models/{model_id}:generateContent"
    thinking = json.loads((ROOT / "raw" / "capability-probes.json").read_text(encoding="utf-8"))["providers"]["gemini"]["primary_thinking_config"]
    all_parts = [{"text": text}]
    if parts:
        all_parts.extend(parts)
    body = {"contents": [{"role": "user", "parts": all_parts}], "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 3000, "thinkingConfig": thinking}}
    settings = {"thinkingConfig": thinking, "responseMimeType": "application/json", "maxOutputTokens": 3000, "strategy": strategy, "round": round_no, "page_numbers": pages}
    call_id = f"l2-{paper['arxiv_id']}-{strategy}-r{round_no}"
    if call_tag:
        call_id += f"-{call_tag}"
    encoded_input = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
    input_hash = hashlib.sha256(encoded_input.encode("utf-8")).hexdigest()
    assert_budget(estimated_cost)
    payload, history = request_json(provider="gemini", call_id=call_id, arm_id=f"l2-{strategy}", model_id=model_id, endpoint=endpoint, settings=settings, body=body, headers=gemini_headers(), timeout=timeout, out_dir=f"l2/{strategy}")
    add_meta(history, {"paper_id": paper["arxiv_id"], "strategy": strategy, "round": round_no, "input_sha256": input_hash, "page_numbers_sent": pages or [], "input_text_bytes": len(text.encode("utf-8")), "inline_part_bytes": sum(len(p.get("inlineData", {}).get("data", "")) * 3 // 4 for p in (parts or []))})
    result = {"paper_id": paper["arxiv_id"], "strategy": strategy, "round": round_no, "call_artifacts": [x["artifact"] for x in history], "latency_ms": sum(x["latency_ms"] for x in history), "http_status": history[-1]["http_status"] if history else None, "pages_sent": pages or [], "input_text_bytes": len(text.encode("utf-8")), "inline_part_bytes": sum(len(p.get("inlineData", {}).get("data", "")) * 3 // 4 for p in (parts or [])), "input_sha256": input_hash, "parsed": None, "parse_error": None}
    if payload:
        try:
            result["parsed"] = extract_json(extract_gemini(payload))
        except (ValueError, json.JSONDecodeError) as exc:
            result["parse_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    else:
        result["provider_error"] = json.loads((ROOT / history[-1]["artifact"]).read_text(encoding="utf-8")).get("error") if history else "no attempt result"
    return result


def reusable_abstract_call(paper_id: str) -> dict | None:
    """Recover the already completed 2609.29095 A call after the host interruption."""
    path = ROOT / "raw" / "responses" / "l2" / "A" / f"l2-{paper_id}-A-r1-a1.json"
    if not path.exists():
        return None
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved.get("http_status") != 200 or not isinstance(saved.get("output"), str):
        return None
    try:
        parsed = extract_json(saved["output"])
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(parsed.get("candidate_claims"), list):
        return None
    return {
        "paper_id": paper_id, "strategy": "A", "round": 1,
        "call_artifacts": [saved.get("artifact", path.relative_to(ROOT).as_posix())],
        "latency_ms": int(saved.get("latency_ms") or 0), "http_status": 200,
        "pages_sent": [], "input_text_bytes": int(saved.get("input_text_bytes") or 0),
        "inline_part_bytes": 0, "input_sha256": saved.get("input_sha256"),
        "parsed": parsed, "parse_error": None, "reused_after_resume": True,
    }


def save_checkpoint(outcomes: dict, target: int, status: str = "running") -> None:
    write_json(ROOT / "raw" / "l2-results.json", {
        "schema_version": 1, "status": status,
        "papers_completed": sum(all(k in row.get("strategies", {}) for k in ("A", "B", "C", "D")) for row in outcomes.values()),
        "papers_target": target, "results": outcomes,
    })


def initial_pages(texts: list[str]) -> list[int]:
    n = len(texts)
    selected = {1}
    if n >= 2:
        selected.add(2)
    early = [(i + 1, t) for i, t in enumerate(texts[:max(6, n // 3)])]
    late = [(i + 1, t) for i, t in enumerate(texts[max(0, n - 8):], start=max(0, n - 8))]
    intro = next((i for i, t in early if re.search(r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?introduction\b", t)), None)
    closing = next((i for i, t in reversed(late) if re.search(r"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?(?:conclusions?|limitations|discussion)\b", t)), None)
    if intro:
        selected.add(intro)
    if closing:
        selected.add(closing)
    if n >= 2:
        selected.update({n - 1, n})
    return sorted(p for p in selected if 1 <= p <= n)[:6]


def render_pages(pdf_path: Path, pages: list[int]) -> list[dict]:
    doc = pymupdf.open(pdf_path)
    parts = []
    for number in pages:
        pix = doc[number - 1].get_pixmap(matrix=pymupdf.Matrix(1.0, 1.0), alpha=False, colorspace=pymupdf.csRGB)
        data = pix.tobytes("png")
        parts.append({"text": f"\nSELECTED PDF PAGE {number} (1-indexed):"})
        parts.append({"inlineData": {"mimeType": "image/png", "data": base64.b64encode(data).decode("ascii")}})
    doc.close()
    return parts


def prompt_for(strategy: str, paper: dict, text: str, pages: list[int] | None = None) -> str:
    heading = {"A": "Strategy A — abstract and metadata only.", "B": "Strategy B — read this entire native PDF.", "C": "Strategy C — selective visual page reading; inspect only pages attached to this request plus the previous packet.", "D": "Strategy D — bounded full-document text reference; this entire extracted PDF text is the reference input."}[strategy]
    body = {"paper_id": paper["arxiv_id"], "title": paper.get("arxiv_title_differs_from_local") or paper["title"], "authors": paper.get("arxiv_metadata", {}).get("authors") or paper.get("authors"), "categories": paper.get("arxiv_metadata", {}).get("categories") or paper.get("categories")}
    return SYSTEM + "\n\n" + heading + "\nPaper metadata: " + json.dumps(body, ensure_ascii=False) + "\n\nEvidence/text for this strategy:\n" + text


def claim_objects(result: dict | None) -> list[dict]:
    if not isinstance(result, dict):
        return []
    claims = result.get("candidate_claims")
    return claims if isinstance(claims, list) else []


def all_pdf_text(pdf_path: Path, page_text: dict[str, list[str]], paper_id: str) -> str:
    texts = page_text[paper_id]
    return "\n\n".join(f"[PDF PAGE {i + 1}]\n{text}" for i, text in enumerate(texts))


def run_selective(paper: dict, model_id: str, pdf_path: Path, texts: list[str], page_cap: int = 10) -> dict:
    paper_id = paper["arxiv_id"]
    seen = initial_pages(texts)
    requests_seen = []
    previous_packet = "No prior packet yet."
    rounds = []
    stop_reason = None
    max_rounds = 4
    for round_no in range(1, max_rounds + 1):
        prompt = prompt_for("C", paper, f"Previously seen pages: {seen}\nPrevious packet: {previous_packet}\nInspect these newly attached pages. Request exact additional pages if needed; leave stop_reason null when requesting them.")
        parts = render_pages(pdf_path, seen if round_no == 1 else requests_seen[-1]["accepted_pages"])
        image_bytes = sum(len(p.get("inlineData", {}).get("data", "")) * 3 // 4 for p in parts if "inlineData" in p)
        call = gemini_call(paper=paper, strategy="C", round_no=round_no, model_id=model_id, text=prompt, parts=parts, pages=seen if round_no == 1 else requests_seen[-1]["accepted_pages"], estimated_cost=max(0.02, (len(seen) * 3500 + 4000) * 0.30 / 1_000_000 + 3000 * 2.50 / 1_000_000))
        call["image_bytes_sent"] = image_bytes
        rounds.append(call)
        parsed = call.get("parsed")
        if not isinstance(parsed, dict):
            stop_reason = call.get("provider_error") or call.get("parse_error") or "no_model_output"
            break
        previous_packet = json.dumps({"candidate_claims": parsed.get("candidate_claims"), "key_claims": parsed.get("key_claims"), "limitations": parsed.get("limitations")}, ensure_ascii=False)
        raw_requests = parsed.get("requested_pages") or []
        if not isinstance(raw_requests, list):
            raw_requests = []
        requested = []
        accepted = []
        remaining = max(0, page_cap - len(seen))
        for item in raw_requests:
            if not isinstance(item, dict) or not isinstance(item.get("pages"), list):
                continue
            nums = []
            for num in item["pages"]:
                if isinstance(num, int) and 1 <= num <= len(texts) and num not in seen and num not in accepted:
                    nums.append(num)
            requested.append({"pages": nums, "reason": str(item.get("reason") or "model omitted reason")})
            accepted.extend(nums)
        accepted = sorted(accepted[:remaining])
        requests_seen.append({"round": round_no, "model_requests": requested, "accepted_pages": accepted})
        if not accepted:
            stop_reason = str(parsed.get("stop_reason") or "model_returned_no_valid_additional_pages")
            break
        seen = sorted(set(seen) | set(accepted))
        if len(seen) >= page_cap:
            stop_reason = "host_page_budget_reached"
            break
    else:
        stop_reason = "host_round_budget_reached"
    last = rounds[-1].get("parsed") if rounds else None
    return {"paper_id": paper_id, "strategy": "C", "initial_pages_seen": initial_pages(texts), "pages_examined": seen, "requested_pages": requests_seen, "stop_reason": stop_reason, "candidate_claims": claim_objects(last), "key_claims": (last or {}).get("key_claims", []), "limitations": (last or {}).get("limitations", []), "rounds": rounds}


def run() -> dict:
    sample = json.loads((ROOT / "raw" / "sampling.json").read_text(encoding="utf-8"))
    cap = json.loads((ROOT / "raw" / "capability-probes.json").read_text(encoding="utf-8"))
    model_id = cap["providers"]["gemini"]["model_id_sent"]
    text_map = json.loads((ROOT / "scratch" / "pdf-text.json").read_text(encoding="utf-8"))
    info_map = json.loads((ROOT / "scratch" / "pdf-info.json").read_text(encoding="utf-8"))
    checkpoint = ROOT / "raw" / "l2-results.json"
    if checkpoint.exists():
        previous = json.loads(checkpoint.read_text(encoding="utf-8"))
        outcomes = previous.get("results", {})
    else:
        outcomes = {}
    target = len(sample["l2_paper_ids"])
    save_checkpoint(outcomes, target)
    for paper_id in sample["l2_paper_ids"]:
        previous_row = outcomes.get(paper_id, {})
        previous_strategies = previous_row.get("strategies", {})
        if all(key in previous_strategies for key in ("A", "B", "C", "D")):
            continue
        paper = next(p for p in sample["papers"] if p["arxiv_id"] == paper_id)
        pdf_info = sample["pdf_outcomes"][paper_id]
        pdf_path = ROOT / pdf_info["artifact"]
        pdf_bytes = pdf_path.stat().st_size
        abstract_text = json.dumps({"paper_id": paper_id, "title": paper.get("arxiv_title_differs_from_local") or paper["title"], "authors": paper.get("arxiv_metadata", {}).get("authors") or paper.get("authors"), "categories": paper.get("arxiv_metadata", {}).get("categories") or paper.get("categories"), "abstract": paper["abstract"]}, ensure_ascii=False)
        outcomes[paper_id] = previous_row or {"paper_id": paper_id, "pdf": {k: pdf_info.get(k) for k in ["artifact", "bytes", "page_count", "text_page_ratio", "image_count", "figure_reference_count", "table_reference_count"]}, "strategies": {}}
        outcomes[paper_id].setdefault("pdf", {k: pdf_info.get(k) for k in ["artifact", "bytes", "page_count", "text_page_ratio", "image_count", "figure_reference_count", "table_reference_count"]})
        strategies = outcomes[paper_id].setdefault("strategies", {})

        # A: abstract plus metadata. This is also the input basis of L1 routing.
        if "A" not in strategies:
            a = reusable_abstract_call(paper_id) if paper_id == "2609.29095" else None
            if a is None:
                a = gemini_call(paper=paper, strategy="A", round_no=1, model_id=model_id, text=prompt_for("A", paper, abstract_text), estimated_cost=0.015)
            strategies["A"] = {"paper_id": paper_id, "strategy": "A", "pages_processed": 0, "abstract_chars": len(paper["abstract"]), "candidate_claims": claim_objects(a.get("parsed")), "key_claims": (a.get("parsed") or {}).get("key_claims", []), "limitations": (a.get("parsed") or {}).get("limitations", []), "call": a}
            save_checkpoint(outcomes, target)

        # B: the whole PDF supplied as one native document part.
        if "B" not in strategies:
            pdf_data = pdf_path.read_bytes()
            bprompt = prompt_for("B", paper, "The full paper is attached as one application/pdf part.")
            bpart = [{"inlineData": {"mimeType": "application/pdf", "data": base64.b64encode(pdf_data).decode("ascii")}}]
            estimate_b = (pdf_info["page_count"] * 3500 + 3000) * 0.30 / 1_000_000 + 3000 * 2.50 / 1_000_000
            tag = "resume1" if paper_id == "2609.29095" else None
            b = gemini_call(paper=paper, strategy="B", round_no=1, model_id=model_id, text=bprompt, parts=bpart, pages=list(range(1, pdf_info["page_count"] + 1)), timeout=300, estimated_cost=max(estimate_b, 0.03), call_tag=tag)
            strategies["B"] = {"paper_id": paper_id, "strategy": "B", "pages_processed": pdf_info["page_count"], "pdf_bytes_sent": len(pdf_data), "candidate_claims": claim_objects(b.get("parsed")), "key_claims": (b.get("parsed") or {}).get("key_claims", []), "limitations": (b.get("parsed") or {}).get("limitations", []), "call": b}
            save_checkpoint(outcomes, target)

        # C: initial page set plus model-requested visual pages, capped at ten.
        if "C" not in strategies:
            c = run_selective(paper, model_id, pdf_path, text_map[paper_id], page_cap=10)
            strategies["C"] = c
            save_checkpoint(outcomes, target)

        # D: one full-text analysis over page-labelled text. No chunker/index.
        if "D" not in strategies:
            full_text = all_pdf_text(pdf_path, text_map, paper_id)
            d_prompt = prompt_for("D", paper, full_text)
            d_estimate = (len(full_text.encode("utf-8")) // 3 + 5000) * 0.30 / 1_000_000 + 3000 * 2.50 / 1_000_000
            d = gemini_call(paper=paper, strategy="D", round_no=1, model_id=model_id, text=d_prompt, timeout=300, estimated_cost=max(d_estimate, 0.03))
            parsed_d = d.get("parsed") or {}
            strategies["D"] = {"paper_id": paper_id, "strategy": "D", "pages_processed": pdf_info["page_count"], "text_pages": info_map[paper_id]["text_pages"], "text_page_ratio": info_map[paper_id]["text_page_ratio"], "full_text_bytes": len(full_text.encode("utf-8")), "candidate_claims": claim_objects(parsed_d), "key_claims": parsed_d.get("key_claims", []), "limitations": parsed_d.get("limitations", []), "load_bearing_pages": parsed_d.get("load_bearing_pages", []), "call": d}
            save_checkpoint(outcomes, target)
    final = {"schema_version": 1, "status": "complete", "papers_completed": target, "papers_target": target, "results": outcomes}
    write_json(checkpoint, final)
    return final


if __name__ == "__main__":
    out = run()
    print(json.dumps({"papers": out["papers_completed"], "strategies": ["A", "B", "C", "D"], "gemini_model": json.loads((ROOT / "raw/capability-probes.json").read_text())["providers"]["gemini"]["model_id_sent"]}, indent=2))
