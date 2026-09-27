#!/usr/bin/env python3
"""Bounded DQ84 Luna-vs-Gemini evidence architecture benchmark."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
import platform
import random
import re
import shutil
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path.cwd()
REF = Path.home() / ".hermes/ops-cards/dq79-evidence"
PAPER_IDS = [
    "2609.29808", "2609.29095", "2609.28614", "2609.30217",
    "2609.28585", "2609.28586", "2609.27263", "2609.24122",
]
ALLOWED_HOSTS = {
    "api.openai.com", "generativelanguage.googleapis.com", "api.deepseek.com",
}
DIMENSIONS = [
    "faithfulness", "evidence_support", "insight_depth", "systems_relevance",
    "actionability", "compression_information_density",
    "durable_memory_precision_proxy",
]
RATE_CARD = {
    "openai": {"input": 0.10, "cached_input": 0.01, "output": 0.50},
    "gemini": {"input": 0.30, "cached_input": 0.30, "output": 2.50},
    "deepseek_offpeak": {"input": 0.15, "cached_input": 0.003, "output": 0.60},
    "deepseek_peak": {"input": 0.30, "cached_input": 0.006, "output": 1.20},
    # Conservative budget estimate; actual per-attempt tier is computed by DQ79 provider.py.
    "deepseek": {"input": 0.30, "cached_input": 0.006, "output": 1.20},
}
REPORT_NAME = "dq84-luna-vs-gemini-evidence-benchmark.md"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def relhome(path: Path) -> str:
    try:
        return "~/" + path.relative_to(Path.home()).as_posix()
    except ValueError:
        return path.as_posix()


def extract_json(text: str) -> dict:
    """DQ79 run_l1.extract_json, isolated from its PDF-only import dependencies."""
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
        for index, char in enumerate(text[start:], start):
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


def load_modules():
    """Import the exact DQ79 helpers while stubbing only unused PDF dependencies."""
    scratch = str(ROOT / "scratch")
    if scratch not in sys.path:
        sys.path.insert(0, scratch)
    stub_l1 = types.ModuleType("run_l1")
    stub_l1.extract_json = extract_json
    sys.modules["run_l1"] = stub_l1
    if "pymupdf" not in sys.modules:
        sys.modules["pymupdf"] = types.ModuleType("pymupdf")
    provider = importlib.import_module("provider")
    run_l2 = importlib.import_module("run_l2")
    run_l3 = importlib.import_module("run_l3")
    l2_metrics = importlib.import_module("l2_metrics")
    l3_metrics = importlib.import_module("l3_metrics")
    return provider, run_l2, run_l3, l2_metrics, l3_metrics


def copy_reuse_files() -> dict:
    destination = ROOT / "scratch"
    destination.mkdir(parents=True, exist_ok=True)
    names = ("provider.py", "run_l2.py", "run_l3.py", "l2_metrics.py", "l3_metrics.py")
    copied = {}
    for name in names:
        source = REF / "scratch" / name
        target = destination / name
        shutil.copyfile(source, target)
        copied[name] = {
            "source": relhome(source),
            "destination": target.relative_to(ROOT).as_posix(),
            "sha256": sha256_bytes(target.read_bytes()),
        }
    return copied


def context():
    required = [ROOT / "scratch" / name for name in (
        "provider.py", "run_l2.py", "run_l3.py", "l2_metrics.py", "l3_metrics.py",
    )]
    if not all(x.exists() for x in required):
        copy_reuse_files()
    provider, run_l2, run_l3, l2_metrics, l3_metrics = load_modules()
    sample = read_json(REF / "raw/sampling.json")
    text_map = read_json(REF / "scratch/pdf-text.json")
    papers = {p["arxiv_id"]: p for p in sample["papers"]}
    d_results = {}
    for pid in PAPER_IDS:
        artifact = REF / "raw/responses/l2/D" / f"l2-{pid}-D-r1-a1.json"
        d_results[pid] = read_json(artifact)
    agenda_path = Path.home() / "src/rmax-ai/knowledge-graph/topics/ai-papers.md"
    agenda = agenda_path.read_text(encoding="utf-8")[:12000] if agenda_path.exists() else ""
    return {
        "provider": provider, "run_l2": run_l2, "run_l3": run_l3,
        "l2_metrics": l2_metrics, "l3_metrics": l3_metrics,
        "sample": sample, "papers": papers,
        "text_map": text_map, "d_artifacts": d_results, "agenda": agenda,
    }


def d_body(prompt: str, thinking: dict) -> dict:
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "maxOutputTokens": 3000,
            "thinkingConfig": thinking,
        },
    }


def prompt_templates(run_l2, run_l3) -> dict[str, str]:
    luna_user_base = "Follow the artifact contract exactly.\n\n{METADATA_JSON}\nSOURCE METHOD: {SOURCE_METHOD}\nSOURCE:\n{SOURCE_PAYLOAD}"
    return {
        "armA-luna.md": (
            "SYSTEM\n" + run_l3.SYSTEM + "\n\nUSER CONTENT TEMPLATE\n" +
            luna_user_base.replace(
                "{SOURCE_METHOD}",
                "strategy-D complete page-labelled PyMuPDF text extraction",
            ) + "\n"
        ),
        "gemini-packet.md": (
            "GEMINI D SYSTEM AND HEADING\n" + run_l2.SYSTEM + "\n\n" +
            "Strategy D — bounded full-document text reference; this entire extracted PDF text is the reference input.\n" +
            "Paper metadata: {PAPER_METADATA_JSON}\n\nEvidence/text for this strategy:\n{PAGE_LABELLED_FULL_TEXT}\n"
        ),
        "armB-luna.md": (
            "SYSTEM\n" + run_l3.SYSTEM + "\n\nUSER CONTENT TEMPLATE\n" +
            luna_user_base.replace(
                "{SOURCE_METHOD}",
                "Gemini Flash-Lite structured evidence packet extracted from the full page-labelled paper text",
            ) + "\n"
        ),
    }


def write_prompts(ctx: dict) -> dict:
    prompt_dir = ROOT / "raw/prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    prompts = prompt_templates(ctx["run_l2"], ctx["run_l3"])
    prompts["canonical-output-schema.json"] = json.dumps(
        ctx["run_l3"].OUTPUT_SCHEMA, ensure_ascii=False, indent=2
    ) + "\n"
    hashes = {}
    for name, value in prompts.items():
        path = prompt_dir / name
        path.write_text(value, encoding="utf-8")
        hashes[name] = sha256_bytes(value.encode("utf-8"))
    (prompt_dir / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in hashes.items()), encoding="utf-8"
    )
    public_dir = ROOT / "public/prompts"
    public_dir.mkdir(parents=True, exist_ok=True)
    for name, value in prompts.items():
        (public_dir / name).write_text(value, encoding="utf-8")
    (public_dir / "SHA256SUMS.txt").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in hashes.items()), encoding="utf-8"
    )
    return hashes


def compatibility_check(ctx: dict) -> dict:
    cap = read_json(REF / "raw/capability-probes.json")
    thinking = cap["providers"]["gemini"]["primary_thinking_config"]
    rows = []
    for pid in PAPER_IDS:
        paper = ctx["papers"][pid]
        full_text = ctx["run_l2"].all_pdf_text(None, ctx["text_map"], pid)
        prompt = ctx["run_l2"].prompt_for("D", paper, full_text)
        body = d_body(prompt, thinking)
        body_text = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
        computed = sha256_bytes(body_text.encode("utf-8"))
        artifact = ctx["d_artifacts"][pid]
        expected = artifact.get("input_sha256")
        rows.append({
            "paper_id": pid,
            "page_count": len(ctx["text_map"][pid]),
            "full_page_labelled_text_bytes": len(full_text.encode("utf-8")),
            "d_prompt_bytes": len(prompt.encode("utf-8")),
            "d_request_body_sha256_expected": expected,
            "d_request_body_sha256_reconstructed": computed,
            "matches": computed == expected,
            "residual": None if computed == expected else (
                "The exact D request-body hash did not match after reusing the recorded D prompt and Gemini generationConfig."
            ),
            "reference_artifact": relhome(REF / "raw/responses/l2/D" / f"l2-{pid}-D-r1-a1.json"),
        })
    result = {
        "method": "Reconstructed run_l2.all_pdf_text + run_l2.prompt_for('D') and the exact D request body; SHA256 over compact UTF-8 JSON body as run_l2.gemini_call did.",
        "reference_bundle": relhome(REF),
        "paper_count": len(rows),
        "all_match": all(r["matches"] for r in rows),
        "papers": rows,
    }
    write_json(ROOT / "raw/inputs-check.json", result)
    return result


def report_headings() -> list[str]:
    return [
        "Setup and model identifiers", "Benchmark design and controls",
        "Arm A — one-pass GPT-6 Luna", "Arm B — Gemini evidence packet → GPT-6 Luna",
        "Evidence integrity metrics", "Insight quality (blind judge)", "Reliability",
        "Failure cases", "Cost and latency",
        "Scale model (1k/10k/100k/1M + funnel + throughput)",
        "Verdict: does the Gemini stage earn its keep", "Caveats",
    ]


def create_report_skeleton(status: str = "prepared; provider matrix not yet run") -> None:
    lines = [
        "# DQ84 Luna vs Gemini evidence benchmark", "",
        f"Run status: **{status}** (updated {utc_now()}).", "",
        "### Incremental checkpoint", "",
        "This report is rewritten at each completed paper or judge cell. The raw checkpoint files are authoritative for partial runs.",
        "",
    ]
    for heading in report_headings():
        lines.extend([f"## {heading}", "", "Pending. See `raw/manifest.json` and the per-arm checkpoint files for current status.", ""])
    (ROOT / REPORT_NAME).write_text("\n".join(lines), encoding="utf-8")


def manifest_update(status: str, prompt_hashes: dict | None = None,
                    input_check: dict | None = None, extra: dict | None = None) -> None:
    path = ROOT / "raw/manifest.json"
    prior = read_json(path) if path.exists() else {}
    value = {
        **prior,
        "benchmark": "delegation-queue#84 Luna vs Gemini evidence extraction",
        "status": status,
        "updated_at_utc": utc_now(),
        "writable_scope": "scratch worktree only; no source corpus or system state modified",
        "reference_bundle": relhome(REF),
        "paper_ids": PAPER_IDS,
        "rate_card_usd_per_million": RATE_CARD,
        "rate_card_basis": "DQ79 cached cost-report.json and dq79-ai-papers-routing-eval.md; estimates, not invoices",
        "prompt_sha256": prompt_hashes if prompt_hashes is not None else prior.get("prompt_sha256", {}),
        "compatibility_check": {
            "all_match": input_check.get("all_match") if input_check else prior.get("compatibility_check", {}).get("all_match"),
            "matches": sum(bool(x.get("matches")) for x in input_check.get("papers", [])) if input_check else prior.get("compatibility_check", {}).get("matches"),
            "papers": len(input_check.get("papers", [])) if input_check else prior.get("compatibility_check", {}).get("papers"),
        },
        "artifacts": prior.get("artifacts", []),
    }
    if extra:
        value.update(extra)
    write_json(path, value)


def prepare() -> None:
    for path in ("raw/prompts", "raw/responses/probes", "raw/responses/armA/openai",
                 "raw/responses/armB/gemini", "raw/responses/armB/openai",
                 "raw/responses/judge/gemini", "raw/responses/judge/deepseek",
                 "raw/judge", "public/metrics", "public/prompts", "public/representative-outputs"):
        (ROOT / path).mkdir(parents=True, exist_ok=True)
    reused = copy_reuse_files()
    ctx = context()
    prompt_hashes = write_prompts(ctx)
    check = compatibility_check(ctx)
    environment = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "requests": importlib.import_module("requests").__version__,
        "timezone": "UTC",
        "reference_versions": {
            "DQ79 report": relhome(REF / "dq79-ai-papers-routing-eval.md"),
            "provider": relhome(REF / "scratch/provider.py"),
            "run_l2": relhome(REF / "scratch/run_l2.py"),
            "run_l3": relhome(REF / "scratch/run_l3.py"),
            "l2_metrics": relhome(REF / "scratch/l2_metrics.py"),
            "l3_metrics": relhome(REF / "scratch/l3_metrics.py"),
        },
        "copied_reuse_files": reused,
    }
    manifest_update("prepared", prompt_hashes, check, {
        "environment": environment,
        "network_policy": "provider requests only; allowlisted API hosts with redirects disabled",
        "all_provider_attempts_included_in_cost": True,
        "budget_cap_usd": 8.0,
    })
    (ROOT / "raw/capability-probes.json").write_text(json.dumps({
        "status": "pending",
        "probes": {},
        "required_settings": {
            "openai": {"model_id_sent": "gpt-6-luna", "endpoint": "https://api.openai.com/v1/chat/completions", "reasoning_effort": "none", "response_format": "json_schema strict canonical OUTPUT_SCHEMA", "max_completion_tokens": 3600},
            "gemini": {"model_id_sent": "gemini-3.5-flash-lite", "endpoint": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent", "thinkingConfig": {"thinkingLevel": "low"}, "responseMimeType": "application/json", "maxOutputTokens": 3000},
        },
        "verification_method": "One tiny provider smoke call each before matrix; at most one second targeted smoke call if the first fails.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for filename in ("armA-results.json", "armB-results.json"):
        p = ROOT / "raw" / filename
        if not p.exists():
            write_json(p, {"status": "pending", "papers_target": len(PAPER_IDS), "papers": {}})
    p = ROOT / "raw/judge-results.json"
    if not p.exists():
        write_json(p, {"status": "pending", "papers_target": len(PAPER_IDS), "judges": {}})
    create_report_skeleton("prepared; D input compatibility check complete")
    write_progress("prepared")
    print(json.dumps({"prepared": True, "compatibility_check": check["all_match"],
                      "prompt_sha256": prompt_hashes}, indent=2))


def guarded_requests(provider) -> None:
    original = provider.requests.request

    def request(method, url, **kwargs):
        host = urlparse(url).hostname
        if host not in ALLOWED_HOSTS:
            raise RuntimeError("blocked non-provider network host")
        kwargs["allow_redirects"] = False
        return original(method, url, **kwargs)

    provider.requests.request = request


def completion_finish(provider_name: str, payload: dict | None) -> str | None:
    if not payload:
        return None
    if provider_name in ("openai", "deepseek"):
        return ((payload.get("choices") or [{}])[0] or {}).get("finish_reason")
    candidates = payload.get("candidates") or []
    return (candidates[0] or {}).get("finishReason") if candidates else None


def is_truncated(provider_name: str, payload: dict | None) -> bool:
    finish = (completion_finish(provider_name, payload) or "").upper()
    if provider_name == "gemini":
        return finish in {"MAX_TOKENS", "MAX_OUTPUT_TOKENS"}
    return finish in {"LENGTH", "MAX_TOKENS"}


def estimate_usd(provider_name: str, body: dict, max_output: int) -> float:
    rates = RATE_CARD[provider_name]
    input_est = len(json.dumps(body, ensure_ascii=False).encode("utf-8")) / 3.0
    return ((input_est * rates["input"]) + (max_output * rates["output"])) / 1_000_000 + 0.001


def persist_attempt_metadata(provider, history: list[dict], metadata: dict) -> None:
    for row in history:
        path = ROOT / row["artifact"]
        item = read_json(path)
        item.update(metadata)
        provider.write_json(path, item)


def call_with_truncation_retry(*, ctx: dict, provider_name: str, call_id: str,
                               arm_id: str, model_id: str, endpoint: str,
                               settings: dict, body: dict, headers: dict,
                               out_dir: str, max_output: int,
                               input_sha256: str,
                               retry_suffix: str) -> tuple[dict | None, list[dict], dict]:
    provider = ctx["provider"]
    provider.assert_budget(estimate_usd(provider_name, body, max_output))
    payload, history = provider.request_json(
        provider=provider_name, call_id=call_id, arm_id=arm_id,
        model_id=model_id, endpoint=endpoint, settings=settings, body=body,
        headers=headers, timeout=300, out_dir=out_dir, max_retries=2,
        retry_backoff=2.0,
    )
    persist_attempt_metadata(provider, history, {"input_sha256": input_sha256})
    adjustments = {"truncation_retry": False, "retry_input_sha256": None}
    if payload and is_truncated(provider_name, payload):
        short_body = copy.deepcopy(body)
        if provider_name == "openai":
            short_body["messages"][-1]["content"] += "\n\n" + retry_suffix
        elif provider_name == "gemini":
            short_body["contents"][0]["parts"][0]["text"] += "\n\n" + retry_suffix
        retry_hash = sha256_bytes(json.dumps(short_body, ensure_ascii=False, sort_keys=True).encode("utf-8"))
        provider.assert_budget(estimate_usd(provider_name, short_body, max_output))
        payload2, history2 = provider.request_json(
            provider=provider_name, call_id=call_id + "-short-output-retry",
            arm_id=arm_id, model_id=model_id, endpoint=endpoint,
            settings=settings, body=short_body, headers=headers, timeout=300,
            out_dir=out_dir, max_retries=2, retry_backoff=2.0,
        )
        persist_attempt_metadata(provider, history2, {
            "retry_reason": "provider finish reason indicated max-token truncation",
            "output_instruction_adjustment": retry_suffix,
            "input_sha256": retry_hash,
        })
        history += history2
        payload = payload2
        adjustments = {"truncation_retry": True, "retry_input_sha256": retry_hash,
                      "retry_artifacts": [h["artifact"] for h in history2]}
    return payload, history, adjustments


def native_schema_errors(value: object, schema: dict, path: str = "$root") -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            return [f"{path}: expected object"]
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}.{key}: required field missing")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{path}.{key}: extra property")
        for key, child in props.items():
            if key in value:
                errors.extend(native_schema_errors(value[key], child, f"{path}.{key}"))
    elif expected == "array":
        if not isinstance(value, list):
            return [f"{path}: expected array"]
        for idx, item in enumerate(value):
            errors.extend(native_schema_errors(item, schema.get("items", {}), f"{path}[{idx}]"))
    elif expected == "string":
        if not isinstance(value, str):
            errors.append(f"{path}: expected string")
    elif expected == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            errors.append(f"{path}: expected integer")
    elif expected == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            errors.append(f"{path}: expected number")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: enum violation")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum")
    return errors


def decode_generation(ctx: dict, provider_name: str, payload: dict | None,
                      pages: dict[int, str]) -> dict:
    run_l3 = ctx["run_l3"]
    result: dict = {
        "finish_reason": completion_finish(provider_name, payload),
        "provider_echoed_model_id": payload.get("model") if provider_name == "openai" and payload else None,
        "provider_echoed_model_version": payload.get("modelVersion") if provider_name == "gemini" and payload else None,
        "raw_output": None,
        "canonical_output": None,
        "canonicalization": None,
        "native_schema_errors": [],
        "normalized_schema_errors": [],
        "deterministic_checks": None,
        "parse_error": None,
    }
    if not payload:
        result["provider_error"] = "no model response"
        return result
    raw_text = run_l3.response_text(provider_name, payload)
    result["raw_output_text"] = raw_text
    try:
        raw_obj = extract_json(raw_text)
        canonical, mapping = run_l3.canonicalize(raw_obj)
        result["raw_output"] = raw_obj
        result["canonical_output"] = canonical
        result["canonicalization"] = mapping
        result["native_schema_errors"] = native_schema_errors(raw_obj, run_l3.OUTPUT_SCHEMA)
        result["normalized_schema_errors"] = native_schema_errors(canonical, run_l3.OUTPUT_SCHEMA)
        result["deterministic_checks"] = run_l3.check_output(canonical, pages)
    except (ValueError, json.JSONDecodeError) as exc:
        result["parse_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    return result


def packet_from_output(parsed: dict) -> dict:
    return {
        "candidate_claims": parsed.get("candidate_claims") if isinstance(parsed.get("candidate_claims"), list) else [],
        "key_claims": parsed.get("key_claims") if isinstance(parsed.get("key_claims"), list) else [],
        "limitations": parsed.get("limitations") if isinstance(parsed.get("limitations"), list) else [],
        "load_bearing_pages": parsed.get("load_bearing_pages") if isinstance(parsed.get("load_bearing_pages"), list) else [],
    }


def packet_schema_issues(packet: dict) -> list[str]:
    errors = []
    if not all(isinstance(packet.get(key), list) for key in (
            "candidate_claims", "key_claims", "limitations", "load_bearing_pages")):
        errors.append("required packet fields must be arrays")
    for i, item in enumerate(packet.get("candidate_claims", [])):
        if not isinstance(item, dict) or not isinstance(item.get("claim"), str):
            errors.append(f"candidate_claims[{i}] must contain a string claim")
            continue
        if item.get("importance") not in {"load_bearing", "supporting"}:
            errors.append(f"candidate_claims[{i}] importance must be load_bearing or supporting")
        if not isinstance(item.get("evidence_refs"), list):
            errors.append(f"candidate_claims[{i}] evidence_refs must be an array")
            continue
        for j, ref in enumerate(item["evidence_refs"]):
            if not isinstance(ref, dict) or not isinstance(ref.get("page"), int) or not isinstance(ref.get("quote"), str):
                errors.append(f"candidate_claims[{i}].evidence_refs[{j}] requires integer page and string quote")
    if any(not isinstance(x, str) for x in packet.get("key_claims", [])):
        errors.append("key_claims must contain strings")
    if any(not isinstance(x, str) for x in packet.get("limitations", [])):
        errors.append("limitations must contain strings")
    if any(isinstance(x, bool) or not isinstance(x, int) for x in packet.get("load_bearing_pages", [])):
        errors.append("load_bearing_pages must contain integers")
    return errors


def packet_claims(packet: dict) -> list[dict]:
    claims = []
    for item in packet.get("candidate_claims", []):
        if isinstance(item, dict) and isinstance(item.get("claim"), str):
            claims.append(item)
    for item in packet.get("key_claims", []):
        if isinstance(item, str):
            claims.append({"claim": item, "evidence_refs": []})
        elif isinstance(item, dict) and isinstance(item.get("claim"), str):
            claims.append(item)
    seen = set()
    result = []
    for claim in claims:
        key = claim.get("claim", "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(claim)
    return result


def make_luna_body(ctx: dict, user_text: str) -> tuple[str, dict, dict, dict]:
    return ctx["run_l3"].gen_request("openai", "gpt-6-luna", user_text)


def save_checkpoint(filename: str, value: dict) -> None:
    write_json(ROOT / "raw" / filename, value)
    write_progress(f"updated {filename}")


def provider_is_hard_outage(history: list[dict]) -> bool:
    if not history:
        return True
    last = history[-1]
    status = last.get("http_status")
    error = str(last.get("error") or "").lower()
    if status in (401, 403):
        return True
    return status is None and any(x in error for x in (
        "name or service not known", "name resolution", "getaddrinfo",
        "connectionerror", "connecttimeout", "connection refused", "temporary failure in name",
        "dns", "tls", "sslerror",
    ))


def run_openai_probe(ctx: dict, probe_no: int = 1) -> dict:
    provider = ctx["provider"]
    l3 = ctx["run_l3"]
    user = "For this tiny settings probe, return the smallest valid paper_insight artifact with empty arrays and no citations."
    endpoint, settings, body, headers = l3.gen_request("openai", "gpt-6-luna", user)
    settings = {**settings, "probe": True}
    call_id = f"dq84-probe-openai-{probe_no}"
    body_hash = sha256_bytes(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    payload, history, retry = call_with_truncation_retry(
        ctx=ctx, provider_name="openai", call_id=call_id, arm_id="dq84-capability-probe",
        model_id="gpt-6-luna", endpoint=endpoint, settings=settings, body=body,
        headers=headers, out_dir="probes", max_output=3600, input_sha256=body_hash,
        retry_suffix="Use empty arrays where allowed and keep every required key; no optional prose.",
    )
    decode = decode_generation(ctx, "openai", payload, {})
    passed = bool(payload and not decode.get("parse_error") and not decode.get("native_schema_errors"))
    return {
        "provider": "openai", "model_id_sent": "gpt-6-luna",
        "endpoint": endpoint, "settings": settings, "http_status": history[-1].get("http_status") if history else None,
        "attempt_artifacts": [h["artifact"] for h in history],
        "usage": history[-1].get("usage") if history else None,
        "response_model_id": decode.get("provider_echoed_model_id"),
        "finish_reason": decode.get("finish_reason"),
        "native_schema_pass": not bool(decode.get("native_schema_errors")),
        "parse_error": decode.get("parse_error"), "retry": retry,
        "passed": passed,
    }


def run_gemini_probe(ctx: dict, probe_no: int = 1) -> dict:
    provider = ctx["provider"]
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
    settings = {
        "thinkingConfig": {"thinkingLevel": "low"},
        "responseMimeType": "application/json", "maxOutputTokens": 3000,
        "probe": True,
    }
    body = {
        "systemInstruction": {"parts": [{"text": "Return only the exact JSON object requested by the user."}]},
        "contents": [{"role": "user", "parts": [{"text": "Return exactly {\"probe\":\"ok\"}."}]}],
        "generationConfig": {
            "responseMimeType": "application/json", "maxOutputTokens": 3000,
            "thinkingConfig": {"thinkingLevel": "low"},
        },
    }
    body_hash = sha256_bytes(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    payload, history, retry = call_with_truncation_retry(
        ctx=ctx, provider_name="gemini", call_id=f"dq84-probe-gemini-{probe_no}",
        arm_id="dq84-capability-probe", model_id="gemini-3.5-flash-lite",
        endpoint=endpoint, settings=settings, body=body,
        headers=provider.gemini_headers(), out_dir="probes", max_output=3000,
        input_sha256=body_hash,
        retry_suffix="Return only the one requested JSON object with no extra fields.",
    )
    text = provider.extract_text("gemini", payload) if payload else ""
    try:
        parsed = extract_json(text)
    except (ValueError, json.JSONDecodeError):
        parsed = None
    passed = bool(payload and isinstance(parsed, dict) and parsed.get("probe") == "ok")
    return {
        "provider": "gemini", "model_id_sent": "gemini-3.5-flash-lite",
        "endpoint": endpoint, "settings": settings,
        "http_status": history[-1].get("http_status") if history else None,
        "attempt_artifacts": [h["artifact"] for h in history],
        "usage": history[-1].get("usage") if history else None,
        "response_model_id": (payload or {}).get("model"),
        "response_model_version": (payload or {}).get("modelVersion"),
        "finish_reason": completion_finish("gemini", payload),
        "response_parsed": parsed, "retry": retry, "passed": passed,
    }


def run_probes(ctx: dict) -> dict:
    path = ROOT / "raw/capability-probes.json"
    saved = read_json(path)
    probes = saved.get("probes", {})
    provider = ctx["provider"]
    for name, func in (("openai", run_openai_probe), ("gemini", run_gemini_probe)):
        if probes.get(name, {}).get("passed"):
            continue
        history = probes.get(name, {}).get("history", [])
        # One smoke call, plus at most one targeted repeat when the first fails.
        attempt_no = len(history) + 1
        try:
            result = func(ctx, attempt_no)
        except (KeyError, RuntimeError, Exception) as exc:
            result = {
                "provider": name, "passed": False,
                "local_error": provider.sanitize(f"{type(exc).__name__}: {exc}"),
                "attempt_artifacts": [], "settings": saved["required_settings"].get(name),
            }
        history.append(result)
        probes[name] = {"passed": bool(result.get("passed")), "history": history,
                        "latest": result}
        if not result.get("passed") and len(history) < 2:
            try:
                result = func(ctx, len(history) + 1)
            except Exception as exc:
                result = {"provider": name, "passed": False,
                          "local_error": provider.sanitize(f"{type(exc).__name__}: {exc}"),
                          "attempt_artifacts": [], "settings": saved["required_settings"].get(name)}
            history.append(result)
            probes[name] = {"passed": bool(result.get("passed")), "history": history,
                            "latest": result}
        saved["probes"] = probes
        saved["status"] = "complete" if all(probes.get(p, {}).get("passed") for p in ("openai", "gemini")) else "partial_or_blocked"
        write_json(path, saved)
        manifest_update("probes complete" if saved["status"] == "complete" else "probe failure recorded")
        write_progress(saved["status"])
    return saved


def luna_user_from_reference(ctx: dict, pid: str, packet_text: str | None = None) -> tuple[str, dict[int, str], str]:
    paper = ctx["papers"][pid]
    reference, pages, method = ctx["run_l3"].paper_sources(
        paper, {}, ctx["text_map"], "full_reference"
    )
    if packet_text is None:
        return reference, pages, method
    metadata, sep, _ = reference.partition("\nSOURCE METHOD:")
    if not sep:
        raise ValueError("Could not isolate canonical metadata block in run_l3.paper_sources")
    b_method = "Gemini Flash-Lite structured evidence packet extracted from the full page-labelled paper text"
    return metadata + "\nSOURCE METHOD: " + b_method + "\nSOURCE:\n" + packet_text, pages, b_method


def call_luna(ctx: dict, *, pid: str, arm: str, user_text: str,
              pages: dict[int, str]) -> dict:
    provider = ctx["provider"]
    endpoint, settings, body, headers = make_luna_body(ctx, user_text)
    body_hash = sha256_bytes(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    method = "armA" if arm == "A" else "armB"
    call_id = f"dq84-{method}-luna-{pid}"
    payload, history, retry = call_with_truncation_retry(
        ctx=ctx, provider_name="openai", call_id=call_id, arm_id=f"dq84-{method}",
        model_id="gpt-6-luna", endpoint=endpoint, settings=settings, body=body,
        headers=headers, out_dir=f"{method}/openai", max_output=3600,
        input_sha256=body_hash,
        retry_suffix="Keep the artifact compact: one insight, at most two key claims and two evidence items, and minimal limitations; retain every required key and page citation.",
    )
    persist_attempt_metadata(provider, history, {
        "paper_id": pid, "architecture_arm": arm,
        "user_content_sha256": sha256_bytes(user_text.encode("utf-8")),
        "source_method": "strategy-D complete page-labelled PyMuPDF text extraction" if arm == "A" else "Gemini Flash-Lite structured evidence packet extracted from the full page-labelled paper text",
    })
    decoded = decode_generation(ctx, "openai", payload, pages)
    return {
        "provider": "openai", "model_id_sent": "gpt-6-luna",
        "request_body_sha256": body_hash,
        "user_content_sha256": sha256_bytes(user_text.encode("utf-8")),
        "user_content_bytes": len(user_text.encode("utf-8")),
        "settings": settings, "http_status": history[-1].get("http_status") if history else None,
        "latency_ms_attempt_sum": sum(int(h.get("latency_ms") or 0) for h in history),
        "attempt_artifacts": [h["artifact"] for h in history],
        "attempt_usage": [h.get("usage") for h in history],
        "retry": retry, **decoded,
        "completed": bool(payload),
    }


def call_gemini_packet(ctx: dict, *, pid: str) -> dict:
    provider, l2 = ctx["provider"], ctx["run_l2"]
    paper = ctx["papers"][pid]
    full_text = l2.all_pdf_text(None, ctx["text_map"], pid)
    prompt = l2.prompt_for("D", paper, full_text)
    cap = read_json(REF / "raw/capability-probes.json")
    thinking = cap["providers"]["gemini"]["primary_thinking_config"]
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
    settings = {"thinkingConfig": thinking, "responseMimeType": "application/json",
                "maxOutputTokens": 3000, "strategy": "D", "round": 1,
                "page_numbers": None}
    body = d_body(prompt, thinking)
    body_hash = sha256_bytes(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    payload, history, retry = call_with_truncation_retry(
        ctx=ctx, provider_name="gemini", call_id=f"dq84-B-gemini-packet-{pid}",
        arm_id="dq84-B-gemini-packet", model_id="gemini-3.5-flash-lite",
        endpoint=endpoint, settings=settings, body=body,
        headers=provider.gemini_headers(), out_dir="armB/gemini",
        max_output=3000, input_sha256=body_hash,
        retry_suffix="Return only the required compact D JSON packet: keep up to two candidate claims, two key claims, three limitations, and five load-bearing pages; preserve page citations and numeric results.",
    )
    persist_attempt_metadata(provider, history, {
        "paper_id": pid, "strategy": "D", "input_text_bytes": len(prompt.encode("utf-8")),
        "page_labelled_full_text_bytes": len(full_text.encode("utf-8")),
        "input_text_sha256": sha256_bytes(prompt.encode("utf-8")),
    })
    result = {
        "provider": "gemini", "model_id_sent": "gemini-3.5-flash-lite",
        "request_body_sha256": body_hash,
        "input_text_sha256": sha256_bytes(prompt.encode("utf-8")),
        "input_text_bytes": len(prompt.encode("utf-8")),
        "page_labelled_full_text_bytes": len(full_text.encode("utf-8")),
        "settings": settings, "http_status": history[-1].get("http_status") if history else None,
        "latency_ms_attempt_sum": sum(int(h.get("latency_ms") or 0) for h in history),
        "attempt_artifacts": [h["artifact"] for h in history],
        "attempt_usage": [h.get("usage") for h in history], "retry": retry,
        "finish_reason": completion_finish("gemini", payload),
        "provider_echoed_model_id": (payload or {}).get("model"),
        "provider_echoed_model_version": (payload or {}).get("modelVersion"),
        "parsed_packet": None, "serialized_packet": None,
        "packet_serialization": "Select exactly candidate_claims, key_claims, limitations, load_bearing_pages from the D JSON; missing or wrong-typed fields become empty arrays; serialize UTF-8 with sorted keys, compact separators, ensure_ascii=false.",
        "parse_error": None, "completed": bool(payload),
    }
    if payload:
        try:
            output = extract_json(provider.extract_text("gemini", payload))
            packet = packet_from_output(output)
            result["parsed_packet"] = packet
            result["serialized_packet"] = canonical_json(packet)
            result["packet_schema_errors"] = packet_schema_issues(packet)
            result["packet_schema_pass"] = not result["packet_schema_errors"]
        except (ValueError, json.JSONDecodeError) as exc:
            result["parse_error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
    return result


def arm_checkpoint(name: str) -> dict:
    path = ROOT / "raw" / f"arm{name}-results.json"
    return read_json(path) if path.exists() else {"status": "running", "papers_target": len(PAPER_IDS), "papers": {}}


def run_arm_a(ctx: dict, can_run: bool) -> dict:
    state = arm_checkpoint("A")
    if not can_run:
        state["status"] = "blocked: OpenAI capability probe failed after two targeted attempts"
        save_checkpoint("armA-results.json", state)
        return state
    state.setdefault("papers", {})
    outage = state.get("provider_outage")
    for pid in PAPER_IDS:
        if state["papers"].get(pid, {}).get("completed"):
            continue
        if outage:
            break
        started = time.perf_counter()
        user_text, pages, method = luna_user_from_reference(ctx, pid)
        cell = {
            "paper_id": pid, "source_method": method,
            "page_count": len(pages), "input_pages": sorted(pages),
            "input_user_text_sha256": sha256_bytes(user_text.encode("utf-8")),
            "started_at_utc": utc_now(),
        }
        try:
            generated = call_luna(ctx, pid=pid, arm="A", user_text=user_text, pages=pages)
        except Exception as exc:
            generated = {"completed": False, "local_error": ctx["provider"].sanitize(f"{type(exc).__name__}: {exc}"), "attempt_artifacts": []}
        cell.update(generated)
        cell["end_to_end_latency_ms"] = int((time.perf_counter() - started) * 1000)
        cell["completed"] = True
        state["papers"][pid] = cell
        history = []
        if generated.get("attempt_artifacts"):
            last_path = ROOT / generated["attempt_artifacts"][-1]
            if last_path.exists():
                history = [read_json(ROOT / item) for item in generated["attempt_artifacts"]]
        if not generated.get("canonical_output") and provider_is_hard_outage(history):
            state["provider_outage"] = {
                "paper_id": pid,
                "reason": "matrix call failed before model response with authentication or connection/DNS failure after the capability probe passed",
                "provider": "openai",
            }
            outage = state["provider_outage"]
        state["status"] = "running"
        save_checkpoint("armA-results.json", state)
    if state.get("provider_outage"):
        state["status"] = "outage; remaining arm-A papers not attempted"
    elif len(state["papers"]) >= len(PAPER_IDS):
        state["status"] = "complete"
    else:
        state["status"] = "partial"
    save_checkpoint("armA-results.json", state)
    return state


def run_arm_b(ctx: dict, gemini_can_run: bool, openai_can_run: bool) -> dict:
    state = arm_checkpoint("B")
    state.setdefault("papers", {})
    if not gemini_can_run:
        state["status"] = "blocked: Gemini capability probe failed after two targeted attempts"
        save_checkpoint("armB-results.json", state)
        return state
    for pid in PAPER_IDS:
        row = state["papers"].setdefault(pid, {"paper_id": pid})
        if row.get("completed"):
            continue
        started = time.perf_counter()
        if not row.get("gemini_stage"):
            try:
                row["gemini_stage"] = call_gemini_packet(ctx, pid=pid)
            except Exception as exc:
                row["gemini_stage"] = {
                    "completed": False, "local_error": ctx["provider"].sanitize(f"{type(exc).__name__}: {exc}"),
                    "attempt_artifacts": [],
                }
            save_checkpoint("armB-results.json", state)
        stage1 = row["gemini_stage"]
        packet_text = stage1.get("serialized_packet")
        if not packet_text:
            row["completed"] = True
            row["status"] = "extraction stage failed or returned unparseable JSON; Luna hand-off unavailable"
            row["end_to_end_latency_ms"] = int((time.perf_counter() - started) * 1000)
            save_checkpoint("armB-results.json", state)
            continue
        if not openai_can_run:
            row["completed"] = True
            row["status"] = "Gemini packet completed; Luna final stage blocked by failed OpenAI probe"
            row["end_to_end_latency_ms"] = int((time.perf_counter() - started) * 1000)
            save_checkpoint("armB-results.json", state)
            continue
        user_text, pages, method = luna_user_from_reference(ctx, pid, packet_text)
        row["handoff"] = {
            "serialization": stage1["packet_serialization"],
            "packet_sha256": sha256_bytes(packet_text.encode("utf-8")),
            "packet_bytes": len(packet_text.encode("utf-8")),
            "metadata_matches_armA": True,
            "only_luna_prompt_changes": "SOURCE METHOD line and SOURCE payload; system prompt, prefix, and metadata block are copied from arm-A full_reference call shape.",
        }
        try:
            row["luna_stage"] = call_luna(ctx, pid=pid, arm="B", user_text=user_text, pages=pages)
        except Exception as exc:
            row["luna_stage"] = {"completed": False,
                                  "local_error": ctx["provider"].sanitize(f"{type(exc).__name__}: {exc}"),
                                  "attempt_artifacts": []}
        row["status"] = "complete" if row["luna_stage"].get("canonical_output") else "Luna final stage returned no canonical output"
        row["completed"] = True
        row["source_method"] = method
        row["page_count"] = len(pages)
        row["end_to_end_latency_ms"] = int((time.perf_counter() - started) * 1000)
        # A failed authentication/DNS/connection response is an arm-wide outage; retain this cell and stop.
        if not row["luna_stage"].get("canonical_output"):
            refs = [ROOT / item for item in row["luna_stage"].get("attempt_artifacts", [])]
            hist = [read_json(p) for p in refs if p.exists()]
            if provider_is_hard_outage(hist):
                state["provider_outage"] = {
                    "paper_id": pid, "stage": "luna", "provider": "openai",
                    "reason": "matrix call failed before model response with authentication or connection/DNS failure after the capability probe passed",
                }
                save_checkpoint("armB-results.json", state)
                break
        save_checkpoint("armB-results.json", state)
    if state.get("provider_outage"):
        state["status"] = "partial; provider outage stopped remaining B final stages"
    elif sum(bool(x.get("completed")) for x in state["papers"].values()) >= len(PAPER_IDS):
        state["status"] = "complete"
    else:
        state["status"] = "partial"
    save_checkpoint("armB-results.json", state)
    return state


def judge_prompt(ctx: dict, pid: str, label_to_arm: dict,
                 armA: dict, armB: dict) -> str:
    pages = ctx["text_map"][pid]
    by_num = {i + 1: value for i, value in enumerate(pages)}
    cited = set()
    for cell in (armA, armB):
        out = cell.get("canonical_output") or {}
        items = (out.get("paper") or {}).get("key_claims", []) + (out.get("paper") or {}).get("evidence", []) + out.get("insights", [])
        for item in items:
            for ref in item.get("evidence_refs", []) if isinstance(item, dict) else []:
                page = ref.get("page") if isinstance(ref, dict) else None
                if isinstance(page, int) and page in by_num:
                    cited.add(page)
    candidate_rows = []
    for label, arm in label_to_arm.items():
        cell = armA if arm == "A" else armB
        candidate_rows.append({"blind_label": label, "artifact": cell.get("canonical_output"),
                               "cited_pages_source_text": [{"page": n, "text": by_num[n]} for n in sorted(cited)]})
    prompt = {
        "paper_id": pid,
        "agenda_context": ctx["agenda"],
        "instruction": (
            "Independently score both artifacts against only their cited source pages and the agenda. "
            "Do not guess generator identity or convert any preference/winner statement into numeric scores. "
            "Give each dimension an integer from 0 (poor/unsupported) to 4 (strong), plus one brief reason. "
            "Uncertainty calibration is not scored because no confidence/outcome series exists; do not add that dimension. "
            "Return JSON only with exactly one score object for blind labels A and B."
        ),
        "required_dimensions": DIMENSIONS,
        "blind_candidates": candidate_rows,
    }
    return json.dumps(prompt, ensure_ascii=False, separators=(",", ":"))


def judge_schema_issues(output: object) -> list[str]:
    errors = []
    if not isinstance(output, dict) or not isinstance(output.get("scores"), list):
        return ["scores must be an array"]
    rows = output["scores"]
    labels = [x.get("blind_label") for x in rows if isinstance(x, dict)]
    if sorted(labels) != ["A", "B"]:
        errors.append("expected exactly one score object for blind labels A and B")
    for row in rows:
        if not isinstance(row, dict):
            errors.append("score row must be an object")
            continue
        for dim in DIMENSIONS:
            value = row.get(dim)
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 4:
                errors.append(f"{row.get('blind_label')}.{dim} must be an integer 0..4")
        if not isinstance(row.get("brief_reason"), str) or not row.get("brief_reason", "").strip():
            errors.append(f"{row.get('blind_label')}.brief_reason must be a nonempty string")
    return errors


def call_judge(ctx: dict, *, provider_name: str, model_id: str,
               pid: str, prompt: str, label_to_arm: dict) -> dict:
    provider = ctx["provider"]
    if provider_name == "gemini":
        endpoint = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"
        system = "You are an independent blind judge of evidence-grounded paper insight artifacts."
        settings = {"thinkingConfig": {"thinkingLevel": "low"}, "responseMimeType": "application/json",
                    "maxOutputTokens": 2200, "blind": True, "dimensions": DIMENSIONS}
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 2200,
                                 "thinkingConfig": {"thinkingLevel": "low"}},
        }
        headers = provider.gemini_headers()
        max_output = 2200
    else:
        endpoint = "https://api.deepseek.com/chat/completions"
        system = (
            "You are an independent blind judge of evidence-grounded paper insight artifacts. "
            "Return JSON only; score each candidate from 0 to 4 for every required dimension and give a brief reason."
        )
        settings = {"reasoning_effort": "none", "response_format": "json_object",
                    "max_tokens": 2200, "blind": True, "dimensions": DIMENSIONS}
        body = {
            "model": model_id,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "reasoning_effort": "none", "max_tokens": 2200,
            "response_format": {"type": "json_object"},
        }
        headers = provider.chat_headers("deepseek")
        max_output = 2200
    request_hash = sha256_bytes(json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    payload, history, retry = call_with_truncation_retry(
        ctx=ctx, provider_name=provider_name,
        call_id=f"dq84-judge-{provider_name}-{pid}", arm_id=f"dq84-blind-judge-{provider_name}",
        model_id=model_id, endpoint=endpoint, settings=settings, body=body,
        headers=headers, out_dir=f"judge/{provider_name}", max_output=max_output,
        input_sha256=request_hash,
        retry_suffix="Keep each reason to one short sentence and retain every required score field.",
    )
    raw_text = provider.extract_text(provider_name, payload) if payload else ""
    parsed = None
    parse_error = None
    if payload:
        try:
            parsed = extract_json(raw_text)
        except (ValueError, json.JSONDecodeError) as exc:
            parse_error = f"{type(exc).__name__}: {str(exc)[:300]}"
    persist_attempt_metadata(provider, history, {"paper_id": pid, "blind": True, "judge_provider": provider_name})
    return {
        "provider": provider_name, "model_id_sent": model_id,
        "provider_echoed_model_id": (payload or {}).get("model"),
        "provider_echoed_model_version": (payload or {}).get("modelVersion"),
        "request_body_sha256": request_hash, "settings": settings,
        "http_status": history[-1].get("http_status") if history else None,
        "attempt_artifacts": [h["artifact"] for h in history],
        "attempt_usage": [h.get("usage") for h in history],
        "latency_ms_attempt_sum": sum(int(h.get("latency_ms") or 0) for h in history),
        "retry": retry, "output": parsed, "parse_error": parse_error,
        "schema_issues": judge_schema_issues(parsed),
        "schema_pass": not bool(judge_schema_issues(parsed)),
        "label_to_arm_internal": label_to_arm,
        "completed": bool(payload),
    }


def run_judges(ctx: dict, arm_a: dict, arm_b: dict,
               gemini_can_run: bool, deepseek_available: bool) -> dict:
    path = ROOT / "raw/judge-results.json"
    state = read_json(path)
    state.setdefault("judges", {})
    map_path = ROOT / "raw/judge/judge-map.json"
    mapping = read_json(map_path) if map_path.exists() else {"design": "labels permuted deterministically per paper", "papers": {}}
    gemini_count = sum(bool(x.get("schema_pass")) for x in state["judges"].values() if x.get("provider") == "gemini")
    deepseek_enabled = bool(deepseek_available)
    deepseek_probe_results = []
    for pid in PAPER_IDS:
        a = arm_a.get("papers", {}).get(pid, {})
        b = arm_b.get("papers", {}).get(pid, {}).get("luna_stage", {})
        if not isinstance(a.get("canonical_output"), dict) or not isinstance(b.get("canonical_output"), dict):
            continue
        if pid not in mapping["papers"]:
            labels = ["A", "B"]
            seed = int(sha256_bytes(f"dq84/{pid}".encode())[:8], 16)
            random.Random(seed).shuffle(labels)
            mapping["papers"][pid] = {
                "label_to_arm": {labels[0]: "A", labels[1]: "B"},
                "shuffle_seed_sha256": sha256_bytes(f"dq84/{pid}".encode()),
            }
            write_json(map_path, mapping)
        label_map = mapping["papers"][pid]["label_to_arm"]
        prompt = judge_prompt(ctx, pid, label_map, a, b)
        for judge_provider in ("gemini", "deepseek"):
            if judge_provider == "gemini" and not gemini_can_run:
                continue
            if judge_provider == "deepseek" and not deepseek_enabled:
                continue
            key = f"{pid}/{judge_provider}"
            if key in state["judges"]:
                continue
            try:
                scored = call_judge(
                    ctx, provider_name=judge_provider,
                    model_id="gemini-3.5-flash-lite" if judge_provider == "gemini" else "deepseek-flash",
                    pid=pid, prompt=prompt, label_to_arm=label_map,
                )
            except Exception as exc:
                scored = {"provider": judge_provider, "completed": False,
                          "local_error": ctx["provider"].sanitize(f"{type(exc).__name__}: {exc}"),
                          "schema_pass": False, "schema_issues": ["local provider call error"],
                          "attempt_artifacts": [], "label_to_arm_internal": label_map}
            state["judges"][key] = scored
            save_checkpoint("judge-results.json", state)
            if judge_provider == "deepseek":
                deepseek_probe_results.append(bool(scored.get("schema_pass")))
                if len(deepseek_probe_results) >= 2 and not all(deepseek_probe_results):
                    state["deepseek_second_judge"] = "stopped after first two pair cells were not both schema-compliant; Gemini remains the primary judge"
                    deepseek_enabled = False
                    save_checkpoint("judge-results.json", state)
                elif len(deepseek_probe_results) >= 2 and all(deepseek_probe_results):
                    state["deepseek_second_judge"] = "first two pair cells were schema-compliant; completed remaining eligible papers"
            elif judge_provider == "gemini":
                gemini_count += bool(scored.get("schema_pass"))
    state["status"] = "complete" if len(state["judges"]) else "no eligible paired judge cells"
    state["uncertainty_calibration"] = "N/A: no confidence/outcome series"
    state["deepseek_second_judge"] = state.get("deepseek_second_judge", (
        "not run: DEEPSEEK_API_KEY unavailable" if not deepseek_available else
        "not run: primary Gemini judge was sufficient; optional second judge not selected"
    ))
    save_checkpoint("judge-results.json", state)
    return state


def write_progress(status: str) -> None:
    def safe_state(name: str) -> dict:
        try:
            return read_json(ROOT / "raw" / name)
        except (OSError, json.JSONDecodeError):
            return {}
    a, b, j = safe_state("armA-results.json"), safe_state("armB-results.json"), safe_state("judge-results.json")
    cap = safe_state("capability-probes.json")
    a_done = sum(bool(x.get("completed")) for x in a.get("papers", {}).values())
    b_done = sum(bool(x.get("completed")) for x in b.get("papers", {}).values())
    judged = len(j.get("judges", {}))
    try:
        p, _, _, _, _ = load_modules()
        totals = p.rolling_totals()
    except Exception:
        totals = {"calls": 0, "estimated_cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
    checkpoint = {
        "status": status,
        "updated_at_utc": utc_now(),
        "armA_completed_papers": a_done,
        "armB_completed_papers": b_done,
        "judge_cells": judged,
        "capability_probes": {k: v.get("passed") for k, v in cap.get("probes", {}).items()},
        "provider_attempts": totals,
    }
    prior = (ROOT / REPORT_NAME).read_text(encoding="utf-8") if (ROOT / REPORT_NAME).exists() else ""
    if not prior or not all(f"## {x}" in prior for x in report_headings()):
        create_report_skeleton(status)
        prior = (ROOT / REPORT_NAME).read_text(encoding="utf-8")
    start, end = prior.find("## Incremental checkpoint"), prior.find("## Setup and model identifiers")
    summary = [
        "### Incremental checkpoint", "",
        f"Last checkpoint: **{status}** at {checkpoint['updated_at_utc']}.",
        f"- Arm A completed papers: {a_done}/8.",
        f"- Arm B completed papers: {b_done}/8.",
        f"- Judge cells persisted: {judged}.",
        f"- Provider attempts persisted: {totals.get('calls', 0)}; estimated spend ${totals.get('estimated_cost_usd', 0.0):.6f}.",
        f"- Probe outcomes: `{json.dumps(checkpoint['capability_probes'], sort_keys=True)}`.",
        "- Detailed attempt outputs and per-paper checkpoints are in `raw/responses/`, `raw/armA-results.json`, and `raw/armB-results.json`.",
        "",
    ]
    if start >= 0 and end > start:
        prior = prior[:start] + "\n".join(summary) + prior[end:]
    write_json(ROOT / "raw/progress.json", checkpoint)
    (ROOT / REPORT_NAME).write_text(prior, encoding="utf-8")


def run() -> None:
    ctx = context()
    guarded_requests(ctx["provider"])
    probes = run_probes(ctx)
    openai_ok = bool(probes.get("probes", {}).get("openai", {}).get("passed"))
    gemini_ok = bool(probes.get("probes", {}).get("gemini", {}).get("passed"))
    arm_a = run_arm_a(ctx, openai_ok)
    arm_b = run_arm_b(ctx, gemini_ok, openai_ok)
    deepseek_available = bool(os.environ.get("DEEPSEEK_API_KEY"))
    judges = run_judges(ctx, arm_a, arm_b, gemini_ok, deepseek_available)
    manifest_update("provider matrix complete or partial", extra={
        "arm_status": {"A": arm_a.get("status"), "B": arm_b.get("status")},
        "judge_status": judges.get("status"),
    })
    write_progress("provider matrix complete or partial")
    print(json.dumps({
        "armA_status": arm_a.get("status"), "armA_papers": len(arm_a.get("papers", {})),
        "armB_status": arm_b.get("status"), "armB_papers": len(arm_b.get("papers", {})),
        "judge_cells": len(judges.get("judges", {})),
        "usage_and_spend": ctx["provider"].rolling_totals(),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "prepare"
    if command == "prepare":
        prepare()
    elif command == "run":
        run()
    else:
        raise SystemExit("usage: python3 bench.py [prepare|run|analyze]")
