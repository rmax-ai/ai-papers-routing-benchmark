#!/usr/bin/env python3
"""Derive auditable L3 schema, evidence, blind-judge, and sensitivity metrics."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path.cwd()
DIMENSIONS = ["faithfulness", "evidence_support", "insight_depth", "novelty_identification",
              "systems_relevance", "actionability", "compression_information_density",
              "systems_relevance_and_actionability", "uncertainty_calibration",
              "durable_memory_precision_proxy"]

ALIASES = {
    "faithfulness": "faithfulness",
    "evidence_support": "evidence_support",
    "insight_depth": "insight_depth", "depth": "insight_depth",
    "novelty_identification": "novelty_identification", "novelty": "novelty_identification",
    "systems_relevance": "systems_relevance",
    "actionability": "actionability",
    "systems_relevance_and_actionability": "systems_relevance_and_actionability",
    "compression_information_density": "compression_information_density", "compression": "compression_information_density",
    "uncertainty_calibration": "uncertainty_calibration",
    "durable_memory_precision_proxy": "durable_memory_precision_proxy",
    "durable_memory_precision": "durable_memory_precision_proxy",
}


def score_number(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and 0 <= value <= 4:
        return int(value)
    if isinstance(value, dict):
        for key in ("score", "rating", "value"):
            parsed = score_number(value.get(key))
            if parsed is not None:
                return parsed
    return None


def candidate_label(obj: dict, fallback: str | None = None) -> str | None:
    for key in ("blind_label", "candidate_label", "label", "blind_candidate"):
        value = obj.get(key)
        if isinstance(value, str):
            value = value.strip().upper().replace("BLIND_LABEL_", "").replace("CANDIDATE_", "")
            if value in ("A", "B", "C"):
                return value
    if fallback:
        value = fallback.strip().upper().replace("BLIND_LABEL_", "").replace("CANDIDATE_", "")
        if value.startswith("SCORE_CANDIDATE_"):
            value = value.rsplit("_", 1)[-1]
        if value in ("A", "B", "C"):
            return value
    return None


def flatten_score_object(obj: object, fallback_label: str | None = None) -> dict | None:
    if not isinstance(obj, dict):
        return None
    label = candidate_label(obj, fallback_label)
    if label is None:
        return None
    scores = {"blind_label": label}
    for source, value in obj.items():
        normalized_source = source.removesuffix("_score") if isinstance(source, str) else source
        target = ALIASES.get(normalized_source)
        parsed = score_number(value)
        if target and parsed is not None:
            scores[target] = parsed
    return scores if len(scores) > 1 else None


def normalized_judge_scores(output: object) -> tuple[list[dict], str | None]:
    """Read common score-bearing variants without inventing missing dimensions."""
    if not isinstance(output, dict):
        return [], "non_object_output"
    candidates: list[dict] = []
    for key in ("scores", "evaluations", "candidate_evaluations", "candidate_scores"):
        value = output.get(key)
        if isinstance(value, list):
            candidates.extend(obj for obj in value if isinstance(obj, dict))
        elif isinstance(value, dict):
            for label, obj in value.items():
                if isinstance(obj, dict):
                    copied = dict(obj)
                    copied.setdefault("blind_label", label)
                    candidates.append(copied)
        # Some judges return a single score dictionary rather than a list.
        elif value is None and key == "scores" and any(
                (k.removesuffix("_score") if isinstance(k, str) else k) in ALIASES for k in output):
            candidates.append(output)

    for key in ("evaluation", "evaluations"):
        nested = output.get(key)
        if isinstance(nested, dict):
            for label, obj in nested.items():
                if isinstance(obj, dict):
                    copied = dict(obj)
                    copied.setdefault("blind_label", label)
                    candidates.append(copied)
    for key in ("score_candidate_a", "score_candidate_b", "score_candidate_c"):
        value = output.get(key)
        if isinstance(value, dict):
            candidates.append({**value, "blind_label": key.rsplit("_", 1)[-1].upper()})
    if any((k.removesuffix("_score") if isinstance(k, str) else k) in ALIASES for k in output) and candidate_label(output):
        candidates.append(output)

    normalized = []
    seen = set()
    for candidate in candidates:
        item = flatten_score_object(candidate)
        if item:
            signature = (item["blind_label"], tuple(sorted((k, v) for k, v in item.items() if k != "blind_label")))
            if signature not in seen:
                normalized.append(item)
                seen.add(signature)
    return normalized, None if normalized else "no_candidate_dimension_scores"


def read_artifacts(cell: dict) -> list[dict]:
    paths = list(cell.get("call_artifacts", [])) + list(cell.get("superseded_invalid_response_artifacts", []))
    values = []
    for rel in dict.fromkeys(paths):
        path = ROOT / rel
        if path.exists():
            try:
                values.append(json.loads(path.read_text(encoding="utf-8")))
            except json.JSONDecodeError:
                continue
    return values


def cell_cost(cell: dict) -> dict:
    artifacts = read_artifacts(cell)
    return {"attempts": len(artifacts), "input_tokens": sum(int((a.get("usage") or {}).get("input_tokens") or 0) for a in artifacts),
            "output_tokens": sum(int((a.get("usage") or {}).get("output_tokens") or 0) for a in artifacts),
            "cost_usd": sum(float((a.get("cost") or {}).get("amount") or 0) for a in artifacts),
            "latency_ms": sum(int(a.get("latency_ms") or 0) for a in artifacts),
            "http_200_attempts": sum(a.get("http_status") == 200 for a in artifacts)}


def main() -> None:
    data = json.loads((ROOT / "raw/l3-results.json").read_text(encoding="utf-8"))
    by_cell: dict[str, dict] = {}
    judge_bins: dict[tuple[str, str], dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    per_paper = {}
    failures = []
    judge_format = {"logical_calls": 0, "calls_with_dimension_scores": 0,
                    "calls_without_dimension_scores": [], "calls_with_partial_scores": 0,
                    "normalized_candidates": 0}
    for pid, row in data.get("results", {}).items():
        per_paper[pid] = {"generations": {}, "judge_scores": {}}
        for path, cells in row.get("generations", {}).items():
            if path not in ("full_reference", "selective"):
                continue
            for provider, cell in cells.items():
                if provider not in ("deepseek", "gemini", "openai"):
                    continue
                key = f"{path}/{provider}"
                agg = by_cell.setdefault(key, {"path": path, "model": provider, "papers": 0, "responses": 0,
                    "model_emitted_canonical": 0, "normalized_schema_pass": 0, "page_valid_outputs": 0,
                    "quote_cited_page_rates": [], "quote_any_page_rates": [], "confidence_values": [],
                    "insight_counts": [], "attempts": 0, "input_tokens": 0, "output_tokens": 0,
                    "cost_usd": 0.0, "latency_ms": 0, "failures": []})
                agg["papers"] += 1
                checks = cell.get("deterministic_checks") or {}
                output = cell.get("output")
                if isinstance(output, dict):
                    agg["responses"] += 1
                    agg["model_emitted_canonical"] += bool(cell.get("model_emitted_canonical_shape"))
                    agg["normalized_schema_pass"] += bool(checks.get("schema_shape_pass"))
                    agg["page_valid_outputs"] += bool(checks.get("all_cited_pages_valid"))
                    if checks.get("quote_containment_cited_page_rate") is not None:
                        agg["quote_cited_page_rates"].append(checks["quote_containment_cited_page_rate"])
                    if checks.get("quote_containment_any_page_rate") is not None:
                        agg["quote_any_page_rates"].append(checks["quote_containment_any_page_rate"])
                    insights = output.get("insights") or []
                    agg["insight_counts"].append(len(insights))
                    agg["confidence_values"].extend(float(i["confidence"]) for i in insights if isinstance(i, dict) and isinstance(i.get("confidence"), (int, float)))
                else:
                    failure = {"paper_id": pid, "path": path, "model": provider,
                               "http_status": cell.get("http_status"), "provider_error": cell.get("provider_error"),
                               "parse_error": cell.get("parse_error"), "artifacts": cell.get("call_artifacts", [])}
                    agg["failures"].append(failure)
                    failures.append(failure)
                costs = cell_cost(cell)
                for metric in ("attempts", "input_tokens", "output_tokens", "latency_ms", "http_200_attempts"):
                    agg[metric] = agg.get(metric, 0) + costs.get(metric, 0)
                agg["cost_usd"] += costs["cost_usd"]
                per_paper[pid]["generations"].setdefault(path, {})[provider] = {
                    "http_status": cell.get("http_status"), "model_emitted_canonical_shape": cell.get("model_emitted_canonical_shape"),
                    "normalized_schema_pass": checks.get("schema_shape_pass"),
                    "all_cited_pages_valid": checks.get("all_cited_pages_valid"),
                    "quote_containment_cited_page_rate": checks.get("quote_containment_cited_page_rate"),
                    "quote_containment_any_page_rate": checks.get("quote_containment_any_page_rate"),
                    "insight_count": len(output.get("insights", [])) if isinstance(output, dict) else None,
                    "calls": costs}
        for judge_key, judge in row.get("judges", {}).items():
            judge_format["logical_calls"] += 1
            mapping = judge.get("label_to_model_internal", {})
            scores, format_issue = normalized_judge_scores(judge.get("output"))
            if scores:
                judge_format["calls_with_dimension_scores"] += 1
                judge_format["normalized_candidates"] += len(scores)
                # The prompt asks for nine dimensions; the extra combined field
                # preserves judge variants without splitting one score in two.
                if any(len(item) < 10 for item in scores):
                    judge_format["calls_with_partial_scores"] += 1
            else:
                judge_format["calls_without_dimension_scores"].append({
                    "paper_id": pid, "judge_cell": judge_key,
                    "format_issue": format_issue,
                    "call_artifacts": judge.get("call_artifacts", []),
                    "winner_field_present": any(k in (judge.get("output") or {}) for k in
                        ("winner", "chosen_blind_label", "selected_candidate", "selected_blind_label", "preferred_blind_label"))
                        if isinstance(judge.get("output"), dict) else False})
            for scored in scores:
                model = mapping.get(scored.get("blind_label"))
                if model not in ("deepseek", "gemini", "openai", "openai_none", "openai_medium"):
                    continue
                path = judge_key.split("/", 1)[0]
                for dimension in DIMENSIONS:
                    value = scored.get(dimension)
                    if isinstance(value, (int, float)):
                        judge_bins[(path, model)][dimension].append(int(value))
                        per_paper[pid].setdefault("_judge_ratings", {}).setdefault(path, {}).setdefault(model, {}).setdefault(dimension, []).append(int(value))

        for path, models in per_paper[pid].get("_judge_ratings", {}).items():
            per_paper[pid]["judge_scores"][path] = {}
            per_paper[pid]["judge_score_counts"] = per_paper[pid].setdefault("judge_score_counts", {})
            per_paper[pid]["judge_score_counts"][path] = {}
            for model, dimensions in models.items():
                per_paper[pid]["judge_scores"][path][model] = {}
                per_paper[pid]["judge_score_counts"][path][model] = {}
                for dimension, values in dimensions.items():
                    per_paper[pid]["judge_scores"][path][model][dimension] = statistics.mean(values)
                    per_paper[pid]["judge_score_counts"][path][model][dimension] = len(values)
        per_paper[pid].pop("_judge_ratings", None)

    aggregate = {}
    for key, cell in by_cell.items():
        responses = cell["responses"]
        aggregate[key] = {**cell,
            "model_emitted_canonical_rate": cell["model_emitted_canonical"] / responses if responses else None,
            "normalized_schema_pass_rate": cell["normalized_schema_pass"] / responses if responses else None,
            "page_valid_output_rate": cell["page_valid_outputs"] / responses if responses else None,
            "mean_quote_containment_cited_page": statistics.mean(cell["quote_cited_page_rates"]) if cell["quote_cited_page_rates"] else None,
            "mean_quote_containment_any_page": statistics.mean(cell["quote_any_page_rates"]) if cell["quote_any_page_rates"] else None,
            "mean_confidence": statistics.mean(cell["confidence_values"]) if cell["confidence_values"] else None,
            "mean_insights_per_output": statistics.mean(cell["insight_counts"]) if cell["insight_counts"] else None}
        for key_to_remove in ("model_emitted_canonical", "normalized_schema_pass", "page_valid_outputs", "quote_cited_page_rates", "quote_any_page_rates", "confidence_values", "insight_counts"):
            aggregate[key].pop(key_to_remove, None)
    judge_aggregate = {}
    for (path, model), dims in judge_bins.items():
        judge_aggregate.setdefault(path, {})[model] = {d: {"mean_0_to_4": statistics.mean(values), "n": len(values)} for d, values in dims.items()}
    sensitivity = {}
    for pid, row in data.get("results", {}).items():
        medium = row.get("openai_medium")
        primary = row.get("generations", {}).get("full_reference", {}).get("openai")
        if isinstance(medium, dict) and isinstance(primary, dict):
            sensitivity[pid] = {"primary_checks": primary.get("deterministic_checks"),
                "medium_checks": medium.get("deterministic_checks"),
                "primary_confidences": [i.get("confidence") for i in (primary.get("output") or {}).get("insights", [])],
                "medium_confidences": [i.get("confidence") for i in (medium.get("output") or {}).get("insights", [])],
                "primary_insights": len((primary.get("output") or {}).get("insights", [])),
                "medium_insights": len((medium.get("output") or {}).get("insights", [])),
                "blind_gemini_scores": row.get("judges", {}).get("full_reference/sensitivity_gemini")}
    out = {"schema_version": 1, "status": data.get("status"), "sample_n": len(per_paper),
        "routing_policy": data.get("routing_policy"), "aggregate": aggregate,
        "blind_judge_scores_0_to_4": judge_aggregate, "sensitivity": sensitivity,
        "per_paper": per_paper, "generation_failures": failures,
        "judge_format_audit": judge_format,
        "judge_design": "OpenAI judges DeepSeek and Gemini; Gemini judges GPT-Luna and DeepSeek; a separate Gemini pair judge compares GPT-Luna none vs medium on four papers; all generator labels are blinded.",
        "quality_dimensions_are_separate": DIMENSIONS}
    (ROOT / "raw/l3-metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": out["status"], "generator_cells": {
        k: {"responses": v["responses"], "normalized_pass_rate": v["normalized_schema_pass_rate"],
            "quote_page": v["mean_quote_containment_cited_page"],
            "tokens_in_out": [v["input_tokens"], v["output_tokens"]], "cost": v["cost_usd"]}
        for k,v in aggregate.items()}, "judge_format_audit": judge_format,
        "judge_means": judge_aggregate, "generation_failures": len(failures)}, indent=2))


if __name__ == "__main__":
    main()
