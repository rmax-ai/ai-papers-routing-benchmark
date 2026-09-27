#!/usr/bin/env python3
"""Build the final raw artifact index and checksums without external dependencies."""

import hashlib
import json
from pathlib import Path

ROOT = Path.cwd()
RAW = ROOT / "raw"
REPORT = ROOT / "dq79-ai-papers-routing-eval.md"
MANIFEST = RAW / "manifest.json"
CHECKSUMS = RAW / "SHA256SUMS.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    paths = sorted(path for path in RAW.rglob("*")
                   if path.is_file() and path not in (MANIFEST, CHECKSUMS))
    artifacts = [{ "path": path.relative_to(RAW).as_posix(),
                   "bytes": path.stat().st_size, "sha256": sha256(path) }
                 for path in paths]
    response_paths = sorted((RAW / "responses").rglob("*.json"))
    by_status: dict[str, int] = {}
    for path in response_paths:
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        status = str(item.get("http_status"))
        by_status[status] = by_status.get(status, 0) + 1
    cost = json.loads((RAW / "cost-report.json").read_text(encoding="utf-8"))
    pdfs = [path for path in (RAW / "pdfs").glob("*") if path.is_file()]
    paper_counts = {}
    for name in ("l1-results.json", "l2-results.json", "l3-results.json", "l4-results.json"):
        path = RAW / name
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
            rows = item.get("results", [])
            paper_counts[name] = len(rows) if isinstance(rows, (list, dict)) else 0
        except (OSError, json.JSONDecodeError):
            paper_counts[name] = 0
    manifest = {
        "schema_version": 1,
        "status": "complete",
        "run_date_utc": "2026-09-26",
        "report": {
            "path": "../dq79-ai-papers-routing-eval.md",
            "bytes": REPORT.stat().st_size,
            "sha256": sha256(REPORT),
        },
        "artifacts": artifacts,
        "counts": {
            "raw_artifacts_indexed_excluding_manifest_and_checksums": len(artifacts),
            "provider_response_attempt_files": len(response_paths),
            "provider_response_attempts_by_http_status": by_status,
            "result_paper_or_record_counts": paper_counts,
            "pdf_files": len(pdfs),
            "pdf_bytes": sum(path.stat().st_size for path in pdfs),
            "provider_attempts": cost["total_attempts"],
            "provider_http_200": cost["responses_200"],
            "provider_errors": cost["errors"],
            "estimated_cost_usd": cost["estimated_total_cost_usd"],
        },
        "index_note": "The artifact array excludes manifest.json and SHA256SUMS.txt to avoid recursive self-hashing. SHA256SUMS.txt covers every raw file including manifest.json and also the report via ../dq79-ai-papers-routing-eval.md.",
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    checksum_paths = sorted(path for path in RAW.rglob("*")
                            if path.is_file() and path != CHECKSUMS)
    checksum_paths.append(REPORT)
    lines = [f"{sha256(path)}  {path.relative_to(RAW).as_posix() if path.is_relative_to(RAW) else '../' + path.name}"
             for path in checksum_paths]
    CHECKSUMS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": manifest["status"],
        "raw_artifacts": len(artifacts),
        "provider_attempt_files": len(response_paths),
        "provider_attempts": cost["total_attempts"],
        "estimated_cost_usd": cost["estimated_total_cost_usd"],
        "checksum_entries": len(checksum_paths),
        "manifest_sha256": sha256(MANIFEST),
        "report_sha256": sha256(REPORT),
    }, indent=2))


if __name__ == "__main__":
    main()
