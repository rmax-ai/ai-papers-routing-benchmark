#!/usr/bin/env python3
"""Verify fixed-key L1 JSON compliance on one paper before the full matrix."""

import hashlib
import json
from pathlib import Path

from run_l1 import PROMPT, ROOT, run_chat
from provider import write_json


def main() -> None:
    sample = json.loads((ROOT / "raw" / "sampling.json").read_text(encoding="utf-8"))
    cap = json.loads((ROOT / "raw" / "capability-probes.json").read_text(encoding="utf-8"))
    paper = sample["papers"][0]
    state_obj = {"paper_id": paper["arxiv_id"], "title": paper.get("arxiv_title_differs_from_local") or paper.get("title"), "authors": paper.get("arxiv_metadata", {}).get("authors") or paper.get("authors"), "categories": paper.get("arxiv_metadata", {}).get("categories") or paper.get("categories"), "abstract": paper.get("abstract", "")}
    state = json.dumps(state_obj, ensure_ascii=False, separators=(",", ":"))
    input_hash = hashlib.sha256((PROMPT + "\n" + state).encode("utf-8")).hexdigest()
    gemini_id = cap["providers"]["gemini"]["model_id_sent"]
    results = {}
    for provider in ("deepseek", "gemini", "openai"):
        results[provider] = run_chat(provider, paper, state, input_hash, gemini_id)
    data = {"status": "prompt-compliance-pilot", "paper_id": paper["arxiv_id"], "input_sha256": input_hash, "results": results}
    write_json(ROOT / "raw" / "l1-prompt-pilot-corrected.json", data)
    print(json.dumps({key: {"status": value.get("http_status"), "parse_error": value.get("parse_error"), "validation_errors": value.get("validation_errors"), "artifact": value.get("call_artifacts")} for key, value in results.items()}, indent=2))


if __name__ == "__main__":
    main()
