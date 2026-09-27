#!/usr/bin/env python3
"""Reconstruct spend, usage, latency, and rate tiers from persisted attempts."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path.cwd()


def main() -> None:
    groups: dict[tuple[str, str, str], dict] = defaultdict(lambda: {
        "attempts": 0, "responses_200": 0, "errors": 0, "input_tokens": 0,
        "output_tokens": 0, "cached_input_tokens": 0, "reasoning_tokens": 0,
        "cost_usd": 0.0, "latency_ms": [], "call_ids": set(), "rate_sources": set(), "tiers": defaultdict(float),
    })
    errors = []
    all_rates, all_tiers = set(), defaultdict(float)
    stages: dict[str, dict] = defaultdict(lambda: {
        "attempts": 0, "responses_200": 0, "errors": 0, "input_tokens": 0,
        "output_tokens": 0, "cached_input_tokens": 0, "reasoning_tokens": 0,
        "cost_usd": 0.0, "latency_ms": [], "call_ids": set(),
        "rate_sources": set(), "tiers": defaultdict(float),
    })
    total = {"attempts": 0, "responses_200": 0, "errors": 0, "input_tokens": 0,
             "output_tokens": 0, "cached_input_tokens": 0, "reasoning_tokens": 0,
             "cost_usd": 0.0, "latency_ms": []}
    for path in (ROOT / "raw/responses").rglob("*.json"):
        try:
            call = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        arm = str(call.get("arm_id") or "unknown")
        if arm.startswith("l1-"):
            stage = "L1"
        elif arm.startswith("l2-"):
            stage = "L2"
        elif arm.startswith("l3-"):
            stage = "L3"
        elif arm.startswith("l4-"):
            stage = "L4"
        else:
            stage = "capability/probe"
        provider = str(call.get("provider") or "unknown")
        key = (stage, arm, provider)
        row = groups[key]
        usage, cost = call.get("usage") or {}, call.get("cost") or {}
        amount = float(cost.get("amount") or 0)
        status = call.get("http_status")
        input_t = int(usage.get("input_tokens") or 0)
        output_t = int(usage.get("output_tokens") or 0)
        cached_t = int(usage.get("cached_input_tokens") or 0)
        reason_t = int(usage.get("reasoning_tokens") or 0)
        latency = int(call.get("latency_ms") or 0)
        row["attempts"] += 1
        row["responses_200"] += status == 200
        row["errors"] += status != 200
        row["input_tokens"] += input_t
        row["output_tokens"] += output_t
        row["cached_input_tokens"] += cached_t
        row["reasoning_tokens"] += reason_t
        row["cost_usd"] += amount
        row["latency_ms"].append(latency)
        row["call_ids"].add(call.get("call_id"))
        source = cost.get("rate_source")
        tier = cost.get("tier")
        if source:
            row["rate_sources"].add(source)
            all_rates.add(source)
        if tier:
            row["tiers"][tier] += amount
            all_tiers[tier] += amount
        total["attempts"] += 1
        total["responses_200"] += status == 200
        total["errors"] += status != 200
        total["input_tokens"] += input_t
        total["output_tokens"] += output_t
        total["cached_input_tokens"] += cached_t
        total["reasoning_tokens"] += reason_t
        total["cost_usd"] += amount
        total["latency_ms"].append(latency)
        stage_row = stages[stage]
        stage_row["attempts"] += 1
        stage_row["responses_200"] += status == 200
        stage_row["errors"] += status != 200
        stage_row["input_tokens"] += input_t
        stage_row["output_tokens"] += output_t
        stage_row["cached_input_tokens"] += cached_t
        stage_row["reasoning_tokens"] += reason_t
        stage_row["cost_usd"] += amount
        stage_row["latency_ms"].append(latency)
        stage_row["call_ids"].add(call.get("call_id"))
        if source:
            stage_row["rate_sources"].add(source)
        if tier:
            stage_row["tiers"][tier] += amount
        if status != 200:
            errors.append({"artifact": path.relative_to(ROOT).as_posix(), "arm_id": arm,
                           "provider": provider, "http_status": status, "cost_usd": amount,
                           "error": call.get("error")})
    def summarize(row: dict) -> dict:
        lat = row["latency_ms"]
        ordered = sorted(lat)
        return {"attempts": row["attempts"], "unique_call_ids": len(row["call_ids"]),
            "responses_200": row["responses_200"], "errors": row["errors"],
            "input_tokens": row["input_tokens"], "output_tokens": row["output_tokens"],
            "cached_input_tokens": row["cached_input_tokens"], "reasoning_tokens": row["reasoning_tokens"],
            "cost_usd": round(row["cost_usd"], 12),
            "latency_ms_sum_excluding_backoff": sum(lat),
            "latency_ms_median_per_attempt": statistics.median(lat) if lat else None,
            "latency_ms_p90_per_attempt": ordered[min(len(ordered)-1, int(.9 * len(ordered)))] if ordered else None,
            "deepseek_tier_cost_usd": {k: round(v, 12) for k,v in row["tiers"].items()},
            "rate_sources": sorted(row["rate_sources"])}
    stage_rows = {"/".join(key): summarize(row) for key, row in sorted(groups.items())}
    stage_totals = {stage: summarize(row) for stage, row in sorted(stages.items())}
    ordered = sorted(total["latency_ms"])
    out = {"schema_version": 1, "status": "complete",
        "accounting_method": "Sum every persisted HTTP attempt's provider usage against its saved cost.rate_source and rates_used_usd_per_million. Error attempts with no model response have zero usage/cost. Latency sums provider round trips only and excludes retry backoff.",
        "total_attempts": total["attempts"], "responses_200": total["responses_200"],
        "errors": total["errors"], "input_tokens": total["input_tokens"],
        "output_tokens": total["output_tokens"], "cached_input_tokens": total["cached_input_tokens"],
        "reasoning_tokens": total["reasoning_tokens"], "estimated_total_cost_usd": round(total["cost_usd"], 12),
        "latency_ms_sum_excluding_backoff": sum(total["latency_ms"]),
        "latency_ms_median_per_attempt": statistics.median(total["latency_ms"]) if total["latency_ms"] else None,
        "latency_ms_p90_per_attempt": ordered[min(len(ordered)-1, int(.9 * len(ordered)))] if ordered else None,
        "deepseek_peak_offpeak_cost_usd": {k: round(v, 12) for k,v in all_tiers.items()},
        "rate_sources": sorted(all_rates), "by_stage": stage_totals,
        "by_stage_arm_provider": stage_rows,
        "failed_attempt_artifacts": errors}
    (ROOT / "raw/cost-report.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"attempts": out["total_attempts"], "responses_200": out["responses_200"],
        "errors": out["errors"], "tokens_in_out": [out["input_tokens"], out["output_tokens"]],
        "estimated_usd": out["estimated_total_cost_usd"], "deepseek_tiers": out["deepseek_peak_offpeak_cost_usd"],
        "by_stage": {stage: sum(row["attempts"] for key,row in stage_rows.items() if key.startswith(stage + "/")) for stage in ("L1","L2","L3","L4","capability/probe")}}, indent=2))


if __name__ == "__main__":
    main()
