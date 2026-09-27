#!/usr/bin/env python3
"""Summarize typed JEV post-checks against deterministic/proxy labels."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path.cwd()
LABELS = {
    "supported_by_supplied_evidence": ("quote_containment_cited_page_rate", .75, "judge_evidence_support"),
    "agenda_relevant": ("high_value_proxy_label", .60, "judge_systems_relevance"),
    "duplicates_supplied_existing_insight": (None, .75, None),
    "has_actionable_implication": ("judge_actionable", .60, "judge_actionability"),
    "escalate_for_deeper_review": (None, .65, None),
}


def prob(answer: dict | None) -> float | None:
    if not isinstance(answer, dict):
        return None
    value = answer.get("probability")
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if 0 <= value <= 1 else None


def score_rows() -> dict:
    out = {}
    for path, data in (("raw/l3-metrics.json", None),):
        p = ROOT / path
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            out = data.get("per_paper", {})
    return out


def normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def main() -> None:
    l4 = json.loads((ROOT / "raw/l4-results.json").read_text(encoding="utf-8"))
    sampling = json.loads((ROOT / "raw/sampling.json").read_text(encoding="utf-8"))
    paper_map = {p["arxiv_id"]: p for p in sampling["papers"]}
    l3_rows = score_rows()
    l3_results = json.loads((ROOT / "raw/l3-results.json").read_text(encoding="utf-8"))["results"]
    text_map = json.loads((ROOT / "scratch/pdf-text.json").read_text(encoding="utf-8"))
    items = []
    for pid, cells in l4.get("results", {}).items():
        for key, result in cells.items():
            path, provider, _ = key.split("/")
            answers = result.get("answers") or {}
            checks = (l3_rows.get(pid, {}).get("generations", {}).get(path, {}).get(provider, {}))
            jscore = l3_rows.get(pid, {}).get("judge_scores", {}).get(path, {}).get(provider, {})
            generation = l3_results.get(pid, {}).get("generations", {}).get(path, {}).get(provider, {})
            insights = ((generation.get("output") or {}).get("insights") or [])
            first_insight = insights[0] if insights and isinstance(insights[0], dict) else {}
            available_pages = set(l3_results.get(pid, {}).get("inputs", {}).get(path, {}).get("pages", []))
            page_texts = text_map.get(pid, [])
            refs = first_insight.get("evidence_refs") or []
            ref_results = []
            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                page, quote = ref.get("page"), str(ref.get("quote") or "")
                seen_text = page_texts[page - 1] if isinstance(page, int) and 0 < page <= len(page_texts) and page in available_pages else ""
                ref_results.append(bool(quote and normalized(quote) in normalized(seen_text)))
            support_rate = sum(ref_results) / len(ref_results) if ref_results else 0.0
            items.append({"paper_id": pid, "path": path, "generator": provider,
                "stratum": paper_map.get(pid, {}).get("stratum"),
                "high_value_proxy_label": paper_map.get(pid, {}).get("high_value_proxy_label"),
                "answers": answers, "support_quote_containment_rate": support_rate,
                "candidate_evidence_ref_count": len(ref_results),
                "candidate_exact_quote_support_label": bool(ref_results) and all(ref_results),
                "judge_actionable": (jscore.get("actionability", 0) >= 3) if "actionability" in jscore else None,
                "judge_faithfulness": jscore.get("faithfulness"), "judge_evidence_support": jscore.get("evidence_support"),
                "judge_systems_relevance": jscore.get("systems_relevance"), "judge_actionability": jscore.get("actionability"),
                "call_artifacts": result.get("call_artifacts", [])})
    per_question = {}
    for question, (label_name, threshold, judge_name) in LABELS.items():
        pairs, agree = [], 0
        judge_pairs, judge_agree = [], 0
        tp = fp = tn = fn = 0
        for item in items:
            p = prob(item["answers"].get(question))
            if p is None:
                continue
            label = None
            if label_name == "quote_containment_cited_page_rate":
                value = item["support_quote_containment_rate"]
                label = (value >= 1.0) if value is not None else None
            elif label_name == "high_value_proxy_label":
                value = item[label_name]
                label = bool(value) if value is not None else None
            elif label_name == "judge_actionable":
                label = item[label_name]
            decision = p >= threshold
            row = {"paper_id": item["paper_id"], "path": item["path"], "generator": item["generator"], "probability": p, "host_decision": decision, "proxy_label": label}
            if label is not None:
                y = bool(label)
                pairs.append((p, int(y)))
                agree += decision == y
                tp += decision and y
                fp += decision and not y
                tn += not decision and not y
                fn += not decision and y
                row["agreement"] = decision == y
            jscore = item.get(judge_name) if judge_name else None
            judge_label = (jscore >= 3) if isinstance(jscore, (int, float)) else None
            if judge_label is not None:
                judge_pairs.append((p, int(judge_label)))
                judge_agree += decision == judge_label
                row["blind_judge_label"] = judge_label
                row["agreement_vs_blind_judge"] = decision == judge_label
            per_question.setdefault(question, {"threshold": threshold, "label_source": label_name,
                "n_answers": 0, "mean_probability": None, "brier": None, "agreement_vs_label": None,
                "judge_label_source": judge_name, "n_judge_labeled": 0,
                "brier_vs_blind_judge": None, "agreement_vs_blind_judge": None,
                "tp": 0, "fp": 0, "tn": 0, "fn": 0, "probabilities_without_gold_label": []})["n_answers"] += 1
            if label is None:
                per_question[question]["probabilities_without_gold_label"].append(p)
            item.setdefault("question_rows", {})[question] = row
        q = per_question.setdefault(question, {"threshold": threshold, "label_source": label_name,
            "n_answers": 0, "mean_probability": None, "brier": None, "agreement_vs_label": None,
            "judge_label_source": judge_name, "n_judge_labeled": 0,
            "brier_vs_blind_judge": None, "agreement_vs_blind_judge": None,
            "tp": 0, "fp": 0, "tn": 0, "fn": 0, "probabilities_without_gold_label": []})
        allp = [prob(item["answers"].get(question)) for item in items]
        allp = [p for p in allp if p is not None]
        q["mean_probability"] = sum(allp)/len(allp) if allp else None
        q["n_labeled"] = len(pairs)
        q["brier"] = sum((p-y)**2 for p,y in pairs)/len(pairs) if pairs else None
        q["agreement_vs_label"] = agree / len(pairs) if pairs else None
        q["n_judge_labeled"] = len(judge_pairs)
        q["brier_vs_blind_judge"] = sum((p-y)**2 for p,y in judge_pairs)/len(judge_pairs) if judge_pairs else None
        q["agreement_vs_blind_judge"] = judge_agree / len(judge_pairs) if judge_pairs else None
        q.update(tp=tp, fp=fp, tn=tn, fn=fn)
        q.pop("probabilities_without_gold_label", None)
    out = {"schema_version": 1, "status": l4.get("status"),
        "sampled_candidate_insights": len(items), "per_question": per_question,
        "per_candidate": items,
        "label_limits": "Evidence support uses exact quoted-text containment as a noisy support proxy, not semantic entailment. Agenda relevance uses purposive high-value stratum labels, not gold relevance. Actionability uses blind LLM judge score >=3/4. Duplicate and escalation have no gold labels; no Brier score is reported for them."}
    (ROOT / "raw/l4-metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": out["status"], "n": len(items), "questions": {k:{m:v for m,v in q.items() if m not in ('probabilities_without_gold_label',)} for k,q in per_question.items()}}, indent=2))


if __name__ == "__main__":
    main()
