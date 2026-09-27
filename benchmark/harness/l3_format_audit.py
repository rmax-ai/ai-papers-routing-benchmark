#!/usr/bin/env python3
"""Index canonical-shape, normalization, and deterministic-check outcomes for every L3 cell."""

import json
from pathlib import Path

ROOT = Path.cwd()


def main() -> None:
    data = json.loads((ROOT / "raw/l3-results.json").read_text(encoding="utf-8"))
    rows = []
    for paper_id, paper in data.get("results", {}).items():
        for path, models in paper.get("generations", {}).items():
            for provider, cell in models.items():
                rows.append({"paper_id": paper_id, "input_path": path, "provider": provider,
                    "model_emitted_keys": cell.get("model_emitted_keys"),
                    "model_emitted_canonical_shape": cell.get("model_emitted_canonical_shape"),
                    "host_normalization": cell.get("host_normalization"),
                    "deterministic_checks": cell.get("deterministic_checks"),
                    "http_status": cell.get("http_status"), "parse_error": cell.get("parse_error"),
                    "provider_error": cell.get("provider_error"),
                    "call_artifacts": cell.get("call_artifacts", []),
                    "superseded_invalid_response_artifacts": cell.get("superseded_invalid_response_artifacts", [])})
        sensitivity = paper.get("openai_medium")
        if isinstance(sensitivity, dict):
            rows.append({"paper_id": paper_id, "input_path": "full_reference-openai-medium",
                "provider": "openai", "model_emitted_keys": sensitivity.get("model_emitted_keys"),
                "model_emitted_canonical_shape": sensitivity.get("model_emitted_canonical_shape"),
                "host_normalization": sensitivity.get("host_normalization"),
                "deterministic_checks": sensitivity.get("deterministic_checks"),
                "http_status": sensitivity.get("http_status"), "parse_error": sensitivity.get("parse_error"),
                "provider_error": sensitivity.get("provider_error"),
                "call_artifacts": sensitivity.get("call_artifacts", []),
                "superseded_invalid_response_artifacts": sensitivity.get("superseded_invalid_response_artifacts", [])})
    out = {"schema_version": 1, "status": data.get("status"), "cell_count": len(rows),
        "method": "One record per generator/path/paper and reasoning sensitivity cell; normalized checks are deterministic host results; raw response files remain authoritative.",
        "results": rows}
    (ROOT / "raw/l3-format-findings.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": out["status"], "cell_count": out["cell_count"]}, indent=2))


if __name__ == "__main__":
    main()
