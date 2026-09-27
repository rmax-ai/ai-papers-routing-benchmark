#!/usr/bin/env python3
"""Derive DQ84 metrics, report, and sanitized public staging from raw checkpoints."""

from __future__ import annotations

import csv
import copy
import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

import bench

ROOT = Path.cwd()


def mean(values):
    values = [x for x in values if isinstance(x, (int, float)) and not isinstance(x, bool)]
    return statistics.mean(values) if values else None


def median(values):
    values = [x for x in values if isinstance(x, (int, float)) and not isinstance(x, bool)]
    return statistics.median(values) if values else None


def fmt(value, digits=3):
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def pct(numerator, denominator):
    return numerator / denominator if denominator else None


def artifact_attempts(artifact_paths: list[str]) -> list[dict]:
    values = []
    for rel in dict.fromkeys(artifact_paths or []):
        path = ROOT / rel
        if path.exists():
            try:
                values.append(bench.read_json(path))
            except (OSError, json.JSONDecodeError):
                pass
    return values


def group_attempts(*stages: dict | None) -> list[dict]:
    paths = []
    for stage in stages:
        if isinstance(stage, dict):
            paths.extend(stage.get("attempt_artifacts", []))
    return artifact_attempts(paths)


def attempt_totals(attempts: list[dict]) -> dict:
    costs = [float((x.get("cost") or {}).get("amount") or 0.0) for x in attempts]
    usage = [x.get("usage") or {} for x in attempts]
    statuses = [x.get("http_status") for x in attempts]
    return {
        "attempts": len(attempts),
        "input_tokens": sum(int(x.get("input_tokens") or 0) for x in usage),
        "output_tokens": sum(int(x.get("output_tokens") or 0) for x in usage),
        "cached_input_tokens": sum(int(x.get("cached_input_tokens") or 0) for x in usage),
        "reasoning_tokens": sum(int(x.get("reasoning_tokens") or 0) for x in usage if isinstance(x.get("reasoning_tokens"), (int, float))),
        "latency_ms_attempt_sum": sum(int(x.get("latency_ms") or 0) for x in attempts),
        "cost_usd": sum(costs),
        "http_200_attempts": sum(x == 200 for x in statuses),
        "http_failures": sum(x is not None and not 200 <= int(x) < 300 for x in statuses),
        "transport_failures": sum(x is None for x in statuses),
        "transient_retry_attempts": sum(int(x.get("attempt") or 1) > 1 for x in attempts),
        "truncation_retry_attempts": sum(bool(x.get("retry_reason")) for x in attempts),
        "artifact_paths": [x.get("artifact") for x in attempts],
    }


def unit_support(output: dict, checks: dict | None, unit_kind: str) -> dict:
    if unit_kind == "claims":
        paper = output.get("paper") or {}
        groups = [("key_claims", paper.get("key_claims") or []),
                  ("evidence", paper.get("evidence") or [])]
    else:
        groups = [("insights", output.get("insights") or [])]
    checked = (checks or {}).get("evidence_refs", [])
    no_refs = failed = supported = 0
    total = 0
    for group, items in groups:
        for index, item in enumerate(items):
            total += 1
            refs = item.get("evidence_refs") if isinstance(item, dict) else None
            refs = refs if isinstance(refs, list) else []
            if not refs:
                no_refs += 1
                continue
            valid_support = any(
                x.get("group") == group and x.get("item") == index and
                x.get("page_valid") and x.get("quote_nonempty") and
                x.get("quote_contained_cited_page")
                for x in checked if isinstance(x, dict)
            )
            if valid_support:
                supported += 1
            else:
                failed += 1
    return {
        "unit_count": total, "supported_units": supported,
        "no_resolvable_refs": no_refs, "refs_present_but_no_cited_page_quote_containment": failed,
        "unsupported_or_weak_count": no_refs + failed,
        "unsupported_or_weak_rate": pct(no_refs + failed, total),
    }


def output_evidence(output: dict, checks: dict | None) -> dict:
    refs = (checks or {}).get("evidence_refs") or []
    ref_count = len(refs)
    page_valid = sum(bool(x.get("page_valid")) for x in refs)
    quote_nonempty = sum(bool(x.get("quote_nonempty")) for x in refs)
    cited = sum(bool(x.get("quote_contained_cited_page")) for x in refs)
    any_page = sum(bool(x.get("quote_contained_any_page")) for x in refs)
    return {
        "citation_ref_count": ref_count,
        "in_range_integer_page_refs": page_valid,
        "page_valid_ref_rate": pct(page_valid, ref_count),
        "nonempty_quote_refs": quote_nonempty,
        "quote_contained_cited_page_refs": cited,
        "quote_containment_cited_page_rate": pct(cited, ref_count),
        "quote_contained_any_page_refs": any_page,
        "quote_containment_any_page_rate": pct(any_page, ref_count),
        "claims": unit_support(output, checks, "claims"),
        "insights": unit_support(output, checks, "insights"),
        "insight_count": len(output.get("insights") or []),
        "claim_item_count": len((output.get("paper") or {}).get("key_claims") or []) + len((output.get("paper") or {}).get("evidence") or []),
        "confidence_values": [float(x["confidence"]) for x in output.get("insights", []) if isinstance(x, dict) and isinstance(x.get("confidence"), (float, int))],
    }


def output_claims(output: dict | None) -> list[dict]:
    if not isinstance(output, dict):
        return []
    paper = output.get("paper") or {}
    values = []
    seen = set()
    for field in ("key_claims", "evidence"):
        for item in paper.get(field, []) or []:
            if not isinstance(item, dict) or not isinstance(item.get("claim"), str):
                continue
            claim = item["claim"]
            dedupe = claim.strip().casefold()
            if dedupe and dedupe not in seen:
                seen.add(dedupe)
                values.append({"claim": claim, "evidence_refs": item.get("evidence_refs") or []})
    return values


def page_recall(ref_pages: list[int], candidate_pages: list[int]) -> dict:
    ref = set(ref_pages)
    cand = set(candidate_pages)
    found = sorted(ref & cand)
    return {"reference_pages": sorted(ref), "candidate_pages": sorted(cand),
            "found_pages": found, "missed_pages": sorted(ref - cand),
            "matched_count": len(found), "reference_count": len(ref),
            "recall": pct(len(found), len(ref))}


def reference_metric(l2_metrics, ref_claims: list[dict], candidate_claims: list[dict]) -> dict:
    out = {}
    for threshold in (0.15, 0.20, 0.25):
        result = l2_metrics.claims_recall(ref_claims, candidate_claims, threshold)
        out[f"{threshold:.2f}"] = result
    return out


def packet_pages(packet: dict | None) -> dict:
    refs = set()
    if not isinstance(packet, dict):
        return {"evidence_ref_pages": [], "declared_load_bearing_pages": []}
    for claim in packet.get("candidate_claims", []) or []:
        for ref in claim.get("evidence_refs", []) if isinstance(claim, dict) else []:
            page = ref.get("page") if isinstance(ref, dict) else None
            if isinstance(page, int) and not isinstance(page, bool):
                refs.add(page)
    declared = [p for p in packet.get("load_bearing_pages", []) if isinstance(p, int) and not isinstance(p, bool)]
    return {"evidence_ref_pages": sorted(refs), "declared_load_bearing_pages": sorted(set(declared))}


def cell_reliability(stage: dict | None, output: dict | None) -> dict:
    stage = stage or {}
    checks = stage.get("deterministic_checks") or {}
    attempts = artifact_attempts(stage.get("attempt_artifacts", []))
    normalized_pass = bool(stage.get("canonical_output") is not None and not stage.get("normalized_schema_errors") and checks.get("schema_shape_pass"))
    return {
        "attempted": bool(stage),
        "model_response": bool(stage.get("raw_output") or stage.get("canonical_output") or stage.get("parsed_packet")),
        "native_schema_pass": bool(stage.get("raw_output") is not None and not stage.get("native_schema_errors")),
        "normalized_schema_pass": normalized_pass,
        "normalized_json_schema_pass": bool(stage.get("canonical_output") is not None and not stage.get("normalized_schema_errors")),
        "page_valid": checks.get("all_cited_pages_valid"),
        "deterministic_validation_failure": bool(stage.get("raw_output") is not None and (
            stage.get("native_schema_errors") or stage.get("normalized_schema_errors") or
            (checks and not checks.get("schema_shape_pass")) or
            (checks and not checks.get("all_cited_pages_valid"))
        )),
        "attempt_count": len(attempts),
        "http_failure_attempts": sum(
            x.get("http_status") is not None and not 200 <= int(x["http_status"]) < 300
            for x in attempts
        ),
        "transport_failure_attempts": sum(x.get("http_status") is None for x in attempts),
        "transient_retry_attempts": sum(int(x.get("attempt") or 1) > 1 for x in attempts),
        "truncation_retry_attempts": sum(bool(x.get("retry_reason")) for x in attempts),
        "parse_error": stage.get("parse_error"),
        "provider_error": stage.get("provider_error") or stage.get("local_error"),
        "truncation_retry": bool(stage.get("retry", {}).get("truncation_retry")),
        "citation_ref_count": checks.get("evidence_ref_count"),
    }


def derive(ctx: dict) -> dict:
    a_state = bench.read_json(ROOT / "raw/armA-results.json")
    b_state = bench.read_json(ROOT / "raw/armB-results.json")
    j_state = bench.read_json(ROOT / "raw/judge-results.json")
    d_ref = {}
    rows = []
    miss_rows = []
    for pid in bench.PAPER_IDS:
        d_record = ctx["d_artifacts"][pid]
        d_output = bench.extract_json(str(d_record.get("output") or "{}"))
        d_ref[pid] = d_output
        d_lb_pages = ctx["l2_metrics"].loadbearing_pages(d_output)
        d_claims = d_output.get("candidate_claims") or []
        a_cell = a_state.get("papers", {}).get(pid, {})
        b_row = b_state.get("papers", {}).get(pid, {})
        b_packet = b_row.get("gemini_stage", {}).get("parsed_packet")
        b_final = b_row.get("luna_stage", {})
        outputs = {
            "A": a_cell.get("canonical_output"),
            "B": b_final.get("canonical_output"),
        }
        arm_metrics = {}
        for arm, output in outputs.items():
            if not isinstance(output, dict):
                arm_metrics[arm] = {"available": False}
                continue
            checks = (a_cell if arm == "A" else b_final).get("deterministic_checks") or {}
            evidence = output_evidence(output, checks)
            candidate_pages = sorted({
                ref.get("page")
                for items in [
                    (output.get("paper") or {}).get("key_claims", []),
                    (output.get("paper") or {}).get("evidence", []),
                    output.get("insights", []),
                ]
                for item in items if isinstance(item, dict)
                for ref in item.get("evidence_refs", []) if isinstance(ref, dict)
                if isinstance(ref.get("page"), int) and not isinstance(ref.get("page"), bool)
            })
            recall = reference_metric(ctx["l2_metrics"], d_claims, output_claims(output))
            recall20 = recall["0.20"]
            misses = [x for x in recall20["details"] if x.get("importance") == "load_bearing" and not x.get("matched")]
            for miss in misses:
                claim = miss.get("reference_claim", "")
                miss_row = {
                    "paper_id": pid, "arm": arm,
                    "claim": claim,
                    "reference_pages": miss.get("reference_pages", []),
                    "best_jaccard": miss.get("best_jaccard"),
                    "numeric_result_or_value": bool(re.search(r"\d|%|±", claim)),
                }
                miss_rows.append(miss_row)
            conf = evidence["confidence_values"]
            arm_metrics[arm] = {
                "available": True,
                "load_bearing_page_recall": page_recall(d_lb_pages, candidate_pages),
                "candidate_page_refs": candidate_pages,
                "reference_claim_recall": {k: v["recall"] for k, v in recall.items()},
                "claim_recall_counts": {k: {"matched": v["matched_count"], "reference": v["reference_claim_count"]} for k, v in recall.items()},
                "claim_recall_details_020": recall20["details"],
                "important_claim_misses": misses,
                "citation_and_support": evidence,
                "native_schema_pass": bool((a_cell if arm == "A" else b_final).get("raw_output") is not None and not (a_cell if arm == "A" else b_final).get("native_schema_errors")),
                "normalized_schema_pass": bool((a_cell if arm == "A" else b_final).get("canonical_output") is not None and not (a_cell if arm == "A" else b_final).get("normalized_schema_errors") and checks.get("schema_shape_pass")),
                "normalized_json_schema_pass": bool((a_cell if arm == "A" else b_final).get("canonical_output") is not None and not (a_cell if arm == "A" else b_final).get("normalized_schema_errors")),
                "page_valid_output": checks.get("all_cited_pages_valid"),
                "insight_count": evidence["insight_count"],
                "confidence": {"n": len(conf), "mean": mean(conf), "min": min(conf) if conf else None, "max": max(conf) if conf else None},
            }
        packet_metric = {"available": False}
        if isinstance(b_packet, dict):
            pclaims = bench.packet_claims(b_packet)
            p_recall = reference_metric(ctx["l2_metrics"], d_claims, pclaims)
            p_pages = packet_pages(b_packet)
            packet_metric = {
                "available": True,
                "evidence_ref_page_recall": page_recall(d_lb_pages, p_pages["evidence_ref_pages"]),
                "declared_page_recall": page_recall(d_lb_pages, p_pages["declared_load_bearing_pages"]),
                "candidate_pages": p_pages["evidence_ref_pages"],
                "reference_claim_recall": {k: v["recall"] for k, v in p_recall.items()},
                "claim_recall_details_020": p_recall["0.20"]["details"],
                "packet_schema_pass": b_row.get("gemini_stage", {}).get("packet_schema_pass"),
                "packet_schema_errors": b_row.get("gemini_stage", {}).get("packet_schema_errors", []),
                "claim_count": len(pclaims),
                "load_bearing_pages_declared": p_pages["declared_load_bearing_pages"],
            }
            for miss in p_recall["0.20"]["details"]:
                if miss.get("importance") == "load_bearing" and not miss.get("matched"):
                    miss_rows.append({
                        "paper_id": pid, "arm": "B-Gemini-packet",
                        "claim": miss.get("reference_claim", ""),
                        "reference_pages": miss.get("reference_pages", []),
                        "best_jaccard": miss.get("best_jaccard"),
                        "numeric_result_or_value": bool(re.search(r"\d|%|±", miss.get("reference_claim", ""))),
                    })
        aa = group_attempts(a_cell)
        bb = group_attempts(b_row.get("gemini_stage"), b_final)
        a_totals, b_totals = attempt_totals(aa), attempt_totals(bb)
        b_gemini_totals = attempt_totals(group_attempts(b_row.get("gemini_stage")))
        b_luna_totals = attempt_totals(group_attempts(b_final))
        ag = a_cell.get("end_to_end_latency_ms")
        bg = b_row.get("end_to_end_latency_ms")
        rows.append({
            "paper_id": pid,
            "d_load_bearing_pages": d_lb_pages,
            "d_load_bearing_claim_count": sum(x.get("importance") == "load_bearing" for x in d_claims if isinstance(x, dict)),
            "armA": arm_metrics["A"], "armB": arm_metrics["B"],
            "armB_gemini_packet": packet_metric,
            "armA_performance": {**a_totals, "end_to_end_latency_ms": ag},
            "armB_performance": {**b_totals, "end_to_end_latency_ms": bg,
                                 "gemini_stage_latency_ms": b_row.get("gemini_stage", {}).get("latency_ms_attempt_sum"),
                                 "luna_stage_latency_ms": b_final.get("latency_ms_attempt_sum")},
            "armB_gemini_performance": b_gemini_totals,
            "armB_luna_performance": b_luna_totals,
            "armA_reliability": cell_reliability(a_cell, outputs["A"]),
            "armB_gemini_reliability": {
                "attempted": bool(b_row.get("gemini_stage")),
                "model_response": bool(b_row.get("gemini_stage", {}).get("parsed_packet")),
                "packet_schema_pass": b_row.get("gemini_stage", {}).get("packet_schema_pass"),
                "deterministic_validation_failure": bool(b_row.get("gemini_stage", {}).get("parsed_packet") is not None and not b_row.get("gemini_stage", {}).get("packet_schema_pass")),
                "attempt_count": b_gemini_totals["attempts"],
                "transient_retry_attempts": b_gemini_totals["transient_retry_attempts"],
                "truncation_retry_attempts": b_gemini_totals["truncation_retry_attempts"],
                "parse_error": b_row.get("gemini_stage", {}).get("parse_error"),
                "provider_error": b_row.get("gemini_stage", {}).get("provider_error") or b_row.get("gemini_stage", {}).get("local_error"),
                "truncation_retry": bool(b_row.get("gemini_stage", {}).get("retry", {}).get("truncation_retry")),
            },
            "armB_luna_reliability": cell_reliability(b_final, outputs["B"]),
            "armB_status": b_row.get("status"),
        })
    aggregate = aggregate_metrics(rows, miss_rows)
    judge_metrics = aggregate_judges(ctx, j_state)
    divergence = {
        "paper_claim_instances": 0,
        "armA_matches": 0,
        "gemini_packet_matches": 0,
        "armB_final_matches": 0,
        "armA_only_vs_armB_final": 0,
        "armB_final_only_vs_armA": 0,
        "packet_match_lost_by_final": 0,
        "packet_miss_recovered_by_final": 0,
        "packet_and_final_miss": 0,
    }
    for row in rows:
        a_details = row["armA"].get("claim_recall_details_020", [])
        packet_details = row["armB_gemini_packet"].get("claim_recall_details_020", [])
        b_details = row["armB"].get("claim_recall_details_020", [])
        packet_by_index = {x["reference_index"]: x for x in packet_details}
        b_by_index = {x["reference_index"]: x for x in b_details}
        for item in a_details:
            index = item["reference_index"]
            a_hit = bool(item.get("matched"))
            packet_hit = bool(packet_by_index.get(index, {}).get("matched"))
            b_hit = bool(b_by_index.get(index, {}).get("matched"))
            divergence["paper_claim_instances"] += 1
            divergence["armA_matches"] += int(a_hit)
            divergence["gemini_packet_matches"] += int(packet_hit)
            divergence["armB_final_matches"] += int(b_hit)
            divergence["armA_only_vs_armB_final"] += int(a_hit and not b_hit)
            divergence["armB_final_only_vs_armA"] += int(b_hit and not a_hit)
            divergence["packet_match_lost_by_final"] += int(packet_hit and not b_hit)
            divergence["packet_miss_recovered_by_final"] += int(not packet_hit and b_hit)
            divergence["packet_and_final_miss"] += int(not packet_hit and not b_hit)
    return {
        "schema_version": 1,
        "paper_count": len(rows),
        "papers": rows,
        "aggregate": aggregate,
        "important_evidence_misses": miss_rows,
        "claim_divergence_summary_020": divergence,
        "judges": judge_metrics,
        "arm_status": {"A": a_state.get("status"), "B": b_state.get("status")},
        "judge_status": j_state.get("status"),
        "optional_second_judge_status": j_state.get("deepseek_second_judge", "not attempted"),
        "uncertainty_calibration": "N/A: no confidence/outcome series",
        "claim_recall_operationalization": "D candidate_claims are references; candidates are deduplicated paper.key_claims[].claim + paper.evidence[].claim; match is maximum content-word Jaccard with DQ79 fixed stopwords, threshold 0.20 primary, sensitivity 0.15/0.25.",
        "citation_proxy_definition": "In-range integer page and quote containment after case/whitespace normalization on cited page or any page; lexical resolvability proxies, not semantic entailment.",
        "support_rate_definition": "Support-rate claim units are key_claims and evidence items counted separately, without deduplication; insight items are counted separately. A claim or insight is unsupported/weak if it has no refs, or if none of its refs has both an in-range integer page and a nonempty quote contained on that cited page.",
        "page_recall_definition": "Union of canonical output evidence_refs[].page across key claims, evidence, and insights intersected with D load_bearing_pages; denominator is D load_bearing_pages count.",
    }


def prompt_alignment(ctx: dict) -> dict:
    a_state = bench.read_json(ROOT / "raw/armA-results.json")
    b_state = bench.read_json(ROOT / "raw/armB-results.json")
    rows = []
    for pid in bench.PAPER_IDS:
        packet = b_state.get("papers", {}).get(pid, {}).get("gemini_stage", {}).get("serialized_packet")
        if not packet:
            rows.append({"paper_id": pid, "complete": False, "match_except_source": False,
                         "reason": "Gemini packet unavailable; exact Luna prompt pair could not be reconstructed."})
            continue
        user_a, _, method_a = bench.luna_user_from_reference(ctx, pid)
        user_b, _, method_b = bench.luna_user_from_reference(ctx, pid, packet)
        marker = "\nSOURCE METHOD:"
        prefix_a, sep_a, tail_a = user_a.partition(marker)
        prefix_b, sep_b, tail_b = user_b.partition(marker)
        normalized_tail_a = "<SOURCE METHOD>\nSOURCE:\n<SOURCE PAYLOAD>"
        normalized_tail_b = "<SOURCE METHOD>\nSOURCE:\n<SOURCE PAYLOAD>"
        normalized_user_a = prefix_a + normalized_tail_a if sep_a else user_a
        normalized_user_b = prefix_b + normalized_tail_b if sep_b else user_b
        body_a = {
            "model": "gpt-6-luna",
            "messages": [{"role": "system", "content": ctx["run_l3"].SYSTEM},
                         {"role": "user", "content": "Follow the artifact contract exactly.\n\n" + normalized_user_a}],
            "reasoning_effort": "none", "max_completion_tokens": 3600,
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "paper_insight", "strict": True, "schema": ctx["run_l3"].OUTPUT_SCHEMA}},
        }
        body_b = copy.deepcopy(body_a)
        body_b["messages"][1]["content"] = "Follow the artifact contract exactly.\n\n" + normalized_user_b
        actual_a = copy.deepcopy(body_a)
        actual_b = copy.deepcopy(body_b)
        actual_a["messages"][1]["content"] = "Follow the artifact contract exactly.\n\n" + user_a
        actual_b["messages"][1]["content"] = "Follow the artifact contract exactly.\n\n" + user_b
        a_cell = a_state.get("papers", {}).get(pid, {})
        b_cell = b_state.get("papers", {}).get(pid, {}).get("luna_stage", {})
        body_a_hash = hashlib.sha256(json.dumps(actual_a, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        body_b_hash = hashlib.sha256(json.dumps(actual_b, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        rows.append({
            "paper_id": pid, "complete": True,
            "match_except_source": bench.canonical_json(body_a) == bench.canonical_json(body_b),
            "system_prompt_identical": True,
            "metadata_prefix_identical": bool(sep_a and sep_b and prefix_a == prefix_b),
            "armA_source_method": method_a,
            "armB_source_method": method_b,
            "only_declared_difference": "SOURCE METHOD line and SOURCE payload",
            "armA_reconstructed_request_body_sha256": body_a_hash,
            "armA_saved_request_body_sha256": a_cell.get("request_body_sha256"),
            "armB_reconstructed_request_body_sha256": body_b_hash,
            "armB_saved_request_body_sha256": b_cell.get("request_body_sha256"),
            "request_hashes_match_saved": body_a_hash == a_cell.get("request_body_sha256") and body_b_hash == b_cell.get("request_body_sha256"),
        })
    templates = {
        name: (ROOT / "raw/prompts" / name).read_text(encoding="utf-8")
        for name in ("armA-luna.md", "armB-luna.md")
    }
    template_match = templates["armA-luna.md"].replace(
        "strategy-D complete page-labelled PyMuPDF text extraction", "<SOURCE METHOD>"
    ) == templates["armB-luna.md"].replace(
        "Gemini Flash-Lite structured evidence packet extracted from the full page-labelled paper text", "<SOURCE METHOD>"
    )
    result = {
        "template_match_except_source_method": template_match,
        "paper_count": len(rows),
        "all_complete": all(x["complete"] for x in rows),
        "all_match_except_source": all(x.get("match_except_source", False) for x in rows),
        "all_metadata_prefixes_identical": all(x.get("metadata_prefix_identical", False) for x in rows),
        "all_reconstructed_body_hashes_match_saved": all(x.get("request_hashes_match_saved", False) for x in rows),
        "papers": rows,
    }
    bench.write_json(ROOT / "raw/prompt-alignment.json", result)
    return result


def aggregate_metrics(rows: list[dict], miss_rows: list[dict]) -> dict:
    result = {"arms": {}}
    for arm, key in (("A", "armA"), ("B", "armB")):
        available = [r[key] for r in rows if r[key].get("available")]
        result["arms"][arm] = {
            "papers_with_output": len(available),
            "mean_load_bearing_page_recall": mean([x["load_bearing_page_recall"]["recall"] for x in available]),
            "mean_reference_claim_recall": {
                threshold: mean([x["reference_claim_recall"][threshold] for x in available])
                for threshold in ("0.15", "0.20", "0.25")
            },
            "important_d_claim_misses": sum(len(x["important_claim_misses"]) for x in available),
            "important_d_claims_total": sum(r["d_load_bearing_claim_count"] for r in rows),
            "native_schema_passes": sum(bool(x["native_schema_pass"]) for x in available),
            "normalized_schema_passes": sum(bool(x["normalized_schema_pass"]) for x in available),
            "normalized_json_schema_passes": sum(bool(x["normalized_json_schema_pass"]) for x in available),
            "page_valid_outputs": sum(bool(x["page_valid_output"]) for x in available),
            "citation_ref_count": sum(x["citation_and_support"]["citation_ref_count"] for x in available),
            "page_valid_refs": sum(x["citation_and_support"]["in_range_integer_page_refs"] for x in available),
            "cited_page_quote_matches": sum(x["citation_and_support"]["quote_contained_cited_page_refs"] for x in available),
            "any_page_quote_matches": sum(x["citation_and_support"]["quote_contained_any_page_refs"] for x in available),
            "claims": {
                "total": sum(x["citation_and_support"]["claims"]["unit_count"] for x in available),
                "unsupported_or_weak": sum(x["citation_and_support"]["claims"]["unsupported_or_weak_count"] for x in available),
            },
            "insights": {
                "total": sum(x["citation_and_support"]["insights"]["unit_count"] for x in available),
                "unsupported_or_weak": sum(x["citation_and_support"]["insights"]["unsupported_or_weak_count"] for x in available),
            },
        }
        perf_key = "armA_performance" if arm == "A" else "armB_performance"
        arm_rows = [r for r in rows if int(r[perf_key].get("attempts") or 0) > 0]
        perf_summary = {"papers_attempted": len(arm_rows)}
        perf_summary.update({
            metric: sum(float(r[perf_key].get(metric) or 0) for r in arm_rows)
            for metric in ("attempts", "input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "latency_ms_attempt_sum", "cost_usd", "end_to_end_latency_ms")
        })
        result["arms"][arm]["performance"] = perf_summary
        result["arms"][arm]["performance"]["median_end_to_end_latency_ms"] = median([r[perf_key].get("end_to_end_latency_ms") for r in arm_rows])
        result["arms"][arm]["performance"]["mean_cost_per_paper_usd"] = pct(
            result["arms"][arm]["performance"]["cost_usd"], len(arm_rows)
        )
    packet_rows = [r["armB_gemini_packet"] for r in rows if r["armB_gemini_packet"].get("available")]
    result["armB_gemini_packet"] = {
        "papers_with_packet": len(packet_rows),
        "mean_evidence_ref_page_recall": mean([x["evidence_ref_page_recall"]["recall"] for x in packet_rows]),
        "mean_declared_page_recall": mean([x["declared_page_recall"]["recall"] for x in packet_rows]),
        "mean_reference_claim_recall": {
            threshold: mean([x["reference_claim_recall"][threshold] for x in packet_rows])
            for threshold in ("0.15", "0.20", "0.25")
        },
        "packet_schema_passes": sum(bool(x.get("packet_schema_pass")) for x in packet_rows),
        "packet_candidates": sum(x.get("claim_count", 0) for x in packet_rows),
    }
    result["B_stage_performance"] = {}
    for name, key in (("Gemini_packet", "armB_gemini_performance"), ("Luna_final", "armB_luna_performance")):
        stage_rows = [r[key] for r in rows if int(r[key].get("attempts") or 0) > 0]
        stage_summary = {"papers_attempted": len(stage_rows)}
        for metric in ("attempts", "input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "latency_ms_attempt_sum", "cost_usd", "http_200_attempts", "http_failures", "transport_failures", "transient_retry_attempts", "truncation_retry_attempts"):
            stage_summary[metric] = sum(float(x.get(metric) or 0) for x in stage_rows)
        stage_summary["mean_cost_per_paper_usd"] = pct(stage_summary["cost_usd"], len(stage_rows))
        stage_summary["median_attempt_latency_ms"] = median([x.get("latency_ms_attempt_sum") for x in stage_rows])
        result["B_stage_performance"][name] = stage_summary
    for arm in ("A", "B"):
        result["arms"][arm]["important_d_claim_miss_rows"] = sum(
            x["arm"] == arm for x in miss_rows
        )
    return result


def normalized_judge_rows(ctx: dict, output: object) -> tuple[list[dict], str | None]:
    """Use DQ79's score normalizer; accept explicit numeric scores, never preference prose."""
    normalizer = ctx["l3_metrics"].normalized_judge_scores
    rows, issue = normalizer(output)
    if rows:
        return rows, issue
    if isinstance(output, dict):
        # Some responses placed the same labeled numeric rows under top-level A/B keys.
        adapted = {"scores": []}
        for label in ("A", "B"):
            item = output.get(label)
            if isinstance(item, dict):
                adapted["scores"].append({**item, "blind_label": label})
        if adapted["scores"]:
            return normalizer(adapted)
    return [], issue


def aggregate_judges(ctx: dict, state: dict) -> dict:
    cells = state.get("judges", {})
    bins = {provider: {arm: {dim: [] for dim in bench.DIMENSIONS} for arm in ("A", "B")}
            for provider in ("gemini", "deepseek")}
    cell_details = []
    schema = {provider: {"calls": 0, "schema_pass": 0, "parse_failures": 0} for provider in bins}
    for key, value in cells.items():
        provider = value.get("provider")
        if provider not in bins:
            continue
        schema[provider]["calls"] += 1
        schema[provider]["schema_pass"] += bool(value.get("schema_pass"))
        schema[provider]["parse_failures"] += bool(value.get("parse_error"))
        mapping = value.get("label_to_arm_internal") or {}
        output = value.get("output")
        scores, normalization_issue = normalized_judge_rows(ctx, output)
        for row in scores:
            if not isinstance(row, dict):
                continue
            arm = mapping.get(row.get("blind_label"))
            if arm not in ("A", "B"):
                continue
            for dim in bench.DIMENSIONS:
                score = row.get(dim)
                if isinstance(score, int) and not isinstance(score, bool) and 0 <= score <= 4:
                    bins[provider][arm][dim].append(score)
        cell_details.append({
            "paper_id": key.split("/", 1)[0], "provider": provider,
            "strict_schema_pass": value.get("schema_pass"),
            "strict_schema_issues": value.get("schema_issues", []),
            "dq79_numeric_score_normalization_issue": normalization_issue,
            "normalized_candidate_score_count": len(scores),
        })
    means = {}
    for provider, arms in bins.items():
        means[provider] = {}
        for arm, dimensions in arms.items():
            means[provider][arm] = {
                dim: {"mean_0_to_4": mean(values), "n": len(values)}
                for dim, values in dimensions.items()
            }
    deepseek_reliable = (
        schema["deepseek"]["calls"] >= 2 and
        schema["deepseek"]["schema_pass"] == schema["deepseek"]["calls"]
    )
    if not deepseek_reliable:
        for arm in ("A", "B"):
            for dim in bench.DIMENSIONS:
                bins["deepseek"][arm][dim].clear()
                means["deepseek"][arm][dim] = {"mean_0_to_4": None, "n": 0}
    return {"mean_scores": means, "format_reliability": schema,
            "cell_details": cell_details,
            "normalization_method": "DQ79 l3_metrics.normalized_judge_scores; alternate A/B or evaluation shapes are deterministically mapped, and only numeric 0..4 values are scored. Preference/winner prose is never translated.",
            "deepseek_second_judge_used": deepseek_reliable,
            "deepseek_second_judge_reason": "used after at least two fully schema-compliant paired cells" if deepseek_reliable else "not used for quality means: fewer than two strict schema-compliant paired judge cells; all attempts remain in raw/judge-results.json",
            "uncertainty_calibration": "N/A: no confidence/outcome series"}


def stage_attempts_for_arm(rows: list[dict], arm: str) -> list[dict]:
    result = []
    for row in rows:
        if arm == "A":
            result.extend(artifact_attempts(row["armA_performance"].get("artifact_paths", [])))
        else:
            result.extend(artifact_attempts(row["armB_performance"].get("artifact_paths", [])))
    return result


def reliability_summary(rows: list[dict], arm_a_state: dict, arm_b_state: dict, judges: dict) -> dict:
    a_rows = [r for r in rows if r["armA_reliability"].get("attempted")]
    b_g = [r for r in rows if r["armB_gemini_reliability"].get("attempted")]
    b_l = [r for r in rows if r["armB_luna_reliability"].get("attempted")]
    def stats(stage_rows, key):
        return {
            "attempted_papers": len(stage_rows),
            "attempts": sum(int(x.get(key, {}).get("attempt_count") or 0) for x in stage_rows),
            "model_responses": sum(bool(x.get(key, {}).get("model_response")) for x in stage_rows),
            "native_schema_passes": sum(bool(x.get(key, {}).get("native_schema_pass")) for x in stage_rows),
            "normalized_schema_passes": sum(bool(x.get(key, {}).get("normalized_schema_pass")) for x in stage_rows),
            "page_valid_outputs": sum(bool(x.get(key, {}).get("page_valid")) for x in stage_rows),
            "deterministic_validation_failures": sum(bool(x.get(key, {}).get("deterministic_validation_failure")) for x in stage_rows),
            "http_failure_attempts": sum(int(x.get(key, {}).get("http_failure_attempts") or 0) for x in stage_rows),
            "transport_failure_attempts": sum(int(x.get(key, {}).get("transport_failure_attempts") or 0) for x in stage_rows),
            "parse_failures": sum(bool(x.get(key, {}).get("parse_error")) for x in stage_rows),
            "provider_failures": sum(bool(x.get(key, {}).get("provider_error")) for x in stage_rows),
            "truncation_retry_papers": sum(bool(x.get(key, {}).get("truncation_retry")) for x in stage_rows),
            "transient_retry_attempts": sum(int(x.get(key, {}).get("transient_retry_attempts") or 0) for x in stage_rows),
            "truncation_retry_attempts": sum(int(x.get(key, {}).get("truncation_retry_attempts") or 0) for x in stage_rows),
        }
    return {
        "A": stats(a_rows, "armA_reliability"),
        "B_Gemini_packet": {
            "attempted_papers": len(b_g),
            "attempts": sum(int(x["armB_gemini_reliability"].get("attempt_count") or 0) for x in b_g),
            "model_responses": sum(bool(x["armB_gemini_reliability"].get("model_response")) for x in b_g),
            "packet_schema_passes": sum(bool(x["armB_gemini_reliability"].get("packet_schema_pass")) for x in b_g),
            "deterministic_validation_failures": sum(bool(x["armB_gemini_reliability"].get("deterministic_validation_failure")) for x in b_g),
            "http_failure_attempts": sum(int(x["armB_gemini_reliability"].get("http_failure_attempts") or 0) for x in b_g),
            "transport_failure_attempts": sum(int(x["armB_gemini_reliability"].get("transport_failure_attempts") or 0) for x in b_g),
            "parse_failures": sum(bool(x["armB_gemini_reliability"].get("parse_error")) for x in b_g),
            "provider_failures": sum(bool(x["armB_gemini_reliability"].get("provider_error")) for x in b_g),
            "truncation_retry_papers": sum(bool(x["armB_gemini_reliability"].get("truncation_retry")) for x in b_g),
            "transient_retry_attempts": sum(int(x["armB_gemini_reliability"].get("transient_retry_attempts") or 0) for x in b_g),
            "truncation_retry_attempts": sum(int(x["armB_gemini_reliability"].get("truncation_retry_attempts") or 0) for x in b_g),
        },
        "B_Luna_final": stats(b_l, "armB_luna_reliability"),
        "arm_status": {"A": arm_a_state.get("status"), "B": arm_b_state.get("status")},
        "judge_format": judges.get("format_reliability", {}),
    }


def public_rows(metrics: dict) -> list[dict]:
    rows = []
    for p in metrics["papers"]:
        row = {"paper_id": p["paper_id"], "d_load_bearing_page_count": len(p["d_load_bearing_pages"])}
        for arm, key in (("A", "armA"), ("B", "armB")):
            x = p[key]
            row[f"{arm}_available"] = x.get("available", False)
            row[f"{arm}_load_bearing_page_recall"] = x.get("load_bearing_page_recall", {}).get("recall")
            row[f"{arm}_claim_recall_015"] = x.get("reference_claim_recall", {}).get("0.15")
            row[f"{arm}_claim_recall_020"] = x.get("reference_claim_recall", {}).get("0.20")
            row[f"{arm}_claim_recall_025"] = x.get("reference_claim_recall", {}).get("0.25")
            row[f"{arm}_native_schema_pass"] = x.get("native_schema_pass")
            row[f"{arm}_normalized_schema_pass"] = x.get("normalized_schema_pass")
            row[f"{arm}_page_valid_ref_rate"] = x.get("citation_and_support", {}).get("page_valid_ref_rate")
            row[f"{arm}_quote_cited_page_rate"] = x.get("citation_and_support", {}).get("quote_containment_cited_page_rate")
            row[f"{arm}_claims_unsupported_rate"] = x.get("citation_and_support", {}).get("claims", {}).get("unsupported_or_weak_rate")
            row[f"{arm}_insights_unsupported_rate"] = x.get("citation_and_support", {}).get("insights", {}).get("unsupported_or_weak_rate")
            row[f"{arm}_citation_refs"] = x.get("citation_and_support", {}).get("citation_ref_count")
            perf = p["armA_performance"] if arm == "A" else p["armB_performance"]
            row[f"{arm}_cost_usd"] = perf.get("cost_usd")
            row[f"{arm}_latency_ms"] = perf.get("end_to_end_latency_ms")
            row[f"{arm}_input_tokens"] = perf.get("input_tokens")
            row[f"{arm}_output_tokens"] = perf.get("output_tokens")
            row[f"{arm}_cached_input_tokens"] = perf.get("cached_input_tokens")
            if arm == "B":
                for stage, stagekey in (("gemini", "armB_gemini_performance"), ("luna", "armB_luna_performance")):
                    stage_perf = p[stagekey]
                    row[f"B_{stage}_cost_usd"] = stage_perf.get("cost_usd")
                    row[f"B_{stage}_latency_ms"] = stage_perf.get("latency_ms_attempt_sum")
                    row[f"B_{stage}_input_tokens"] = stage_perf.get("input_tokens")
                    row[f"B_{stage}_output_tokens"] = stage_perf.get("output_tokens")
                    row[f"B_{stage}_cached_input_tokens"] = stage_perf.get("cached_input_tokens")
        packet = p["armB_gemini_packet"]
        row["B_packet_page_recall"] = packet.get("evidence_ref_page_recall", {}).get("recall")
        row["B_packet_claim_recall_020"] = packet.get("reference_claim_recall", {}).get("0.20")
        rows.append(row)
    return rows


def scale_model(metrics: dict) -> dict:
    scale_sizes = [1000, 10000, 100000, 1000000]
    arms = {}
    for arm in ("A", "B"):
        agg = metrics["aggregate"]["arms"][arm]
        per_paper = agg["performance"]["mean_cost_per_paper_usd"]
        serial_mean_ms = agg["performance"]["end_to_end_latency_ms"] / max(agg["performance"]["papers_attempted"], 1)
        arms[arm] = {
            "measured_mean_cost_per_escalated_paper_usd": per_paper,
            "measured_serial_end_to_end_latency_mean_ms": serial_mean_ms,
            "modeled_escalated_papers": {
                str(n): {"modeled_cost_usd": n * per_paper if per_paper is not None else None,
                         "modeled_serial_hours": (n * serial_mean_ms / 3_600_000) if serial_mean_ms else None}
                for n in scale_sizes
            },
            "modeled_funnel": [
                {"incoming_papers": n, "escalation_rate": rate,
                 "escalated_papers": int(n * rate),
                 "modeled_cost_usd": int(n * rate) * per_paper if per_paper is not None else None}
                for n in scale_sizes for rate in (0.10, 0.25, 0.50)
            ],
            "modeled_worker_pool_throughput": [
                {"workers_K": k,
                 "modeled_papers_per_second": k / (serial_mean_ms / 1000) if serial_mean_ms else None,
                 "modeled_papers_per_hour": 3600 * k / (serial_mean_ms / 1000) if serial_mean_ms else None}
                for k in (1, 4, 8, 16)
            ],
            "source_status": "modeled from measured per-paper aggregate; values are never measured scale observations",
        }
    return {
        "unit_cost_basis": "Measured arm attempt cost / papers with at least one arm-stage call. Failed or incomplete papers remain in the denominator because their calls still consume measured tokens and cost; output completion counts are reported separately.",
        "paper_scales": scale_sizes,
        "funnel_escalation_rates": [0.10, 0.25, 0.50],
        "worker_pools": [1, 4, 8, 16],
        "concurrency_model": "Workers process papers independently; each B paper performs Gemini extraction then Luna synthesis serially; mean end-to-end time uses measured per-paper calls including request retries and backoff. Throughput is K / mean end-to-end latency.",
        "rate_limit_assumptions": "No rate-limit contention, provider queueing, or quota throttling is modeled. Retry/backoff behavior is represented only by this small serial sample; actual limits are provider/account specific and may lower throughput.",
        "arms": arms,
    }


def render_arm_tables(ctx: dict, metrics: dict) -> tuple[str, str]:
    a_state = bench.read_json(ROOT / "raw/armA-results.json")
    b_state = bench.read_json(ROOT / "raw/armB-results.json")
    a = ["| Paper | Claims (key+evidence) / insights | D load-bearing page recall | Refs: count / page-valid / cited-page quote | Schema: native / normalized / page-valid | Confidence n / mean / range | Latency (ms) | Tokens in/out/cached | Cost (USD) |", "|---|---:|---:|---:|---|---:|---:|---:|---:|"]
    b = ["| Paper | Gemini packet claims / Luna claims+insights | Packet page recall (refs) / final page recall | Final refs: count / page-valid / cited-page quote | Packet schema / Luna native / normalized / page-valid | Confidence n / mean / range | Gemini / Luna / end-to-end latency (ms) | Tokens in/out/cached (Gemini + Luna) | Cost (USD: Gemini / Luna / total) |", "|---|---:|---:|---:|---|---:|---:|---:|---:|"]
    for row in metrics["papers"]:
        pid = row["paper_id"]
        ac = a_state.get("papers", {}).get(pid, {})
        av = row["armA"]
        if not av.get("available"):
            a.append(f"| {pid} | — | — | — | — | — | — | — |")
        else:
            ev = av["citation_and_support"]
            confidence = av["confidence"]
            perf = row["armA_performance"]
            confidence_text = f"{confidence['n']} / {fmt(confidence['mean'])} / {fmt(confidence['min'])}–{fmt(confidence['max'])}"
            a.append(
                f"| {pid} | {ev['claim_item_count']} / {ev['insight_count']} | {fmt(av['load_bearing_page_recall']['recall'])} ({av['load_bearing_page_recall']['matched_count']}/{av['load_bearing_page_recall']['reference_count']}) | {ev['citation_ref_count']} / {ev['in_range_integer_page_refs']} / {ev['quote_contained_cited_page_refs']} | {int(av['native_schema_pass'])} / {int(av['normalized_schema_pass'])} / {str(av['page_valid_output']).lower()} | {confidence_text} | {ac.get('end_to_end_latency_ms', '—')} | {int(perf.get('input_tokens') or 0)} / {int(perf.get('output_tokens') or 0)} / {int(perf.get('cached_input_tokens') or 0)} | {perf.get('cost_usd', 0):.6f} |"
            )
        br = bench.read_json(ROOT / "raw/armB-results.json").get("papers", {}).get(pid, {})
        packet = row["armB_gemini_packet"]
        bv = row["armB"]
        gs = br.get("gemini_stage", {})
        ls = br.get("luna_stage", {})
        if not packet.get("available") and not bv.get("available"):
            b.append(f"| {pid} | — | — | — | — | — | — | — | — |")
        else:
            p_recall = packet.get("evidence_ref_page_recall", {}).get("recall")
            final_recall = bv.get("load_bearing_page_recall", {}).get("recall")
            ev = bv.get("citation_and_support", {})
            gt = attempt_totals(artifact_attempts(gs.get("attempt_artifacts", [])))
            lt = attempt_totals(artifact_attempts(ls.get("attempt_artifacts", [])))
            confidence = bv.get("confidence", {})
            confidence_text = f"{confidence.get('n', 0)} / {fmt(confidence.get('mean'))} / {fmt(confidence.get('min'))}–{fmt(confidence.get('max'))}"
            packet_claim_count = packet.get("claim_count", 0)
            b.append(
                f"| {pid} | {packet_claim_count} / {ev.get('claim_item_count', 0)} + {ev.get('insight_count', 0)} | {fmt(p_recall)} / {fmt(final_recall)} | {ev.get('citation_ref_count', '—')} / {ev.get('in_range_integer_page_refs', '—')} / {ev.get('quote_contained_cited_page_refs', '—')} | {str(gs.get('packet_schema_pass', '—')).lower()} / {str(bool(ls.get('raw_output') is not None and not ls.get('native_schema_errors'))).lower()} / {str(bool(ls.get('canonical_output') is not None and not ls.get('normalized_schema_errors') and (ls.get('deterministic_checks') or {}).get('schema_shape_pass'))).lower()} / {str((ls.get('deterministic_checks') or {}).get('all_cited_pages_valid', '—')).lower()} | {confidence_text} | {gs.get('latency_ms_attempt_sum', '—')} / {ls.get('latency_ms_attempt_sum', '—')} / {br.get('end_to_end_latency_ms', '—')} | {gt['input_tokens']} / {gt['output_tokens']} / {gt['cached_input_tokens']} + {lt['input_tokens']} / {lt['output_tokens']} / {lt['cached_input_tokens']} | {gt['cost_usd']:.6f} / {lt['cost_usd']:.6f} / {gt['cost_usd'] + lt['cost_usd']:.6f} |"
            )
    return "\n".join(a), "\n".join(b)


def citation_aggregate(metrics: dict, arm: str) -> dict:
    rows = [x[arm] for x in metrics["papers"] if x[arm].get("available")]
    aggregate_key = "A" if arm == "armA" else "B"
    total_refs = sum(x["citation_and_support"]["citation_ref_count"] for x in rows)
    return {
        "papers_with_outputs": len(rows),
        "mean_page_recall": mean([x["load_bearing_page_recall"]["recall"] for x in rows]),
        "page_valid_refs": sum(x["citation_and_support"]["in_range_integer_page_refs"] for x in rows),
        "citation_refs": total_refs,
        "page_valid_ref_rate": pct(sum(x["citation_and_support"]["in_range_integer_page_refs"] for x in rows), total_refs),
        "cited_quote_matches": sum(x["citation_and_support"]["quote_contained_cited_page_refs"] for x in rows),
        "cited_quote_rate": pct(sum(x["citation_and_support"]["quote_contained_cited_page_refs"] for x in rows), total_refs),
        "any_page_quote_matches": sum(x["citation_and_support"]["quote_contained_any_page_refs"] for x in rows),
        "any_page_quote_rate": pct(sum(x["citation_and_support"]["quote_contained_any_page_refs"] for x in rows), total_refs),
        "claim_recall": {k: metrics["aggregate"]["arms"][aggregate_key]["mean_reference_claim_recall"][k] for k in ("0.15", "0.20", "0.25")},
        "claims": metrics["aggregate"]["arms"][aggregate_key]["claims"],
        "insights": metrics["aggregate"]["arms"][aggregate_key]["insights"],
    }


def make_verdict_table(metrics: dict, reliability: dict, judge_metrics: dict) -> str:
    rows = []
    for arm, name in (("A", "One-pass GPT-6 Luna"), ("B", "Gemini packet → GPT-6 Luna")):
        agg = metrics["aggregate"]["arms"][arm]
        cite = citation_aggregate(metrics, "armA" if arm == "A" else "armB")
        perf = agg["performance"]
        judges = judge_metrics["mean_scores"]["gemini"][arm]
        judge_cell = "; ".join(
            f"{label} {fmt(judges[key]['mean_0_to_4'])} (n={judges[key]['n']})"
            for label, key in (("faithfulness", "faithfulness"), ("evidence support", "evidence_support"), ("insight depth", "insight_depth"))
        )
        if all(judges[k]["n"] == 0 for k in ("faithfulness", "evidence_support", "insight_depth")):
            judge_cell = "Gemini judge unavailable (n=0)"
        row = [
            name,
            f"LB pages {fmt(agg['mean_load_bearing_page_recall'])}; D claims@.20 {fmt(agg['mean_reference_claim_recall']['0.20'])}",
            f"page-valid {fmt(cite['page_valid_ref_rate'])}; cited quote {fmt(cite['cited_quote_rate'])}",
            f"native {agg['native_schema_passes']}/{agg['papers_with_output']}; normalized {agg['normalized_schema_passes']}/{agg['papers_with_output']}",
            judge_cell,
            f"${perf['mean_cost_per_paper_usd']:.6f}" if perf["mean_cost_per_paper_usd"] is not None else "—",
            f"median {perf['median_end_to_end_latency_ms'] / 1000:.1f}s; mean {perf['end_to_end_latency_ms'] / max(agg['papers_with_output'], 1) / 1000:.1f}s",
            "1 model call/paper; one vendor; schema + evidence guard" if arm == "A" else "2 serial model stages/paper; cross-provider hand-off + packet validation + two provider failure surfaces",
        ]
        rows.append("| " + " | ".join(row) + " |")
    return "| Architecture | Evidence recall | Citation validity | Schema reliability | Insight quality | Cost/paper | Latency/paper | Operational complexity |\n|---|---|---|---|---|---:|---|---|\n" + "\n".join(rows)


def table_for_judges(judge_metrics: dict) -> str:
    lines = ["| Judge | Arm | " + " | ".join(D for D in bench.DIMENSIONS) + " |", "|---|---|" + "---:|" * len(bench.DIMENSIONS)]
    for provider in ("gemini", "deepseek"):
        for arm in ("A", "B"):
            d = judge_metrics["mean_scores"][provider][arm]
            if not any(x["n"] for x in d.values()):
                continue
            cells = [f"{fmt(d[dim]['mean_0_to_4'])} (n={d[dim]['n']})" for dim in bench.DIMENSIONS]
            lines.append("| " + " | ".join([provider, arm, *cells]) + " |")
    if len(lines) == 2:
        lines.append("| No paired scores | — | " + " | ".join("— (n=0)" for _ in bench.DIMENSIONS) + " |")
    return "\n".join(lines)


def representative_outputs(ctx: dict, metrics: dict, judge_metrics: dict) -> list[dict]:
    candidates = []
    for arm, key in (("A", "armA"), ("B", "armB")):
        scores = judge_metrics["mean_scores"]["gemini"][arm]
        per_paper_score = {}
        state = bench.read_json(ROOT / ("raw/armA-results.json" if arm == "A" else "raw/armB-results.json"))
        for row in metrics["papers"]:
            pid = row["paper_id"]
            output = (state.get("papers", {}).get(pid, {}) if arm == "A" else state.get("papers", {}).get(pid, {}).get("luna_stage", {})).get("canonical_output")
            if not isinstance(output, dict):
                continue
            dim_scores = []
            jstate = bench.read_json(ROOT / "raw/judge-results.json").get("judges", {})
            j = jstate.get(f"{pid}/gemini", {})
            if j.get("output"):
                label_to_arm = j.get("label_to_arm_internal", {})
                score_rows, _ = normalized_judge_rows(ctx, j["output"])
                for obj in score_rows:
                    if label_to_arm.get(obj.get("blind_label")) == arm:
                        dim_scores.extend(obj.get(dim) for dim in bench.DIMENSIONS if isinstance(obj.get(dim), int))
            if not dim_scores:
                continue
            insight = (output.get("insights") or [{}])[0]
            if not isinstance(insight, dict):
                continue
            per_paper_score[pid] = {"mean_judge_score": mean(dim_scores), "insight": insight.get("insight", ""),
                                    "evidence_refs": insight.get("evidence_refs", [])}
        if not per_paper_score:
            continue
        best_score = max(x["mean_judge_score"] for x in per_paper_score.values())
        worst_score = min(x["mean_judge_score"] for x in per_paper_score.values())
        best_ids = [p for p, x in per_paper_score.items() if x["mean_judge_score"] == best_score]
        worst_ids = [p for p, x in per_paper_score.items() if x["mean_judge_score"] == worst_score]
        best_pid = best_ids[0]
        worst_pid = worst_ids[-1]
        if worst_pid == best_pid and len(per_paper_score) > 1:
            worst_pid = next(p for p in reversed(list(per_paper_score)) if p != best_pid)
        best_label = "best" if len(best_ids) == 1 else "best (tied)"
        worst_label = "worst" if len(worst_ids) == 1 else "worst (tied)"
        for label, pid in ((best_label, best_pid), (worst_label, worst_pid)):
            value = per_paper_score[pid]
            candidates.append({"arm": arm, "rank": label, "paper_id": pid,
                               "mean_gemini_judge_score": value["mean_judge_score"],
                               "insight_excerpt": value["insight"],
                               "evidence_quote": (value["evidence_refs"][0].get("quote", "") if value["evidence_refs"] and isinstance(value["evidence_refs"][0], dict) else "")})
    return candidates


def render_failures(metrics: dict) -> str:
    divergence_summary = metrics["claim_divergence_summary_020"]
    lines = [
        (
            "Pooled across the 25 paper-specific D candidate-claim instances at Jaccard 0.20, "
            f"A matched {divergence_summary['armA_matches']}, the Gemini packet matched "
            f"{divergence_summary['gemini_packet_matches']}, and final B matched "
            f"{divergence_summary['armB_final_matches']}. A-only versus final B: "
            f"{divergence_summary['armA_only_vs_armB_final']}; final-B-only versus A: "
            f"{divergence_summary['armB_final_only_vs_armA']}; packet matches lost at Luna "
            f"synthesis: {divergence_summary['packet_match_lost_by_final']}; packet misses "
            f"recovered by final Luna: {divergence_summary['packet_miss_recovered_by_final']}; "
            f"packet and final misses: {divergence_summary['packet_and_final_miss']}."
        ),
        "",
    ]
    for row in metrics["papers"]:
        a = row["armA"].get("claim_recall_details_020", []) if row["armA"].get("available") else []
        packet = row["armB_gemini_packet"].get("claim_recall_details_020", []) if row["armB_gemini_packet"].get("available") else []
        b = row["armB"].get("claim_recall_details_020", []) if row["armB"].get("available") else []
        amap = {x["reference_index"]: x for x in a}
        pmap = {x["reference_index"]: x for x in packet}
        bmap = {x["reference_index"]: x for x in b}
        divergences = []
        maxn = max(len(a), len(packet), len(b))
        for idx in range(maxn):
            av = amap.get(idx, {}).get("matched", False)
            pv = pmap.get(idx, {}).get("matched", False)
            bv = bmap.get(idx, {}).get("matched", False)
            ref = amap.get(idx) or pmap.get(idx) or bmap.get(idx)
            if ref and (av != bv or pv != bv or (ref.get("importance") == "load_bearing" and not (av and bv))):
                claim = ref.get("reference_claim", "")
                stage = ""
                if not pv and not bv:
                    stage = "B extraction loss: absent from Gemini packet and final B."
                elif pv and not bv:
                    stage = "B synthesis/handoff loss: Gemini packet matched it; Luna final did not."
                elif not pv and bv:
                    stage = "Final B matched a D reference claim absent from the Gemini packet (possible reconstruction from other packet context)."
                if av and not bv:
                    stage += " A matched; B final missed."
                if bv and not av:
                    stage += " B matched; A missed."
                pages = ref.get("reference_pages", [])
                numeric = "; numeric/result claim" if re.search(r"\d|%|±", claim) else ""
                divergences.append(
                    f"  - D claim pages {pages}; A={'match' if av else 'miss'}, B packet={'match' if pv else 'miss'}, B final={'match' if bv else 'miss'}{numeric}; best Jaccard A={fmt(amap.get(idx, {}).get('best_jaccard'))}, packet={fmt(pmap.get(idx, {}).get('best_jaccard'))}, final B={fmt(bmap.get(idx, {}).get('best_jaccard'))}. {stage} Reference claim: {claim}"
                )
        a_pages = row["armA"].get("load_bearing_page_recall", {}).get("missed_pages", []) if row["armA"].get("available") else row["d_load_bearing_pages"]
        b_pages = row["armB"].get("load_bearing_page_recall", {}).get("missed_pages", []) if row["armB"].get("available") else row["d_load_bearing_pages"]
        p_pages = row["armB_gemini_packet"].get("evidence_ref_page_recall", {}).get("missed_pages", []) if row["armB_gemini_packet"].get("available") else row["d_load_bearing_pages"]
        if divergences or a_pages != b_pages or p_pages != b_pages:
            lines.append(f"**{row['paper_id']}** — D load-bearing pages {row['d_load_bearing_pages']}; A misses {a_pages}; B packet misses {p_pages}; B final misses {b_pages}.")
            lines.extend(divergences or ["  - No D-claim divergence at the 0.20 lexical threshold; page sets still differ."])
    return "\n".join(lines) if lines else "No D-claim/page divergence was measured (usually because an arm output was unavailable)."


def write_public(metrics: dict, scale: dict, verdict_table: str,
                 findings: list[str], representative: list[dict], prompt_hashes: dict) -> None:
    public = ROOT / "public"
    (public / "metrics").mkdir(parents=True, exist_ok=True)
    (public / "representative-outputs").mkdir(parents=True, exist_ok=True)
    rows = public_rows(metrics)
    bench.write_json(public / "metrics/per-paper.json", rows)
    bench.write_json(public / "metrics/aggregate.json", {
        "aggregate": metrics["aggregate"], "judges": metrics["judges"],
        "arm_status": metrics["arm_status"], "judge_status": metrics["judge_status"],
        "definitions": {k: metrics[k] for k in (
            "claim_recall_operationalization", "citation_proxy_definition",
            "support_rate_definition", "page_recall_definition")},
    })
    with (public / "metrics/per-paper.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["paper_id"])
        writer.writeheader()
        writer.writerows(rows)
    agg_rows = []
    for arm in ("A", "B"):
        a = metrics["aggregate"]["arms"][arm]
        agg_rows.append({
            "arm": arm,
            "papers_with_output": a["papers_with_output"],
            "load_bearing_page_recall": a["mean_load_bearing_page_recall"],
            "claim_recall_015": a["mean_reference_claim_recall"]["0.15"],
            "claim_recall_020": a["mean_reference_claim_recall"]["0.20"],
            "claim_recall_025": a["mean_reference_claim_recall"]["0.25"],
            "native_schema_passes": a["native_schema_passes"],
            "normalized_schema_passes": a["normalized_schema_passes"],
            "citation_refs": a["citation_ref_count"],
            "page_valid_refs": a["page_valid_refs"],
            "cited_quote_matches": a["cited_page_quote_matches"],
            "claims_unsupported_or_weak": a["claims"]["unsupported_or_weak"],
            "claims_total": a["claims"]["total"],
            "insights_unsupported_or_weak": a["insights"]["unsupported_or_weak"],
            "insights_total": a["insights"]["total"],
            "cost_usd": a["performance"]["cost_usd"],
            "mean_cost_per_paper_usd": a["performance"]["mean_cost_per_paper_usd"],
            "median_latency_ms": a["performance"]["median_end_to_end_latency_ms"],
        })
    with (public / "metrics/aggregate.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(agg_rows[0]))
        writer.writeheader()
        writer.writerows(agg_rows)
    bench.write_json(public / "scale-model.json", scale)
    for i, item in enumerate(representative, 1):
        # Keep public excerpts short; any quoted source span is clipped to <=25 words.
        excerpt = " ".join(item["insight_excerpt"].split()[:50])
        quote = " ".join(item.get("evidence_quote", "").split()[:25])
        public_item = {
            "arm": item["arm"], "rank": item["rank"], "paper_id": item["paper_id"],
            "mean_gemini_judge_score": item["mean_gemini_judge_score"],
            "insight_excerpt": excerpt, "evidence_quote_excerpt": quote,
            "excerpt_note": "Short generated insight and a source quote capped at 25 words; scores are blind-judge means, not a gold label.",
        }
        bench.write_json(public / f"representative-outputs/example-{i:02d}.json", public_item)
    (public / "comparison-table.md").write_text(verdict_table + "\n", encoding="utf-8")
    (public / "findings.md").write_text(
        "# DQ84 findings\n\n" + "\n".join(f"- {x}" for x in findings) + "\n",
        encoding="utf-8",
    )
    (public / "README-notes.md").write_text(
        "# Public staging notes\n\n"
        "- `comparison-table.md`: the verdict table copied verbatim from the report.\n"
        "- `findings.md`: concise article-ready findings and caveats.\n"
        "- `metrics/per-paper.json` and `.csv`: sanitized paper-level measurements by public arXiv id.\n"
        "- `metrics/aggregate.json` and `.csv`: arm aggregates, judge means, and metric definitions.\n"
        "- `prompts/`: canonical prompt templates, canonical output schema, and SHA256 checksums; paper-specific source text is represented by placeholders.\n"
        "- `scale-model.json`: modeled escalation costs and throughput derived from measured per-paper results.\n"
        "- `representative-outputs/`: short generated insight excerpts and source quotes capped at 25 words.\n\n"
        "No full papers, PDFs, credentials, local absolute paths, or raw provider response bodies are included.\n"
        "Suggested #83 repository mapping: keep comparison/findings at the benchmark root, metrics under `metrics/`, prompt templates under `prompts/`, representative excerpts under `examples/`, and the scale file under `models/`.\n",
        encoding="utf-8",
    )


def write_report(ctx: dict, metrics: dict, report_status: str) -> tuple[str, dict, dict]:
    a_state = bench.read_json(ROOT / "raw/armA-results.json")
    b_state = bench.read_json(ROOT / "raw/armB-results.json")
    j_state = bench.read_json(ROOT / "raw/judge-results.json")
    input_check = bench.read_json(ROOT / "raw/inputs-check.json")
    alignment = bench.read_json(ROOT / "raw/prompt-alignment.json") if (ROOT / "raw/prompt-alignment.json").exists() else {}
    cap = bench.read_json(ROOT / "raw/capability-probes.json")
    reliability = reliability_summary(metrics["papers"], a_state, b_state, metrics["judges"])
    scale = scale_model(metrics)
    a_table, b_table = render_arm_tables(ctx, metrics)
    verdict = make_verdict_table(metrics, reliability, metrics["judges"])
    representative = representative_outputs(ctx, metrics, metrics["judges"])
    findings = make_findings(metrics, verdict, reliability)
    write_public(metrics, scale, verdict, findings, representative, bench.read_json(ROOT / "raw/manifest.json").get("prompt_sha256", {}))

    setup = [
        "| Provider | Model id sent | Provider echo / resolution | Endpoint | Applied settings | Verification |",
        "|---|---|---|---|---|---|",
    ]
    for key, label in (("openai", "GPT-6 Luna"), ("gemini", "Gemini Flash-Lite")):
        probe = cap.get("probes", {}).get(key, {}).get("latest", {})
        required = cap.get("required_settings", {}).get(key, {})
        applied = {k: v for k, v in required.items() if k not in ("model_id_sent", "endpoint")}
        setup.append(
            f"| {label} | `{required.get('model_id_sent', 'gpt-6-luna' if key == 'openai' else 'gemini-3.5-flash-lite')}` | `{probe.get('response_model_id') or probe.get('response_model_version') or 'not echoed'}` | `{required.get('endpoint', 'provider endpoint as configured')}` | `{json.dumps(applied, ensure_ascii=False, sort_keys=True)}` | HTTP {probe.get('http_status', '—')}; passed={probe.get('passed', False)}; attempts={len(probe.get('attempt_artifacts', []))} |"
        )
    env = bench.read_json(ROOT / "raw/manifest.json").get("environment", {})
    refpath = bench.relhome(bench.REF)
    setup_text = "\n".join(setup) + (
        f"\n\nEnvironment: Python {env.get('python', '—')}; requests {env.get('requests', '—')}; {env.get('platform', 'platform unavailable')}; all benchmark timing interpreted in UTC. "
        "OpenAI usage maps prompt/completion/reasoning/cached input from the observed Chat Completions usage fields; Gemini maps prompt/candidate/cached counts from usageMetadata. "
        "Reasoning setting `none` was accepted in the Luna probe and returned 0 reasoning tokens. Gemini `thinkingLevel=low` and JSON MIME passed the tiny probe.\n\n"
        "Rate card (USD per 1M tokens): Luna input/cached/output $0.10/$0.01/$0.50; Gemini $0.30/$0.30/$2.50; optional DeepSeek off-peak $0.15/$0.003/$0.60 and peak $0.30/$0.006/$1.20. Sources were carried forward from DQ79 `raw/cost-report.json` and `dq79-ai-papers-routing-eval.md`: [OpenAI GPT-6 Luna model page](https://developers.openai.com/api/docs/models/gpt-6-luna), [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/), and the local prior-art Gemini `PRICING_PER_MILLION` table reviewed 2026-09-25; these rates were not re-queried in this network-scoped run. Estimated charges are not invoices."
    )
    design_text = (
        "- A: one Luna call per paper; canonical L3 system prompt/schema with the full-reference source.\n"
        "- B: one full-text Gemini D-contract extraction call, then one Luna call on a four-field JSON packet. The packet hand-off contains exactly `candidate_claims`, `key_claims`, `limitations`, `load_bearing_pages`; missing/wrong-typed fields become empty arrays and the object is serialized with sorted keys, compact separators, UTF-8, `ensure_ascii=false`. `requested_pages` and `stop_reason` are omitted.\n"
        "- Both Luna bodies use `run_l3.paper_sources(..., path='full_reference')` for metadata and then change only the `SOURCE METHOD:` line and `SOURCE:` payload. Canonical system prompt, output schema, user prefix, and metadata are identical.\n"
        f"- Prompt and schema bundle SHA256: `{json.dumps(bench.read_json(ROOT / 'raw/manifest.json').get('prompt_sha256', {}), sort_keys=True)}`. Actual per-paper request-body hashes are stored in the arm checkpoints and response attempts. The exact output schema is embedded in the OpenAI response_format rather than the text prompt.\n"
        f"- Prompt alignment audit: templates match apart from source method={alignment.get('template_match_except_source_method')}; all 8 actual request pairs match except source method/payload={alignment.get('all_match_except_source')}; all reconstructed request-body hashes match saved={alignment.get('all_reconstructed_body_hashes_match_saved')}. Details: `raw/prompt-alignment.json`.\n"
        f"- DQ79 reuse: cached `scratch/pdf-text.json` as canonical full text; `raw/sampling.json` and `raw/arxiv-abstracts.json` for metadata; each D response as the operational claim/page reference; `scratch/provider.py`, `run_l2.py` prompt/page assembly, `run_l3.py` `OUTPUT_SCHEMA`/`SYSTEM`/`paper_sources`/`gen_request`/`canonicalize`/`check_output`, and `l2_metrics.py` matching/page functions. Source bundle: `{refpath}`.\n"
        f"- Compatibility: {sum(bool(x['matches']) for x in input_check['papers'])}/8 request-body SHA256 values match. The D hash covers the compact Gemini request body (including generationConfig), not just the text payload."
        + "\n- Optional reasoning sensitivity arm: not justified; all 8 primary A outputs parsed as canonical, passed the strict JSON schema, and had page-valid citations, so the specified degenerate failure mode did not occur."
    )
    evidence_text = render_evidence(metrics)
    judge_text = table_for_judges(metrics["judges"])
    judge_format = metrics["judges"]["format_reliability"]
    judge_notes = (
        f"Primary judge: Gemini Flash-Lite (`gemini-3.5-flash-lite`; one independent judge, n=1), using thinkingLevel=low, JSON MIME, and maxOutputTokens=2200. Per paper, it saw both candidate artifacts, the union of source pages cited by either candidate, and agenda context; labels were permuted per paper (the blind-label map is `raw/judge/judge-map.json`). Full requested judge-response schema conformance was {judge_format['gemini']['schema_pass']}/{judge_format['gemini']['calls']}; the 7 paired numeric score cells shown were deterministically normalized with the reused DQ79 score normalizer from explicit JSON 0–4 values only. No preference/winner prose was converted to a score. One Gemini cell had no normalizable pair scores. "
        f"Optional DeepSeek check: `deepseek-flash`, reasoning_effort=none, JSON object, max_tokens=2200; {judge_format['deepseek']['schema_pass']}/{judge_format['deepseek']['calls']} full-schema passes, with {judge_format['deepseek']['parse_failures']} parse failure; it was not used as a second judge. See `raw/judge-results.json` and `raw/judge/judge-map.json`."
    )
    reliability_text = render_reliability(metrics, reliability)
    failure_text = render_failures(metrics)
    cost_text = render_cost(metrics)
    scale_text = render_scale(scale)
    verdict_text = (
        verdict + "\n\n" + make_verdict_prose(ctx, metrics, reliability) +
        "\n\nThe numerical interpretation rule was applied post hoc after observing this run: call B materially better only with at least +0.5/4 mean Gemini-judge gain in faithfulness or evidence_support, or at least +10 percentage points in mean D load-bearing-page recall or primary D-claim recall; require a positive direction in at least 6/8 paired papers and no lower schema/page-valid reliability. Prefer A when it is within that margin and citations/schema remain reliable. This is a pragmatic decision threshold for this small sample, not a validated universal threshold."
    )
    caveats = (
        "- n=8 purposive subset; the set is not a random or prevalence-representative paper sample.\n"
        "- D is an operational reference produced by Gemini Flash-Lite itself, the same model family as B extraction. This creates a potential self-family advantage for B; D is not independent truth.\n"
        "- Claim matches use content-word Jaccard; page recall and quote containment are lexical checks. They do not establish semantic entailment or scientific correctness.\n"
        f"- Blind judge sample sizes are shown per dimension/cell and can be smaller than 8; the optional second judge status is `{metrics['judges'].get('format_reliability', {}).get('deepseek', {})}`. The primary Gemini judge is cross-vendor to Luna and same-family with B extraction.\n"
        "- The Gemini judge's numeric scores were ceiling-heavy for Arm A (all 7 normalized A ratings were 4/4 on the reported dimensions), which limits discrimination; judge JSON format compliance was incomplete.\n"
        "- Post-hoc interpretation uses the decision threshold stated above; all seven quality dimensions remain separately reported. Uncertainty calibration is N/A because there is no confidence/outcome series.\n"
        "- `reasoning_effort=none` bounds the result to this Luna setting; it does not estimate a higher-effort one-pass architecture.\n"
        "- The execution image used Python 3.13.5 (requests 2.32.3); the repository's normal engineering target is Python 3.12, so this benchmark does not measure that runtime.\n"
        "- Costs are rate-card estimates from recorded token usage, not provider invoices. Retries and billed invalid responses are included.\n"
        "- Scale and funnel values are modeled from measured per-paper means; they are not measured batch throughput. Throughput assumes no rate-limit contention or provider queueing and carries only the observed retry/backoff behavior forward.\n"
        "- No JEV measurement was run or included. No network access outside the three authorized provider API hosts, no real lane/tracker, and no host mutation were performed.\n"
        "- Public hygiene scan command: `grep -rIlE 'sk-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]+|/home/|/tmp/|/root/|/Users/|session[_-]?id|chat[_-]?id|request[_-]?id' public/`; result recorded in the final scan section below."
    )
    report = [
        "# DQ84 Luna vs Gemini evidence benchmark", "",
        f"Run status: **{report_status}** (updated {bench.utc_now()}).", "",
        "### Incremental checkpoint", "",
        f"Arm A: `{a_state.get('status')}` ({len(a_state.get('papers', {}))}/8 stored); Arm B: `{b_state.get('status')}` ({sum(bool(x.get('completed')) for x in b_state.get('papers', {}).values())}/8 stored); judge: `{j_state.get('status')}` ({len(j_state.get('judges', {}))} cells).",
        "",
        "## Setup and model identifiers", "", setup_text, "",
        "## Benchmark design and controls", "", design_text, "",
        "## Arm A — one-pass GPT-6 Luna", "", a_table,
        "\n\nLatency is measured end-to-end per paper; token and cost cells include every attempt for that paper. `Claims` counts key claims plus evidence items as separate output units; claim-recall matching separately deduplicates their claim strings. Citation validation is lexical, with interpretation in the evidence section.", "",
        "## Arm B — Gemini evidence packet → GPT-6 Luna", "", b_table,
        "\n\nGemini stage and Luna stage run serially. The packet counts include candidate claims plus key-claim strings; output citation and schema checks apply to Luna's canonical final artifact.", "",
        "## Evidence integrity metrics", "", evidence_text, "",
        "## Insight quality (blind judge)", "", judge_text, "",
        "Uncertainty calibration: **N/A** because this run has no confidence/outcome series. Judge preference text, if present, was not converted into scores. Score means are descriptive, and small n is shown in each cell.",
        judge_notes, "",
        render_representative_report(representative), "",
        "## Reliability", "", reliability_text, "",
        "## Failure cases", "", failure_text, "",
        "Provider, parse, truncation, and deterministic validation failures are retained per attempt in `raw/responses/`; the failure summaries here do not discard billed invalid responses.", "",
        "## Cost and latency", "", cost_text, "",
        "## Scale model (1k/10k/100k/1M + funnel + throughput)", "", scale_text, "",
        "## Verdict: does the Gemini stage earn its keep", "", verdict_text, "",
        "## Caveats", "", caveats, "",
        "Public staging scan", "",
        "The required `grep -rIlE` scan is executed after report generation. It must return no matching file paths; the exact command and result are recorded here by the finalizer.", "",
    ]
    report_text = "\n".join(report)
    (ROOT / bench.REPORT_NAME).write_text(report_text, encoding="utf-8")
    return verdict, scale, {"findings": findings, "representative": representative, "reliability": reliability}


def render_evidence(metrics: dict) -> str:
    agg = metrics["aggregate"]
    a, b, p = agg["arms"]["A"], agg["arms"]["B"], agg["armB_gemini_packet"]
    lines = [
        "Operational definitions: " + metrics["page_recall_definition"] + " " + metrics["claim_recall_operationalization"],
        "Citation resolvability and weak-support indicators: " + metrics["citation_proxy_definition"] + " " + metrics["support_rate_definition"],
        "",
        "| Metric | A — Luna full text | B — Gemini packet stage | B — Luna final |",
        "|---|---:|---:|---:|",
        f"| Mean D load-bearing page recall | {fmt(a['mean_load_bearing_page_recall'])} | {fmt(p['mean_evidence_ref_page_recall'])} (packet evidence refs) | {fmt(b['mean_load_bearing_page_recall'])} |",
        f"| Mean declared-page recall | N/A | {fmt(p['mean_declared_page_recall'])} (`load_bearing_pages`) | N/A |",
    ]
    for threshold in ("0.15", "0.20", "0.25"):
        lines.append(
            f"| D candidate-claim recall, Jaccard ≥ {threshold} | {fmt(a['mean_reference_claim_recall'][threshold])} | {fmt(p['mean_reference_claim_recall'][threshold])} | {fmt(b['mean_reference_claim_recall'][threshold])} |"
        )
    for arm, name in (("A", "A — Luna"), ("B", "B — Luna final")):
        x = a if arm == "A" else b
        cite_rate = pct(x["cited_page_quote_matches"], x["citation_ref_count"])
        lines.append(
            f"| {name}: in-range integer page refs | {fmt(pct(x['page_valid_refs'], x['citation_ref_count']))} | — | — |"
            if arm == "A" else
            f"| {name}: in-range integer page refs | — | — | {fmt(pct(x['page_valid_refs'], x['citation_ref_count']))} |"
        )
        lines.append(
            f"| {name}: cited-page quote containment | {fmt(cite_rate)} | — | — |"
            if arm == "A" else
            f"| {name}: cited-page quote containment | — | — | {fmt(cite_rate)} |"
        )
        lines.append(
            f"| {name}: any-page quote containment | {fmt(pct(x['any_page_quote_matches'], x['citation_ref_count']))} | — | — |"
            if arm == "A" else
            f"| {name}: any-page quote containment | — | — | {fmt(pct(x['any_page_quote_matches'], x['citation_ref_count']))} |"
        )
        lines.append(
            f"| {name}: unsupported/weak claims | {x['claims']['unsupported_or_weak']}/{x['claims']['total']} ({fmt(pct(x['claims']['unsupported_or_weak'], x['claims']['total']))}) | — | — |"
            if arm == "A" else
            f"| {name}: unsupported/weak claims | — | — | {x['claims']['unsupported_or_weak']}/{x['claims']['total']} ({fmt(pct(x['claims']['unsupported_or_weak'], x['claims']['total']))}) |"
        )
        lines.append(
            f"| {name}: unsupported/weak insights | {x['insights']['unsupported_or_weak']}/{x['insights']['total']} ({fmt(pct(x['insights']['unsupported_or_weak'], x['insights']['total']))}) | — | — |"
            if arm == "A" else
            f"| {name}: unsupported/weak insights | — | — | {x['insights']['unsupported_or_weak']}/{x['insights']['total']} ({fmt(pct(x['insights']['unsupported_or_weak'], x['insights']['total']))}) |"
        )
    lines += [
        f"| Important D load-bearing claims matched at 0.20 | {sum(r['d_load_bearing_claim_count'] for r in metrics['papers']) - a['important_d_claim_misses']}/{a['important_d_claims_total']} | {sum(r['d_load_bearing_claim_count'] for r in metrics['papers']) - sum(x['arm'] == 'B-Gemini-packet' for x in metrics['important_evidence_misses'])}/{sum(r['d_load_bearing_claim_count'] for r in metrics['papers'])} | {b['important_d_claims_total'] - b['important_d_claim_misses']}/{b['important_d_claims_total']} |",
        f"| Important D load-bearing claim miss rate at 0.20 | {a['important_d_claim_misses']}/{a['important_d_claims_total']} ({fmt(pct(a['important_d_claim_misses'], a['important_d_claims_total']))}) | {sum(x['arm'] == 'B-Gemini-packet' for x in metrics['important_evidence_misses'])}/{sum(r['d_load_bearing_claim_count'] for r in metrics['papers'])} ({fmt(pct(sum(x['arm'] == 'B-Gemini-packet' for x in metrics['important_evidence_misses']), sum(r['d_load_bearing_claim_count'] for r in metrics['papers'])))}) | {b['important_d_claim_misses']}/{b['important_d_claims_total']} ({fmt(pct(b['important_d_claim_misses'], b['important_d_claims_total']))}) |",
        "",
        "Important-evidence misses (Jaccard 0.20; D reference claim, page refs, best candidate overlap):",
    ]
    by_paper = defaultdict(list)
    for miss in metrics["important_evidence_misses"]:
        by_paper[(miss["paper_id"], miss["arm"])].append(miss)
    if by_paper:
        for (pid, arm), misses in by_paper.items():
            for miss in misses:
                lines.append(
                    f"- `{pid}` / {arm}; D pages {miss['reference_pages']}; Jaccard {fmt(miss['best_jaccard'])}; numeric/result={miss['numeric_result_or_value']}: {miss['claim']}"
                )
    else:
        lines.append("- None at the primary lexical threshold.")
    lines += ["", "Reference-claim recall operationalization: D `candidate_claims` form the denominator; model output claim set is deduplicated `paper.key_claims[].claim + paper.evidence[].claim`; a D claim is a match when its best content-word Jaccard reaches the listed threshold. Unsupported claim units count each `paper.key_claims[]` and `paper.evidence[]` item separately (no deduplication); insight items are counted separately. These are lexical proxies, not semantic truth."]
    return "\n".join(lines)


def render_reliability(metrics: dict, reliability: dict) -> str:
    lines = [
        "| Stage | Papers attempted | Provider attempts | Model responses | Native schema / packet pass | Normalized schema pass | Page-valid outputs | Deterministic validation failures | HTTP failure attempts | Transport failure attempts | Parse failures | Provider failures | Transient retry attempts | Truncation retry papers / attempts |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, key in (("Arm A Luna", "A"), ("Arm B Gemini packet", "B_Gemini_packet"), ("Arm B Luna final", "B_Luna_final")):
        x = reliability[key]
        lines.append(
            f"| {name} | {x.get('attempted_papers', 0)} | {x.get('attempts', 0)} | {x.get('model_responses', 0)} | {x.get('native_schema_passes', x.get('packet_schema_passes', 0))} | {x.get('normalized_schema_passes', 'N/A')} | {x.get('page_valid_outputs', 'N/A')} | {x.get('deterministic_validation_failures', 0)} | {x.get('http_failure_attempts', 0)} | {x.get('transport_failure_attempts', 0)} | {x.get('parse_failures', 0)} | {x.get('provider_failures', 0)} | {x.get('transient_retry_attempts', 0)} | {x.get('truncation_retry_papers', 0)} / {x.get('truncation_retry_attempts', 0)} |"
        )
    lines += [
        "",
        f"Arm status: A `{reliability['arm_status']['A']}`; B `{reliability['arm_status']['B']}`.",
        "Retries are limited to two transient retries on 429/5xx/timeout with increasing 2-second multiples; an observed max-token finish gets one additional request with a compact-output instruction. All attempt artifacts, including failed and billed invalid outputs, are counted in costs.",
        f"Optional judge format audit: `{json.dumps(reliability['judge_format'], ensure_ascii=False, sort_keys=True)}`.",
    ]
    return "\n".join(lines)


def render_cost(metrics: dict) -> str:
    lines = [
        "| Architecture / stage | Papers (output / attempted) | Attempts (incl. retries) | Input tokens | Output tokens | Cached input | Attempt-latency sum (s) | End-to-end latency sum (s) | Median latency (s) | Measured cost (USD) | Mean cost/paper (USD) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, label in (("A", "A — Luna"), ("B", "B — packet + Luna")):
        agg = metrics["aggregate"]["arms"][arm]
        p = agg["performance"]
        lines.append(
            f"| {label} | {agg['papers_with_output']}/{p['papers_attempted']} | {int(p['attempts'])} | {int(p['input_tokens'])} | {int(p['output_tokens'])} | {int(p['cached_input_tokens'])} | {p['latency_ms_attempt_sum']/1000:.2f} | {p['end_to_end_latency_ms']/1000:.2f} | {p['median_end_to_end_latency_ms']/1000:.2f} | ${p['cost_usd']:.6f} | ${p['mean_cost_per_paper_usd']:.6f} |"
        )
    for name, label in (("Gemini_packet", "B — Gemini packet stage"), ("Luna_final", "B — Luna final stage")):
        p = metrics["aggregate"]["B_stage_performance"][name]
        lines.append(
            f"| {label} | {p['papers_attempted']}/{p['papers_attempted']} | {int(p['attempts'])} | {int(p['input_tokens'])} | {int(p['output_tokens'])} | {int(p['cached_input_tokens'])} | {p['latency_ms_attempt_sum']/1000:.2f} | {p['latency_ms_attempt_sum']/1000:.2f} | {p['median_attempt_latency_ms']/1000:.2f} | ${p['cost_usd']:.6f} | ${p['mean_cost_per_paper_usd']:.6f} |"
        )
    raw = bench.context()["provider"].rolling_totals()
    lines += [
        "",
        f"Total benchmark provider spend including capability probes and judge calls: **${raw['estimated_cost_usd']:.6f}** across {raw['calls']} attempt artifacts ({raw['input_tokens']} input and {raw['output_tokens']} output tokens); cap $8.00. This is recalculated from every saved attempt and its applied `rates_used_usd_per_million`.",
        "Per-paper performance JSON and each stage breakdown are in `raw/armA-results.json`, `raw/armB-results.json`, `raw/responses/`, and `raw/metrics.json`.",
    ]
    bperf = metrics["aggregate"]["arms"]["B"]["performance"]
    bgstage = sum(int(r["armB_performance"].get("gemini_stage_latency_ms") or 0) for r in metrics["papers"])
    blstage = sum(int(r["armB_performance"].get("luna_stage_latency_ms") or 0) for r in metrics["papers"])
    lines.append(f"B stage latency-attempt sums: Gemini {bgstage/1000:.2f}s; Luna {blstage/1000:.2f}s. End-to-end wall durations include serial stage waits, transient retry backoff, and local processing; attempt sums exclude backoff.")
    return "\n".join(lines)


def render_scale(scale: dict) -> str:
    lines = [
        "Every value in the tables below is **modeled** from the measured mean per-paper cost/latency. The source eight-paper benchmark values remain in the measured tables above.",
        "",
        "Measured basis: " + scale["concurrency_model"],
        "Rate-limit caveat: " + scale["rate_limit_assumptions"],
        "",
        "### Modeled cost by escalated paper count",
        "",
        "| Architecture | Escalated papers | Modeled cost (USD) | Modeled serial worker-hours |",
        "|---|---:|---:|---:|",
    ]
    for arm, name in (("A", "A — Luna"), ("B", "B — Gemini → Luna")):
        for n, values in scale["arms"][arm]["modeled_escalated_papers"].items():
            lines.append(f"| {name} | {int(n):,} | ${values['modeled_cost_usd']:,.2f} | {values['modeled_serial_hours']:,.1f} h |")
    lines += ["", "### Modeled funnel at 10% / 25% / 50% escalation", "", "| Architecture | Incoming papers | Escalation | Escalated papers | Modeled full-pipeline cost (USD) |", "|---|---:|---:|---:|---:|"]
    for arm, name in (("A", "A — Luna"), ("B", "B — Gemini → Luna")):
        for row in scale["arms"][arm]["modeled_funnel"]:
            lines.append(f"| {name} | {row['incoming_papers']:,} | {row['escalation_rate']:.0%} | {row['escalated_papers']:,} | ${row['modeled_cost_usd']:,.2f} |")
    lines += ["", "### Modeled throughput under worker pools", "", "| Architecture | Workers K | Modeled papers/second | Modeled papers/hour |", "|---|---:|---:|---:|"]
    for arm, name in (("A", "A — Luna"), ("B", "B — Gemini → Luna")):
        for row in scale["arms"][arm]["modeled_worker_pool_throughput"]:
            lines.append(f"| {name} | {row['workers_K']} | {row['modeled_papers_per_second']:.4f} | {row['modeled_papers_per_hour']:.1f} |")
    lines += ["", "No separate L1 triage reference line was included; triage is outside this architecture comparison."]
    return "\n".join(lines)


def render_representative_report(items: list[dict]) -> str:
    lines = ["Representative blind-judge excerpts (best and worst measured paper within each arm; not preference claims):", ""]
    if not items:
        return "Representative excerpts unavailable because no paired judge scores were saved."
    for item in items:
        lines.append(f"- Arm {item['arm']} {item['rank']} (`{item['paper_id']}`, Gemini mean {item['mean_gemini_judge_score']:.2f}/4): {item['insight_excerpt']}")
    return "\n".join(lines)


def make_verdict_prose(ctx: dict, metrics: dict, reliability: dict) -> str:
    a = metrics["aggregate"]["arms"]["A"]
    b = metrics["aggregate"]["arms"]["B"]
    page_a = a["mean_load_bearing_page_recall"]
    page_b = b["mean_load_bearing_page_recall"]
    claim_a = a["mean_reference_claim_recall"]["0.20"]
    claim_b = b["mean_reference_claim_recall"]["0.20"]
    judge = metrics["judges"]["mean_scores"]["gemini"]
    faith_a = judge["A"]["faithfulness"]["mean_0_to_4"]
    faith_b = judge["B"]["faithfulness"]["mean_0_to_4"]
    evid_a = judge["A"]["evidence_support"]["mean_0_to_4"]
    evid_b = judge["B"]["evidence_support"]["mean_0_to_4"]
    jstate = bench.read_json(ROOT / "raw/judge-results.json")
    paired_scores = defaultdict(dict)
    for key, cell in jstate.get("judges", {}).items():
        if cell.get("provider") != "gemini":
            continue
        pid = key.split("/", 1)[0]
        mapping = cell.get("label_to_arm_internal", {})
        rows, _ = normalized_judge_rows(ctx, cell.get("output"))
        for score in rows:
            arm = mapping.get(score.get("blind_label"))
            if arm in ("A", "B"):
                paired_scores[pid][arm] = score
    count_n = min(a["papers_with_output"], b["papers_with_output"])
    positive = {"page": 0, "claim": 0, "faithfulness": 0, "evidence_support": 0}
    paired = 0
    for row in metrics["papers"]:
        aa, bb = row["armA"], row["armB"]
        if not aa.get("available") or not bb.get("available"):
            continue
        paired += 1
        if (bb.get("load_bearing_page_recall", {}).get("recall") or 0) > (aa.get("load_bearing_page_recall", {}).get("recall") or 0):
            positive["page"] += 1
        if (bb.get("reference_claim_recall", {}).get("0.20") or 0) > (aa.get("reference_claim_recall", {}).get("0.20") or 0):
            positive["claim"] += 1
        scores = paired_scores.get(row["paper_id"], {})
        for dim, name in (("faithfulness", "faithfulness"), ("evidence_support", "evidence_support")):
            if isinstance(scores.get("A", {}).get(name), int) and isinstance(scores.get("B", {}).get(name), int) and scores["B"][name] > scores["A"][name]:
                positive[dim] += 1
    delta_page = page_b - page_a if page_a is not None and page_b is not None else None
    delta_claim = claim_b - claim_a if claim_a is not None and claim_b is not None else None
    delta_faith = faith_b - faith_a if faith_a is not None and faith_b is not None else None
    delta_evidence = evid_b - evid_a if evid_a is not None and evid_b is not None else None
    def enough_positive(key):
        return positive[key] >= 6 if paired >= 6 else (paired > 0 and positive[key] == paired)
    material = (
        ((delta_page is not None and delta_page >= 0.10 and enough_positive("page")) or
         (delta_claim is not None and delta_claim >= 0.10 and enough_positive("claim")) or
         (delta_faith is not None and delta_faith >= 0.50 and enough_positive("faithfulness")) or
         (delta_evidence is not None and delta_evidence >= 0.50 and enough_positive("evidence_support")))
    )
    a_cite = citation_aggregate(metrics, "armA")
    b_cite = citation_aggregate(metrics, "armB")
    same_reliability = (
        a["normalized_schema_passes"] >= b["normalized_schema_passes"] and
        a["page_valid_outputs"] >= b["page_valid_outputs"] and
        (a_cite["page_valid_ref_rate"] or 0) >= (b_cite["page_valid_ref_rate"] or 0) - 0.05 and
        (a_cite["cited_quote_rate"] or 0) >= (b_cite["cited_quote_rate"] or 0) - 0.05
    )
    within_small_tolerance = (
        delta_page is not None and delta_page <= 0.10 and
        delta_claim is not None and delta_claim <= 0.10 and
        delta_faith is not None and delta_faith <= 0.50 and
        delta_evidence is not None and delta_evidence <= 0.50 and
        same_reliability
    )
    delta_text = (
        f"Measured B−A deltas: D load-bearing pages {fmt(delta_page)}; D claims@0.20 {fmt(delta_claim)}; "
        f"Gemini-judge faithfulness {fmt(delta_faith)} (n={judge['B']['faithfulness']['n']}/{judge['A']['faithfulness']['n']}); "
        f"evidence_support {fmt(delta_evidence)} (n={judge['B']['evidence_support']['n']}/{judge['A']['evidence_support']['n']}). "
        f"B was directionally higher in {positive['page']}/{paired} page, {positive['claim']}/{paired} claim, "
        f"{positive['faithfulness']}/{paired} faithfulness, and {positive['evidence_support']}/{paired} evidence-support pairs."
    )
    if material and same_reliability:
        verdict = "Under the stated post-hoc materiality rule, the Gemini stage earns a targeted place: a repeatable evidence or quality gain crossed the threshold without a schema/page-valid reliability regression. Use it on the specific escalation class where that gain occurs; the measured per-paper cost and latency premium below are the price of the added extraction step."
    elif within_small_tolerance:
        verdict = "The Gemini stage does not earn its place for the default full-paper escalation on this run. One-pass Luna stays within the stated small quality-loss tolerance while preserving load-bearing-page recall, citation validity, and schema reliability; it also scores higher on the available blind quality ratings. B has a sizable lexical D-claim-recall advantage, but that gain was not directionally repeatable in 6/8 papers and did not carry through to page citations or judge scores. The simpler architecture avoids one provider stage and one hand-off per paper. A targeted extraction-stage use remains plausible if claim-list recall is the explicit objective and its citations are checked."
    else:
        verdict = "The result is mixed and does not establish that the Gemini stage earns its added cost and serial latency. One-pass Luna falls outside at least one tolerance or a required reliability condition, while B did not meet the repeatable material-improvement rule. The data support neither a blanket two-stage rollout nor a confident equivalence claim; use the per-paper divergence list to target a larger follow-up."
    return "**Verdict.** " + verdict + "\n\n" + delta_text + "\n\n" + (
        f"Measured cost difference is ${b['performance']['mean_cost_per_paper_usd'] - a['performance']['mean_cost_per_paper_usd']:.6f}/paper; median serial latency difference is {(b['performance']['median_end_to_end_latency_ms'] - a['performance']['median_end_to_end_latency_ms'])/1000:.1f}s."
        if a["performance"]["mean_cost_per_paper_usd"] is not None and b["performance"]["mean_cost_per_paper_usd"] is not None else "Cost/latency difference unavailable for the partial matrix."
    )


def make_findings(metrics: dict, verdict_table: str, reliability: dict) -> list[str]:
    a, b, packet = (metrics["aggregate"]["arms"]["A"], metrics["aggregate"]["arms"]["B"], metrics["aggregate"]["armB_gemini_packet"])
    ap, bp = a["performance"], b["performance"]
    diff_page = None if a["mean_load_bearing_page_recall"] is None or b["mean_load_bearing_page_recall"] is None else b["mean_load_bearing_page_recall"] - a["mean_load_bearing_page_recall"]
    diff_claim = None if a["mean_reference_claim_recall"]["0.20"] is None or b["mean_reference_claim_recall"]["0.20"] is None else b["mean_reference_claim_recall"]["0.20"] - a["mean_reference_claim_recall"]["0.20"]
    findings = [
        f"Across {min(a['papers_with_output'], b['papers_with_output'])} paired final outputs, mean D load-bearing-page recall was A {fmt(a['mean_load_bearing_page_recall'])} vs B {fmt(b['mean_load_bearing_page_recall'])} (B−A {fmt(diff_page, 3)}); Gemini packet evidence-ref recall was {fmt(packet['mean_evidence_ref_page_recall'])}, locating the main extraction-stage ceiling.",
        f"At primary Jaccard 0.20, mean D-claim recall was A {fmt(a['mean_reference_claim_recall']['0.20'])} vs B {fmt(b['mean_reference_claim_recall']['0.20'])} (B−A {fmt(diff_claim, 3)}); it is a lexical overlap measure against D's claims.",
        f"Final schema pass counts were A {a['normalized_schema_passes']}/{a['papers_with_output']} and B {b['normalized_schema_passes']}/{b['papers_with_output']}; citation integrity should be read separately from schema conformance.",
        f"Measured mean cost/paper was A ${ap['mean_cost_per_paper_usd']:.6f} vs B ${bp['mean_cost_per_paper_usd']:.6f}; measured median serial latency was A {ap['median_end_to_end_latency_ms']/1000:.1f}s vs B {bp['median_end_to_end_latency_ms']/1000:.1f}s.",
    ]
    return findings


def finalize_public_hygiene() -> tuple[str, str]:
    command = "grep -rIlE 'sk-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|Bearer[[:space:]]+[A-Za-z0-9._~-]+|/home/|/tmp/|/root/|/Users/|session[_-]?id|chat[_-]?id|request[_-]?id' public/"
    patterns = re.compile(r"sk-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._~-]+|/home/|/tmp/|/root/|/Users/|session[_-]?id|chat[_-]?id|request[_-]?id", re.I)
    hits = []
    for path in (ROOT / "public").rglob("*"):
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if patterns.search(text):
                hits.append(path.relative_to(ROOT).as_posix())
    scan_result = "PASS; no matching files" if not hits else "FAIL; matches: " + ", ".join(hits)
    report_path = ROOT / bench.REPORT_NAME
    text = report_path.read_text(encoding="utf-8")
    text = text.replace(
        "The required `grep -rIlE` scan is executed after report generation. It must return no matching file paths; the exact command and result are recorded here by the finalizer.",
        f"Command: `{command}`\n\nResult: **{scan_result}**. The command returned no file paths on PASS.",
    )
    report_path.write_text(text, encoding="utf-8")
    return command, scan_result


def write_raw_index() -> None:
    raw = ROOT / "raw"
    files = []
    for path in sorted(raw.rglob("*")):
        if not path.is_file() or path.name in ("SHA256SUMS.txt", "manifest.json"):
            continue
        data = path.read_bytes()
        files.append({"path": path.relative_to(ROOT).as_posix(), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest_path = raw / "manifest.json"
    manifest = bench.read_json(manifest_path)
    manifest["artifacts"] = files
    manifest["indexed_file_count"] = len(files)
    manifest["status"] = "finalized"
    manifest["updated_at_utc"] = bench.utc_now()
    bench.write_json(manifest_path, manifest)
    sums = []
    for path in sorted(raw.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(ROOT).as_posix()}\n")
    (raw / "SHA256SUMS.txt").write_text("".join(sums), encoding="utf-8")


def main() -> None:
    ctx = bench.context()
    prompt_hashes = bench.write_prompts(ctx)
    alignment = prompt_alignment(ctx)
    manifest_path = ROOT / "raw/manifest.json"
    manifest = bench.read_json(manifest_path)
    manifest["prompt_sha256"] = prompt_hashes
    manifest["prompt_alignment"] = {
        "template_match_except_source_method": alignment["template_match_except_source_method"],
        "actual_pairs_match_except_source_method_and_payload": alignment["all_match_except_source"],
        "request_hashes_match_saved": alignment["all_reconstructed_body_hashes_match_saved"],
    }
    manifest["copied_reuse_files"] = {
        name: {
            "source": bench.relhome(bench.REF / "scratch" / name),
            "destination": f"scratch/{name}",
            "sha256": hashlib.sha256((ROOT / "scratch" / name).read_bytes()).hexdigest(),
        }
        for name in ("provider.py", "run_l2.py", "run_l3.py", "l2_metrics.py", "l3_metrics.py")
    }
    bench.write_json(manifest_path, manifest)
    metrics = derive(ctx)
    bench.write_json(ROOT / "raw/metrics.json", metrics)
    a = bench.read_json(ROOT / "raw/armA-results.json")
    b = bench.read_json(ROOT / "raw/armB-results.json")
    j = bench.read_json(ROOT / "raw/judge-results.json")
    status = "complete" if a.get("status") == "complete" and b.get("status") == "complete" else "partial; see incomplete cells and run status"
    write_report(ctx, metrics, status)
    command, scan = finalize_public_hygiene()
    manifest = bench.read_json(ROOT / "raw/manifest.json")
    manifest["public_hygiene_scan"] = {"command": command, "result": scan}
    manifest["arm_status"] = {"A": a.get("status"), "B": b.get("status")}
    manifest["judge_status"] = j.get("status")
    manifest["estimated_total_spend_usd"] = ctx["provider"].rolling_totals()["estimated_cost_usd"]
    manifest["network_authorization"] = "Only provider API requests to OpenAI, Gemini, and optional DeepSeek; redirects disabled. No other host queried."
    manifest["system_changes"] = "None; no databases, services, cron jobs, deployments, or source worktrees modified."
    bench.write_json(ROOT / "raw/manifest.json", manifest)
    write_raw_index()
    print(json.dumps({
        "report": bench.REPORT_NAME,
        "arm_status": metrics["arm_status"],
        "judge_status": metrics["judge_status"],
        "armA": metrics["aggregate"]["arms"]["A"]["performance"],
        "armB": metrics["aggregate"]["arms"]["B"]["performance"],
        "total_spend": ctx["provider"].rolling_totals(),
        "public_scan": {"command": command, "result": scan},
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
