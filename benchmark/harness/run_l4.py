#!/usr/bin/env python3
"""Run bounded typed JEV post-generation checks on one insight per output."""

from __future__ import annotations

import json
import hashlib
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from provider import JEV_URL, MODELS, assert_budget, jev_headers, request_json, rolling_totals, write_json

ROOT = Path.cwd()
QUESTIONS = {
    "supported_by_supplied_evidence": {"type": "boolean", "instructions": "Is the central factual claim supported by the supplied source excerpts?"},
    "agenda_relevant": {"type": "boolean", "instructions": "Is this insight materially relevant to agent reliability, evaluation/assurance, harness/runtime, MCP/governance, tool use, or long-running workflows?"},
    "duplicates_supplied_existing_insight": {"type": "boolean", "instructions": "Is the insight semantically duplicative of an existing insight explicitly supplied in the state?"},
    "has_actionable_implication": {"type": "boolean", "instructions": "Does it contain an actionable architecture, implementation, or research implication?"},
    "escalate_for_deeper_review": {"type": "boolean", "instructions": "Should this candidate be escalated for deeper human/model review before durable storage?"},
}


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def existing_entry(paper_id: str) -> str:
    base = Path.home() / "src/rmax-ai/knowledge-graph/sources/papers"
    for path in base.glob("*.md"):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if paper_id in content:
            return content[:3500]
    return "No matching per-paper knowledge-graph source entry was found."


def sources_for(paper_id: str, refs: list[dict], pages: list[str]) -> list[dict]:
    out = []
    for ref in refs:
        page = ref.get("page")
        quote = str(ref.get("quote") or "")
        page_text = pages[page - 1] if isinstance(page, int) and 0 < page <= len(pages) else ""
        pos = normalized(page_text).find(normalized(quote)) if quote else -1
        excerpt = page_text[max(0, pos - 300):pos + len(quote) + 500] if pos >= 0 else page_text[:1000]
        out.append({"page": page, "quote": quote, "source_excerpt": excerpt})
    return out[:8]


def main() -> None:
    sample = json.loads((ROOT / "raw/sampling.json").read_text())
    generated = json.loads((ROOT / "raw/l3-results.json").read_text())["results"]
    text_map = json.loads((ROOT / "scratch/pdf-text.json").read_text())
    saved_path = ROOT / "raw/l4-results.json"
    saved = json.loads(saved_path.read_text()).get("results", {}) if saved_path.exists() else {}
    write_json(ROOT / "raw/l4-question-pack.json", {"protocol": "AI Gateway evaluation v4", "questions": QUESTIONS, "thresholds_are_host_owned": {"supported": .75, "relevant": .60, "duplicate": .75, "actionable": .60, "escalate": .65}})
    target = 0
    for paper_id, row in generated.items():
        for path in ("full_reference", "selective"):
            if row.get("inputs", {}).get(path, {}).get("skipped_by_host_policy"):
                continue
            for provider, cell in row.get("generations", {}).get(path, {}).items():
                if provider == "openai_medium" or not isinstance(cell.get("output"), dict):
                    continue
                insights = cell["output"].get("insights") or []
                if insights:
                    target += 1
    completed = 0
    for paper_id in sample["l3_paper_ids"]:
        row = generated.get(paper_id, {})
        l4paper = saved.setdefault(paper_id, {})
        for path in ("full_reference", "selective"):
            if row.get("inputs", {}).get(path, {}).get("skipped_by_host_policy"):
                continue
            pages = text_map[paper_id]
            if path == "selective":
                selected_pages = set(row.get("inputs", {}).get(path, {}).get("pages", []))
                pages = [text if index + 1 in selected_pages else "" for index, text in enumerate(pages)]
            for provider, cell in row.get("generations", {}).get(path, {}).items():
                if provider == "openai_medium" or not isinstance(cell.get("output"), dict):
                    continue
                insights = cell["output"].get("insights") or []
                if not insights:
                    continue
                insight = insights[0]
                key = f"{path}/{provider}/insight-0"
                if key in l4paper:
                    completed += 1
                    continue
                refs = insight.get("evidence_refs") or []
                state = {
                    "paper_id": paper_id,
                    "agenda": "agent reliability, evaluation/assurance, harness/runtime, MCP/governance, tool use, long-running workflows",
                    "candidate_insight": insight,
                    "supplied_source_evidence": sources_for(paper_id, refs, pages),
                    "existing_insight_for_duplicate_check": existing_entry(paper_id),
                }
                body = {"state": json.dumps(state, ensure_ascii=False), "questions": QUESTIONS, "providerOptions": {}}
                state_text = body["state"]
                state_hash = hashlib.sha256(state_text.encode()).hexdigest()
                artifact_id = f"l4-{paper_id}-{path}-{provider}-insight0"
                assert_budget(.001)
                payload, history = request_json(provider="jev", call_id=artifact_id,
                    arm_id=f"l4-{path}-jev", model_id=MODELS["jev"], endpoint=JEV_URL,
                    settings={"protocol": "AI Gateway evaluation v4", "typed_questions": QUESTIONS, "providerOptions": {}},
                    body=body, headers=jev_headers(), timeout=180, out_dir="l4/jev")
                for attempt in history:
                    artifact_path = ROOT / attempt["artifact"]
                    artifact = json.loads(artifact_path.read_text())
                    artifact.update({"paper_id": paper_id, "input_sha256": state_hash,
                        "input_bytes": len(state_text.encode()), "input_chars": len(state_text)})
                    write_json(artifact_path, artifact)
                result = {"paper_id": paper_id, "input_path": path, "generator": provider,
                    "insight_index": 0, "call_artifacts": [h["artifact"] for h in history],
                    "http_status": history[-1]["http_status"] if history else None,
                    "latency_ms": sum(h["latency_ms"] for h in history),
                    "input_sha256": state_hash,
                    "usage": history[-1]["usage"] if history else None,
                    "answers": (payload or {}).get("answers"), "thresholds": {"supported": .75, "relevant": .60, "duplicate": .75, "actionable": .60, "escalate": .65}}
                if not payload:
                    result["provider_error"] = json.loads((ROOT / history[-1]["artifact"]).read_text()).get("error") if history else "no response"
                l4paper[key] = result
                completed += 1
                write_json(saved_path, {"schema_version": 1, "status": "running", "completed": completed, "target": target, "results": saved})
    write_json(saved_path, {"schema_version": 1, "status": "complete", "completed": completed, "target": target, "results": saved})
    print(json.dumps({"completed": completed, "target": target, "usage_and_spend": rolling_totals()}, indent=2))


if __name__ == "__main__":
    main()
