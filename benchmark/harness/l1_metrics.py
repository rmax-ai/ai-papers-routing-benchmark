#!/usr/bin/env python3
"""Compute separate, auditable L1 metrics from persisted judgments."""

from __future__ import annotations

import json
import math
import statistics
from itertools import combinations
from pathlib import Path

ROOT = Path.cwd()
ARMS = ["jev", "deepseek", "gemini", "openai"]
THRESHOLDS = [0.30, 0.40, 0.50, 0.60, 0.70]


def answer(row: dict, arm: str, question: str):
    judgment = row.get("judgments", {}).get(arm) or {}
    if arm == "jev":
        answers = judgment.get("answers") or {}
        raw = answers.get(question)
        if not isinstance(raw, dict):
            return None, None
        if question in ("relevant", "empirical_evidence", "worth_escalating"):
            p = raw.get("probability")
            return (bool(p >= 0.5), float(p)) if isinstance(p, (int, float)) else (None, None)
        if question == "topic":
            return raw.get("choice"), None
        if question == "implementation_relevance":
            val = raw.get("score")
            return (float(val), None) if isinstance(val, (int, float)) else (None, None)
        return None, None
    output = judgment.get("output") or {}
    if question == "relevant":
        return output.get("relevant"), output.get("relevant_probability")
    if question == "empirical_evidence":
        return output.get("empirical_evidence"), output.get("empirical_probability")
    if question == "topic":
        return output.get("topic"), None
    if question == "worth_escalating":
        return output.get("worth_escalating"), output.get("escalation_probability")
    if question == "implementation_relevance":
        return output.get("implementation_relevance"), None
    return None, None


def confusion(probs: list[tuple[float, int]], threshold: float) -> dict:
    tp = fp = tn = fn = 0
    for p, y in probs:
        pred = p >= threshold
        if pred and y:
            tp += 1
        elif pred:
            fp += 1
        elif y:
            fn += 1
        else:
            tn += 1
    return {"threshold": threshold, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "false_negative_rate": fn / (tp + fn) if tp + fn else None}


def aucs(values: list[tuple[float, int]]) -> tuple[float | None, float | None]:
    pos = sum(y for _, y in values)
    neg = len(values) - pos
    if not pos or not neg:
        return None, None
    wins = ties = 0.0
    for p, y in values:
        if not y:
            continue
        for q, z in values:
            if z:
                continue
            wins += float(p > q)
            ties += float(p == q)
    auroc = (wins + 0.5 * ties) / (pos * neg)
    ordered = sorted(values, key=lambda x: (-x[0], x[1]))
    tp = fp = 0
    ap = 0.0
    index = 0
    while index < len(ordered):
        score = ordered[index][0]
        group = []
        while index < len(ordered) and ordered[index][0] == score:
            group.append(ordered[index])
            index += 1
        group_pos = sum(y for _, y in group)
        tp += group_pos
        fp += len(group) - group_pos
        if group_pos:
            ap += (group_pos / pos) * (tp / (tp + fp))
    return auroc, ap


def calibration(values: list[tuple[float, int]]) -> list[dict]:
    bins = []
    for low in (0.0, 0.2, 0.4, 0.6, 0.8):
        high = low + 0.2
        subset = [(p, y) for p, y in values if low <= p < high or (high == 1.0 and p == 1.0)]
        bins.append({"range": f"[{low:.1f},{high:.1f}{']' if high == 1.0 else ')'}",
                     "n": len(subset),
                     "mean_probability": sum(p for p, _ in subset) / len(subset) if subset else None,
                     "observed_positive_rate": sum(y for _, y in subset) / len(subset) if subset else None})
    return bins


def main() -> None:
    source = json.loads((ROOT / "raw" / "l1-results.json").read_text(encoding="utf-8"))
    audit_source = json.loads((ROOT / "raw" / "l1-audit.json").read_text(encoding="utf-8"))
    audit_by_id = {row["arxiv_id"]: row for row in audit_source["papers"]}
    rows = source["results"]
    output: dict = {"source": "raw/l1-results.json", "proxy_label": "high_value_proxy=1; medium_adjacent and low_relevance_control=0", "sample_n": len(rows), "positive_n": sum(bool(r["proxy_relevant_label"]) for r in rows), "models": {}, "pairwise_agreement": {}, "per_paper": []}
    for arm in ARMS:
        relevance = []
        lats = []
        tokens_in = tokens_out = cost = calls = successes = 0
        for row in rows:
            pred, p = answer(row, arm, "relevant")
            if isinstance(p, (int, float)):
                relevance.append((float(p), int(bool(row["proxy_relevant_label"]))))
            judgment = row.get("judgments", {}).get(arm) or {}
            if isinstance(judgment.get("latency_ms"), int):
                lats.append(int(judgment["latency_ms"]))
            for artifact in judgment.get("call_artifacts", []):
                path = ROOT / artifact
                if not path.exists():
                    continue
                call = json.loads(path.read_text(encoding="utf-8"))
                if call.get("used_as_benchmark_measurement") is False:
                    continue
                calls += 1
                usage = call.get("usage") or {}
                tokens_in += int(usage.get("input_tokens") or 0)
                tokens_out += int(usage.get("output_tokens") or 0)
                cost += float((call.get("cost") or {}).get("amount") or 0)
                if call.get("http_status") == 200:
                    successes += 1
        auroc, auprc = aucs(relevance)
        brier = sum((p - y) ** 2 for p, y in relevance) / len(relevance) if relevance else None
        output["models"][arm] = {
            "responses_with_relevance_probability": len(relevance),
            "auroc": auroc,
            "auprc_average_precision": auprc,
            "brier_relevance_vs_proxy": brier,
            "calibration_bins_relevance_vs_proxy": calibration(relevance),
            "threshold_sweep_relevance_vs_proxy": [confusion(relevance, t) for t in THRESHOLDS],
            "logical_calls": sum(bool((row.get("judgments", {}).get(arm) or {}).get("call_artifacts")) for row in rows),
            "network_attempts": calls, "http_200_attempts": successes,
            "input_tokens": tokens_in, "output_tokens": tokens_out,
            "cost_usd": round(cost, 12),
            "latency_ms_per_logical_call": {"median": statistics.median(lats) if lats else None, "p90": sorted(lats)[max(0, math.ceil(0.9 * len(lats)) - 1)] if lats else None, "note": "sum of HTTP attempt response latencies; inter-attempt backoff is excluded"},
        }
        consistency = {}
        for q in ("relevant", "empirical_evidence", "worth_escalating"):
            checked = mismatch = 0
            for row in rows:
                raw_value, p = answer(row, arm, q)
                if isinstance(p, (int, float)) and isinstance(raw_value, bool):
                    checked += 1
                    mismatch += raw_value != (float(p) >= 0.5)
            consistency[q] = {"checked": checked, "mismatch_with_host_0_5_threshold": mismatch}
        output["models"][arm]["boolean_probability_consistency"] = consistency
        audited_rel = []
        audited_empirical = []
        for row in rows:
            gold = audit_by_id.get(row["paper_id"])
            if gold is None:
                continue
            _, rel_p = answer(row, arm, "relevant")
            _, empirical_p = answer(row, arm, "empirical_evidence")
            if isinstance(rel_p, (int, float)):
                audited_rel.append((float(rel_p), int(gold["relevant_to_agenda"])))
            if isinstance(empirical_p, (int, float)):
                audited_empirical.append((float(empirical_p), int(gold["empirical_evidence"])))
        output["models"][arm]["abstract_audit"] = {
            "n": len(audited_rel),
            "relevance_at_host_threshold_0_5": confusion(audited_rel, 0.5),
            "relevance_brier": sum((p-y)**2 for p, y in audited_rel) / len(audited_rel) if audited_rel else None,
            "relevance_calibration_bins": calibration(audited_rel),
            "empirical_evidence_n": len(audited_empirical),
            "empirical_evidence_brier": sum((p-y)**2 for p, y in audited_empirical) / len(audited_empirical) if audited_empirical else None,
            "empirical_evidence_calibration_bins": calibration(audited_empirical),
            "paper_ids": [row["paper_id"] for row in rows if row["paper_id"] in audit_by_id],
            "selection_bias_note": "disagreement-enriched abstract audit; not a population estimate",
        }

    for q in ("relevant", "empirical_evidence", "topic", "worth_escalating", "implementation_relevance"):
        qresult = {}
        for a, b in combinations(ARMS, 2):
            agrees = n = 0
            for row in rows:
                av, _ = answer(row, a, q)
                ap = answer(row, a, q)[1]
                bv, bp = answer(row, b, q)
                if av is None or bv is None:
                    continue
                if q in ("relevant", "empirical_evidence", "worth_escalating"):
                    av = bool(ap >= 0.5) if isinstance(ap, (int, float)) else av
                    bv = bool(bp >= 0.5) if isinstance(bp, (int, float)) else bv
                n += 1
                if q == "implementation_relevance":
                    agrees += abs(float(av) - float(bv)) <= 0.5
                else:
                    agrees += av == bv
            qresult[f"{a}__{b}"] = {"agree": agrees, "n": n, "fraction": agrees / n if n else None, "criterion": "absolute score difference <= 0.5" if q == "implementation_relevance" else "exact"}
        output["pairwise_agreement"][q] = qresult

    for row in rows:
        item = {"paper_id": row["paper_id"], "stratum": row["stratum"], "proxy_label": row["proxy_relevant_label"], "judgments": {}}
        for arm in ARMS:
            item["judgments"][arm] = {q: {"value": answer(row, arm, q)[0], "probability": answer(row, arm, q)[1]} for q in ("relevant", "empirical_evidence", "topic", "worth_escalating", "implementation_relevance")}
        output["per_paper"].append(item)
    (ROOT / "raw" / "l1-metrics.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sample_n": output["sample_n"], "positive_n": output["positive_n"], "models": {a: {"prob_n": v["responses_with_relevance_probability"], "auroc": v["auroc"], "auprc": v["auprc_average_precision"], "brier": v["brier_relevance_vs_proxy"], "logical_calls": v["logical_calls"], "network_attempts": v["network_attempts"], "tokens": [v["input_tokens"], v["output_tokens"]], "cost_usd": v["cost_usd"], "latency": v["latency_ms_per_logical_call"]} for a, v in output["models"].items()}}, indent=2))


if __name__ == "__main__":
    main()
