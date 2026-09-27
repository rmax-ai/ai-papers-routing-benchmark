#!/usr/bin/env python3
"""Run the five-question abstract-only routing comparison."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from provider import (
    DEEPSEEK_URL, GEMINI_BASE, MODELS, OPENAI_URL, assert_budget,
    chat_headers, gemini_headers, jev_headers, request_json, write_json,
)
from run_probes import CHAT_SCHEMA

ROOT = Path.cwd()
PROMPT = (ROOT / "raw" / "chat-prompt-template.md").read_text(encoding="utf-8").split("\n\nUser content template:")[0]
QUESTION_PACK = json.loads((ROOT / "raw" / "jev-question-pack.json").read_text(encoding="utf-8"))


def extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise
        depth = 0
        in_string = escaped = False
        end = None
        for index in range(start, len(text)):
            char = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        if end is None:
            raise
        result = json.loads(text[start:end])
    if not isinstance(result, dict):
        raise ValueError("response is not a JSON object")
    return result


def completion_text(provider: str, payload: dict | None) -> str:
    if not payload:
        return ""
    if provider in ("openai", "deepseek"):
        return str((((payload.get("choices") or [{}])[0].get("message") or {}).get("content")) or "")
    candidates = payload.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    return "".join(str(part.get("text") or "") for part in parts)


def add_context_to_attempts(history: list[dict], paper_id: str, stratum: str, input_hash: str, source: str) -> None:
    for row in history:
        path = ROOT / row["artifact"]
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc.update({"paper_id": paper_id, "stratum": stratum, "input_sha256": input_hash,
                    "input_source": source})
        write_json(path, doc)


def topic_valid(value: Any) -> bool:
    return value in {"agent_reliability", "evals_assurance", "harness_runtime", "mcp_governance", "tool_use", "long_running_workflows", "other", "none"}


def validate_chat(value: dict) -> list[str]:
    errors = []
    for key in ("relevant", "empirical_evidence", "worth_escalating"):
        if not isinstance(value.get(key), bool):
            errors.append(f"{key} is not boolean")
    for key in ("relevant_probability", "empirical_probability", "escalation_probability"):
        if not isinstance(value.get(key), (int, float)) or not 0 <= float(value[key]) <= 1:
            errors.append(f"{key} outside 0..1")
    if not topic_valid(value.get("topic")):
        errors.append("topic outside fixed choice set")
    score = value.get("implementation_relevance")
    if not isinstance(score, (int, float)) or not 0 <= float(score) <= 4:
        errors.append("implementation_relevance outside 0..4")
    return errors


def run_chat(provider: str, paper: dict, state: str, input_hash: str, gemini_id: str) -> dict:
    paper_id = paper["arxiv_id"]
    call_id = f"l1-{paper_id}-{provider}"
    if provider == "openai":
        endpoint, model_id = OPENAI_URL, MODELS["openai"]
        settings = {"reasoning_effort": "none", "structured_output": "json_schema strict", "max_completion_tokens": 1200}
        body = {"model": model_id, "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": state}], "reasoning_effort": "none", "max_completion_tokens": 1200, "response_format": {"type": "json_schema", "json_schema": {"name": "paper_routing", "strict": True, "schema": CHAT_SCHEMA}}}
        headers = chat_headers(provider)
    elif provider == "deepseek":
        endpoint, model_id = DEEPSEEK_URL, MODELS["deepseek"]
        settings = {"reasoning_effort": "none", "structured_output": "json_object", "max_tokens": 1200}
        body = {"model": model_id, "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": state}], "reasoning_effort": "none", "max_tokens": 1200, "response_format": {"type": "json_object"}}
        headers = chat_headers(provider)
    else:
        endpoint, model_id = f"{GEMINI_BASE}/models/{gemini_id}:generateContent", gemini_id
        thinking = json.loads((ROOT / "raw" / "capability-probes.json").read_text(encoding="utf-8"))["providers"]["gemini"]["primary_thinking_config"]
        settings = {"thinkingConfig": thinking, "responseMimeType": "application/json", "maxOutputTokens": 1200}
        body = {"contents": [{"role": "user", "parts": [{"text": PROMPT + "\n\nPaper metadata and abstract:\n" + state}]}], "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 1200, "thinkingConfig": thinking}}
        headers = gemini_headers()
    assert_budget(0.015)
    payload, history = request_json(provider=provider, call_id=call_id, arm_id=f"l1-{provider}", model_id=model_id, endpoint=endpoint, settings=settings, body=body, headers=headers, timeout=180, out_dir=f"l1/{provider}")
    add_context_to_attempts(history, paper_id, paper["stratum"], input_hash, "title+authors+categories+arXiv abstract")
    out = {"paper_id": paper_id, "stratum": paper["stratum"], "arm": provider, "call_artifacts": [x["artifact"] for x in history], "attempt_details": history, "latency_ms": sum(x["latency_ms"] for x in history), "http_status": history[-1]["http_status"] if history else None, "output": None, "parse_error": None, "validation_errors": []}
    if payload:
        try:
            parsed = extract_json(completion_text(provider, payload))
            errors = validate_chat(parsed)
            out["output"] = parsed
            out["validation_errors"] = errors
            out["usage"] = history[-1]["usage"]
        except (ValueError, json.JSONDecodeError) as exc:
            out["parse_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    else:
        out["provider_error"] = (json.loads((ROOT / history[-1]["artifact"]).read_text(encoding="utf-8")).get("error") if history else "no attempt result")
    return out


def run_jev(paper: dict, state: str, input_hash: str) -> dict:
    paper_id = paper["arxiv_id"]
    call_id = f"l1-{paper_id}-jev"
    model_id = MODELS["jev"]
    endpoint = "https://ai-gateway.vercel.sh/v4/ai/evaluation-model"
    settings = {"protocol": "evaluation v4", "typed_questions": QUESTION_PACK["questions"], "providerOptions": {}}
    body = {"state": state, "questions": QUESTION_PACK["questions"], "providerOptions": {}}
    assert_budget(0.015)
    payload, history = request_json(provider="jev", call_id=call_id, arm_id="l1-jev", model_id=model_id, endpoint=endpoint, settings=settings, body=body, headers=jev_headers(), timeout=180, out_dir="l1/jev")
    add_context_to_attempts(history, paper_id, paper["stratum"], input_hash, "title+authors+categories+arXiv abstract")
    out = {"paper_id": paper_id, "stratum": paper["stratum"], "arm": "jev", "call_artifacts": [x["artifact"] for x in history], "attempt_details": history, "latency_ms": sum(x["latency_ms"] for x in history), "http_status": history[-1]["http_status"] if history else None, "answers": (payload or {}).get("answers"), "usage": history[-1]["usage"] if history else None}
    if not payload:
        out["provider_error"] = json.loads((ROOT / history[-1]["artifact"]).read_text(encoding="utf-8")).get("error") if history else "no attempt result"
    return out


def main() -> None:
    sample = json.loads((ROOT / "raw" / "sampling.json").read_text(encoding="utf-8"))
    cap = json.loads((ROOT / "raw" / "capability-probes.json").read_text(encoding="utf-8"))
    gemini_id = cap["providers"]["gemini"]["model_id_sent"]
    if not all(cap["providers"].get(k, {}).get("passed") for k in ("openai", "deepseek", "gemini", "jev")):
        raise SystemExit("capability probe blocker: all four candidate paths must pass before L1")
    results = []
    outages: set[str] = set()
    for paper in sample["papers"]:
        paper_id = paper["arxiv_id"]
        state_obj = {"paper_id": paper_id, "title": paper.get("arxiv_title_differs_from_local") or paper.get("title"), "authors": paper.get("arxiv_metadata", {}).get("authors") or paper.get("authors"), "categories": paper.get("arxiv_metadata", {}).get("categories") or paper.get("categories"), "abstract": paper.get("abstract", "")}
        state = json.dumps(state_obj, ensure_ascii=False, separators=(",", ":"))
        prompt_input_hash = hashlib.sha256((PROMPT + "\n" + state).encode("utf-8")).hexdigest()
        row = {"paper_id": paper_id, "stratum": paper["stratum"], "proxy_relevant_label": paper["high_value_proxy_label"], "input_sha256": prompt_input_hash, "input": state_obj, "judgments": {}}
        if "jev" not in outages:
            row["judgments"]["jev"] = run_jev(paper, state, prompt_input_hash)
            if row["judgments"]["jev"].get("provider_error"):
                outages.add("jev")
        for provider in ("deepseek", "gemini", "openai"):
            if provider in outages:
                row["judgments"][provider] = {"status": "stopped_after_all-error_cell_guard", "reason": "earlier call returned no model response after retries"}
                continue
            result = run_chat(provider, paper, state, prompt_input_hash, gemini_id)
            row["judgments"][provider] = result
            if result.get("provider_error"):
                # Stop this provider's L1 cell after a complete failed request.
                outages.add(provider)
        results.append(row)
        (ROOT / "raw" / "l1-results.json").write_text(json.dumps({"schema_version": 1, "status": "running", "papers_completed": len(results), "provider_outages": sorted(outages), "results": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    final = {"schema_version": 1, "status": "complete" if len(results) == len(sample["papers"]) else "partial", "papers_completed": len(results), "provider_outages": sorted(outages), "results": results}
    write_json(ROOT / "raw" / "l1-results.json", final)
    print(json.dumps({"papers": len(results), "provider_outages": sorted(outages), "judgments": {arm: sum(bool(row["judgments"].get(arm, {}).get("output") or row["judgments"].get(arm, {}).get("answers")) for row in results) for arm in ("jev", "deepseek", "gemini", "openai")}}, indent=2))


if __name__ == "__main__":
    main()
