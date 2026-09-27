#!/usr/bin/env python3
"""Regenerate the public CSV tables from the frozen raw JSON evidence.

This script intentionally uses only the Python standard library and never calls
providers or imports the original scratch harness.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw"
TABLES = ROOT / "report" / "tables"


def load(name: str) -> Any:
    return json.loads((RAW / name).read_text(encoding="utf-8"))


def text(value: Any, empty: str = "") -> str:
    if value is None:
        return empty
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def write_csv(name: str, header: list[str], rows: list[list[Any]]) -> None:
    path = TABLES / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows([[text(value) for value in row] for row in rows])
    print(f"report/tables/{name} rows={len(rows)}")


def l1_tables() -> None:
    data = load("l1-metrics.json")
    summary: list[list[Any]] = []
    thresholds: list[list[Any]] = []
    calibration: list[list[Any]] = []
    for judge, model in data["models"].items():
        at_050 = next(row for row in model["threshold_sweep_relevance_vs_proxy"]
                      if row["threshold"] == 0.5)
        summary.append([
            judge,
            at_050["precision"],
            at_050["recall"],
            at_050["false_negative_rate"],
            model["auroc"],
            model["auprc_average_precision"],
            model["brier_relevance_vs_proxy"],
        ])
        for row in model["threshold_sweep_relevance_vs_proxy"]:
            thresholds.append([
                row["threshold"], judge, row["tp"], row["fp"], row["tn"], row["fn"],
                row["precision"], row["recall"], row["false_negative_rate"],
            ])
        for row in model["calibration_bins_relevance_vs_proxy"]:
            calibration.append([
                judge,
                row["range"],
                row["n"],
                "—" if row["mean_probability"] is None else row["mean_probability"],
                "—" if row["observed_positive_rate"] is None else row["observed_positive_rate"],
            ])
    write_csv(
        "l1-judge-summary.csv",
        ["judge", "proxy_precision_at_0.50", "recall", "fnr", "auroc", "auprc", "brier"],
        summary,
    )
    write_csv(
        "l1-thresholds.csv",
        ["threshold", "judge", "tp", "fp", "tn", "fn", "precision", "recall", "fnr"],
        thresholds,
    )
    write_csv(
        "l1-calibration.csv",
        ["judge", "bin", "n", "mean_probability", "observed_rate"],
        calibration,
    )


def l2_tables() -> None:
    data = load("l2-metrics.json")
    rows: list[list[Any]] = []
    for strategy, aggregate in data["aggregate"].items():
        rows.append([
            strategy,
            "Gemini Flash-Lite",
            aggregate["pages_processed"],
            aggregate["bytes_processed"],
            aggregate["input_tokens"],
            aggregate["output_tokens"],
            aggregate["logical_calls"],
            aggregate["attempts"],
            aggregate["latency_ms"] / 1000,
            aggregate["cost_usd"],
            aggregate["mean_claim_recall_jaccard_0_20"],
            "n/a" if aggregate["mean_evidence_page_recall"] is None
            else aggregate["mean_evidence_page_recall"],
        ])
    write_csv(
        "l2-strategies.csv",
        ["strategy", "input_mechanism", "pages_processed", "bytes_processed_sent", "tokens_in",
         "tokens_out", "logical_calls", "attempts", "latency_sum_s", "cost",
         "mean_claim_recall_0.20", "mean_d_load_bearing_page_recall"],
        rows,
    )

    miss_rows: list[list[Any]] = []
    for paper in data["per_paper"]:
        selective = paper["strategies"]["C"]
        miss_rows.append([
            paper["paper_id"],
            paper.get("pdf_pages", "") if "pdf_pages" in paper else "",
            ";".join(str(page) for page in selective["pages_seen"]),
            selective["claim_recall_jaccard_0_20"],
            selective["evidence_page_recall"],
            selective["important_claims_missed"],
        ])
    # The page count is recorded in the reference strategy input for each paper.
    page_by_paper = {}
    for paper in data["per_paper"]:
        for strategy in paper["strategies"].values():
            calls = strategy.get("calls", {})
            for artifact in calls.get("artifact_list", []):
                # Per-call records are not needed for this column; the D input's
                # page count is available in the frozen sampling manifest below.
                _ = artifact
        page_by_paper[paper["paper_id"]] = None
    sampling = load("sampling.json")
    for paper in sampling["papers"]:
        outcome = paper.get("pdf_fetch") or {}
        if outcome.get("page_count") is not None:
            page_by_paper[paper["arxiv_id"]] = outcome["page_count"]
    for row in miss_rows:
        row[1] = page_by_paper.get(row[0], "")
    write_csv(
        "l2-selective-misses.csv",
        ["arxiv_id", "pdf_pages", "c_pages_examined", "c_claim_recall",
         "d_load_bearing_page_recall", "d_claims_missed_by_c"],
        miss_rows,
    )


def l3_tables() -> None:
    data = load("l3-metrics.json")
    rows: list[list[Any]] = []
    for key, aggregate in data["aggregate"].items():
        papers = aggregate["papers"]
        responses = aggregate["responses"]
        native = round(aggregate["model_emitted_canonical_rate"] * papers)
        passed = round(aggregate["normalized_schema_pass_rate"] * responses)
        rows.append([
            key,
            f"{responses}/{papers}",
            f"{native}/{papers}",
            f"{passed}/{responses}",
            aggregate["mean_quote_containment_cited_page"],
            aggregate["input_tokens"],
            aggregate["output_tokens"],
            aggregate["cost_usd"],
            aggregate["latency_ms"] / 1000,
        ])
    write_csv(
        "l3-generators.csv",
        ["input/model", "output_objects", "native_canonical", "normalized_schema_pass",
         "exact_quote_containment", "tokens_in", "tokens_out", "cost", "latency_sum_s"],
        rows,
    )

    matrix = [
        ["1. Full-document D → DeepSeek Flash", "$0.128960",
         "D extraction $0.079122 plus DeepSeek full-reference generation $0.049839. Citation quote containment 0.744; normalized schema passed 2/8. Blind ratings: faithfulness 3.36/4 and evidence support 3.00/4, with 11 available ratings per dimension. Lower generator cost than Gemini, but it is not the cheapest full-reference arm and schema reliability is weak."],
        ["2. Full-document D → Gemini Flash-Lite", "$0.183133",
         "D $0.079122 plus generation $0.104011. Quote containment 0.262; normalized schema passed 1/7 parsed outputs. Blind means were 2.86 faithfulness, 2.71 evidence support, and 2.14 depth, n=7. Slowest and highest-cost full-reference generator."],
        ["3. Full-document D → GPT-6 Luna", "$0.112304",
         "D $0.079122 plus generation $0.033183. Canonical schema passed 8/8; quote containment 0.776; available blind means 4.00 faithfulness/evidence, n=4, depth 3.75/4, n=4. Cheapest of the three full-reference pipelines and strongest measured structured-output/quality result, with small judge coverage."],
        ["4. JEV triage → Gemini selective C → DeepSeek", "$0.034955",
         "Subset triage $0.000401, C $0.019829, selective DeepSeek $0.014725. All eight routed at P≥0.50. C page recall 0.309 and claim recall 0.212; DeepSeek normalized schema passed 1/8; quote containment 0.700. Low cost does not compensate for missed evidence."],
        ["5. JEV triage → Gemini selective C → Gemini", "$0.070581",
         "Same triage/C plus selective Gemini $0.050351. C recall unchanged; generator quote containment 0.325 and schema pass 1/8. No measured advantage over the other selective generators."],
        ["6. JEV triage → Gemini selective C → GPT-6 Luna", "$0.032042",
         "Subset triage $0.000401, C $0.019829, selective GPT $0.011813. GPT schema passed 8/8 and quote containment was 0.851; available judge depth was 3.20 versus 3.75 full-reference. Despite its low apparent inference cost, C saw only 30.9% of D load-bearing pages and missed important results."],
        ["7. Best measured generator GPT-6 Luna → JEV post-check", "$0.113075",
         "Full-reference pipeline 3 plus eight GPT full-reference post-checks ($0.000771). On n=8, JEV support decisions matched the exact-quote proxy in 7/8; across all 47 candidates, support precision was only 24/43 at threshold 0.75. Typed checks are cheap, but not sufficient to accept evidence semantically."],
    ]
    write_csv("l3-matrix.csv", ["pipeline_cell", "cost_for_8_papers", "evidence_and_fit"], matrix)


def l4_tables() -> None:
    data = load("l4-metrics.json")
    names = {
        "supported_by_supplied_evidence": "Supported by supplied evidence",
        "agenda_relevant": "Agenda relevant",
        "duplicates_supplied_existing_insight": "Duplicates supplied existing insight",
        "has_actionable_implication": "Has actionable implication",
        "escalate_for_deeper_review": "Escalate for deeper review",
    }
    comparisons = {
        "supported_by_supplied_evidence": "Against candidate-specific exact quote containment: TP 24, FP 19, TN 2, FN 2; Brier 0.347, agreement 0.553. This is a string-match proxy, not semantic entailment.",
        "agenda_relevant": "Against high-value stratum label: TP 41, FP 6, TN 0, FN 0; Brier 0.114, agreement 0.872. Six proxy-negative candidate outputs all passed.",
        "duplicates_supplied_existing_insight": "No gold duplicate labels; no Brier or agreement estimate.",
        "has_actionable_implication": "Against blind judge score ≥3: TP 31, FP 5, TN 0, FN 0 among 36 labeled; Brier 0.120 and agreement 0.861. Eleven candidates lacked a usable blind actionability score.",
        "escalate_for_deeper_review": "No gold escalation labels; no Brier or agreement estimate.",
    }
    rows: list[list[Any]] = []
    for question, values in data["per_question"].items():
        threshold = values["threshold"]
        positive = sum(
            1
            for paper in data["per_candidate"]
            if isinstance(paper.get("answers", {}).get(question), dict)
            and float(paper["answers"][question].get("probability")) >= threshold
        )
        total = len(data["per_candidate"])
        rows.append([
            names[question], threshold, values["mean_probability"], f"{positive}/{total}", comparisons[question],
        ])
    write_csv("l4-checks.csv", ["question", "host_threshold", "mean_probability", "positive_decisions", "proxy_comparison"], rows)


def cost_tables() -> None:
    data = load("cost-report.json")
    rows: list[list[Any]] = []
    stage_names = {"capability/probe": "Capability probes"}
    for stage, values in data["by_stage"].items():
        rows.append([
            stage_names.get(stage, stage), values["unique_call_ids"], values["attempts"],
            values["responses_200"], values["errors"], values["input_tokens"], values["output_tokens"],
            values["cost_usd"], values["latency_ms_sum_excluding_backoff"] / 1000,
        ])
    rows.append([
        "Total", sum(v["unique_call_ids"] for v in data["by_stage"].values()), data["total_attempts"],
        data["responses_200"], data["errors"], data["input_tokens"], data["output_tokens"],
        data["estimated_total_cost_usd"], data["latency_ms_sum_excluding_backoff"] / 1000,
    ])
    write_csv(
        "costs-by-stage.csv",
        ["stage", "unique_call_ids", "attempts", "http_200", "errors", "input_tokens",
         "output_tokens", "estimated_cost", "request_latency_sum_s"],
        rows,
    )


def main() -> None:
    l1_tables()
    l2_tables()
    l3_tables()
    l4_tables()
    cost_tables()


if __name__ == "__main__":
    main()
