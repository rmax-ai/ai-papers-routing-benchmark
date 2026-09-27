#!/usr/bin/env python3
"""Select the fixed, stratified issue-79 sample from the read-only stores."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path.cwd()
HOME = Path.home()
PAPERS_DB = HOME / "personal-hermes" / "papers.db"
KURATE_DB = HOME / ".hermes" / "cron" / "output" / "kurate" / "kurate.db"
KG_ROOT = HOME / "src" / "rmax-ai" / "knowledge-graph"

HIGH_IDS = [
    "2609.27263",  # empirically describes agentic workflow practice
    "2609.28585",  # tool-agent cost and runtime defenses
    "2609.28586",  # approval/effect governance
    "2609.28614",  # autonomous research oversight/evaluation
    "2609.28693",  # agent tool access governance
    "2609.28915",  # agent security evidence
    "2609.29095",  # reliability, duplicate effects, tool contracts
    "2609.30217",  # empirical monitor evasion under task pressure
    "2609.30266",  # agent trace integrity
    "2609.29808",  # runtime containment
    "2609.23498",  # MCP workflow authorization consistency
    "2609.24130",  # runtime harness oversight
]
MEDIUM_IDS = [
    "2609.23742",  # structured output and model capability boundary
    "2609.30009",  # domain RAG, not an agent-runtime study
    "2609.24122",  # production retrieval coverage auditing
    "2609.19710",  # constrained text-generation control
    "2609.14245",  # retrieval evidence compression/attribution
    "2609.03213",  # rules versus examples in-context learning
    "2609.15578",  # retrieval confidence and abstention
    "2609.22056",  # multi-hop retrieval confidence
]
LOW_IDS = [
    "2606.01987",  # vehicle-routing graph optimization
    "2606.30487",  # nonlinear state-estimation filter
    "2603.21521",  # microwave object sensing hardware
    "2606.15960",  # labor economics of AI automation, no agent-runtime focus
]


def readonly(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def tilde(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return "~" + str(Path(path).relative_to(HOME))
    except ValueError:
        return path


def kg_matches(ids: set[str]) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {paper_id: [] for paper_id in ids}
    pattern = re.compile(r"(?<!\d)(\d{4}\.\d{4,5})(?:v\d+)?(?!\d)")
    for path in sorted((KG_ROOT / "sources" / "papers").glob("*.md")):
        body = path.read_text(encoding="utf-8", errors="replace")
        found = {m.group(1) for m in pattern.finditer(body)}
        for paper_id in ids & found:
            matches[paper_id].append(tilde(str(path)) or path.name)
    return matches


def main() -> None:
    ids = set(HIGH_IDS + MEDIUM_IDS + LOW_IDS)
    metadata: dict[str, dict] = {}

    conn = readonly(PAPERS_DB)
    conn.row_factory = sqlite3.Row
    for row in conn.execute(
        "SELECT arxiv_id,digest_date,title,authors,categories,paper_date,section,"
        "section_canon,note,url,source_file FROM papers ORDER BY digest_date DESC"
    ):
        paper_id = row["arxiv_id"].split("v")[0]
        if paper_id in ids and paper_id not in metadata:
            metadata[paper_id] = {
                "arxiv_id": paper_id,
                "version": (row["url"] or "").split(paper_id)[-1].strip("v/") or None,
                "title": row["title"],
                "authors": row["authors"],
                "categories": row["categories"],
                "paper_date": row["paper_date"],
                "digest_date": row["digest_date"],
                "section": row["section"],
                "section_canon": row["section_canon"],
                "local_note": row["note"],
                "source_store": "~/personal-hermes/papers.db",
                "source_file": tilde(row["source_file"]),
                "arxiv_url": row["url"],
            }
    conn.close()

    conn = readonly(KURATE_DB)
    conn.row_factory = sqlite3.Row
    for row in conn.execute(
        "SELECT canonical_id,title,authors_json,categories_json,published,abstract,"
        "arxiv_link,best_score FROM papers"
    ):
        paper_id = row["canonical_id"].split("v")[0]
        if paper_id in ids and paper_id not in metadata:
            metadata[paper_id] = {
                "arxiv_id": paper_id,
                "version": (row["arxiv_link"] or "").split(paper_id)[-1].strip("v/") or None,
                "title": row["title"],
                "authors": row["authors_json"],
                "categories": row["categories_json"],
                "paper_date": row["published"],
                "digest_date": None,
                "section": None,
                "section_canon": None,
                "local_note": None,
                "source_store": "~/.hermes/cron/output/kurate/kurate.db",
                "source_file": None,
                "arxiv_url": row["arxiv_link"],
                "abstract_from_kurate": row["abstract"],
                "best_score": row["best_score"],
            }
    conn.close()

    match_map = kg_matches(ids)
    records = []
    missing = []
    for stratum, selected in (
        ("high_value_proxy", HIGH_IDS),
        ("medium_adjacent", MEDIUM_IDS),
        ("low_relevance_control", LOW_IDS),
    ):
        for rank, paper_id in enumerate(selected, start=1):
            item = metadata.get(paper_id)
            if item is None:
                missing.append(paper_id)
                continue
            item = dict(item)
            item["stratum"] = stratum
            item["stratum_rank"] = rank
            item["high_value_proxy_label"] = stratum == "high_value_proxy"
            item["kg_per_paper_entries"] = match_map[paper_id]
            item["deep_processed"] = bool(match_map[paper_id])
            records.append(item)

    doc_candidates = [r for r in records if r["stratum"] in {"high_value_proxy", "medium_adjacent"}]
    # PDF-intensive set is deliberately weighted toward papers whose local
    # summaries describe tables, experiments, multiple evaluation conditions,
    # long horizons, system designs, or longer treatments.
    pdf_preferred = [
        "2609.29808", "2609.29095", "2609.28614", "2609.30217",
        "2609.28585", "2609.28586", "2609.27263", "2609.30009",
        "2609.24122", "2609.23742",
        "2606.01987", "2606.30487", "2603.21521", "2606.15960",
    ]
    pdf_ids = [paper_id for paper_id in pdf_preferred if paper_id in {r["arxiv_id"] for r in doc_candidates}]
    l3_ids = [
        "2609.27263", "2609.28585", "2609.28586", "2609.28614",
        "2609.29095", "2609.30217", "2609.30266", "2609.29808",
        "2609.23742", "2609.30009",
    ]
    policy = {
        "selection_rules": [
            "Deduplicate papers.db by arXiv id, keeping the newest digest_date; select high positives from section_canon in agents/mcp/infra/governance with direct agenda cues in title/note, prioritizing recent empirical, reliability, evaluation, tool, and runtime studies.",
            "Select adjacent-medium papers from papers.db rag/prompt or related application/evaluation work that concerns LLM systems but does not directly study agent routing/runtime reliability.",
            "Select negative controls from the already-ingested kurate.db full-abstract store by excluding direct agent/tool/MCP/workflow/governance/evaluation agenda terms and choosing distinct non-agent AI/optimization/application domains.",
            "KG deep-processing label is determined by a matching arXiv id found in sources/papers/*.md; it is a secondary tag and can overlap any relevance stratum.",
            "Fixed arXiv ID lists above make this specific run reproducible; selection is purposive, not random, and the relevance strata are proxy labels.",
        ],
        "sample_size": len(records),
        "strata_counts": {s: sum(r["stratum"] == s for r in records) for s in ["high_value_proxy", "medium_adjacent", "low_relevance_control"]},
        "deep_processed_count": sum(r["deep_processed"] for r in records),
        "deep_processed_ids": [r["arxiv_id"] for r in records if r["deep_processed"]],
        "missing_from_local_stores": missing,
        "pdf_candidate_ids": pdf_ids,
        "l3_candidate_ids": l3_ids,
        "papers": records,
    }
    out = ROOT / "raw" / "sampling.json"
    out.write_text(json.dumps(policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: policy[k] for k in ["sample_size", "strata_counts", "deep_processed_count", "deep_processed_ids", "missing_from_local_stores", "pdf_candidate_ids", "l3_candidate_ids"]}, indent=2))
    for r in records:
        print(f"{r['stratum']:24} {r['arxiv_id']:11} kg={int(r['deep_processed'])} {r['title']}")


if __name__ == "__main__":
    main()
