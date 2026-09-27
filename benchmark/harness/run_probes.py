#!/usr/bin/env python3
"""Execute and persist the capability probes required before the matrix."""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path
from typing import Any

import pymupdf
import requests

from provider import (
    GEMINI_BASE, MODELS, OPENAI_URL, DEEPSEEK_URL, JEV_URL,
    assert_budget, chat_headers, gemini_headers, jev_headers, request_json,
    rolling_totals, write_json,
)

ROOT = Path.cwd()

CHAT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "relevant": {"type": "boolean"},
        "relevant_probability": {"type": "number", "minimum": 0, "maximum": 1},
        "empirical_evidence": {"type": "boolean"},
        "empirical_probability": {"type": "number", "minimum": 0, "maximum": 1},
        "topic": {"type": "string", "enum": ["agent_reliability", "evals_assurance", "harness_runtime", "mcp_governance", "tool_use", "long_running_workflows", "other", "none"]},
        "worth_escalating": {"type": "boolean"},
        "escalation_probability": {"type": "number", "minimum": 0, "maximum": 1},
        "implementation_relevance": {"type": "number", "minimum": 0, "maximum": 4},
    },
    "required": ["relevant", "relevant_probability", "empirical_evidence", "empirical_probability", "topic", "worth_escalating", "escalation_probability", "implementation_relevance"],
}


def output_of(provider: str, payload: dict | None) -> str:
    if not payload:
        return ""
    if provider in {"openai", "deepseek"}:
        return str((((payload.get("choices") or [{}])[0].get("message") or {}).get("content")) or "")
    candidates = payload.get("candidates") or []
    parts = ((candidates[0].get("content") or {}).get("parts") or []) if candidates else []
    return "".join(str(part.get("text") or "") for part in parts)


def probe_model_list() -> tuple[list[dict], dict]:
    endpoint = f"{GEMINI_BASE}/models"
    payload, _ = request_json(
        provider="gemini", call_id="probe-gemini-model-list", arm_id="capability-model-resolution",
        model_id="GET /v1beta/models", endpoint=endpoint, settings={"method": "GET", "purpose": "resolve model ids before generation"},
        method="GET", headers=gemini_headers(), timeout=120, out_dir="probes",
    )
    if not payload:
        return [], {"status": "failed", "endpoint": endpoint}
    models = payload.get("models") or []
    matches = []
    for item in models:
        name = str(item.get("name") or "")
        display = str(item.get("displayName") or "")
        if "flash-lite" in (name + " " + display).lower():
            matches.append({k: item.get(k) for k in ["name", "version", "displayName", "description", "inputTokenLimit", "outputTokenLimit", "supportedGenerationMethods"] if item.get(k) is not None})
    matches.sort(key=lambda row: ("preview" in row.get("name", "").lower(), row.get("version", ""), row.get("name", "")))
    write_json(ROOT / "raw" / "gemini-model-resolution.json", {"endpoint": endpoint, "status": "success", "matching_models": matches})
    return matches, {"status": "success", "endpoint": endpoint, "matching_models": matches}


def choose_gemini(matches: list[dict]) -> tuple[str | None, dict]:
    stable = [m for m in matches if not any(x in str(m.get("name", "")).lower() for x in ("preview", "latest", "experimental", "-tts", "-image"))]
    # Exclude multimodal siblings (for example TTS) and choose the highest
    # stable text-generation model family from the live catalogue.
    eligible = [m for m in stable if re.fullmatch(r"models/gemini-\d+(?:\.\d+)?-flash-lite(?:-\d{3})?", str(m.get("name", "")))]
    if not eligible:
        return None, {"error": "model catalogue exposed no non-alias stable flash-lite identifier"}
    def version_key(m: dict) -> tuple:
        family = tuple(int(x) for x in re.search(r"gemini-(\d+(?:\.\d+)?)-flash-lite", str(m.get("name", ""))).group(1).split("."))
        release = tuple(int(x) for x in re.findall(r"\d+", str(m.get("version", ""))))
        return family + release
    selected = sorted(eligible, key=version_key)[-1]
    name = str(selected.get("name", ""))
    model_id = name.rsplit("/", 1)[-1]
    return model_id, {"model_entry": selected, "resolved_model_id": model_id, "version": selected.get("version"), "catalogue_endpoint": f"{GEMINI_BASE}/models"}


def openai_probe() -> dict:
    settings = {"reasoning_effort": "none", "response_format": "json_schema strict", "max_completion_tokens": 64}
    schema = {"name": "probe", "strict": True, "schema": {"type": "object", "properties": {"answer": {"type": "integer"}}, "required": ["answer"], "additionalProperties": False}}
    body = {"model": MODELS["openai"], "messages": [{"role": "user", "content": "Return the JSON object with answer equal to 2."}], "reasoning_effort": "none", "max_completion_tokens": 64, "response_format": {"type": "json_schema", "json_schema": schema}}
    assert_budget(0.002)
    payload, history = request_json(provider="openai", call_id="probe-openai", arm_id="capability-openai", model_id=MODELS["openai"], endpoint=OPENAI_URL, settings=settings, body=body, headers=chat_headers("openai"), timeout=180, out_dir="probes")
    return {"model_id_sent": MODELS["openai"], "resolved_model_id": MODELS["openai"], "endpoint": OPENAI_URL, "settings": settings, "status": history[-1]["http_status"] if history else None, "attempt_artifacts": [x["artifact"] for x in history], "mechanisms": {"reasoning_off": "reasoning_effort:none (capability probe; confirm reasoning_tokens=0)", "structured_output": "response_format:json_schema(strict)"}, "usage_mapping": (history[-1]["usage"].get("mapping") if history else None), "reasoning_tokens": (history[-1]["usage"].get("reasoning_tokens") if history else None), "response_text": output_of("openai", payload), "passed": bool(payload)}


def deepseek_probe() -> dict:
    base_settings = {"reasoning_effort": "none", "response_format": "json_object", "max_tokens": 64}
    def send(call_id: str, thinking_mode: str | None) -> tuple[dict | None, list[dict]]:
        settings = dict(base_settings)
        if thinking_mode:
            settings["thinking"] = {"type": "disabled"}
        body: dict[str, Any] = {"model": MODELS["deepseek"], "messages": [{"role": "user", "content": "Return the JSON object with answer equal to 2."}], "response_format": {"type": "json_object"}, "max_tokens": 64}
        body["reasoning_effort"] = "none" if not thinking_mode else "none"
        if thinking_mode:
            body["thinking"] = {"type": "disabled"}
        assert_budget(0.002)
        return request_json(provider="deepseek", call_id=call_id, arm_id="capability-deepseek", model_id=MODELS["deepseek"], endpoint=DEEPSEEK_URL, settings=settings, body=body, headers=chat_headers("deepseek"), timeout=180, out_dir="probes")
    payload, history = send("probe-deepseek-none", None)
    mechanism = "reasoning_effort:none"
    msg = (((payload or {}).get("choices") or [{}])[0].get("message") or {})
    usage = (payload or {}).get("usage") or {}
    counter = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    if payload and (msg.get("reasoning_content") is not None or counter is not None):
        fallback, fallback_history = send("probe-deepseek-thinking-disabled", "thinking_disabled")
        history.extend(fallback_history)
        payload = fallback
        mechanism = 'thinking:{"type":"disabled"}'
        msg = (((payload or {}).get("choices") or [{}])[0].get("message") or {})
        usage = (payload or {}).get("usage") or {}
        counter = (usage.get("completion_tokens_details") or {}).get("reasoning_tokens")
    response = history[-1] if history else {}
    return {"model_id_sent": MODELS["deepseek"], "resolved_model_id": MODELS["deepseek"], "endpoint": DEEPSEEK_URL, "settings": response.get("settings", base_settings), "status": response.get("http_status"), "attempt_artifacts": [x["artifact"] for x in history], "mechanisms": {"reasoning_off": mechanism, "structured_output": "response_format:json_object"}, "usage_mapping": response.get("usage", {}).get("mapping"), "reasoning_counter": counter, "reasoning_content_present": msg.get("reasoning_content") is not None, "response_text": output_of("deepseek", payload), "passed": bool(payload) and msg.get("reasoning_content") is None and counter is None}


def gemini_probe(model_id: str) -> tuple[dict, dict | None]:
    if not model_id:
        return {"passed": False, "error": "no stable model id resolved"}, None
    endpoint = f"{GEMINI_BASE}/models/{model_id}:generateContent"
    modes = [("thinkingBudget", {"thinkingBudget": 0}), ("thinkingLevel", {"thinkingLevel": "low"})]
    selected = None
    history_all = []
    payload = None
    selected_mode = None
    for call_id, (label, config) in enumerate(modes, start=1):
        settings = {"thinkingConfig": config, "responseMimeType": "application/json", "maxOutputTokens": 96}
        body = {"contents": [{"role": "user", "parts": [{"text": "Return JSON with answer equal to 2."}]}], "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 96, "thinkingConfig": config}}
        assert_budget(0.002)
        payload, history = request_json(provider="gemini", call_id=f"probe-gemini-{label}", arm_id="capability-gemini", model_id=model_id, endpoint=endpoint, settings=settings, body=body, headers=gemini_headers(), timeout=180, out_dir="probes")
        history_all.extend(history)
        if payload:
            selected, selected_mode = config, label
            break
    response = history_all[-1] if history_all else {}
    result = {"model_id_sent": model_id, "endpoint": endpoint, "settings": response.get("settings"), "status": response.get("http_status"), "attempt_artifacts": [x["artifact"] for x in history_all], "mechanisms": {"reasoning_minimal": f"generationConfig.thinkingConfig.{selected_mode} accepted" if selected_mode else "neither tested thinking configuration accepted", "structured_output": "generationConfig.responseMimeType:application/json"}, "usage_mapping": response.get("usage", {}).get("mapping"), "thoughts_tokens": response.get("usage", {}).get("reasoning_tokens"), "response_text": output_of("gemini", payload), "passed": bool(payload), "primary_thinking_config": selected}
    pdf_doc = pymupdf.open()
    page = pdf_doc.new_page(width=612, height=792)
    page.insert_text((72, 72), "DQ79 native PDF capability probe. The relevant result is 2.")
    pdf_bytes = pdf_doc.tobytes()
    pdf_doc.close()
    pdf_path = ROOT / "raw" / "capability-probe.pdf"
    pdf_path.write_bytes(pdf_bytes)
    pdf_body = {"contents": [{"role": "user", "parts": [{"text": "Read this one-page PDF and return JSON {\\\"answer\\\": 2} if it states that the relevant result is 2."}, {"inlineData": {"mimeType": "application/pdf", "data": base64.b64encode(pdf_bytes).decode("ascii")}}]}], "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 96, "thinkingConfig": selected or {"thinkingLevel": "low"}}}
    assert_budget(0.002)
    pdf_payload, pdf_history = request_json(provider="gemini", call_id="probe-gemini-pdf", arm_id="capability-gemini-pdf", model_id=model_id, endpoint=endpoint, settings={"document": "inlineData application/pdf", "bytes": len(pdf_bytes), "thinkingConfig": selected or {"thinkingLevel": "low"}, "responseMimeType": "application/json"}, body=pdf_body, headers=gemini_headers(), timeout=180, out_dir="probes")
    result["pdf_probe"] = {"artifact": "raw/capability-probe.pdf", "bytes": len(pdf_bytes), "passed": bool(pdf_payload), "response_text": output_of("gemini", pdf_payload), "attempt_artifacts": [x["artifact"] for x in pdf_history], "usage_mapping": pdf_history[-1]["usage"].get("mapping") if pdf_history else None}
    return result, pdf_payload


def jev_probe() -> dict:
    questions = {"answer_is_two": {"type": "boolean", "instructions": "Does the state say that the answer is 2?"}}
    body = {"state": "The answer is 2.", "questions": questions, "providerOptions": {}}
    settings = {"protocol": "AI Gateway evaluation v4", "questions": questions, "providerOptions": {}}
    assert_budget(0.002)
    payload, history = request_json(provider="jev", call_id="probe-jev", arm_id="capability-jev", model_id=MODELS["jev"], endpoint=JEV_URL, settings=settings, body=body, headers=jev_headers(), timeout=180, out_dir="probes")
    return {"model_id_sent": MODELS["jev"], "resolved_model_id": MODELS["jev"], "endpoint": JEV_URL, "settings": settings, "status": history[-1]["http_status"] if history else None, "attempt_artifacts": [x["artifact"] for x in history], "mechanisms": {"reasoning_off": "not applicable (typed evaluation model)", "structured_output": "typed evaluation protocol v4"}, "usage_mapping": history[-1]["usage"].get("mapping") if history else None, "usage_fields_observed": history[-1]["usage"].get("raw_usage_fields") if history else None, "answers": (payload or {}).get("answers"), "passed": bool(payload)}


def main() -> None:
    gemini_only = "--gemini-only" in sys.argv
    # The sole live catalogue GET precedes generation; the retry path reuses
    # its persisted response to avoid another model-list request.
    if gemini_only:
        stored = json.loads((ROOT / "raw" / "gemini-model-resolution.json").read_text(encoding="utf-8"))
        matches = stored["matching_models"]
        resolution = {"status": stored["status"], "endpoint": stored["endpoint"], "matching_models": matches}
    else:
        matches, resolution = probe_model_list()
    gemini_id, provenance = choose_gemini(matches)
    probes_path = ROOT / "raw" / "capability-probes.json"
    if gemini_only and probes_path.exists():
        probes = json.loads(probes_path.read_text(encoding="utf-8"))
    else:
        probes = {
            "schema_version": 1,
            "run_date": "2026-09-25",
            "candidate_ids": {"deepseek": MODELS["deepseek"], "openai": MODELS["openai"], "gemini_requested": MODELS["gemini_requested"], "jev": MODELS["jev"]},
            "providers": {},
        }
    probes["gemini_model_resolution"] = {**resolution, **provenance, "requested_alias": MODELS["gemini_requested"]}
    if not gemini_only:
        probes["providers"]["openai"] = openai_probe()
        probes["providers"]["deepseek"] = deepseek_probe()
    gemini, _ = gemini_probe(gemini_id)
    probes["providers"]["gemini"] = gemini
    if not gemini_only:
        probes["providers"]["jev"] = jev_probe()
    probes["cumulative_usage_and_spend"] = rolling_totals()
    write_json(ROOT / "raw" / "capability-probes.json", probes)
    print(json.dumps({"probe_status": {k: v.get("passed") for k, v in probes["providers"].items()}, "gemini_resolution": probes["gemini_model_resolution"], "cumulative_usage_and_spend": probes["cumulative_usage_and_spend"]}, indent=2))


if __name__ == "__main__":
    main()
