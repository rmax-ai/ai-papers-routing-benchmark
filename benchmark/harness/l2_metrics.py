#!/usr/bin/env python3
"""Derive deterministic page and claim-recall metrics for Layer 2."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

ROOT = Path.cwd()
STOP = set("a an and are as at be been by can for from has have if in into is it its of on or that the their them then this to was were with without we our how what when where which while across under over between than into using use uses based result results paper study work shows show found find found these those each both such from any all more most less than their itself".split())


def words(value: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (value or "").lower()) if len(w) > 2 and w not in STOP}


def overlap(a: str, b: str) -> float:
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def page_refs(claim: dict) -> list[int]:
    refs = claim.get("evidence_refs") or []
    found = []
    for ref in refs:
        if isinstance(ref, dict) and isinstance(ref.get("page"), int):
            found.append(ref["page"])
    return found


def claims_recall(reference: list[dict], candidate: list[dict], threshold: float) -> dict:
    details = []
    matched = 0
    for index, ref in enumerate(reference):
        ref_text = str(ref.get("claim") or "")
        scored = [(overlap(ref_text, str(cand.get("claim") or "")), cand) for cand in candidate]
        best, best_claim = max(scored, key=lambda x: x[0], default=(0.0, None))
        is_match = best >= threshold
        matched += is_match
        details.append({"reference_index": index, "reference_claim": ref_text,
                        "importance": ref.get("importance", "unspecified"),
                        "reference_pages": page_refs(ref), "best_jaccard": round(best, 4),
                        "matched": is_match,
                        "candidate_claim": best_claim.get("claim") if best_claim else None})
    return {"reference_claim_count": len(reference), "matched_count": matched,
            "recall": matched / len(reference) if reference else None,
            "threshold": threshold, "details": details}


def loadbearing_pages(reference: dict) -> list[int]:
    pages = reference.get("load_bearing_pages") or []
    if pages:
        return sorted({int(p) for p in pages if isinstance(p, int)})
    found = set()
    for claim in reference.get("candidate_claims") or []:
        if claim.get("importance") == "load_bearing":
            found.update(page_refs(claim))
    if not found:
        for claim in reference.get("candidate_claims") or []:
            found.update(page_refs(claim))
    return sorted(found)


def summarize_call(artifacts: list[str]) -> dict:
    attempts = []
    for artifact in artifacts:
        path = ROOT / artifact
        if path.exists():
            attempts.append(json.loads(path.read_text(encoding="utf-8")))
    return {
        "attempts": len(attempts),
        "http_200_attempts": sum(a.get("http_status") == 200 for a in attempts),
        "input_tokens": sum(int((a.get("usage") or {}).get("input_tokens") or 0) for a in attempts),
        "output_tokens": sum(int((a.get("usage") or {}).get("output_tokens") or 0) for a in attempts),
        "cost_usd": round(sum(float((a.get("cost") or {}).get("amount") or 0) for a in attempts), 12),
        "latency_ms": sum(int(a.get("latency_ms") or 0) for a in attempts),
        "artifact_list": artifacts,
    }


def main() -> None:
    results = json.loads((ROOT / "raw" / "l2-results.json").read_text(encoding="utf-8"))["results"]
    sampled = json.loads((ROOT / "raw" / "sampling.json").read_text(encoding="utf-8"))
    sampled_by_id = {p["arxiv_id"]: p for p in sampled["papers"]}
    rows = []
    misses = []
    aggregate = {strategy: {"logical_calls": 0, "attempts": 0, "input_tokens": 0, "output_tokens": 0,
                            "cost_usd": 0.0, "latency_ms": 0, "pages_processed": 0, "bytes_processed": 0}
                 for strategy in ("A", "B", "C", "D")}
    for paper_id, paper in results.items():
        ref = paper["strategies"]["D"]
        ref_claims = ref.get("candidate_claims") or []
        ref_pages = loadbearing_pages(ref)
        per_paper = {"paper_id": paper_id, "reference_load_bearing_pages": ref_pages,
                     "reference_claim_count": len(ref_claims), "strategies": {}}
        for strategy in ("A", "B", "C", "D"):
            data = paper["strategies"][strategy]
            if strategy == "C":
                claims = data.get("candidate_claims") or []
                pages_seen = sorted({page for round_item in data.get("rounds", [])
                                     if round_item.get("http_status") == 200 and round_item.get("parsed")
                                     for page in round_item.get("pages_sent", [])})
                page_bytes = sum(int(x.get("image_bytes_sent") or 0) for x in data.get("rounds", []))
                call_rows = [call for round_item in data.get("rounds", []) for call in round_item.get("call_artifacts", [])]
                calls = summarize_call(call_rows)
                pages_processed = len(pages_seen)
                bytes_processed = page_bytes
                evidence_recall = (len(set(ref_pages) & set(pages_seen)) / len(ref_pages)) if ref_pages else None
            else:
                claims = data.get("candidate_claims") or []
                calls = summarize_call(data.get("call", {}).get("call_artifacts", []))
                if strategy == "A":
                    pages_seen = []
                    pages_processed = 0
                    bytes_processed = len(str(sampled_by_id[paper_id].get("abstract", "")).encode("utf-8"))
                    evidence_recall = None
                elif strategy == "B":
                    page_count = int(paper["pdf"].get("page_count") or 0)
                    pages_seen = list(range(1, page_count + 1))
                    pages_processed = page_count
                    bytes_processed = int(data.get("pdf_bytes_sent") or 0)
                    evidence_recall = (len(set(ref_pages) & set(pages_seen)) / len(ref_pages)) if ref_pages else None
                else:
                    page_count = int(paper["pdf"].get("page_count") or 0)
                    pages_seen = list(range(1, page_count + 1))
                    pages_processed = int(data.get("pages_processed") or 0)
                    bytes_processed = int(data.get("full_text_bytes") or 0)
                    text_page_ratio = float(data.get("text_page_ratio") or 0)
                    evidence_recall = (len(set(ref_pages) & set(range(1, page_count + 1))) / len(ref_pages)) if ref_pages and text_page_ratio >= 0.95 else ((len(set(ref_pages) & set(range(1, page_count + 1))) * text_page_ratio) / len(ref_pages) if ref_pages else None)
            recall_015 = claims_recall(ref_claims, claims, 0.15)
            recall_020 = claims_recall(ref_claims, claims, 0.20)
            recall_025 = claims_recall(ref_claims, claims, 0.25)
            important_missing = [d for d in recall_020["details"] if d["importance"] == "load_bearing" and not d["matched"]]
            for item in important_missing:
                misses.append({"paper_id": paper_id, "strategy": strategy, **item})
            per_paper["strategies"][strategy] = {
                "pages_processed": pages_processed, "pages_seen": pages_seen,
                "bytes_processed": bytes_processed, "evidence_page_recall": evidence_recall,
                "claim_recall_jaccard_0_15": recall_015["recall"],
                "claim_recall_jaccard_0_20": recall_020["recall"],
                "claim_recall_jaccard_0_25": recall_025["recall"],
                "recall_details_at_0_20": recall_020["details"],
                "important_claims_missed": len(important_missing),
                "calls": calls,
            }
            agg = aggregate[strategy]
            agg["logical_calls"] += 1 if strategy != "C" else len(data.get("rounds", []))
            agg["attempts"] += calls["attempts"]
            agg["input_tokens"] += calls["input_tokens"]
            agg["output_tokens"] += calls["output_tokens"]
            agg["cost_usd"] += calls["cost_usd"]
            agg["latency_ms"] += calls["latency_ms"]
            agg["pages_processed"] += pages_processed
            agg["bytes_processed"] += bytes_processed
        rows.append(per_paper)
    aggregate_out = {}
    for strategy, stats in aggregate.items():
        recall = [r["strategies"][strategy]["claim_recall_jaccard_0_20"] for r in rows if r["strategies"][strategy]["claim_recall_jaccard_0_20"] is not None]
        page_recall = [r["strategies"][strategy]["evidence_page_recall"] for r in rows if r["strategies"][strategy]["evidence_page_recall"] is not None]
        threshold_sensitivity = {}
        for threshold in (0.15, 0.20, 0.25):
            scores = []
            for paper_id, paper in results.items():
                ref_claims = paper["strategies"]["D"].get("candidate_claims") or []
                claims = paper["strategies"][strategy].get("candidate_claims") or []
                metric = claims_recall(ref_claims, claims, threshold)["recall"]
                if metric is not None:
                    scores.append(metric)
            threshold_sensitivity[f"{threshold:.2f}"] = statistics.mean(scores) if scores else None
        aggregate_out[strategy] = {**stats,
            "cost_usd": round(stats["cost_usd"], 12),
            "mean_claim_recall_jaccard_0_20": statistics.mean(recall) if recall else None,
            "claim_recall_threshold_sensitivity": threshold_sensitivity,
            "mean_evidence_page_recall": statistics.mean(page_recall) if page_recall else None,
            "papers_with_claim_outputs": sum(bool(r["strategies"][strategy]["claim_recall_jaccard_0_20"] is not None) for r in rows)}
    out = {"schema_version": 1, "sample_n": len(rows),
           "claim_match_method": "content-word Jaccard overlap of candidate claim text after fixed stopword removal; primary match threshold 0.20, sensitivity at 0.15/0.25; lexical proxy, not semantic judge",
           "load_bearing_page_method": "D reference's explicit load_bearing_pages, falling back to page refs on D claims tagged load_bearing; C recall is reference pages intersecting pages examined divided by reference pages",
           "aggregate": aggregate_out, "per_paper": rows, "important_claim_misses": misses}
    (ROOT / "raw" / "l2-metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sample_n": len(rows), "aggregate": aggregate_out,
                      "important_claim_misses": len(misses)}, indent=2))


if __name__ == "__main__":
    main()
