#!/usr/bin/env python3
"""Fetch public arXiv abstracts and a bounded PDF subset; no other hosts."""

from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

import pymupdf
import requests

ROOT = Path.cwd()
MAX_PDF_BYTES = 25 * 1024 * 1024
ARXIV_HOSTS = {"arxiv.org", "export.arxiv.org"}
ATOM = "http://www.w3.org/2005/Atom"
last_request = 0.0


def paced_get(session: requests.Session, url: str, *, stream: bool = False) -> tuple[requests.Response, list[dict]]:
    global last_request
    redirects = []
    current = url
    for _ in range(5):
        parsed = urlparse(current)
        if parsed.hostname not in ARXIV_HOSTS or parsed.scheme != "https":
            raise RuntimeError("blocked request to host outside arxiv.org allowlist")
        wait = 3.0 - (time.monotonic() - last_request)
        if wait > 0:
            time.sleep(wait)
        response = session.get(current, timeout=(15, 180), stream=stream, allow_redirects=False)
        last_request = time.monotonic()
        if response.status_code not in (301, 302, 303, 307, 308):
            if urlparse(response.url).hostname not in ARXIV_HOSTS:
                raise RuntimeError("final request host outside arxiv.org allowlist")
            return response, redirects
        location = response.headers.get("location")
        redirects.append({"status": response.status_code, "host": parsed.hostname})
        if not location:
            return response, redirects
        current = urljoin(current, location)
    raise RuntimeError("too many arXiv redirects")


def read_pdf_info(path: Path) -> dict:
    doc = pymupdf.open(path)
    pages = len(doc)
    texts = [page.get_text("text") for page in doc]
    all_text = "\n".join(texts)
    image_count = sum(len(page.get_images(full=True)) for page in doc)
    figure_refs = len(re.findall(r"\b(?:fig(?:ure)?\.?\s*)(?:[A-Z]?\d+)", all_text, re.I))
    table_refs = len(re.findall(r"\btable\s+(?:[A-Z]?\d+)", all_text, re.I))
    page_text_pages = sum(bool(text.strip()) for text in texts)
    heavy_reasons = []
    if pages >= 20:
        heavy_reasons.append("long: page_count>=20")
    if image_count >= 6 or figure_refs >= 4:
        heavy_reasons.append(f"figure-heavy: images={image_count}, figure_refs={figure_refs}")
    if table_refs >= 3:
        heavy_reasons.append(f"table-heavy: table_refs={table_refs}")
    result = {
        "page_count": pages,
        "text_pages": page_text_pages,
        "text_page_ratio": round(page_text_pages / pages, 3) if pages else 0,
        "image_count": image_count,
        "figure_reference_count": figure_refs,
        "table_reference_count": table_refs,
        "long_figure_or_table_heavy": bool(heavy_reasons),
        "heavy_reasons": heavy_reasons,
        "page_text_chars": [len(t) for t in texts],
        "page_text": texts,
        "whole_text": all_text,
    }
    doc.close()
    return result


def main() -> None:
    sample_path = ROOT / "raw" / "sampling.json"
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    ids = [row["arxiv_id"] for row in sample["papers"]]
    session = requests.Session()
    session.headers["User-Agent"] = "dq79-ai-papers-routing-eval/1.0 (research benchmark)"
    feed_url = "https://export.arxiv.org/api/query?id_list=" + ",".join(ids) + "&max_results=" + str(len(ids))
    feed, feed_redirects = paced_get(session, feed_url)
    feed_bytes = len(feed.content)
    feed.raise_for_status()
    root = ET.fromstring(feed.content)
    abstracts: dict[str, dict] = {}
    for entry in root.findall(f"{{{ATOM}}}entry"):
        raw_id = entry.findtext(f"{{{ATOM}}}id", default="")
        paper_id_match = re.search(r"/(\d{4}\.\d{4,5})(?:v(\d+))?$", raw_id)
        if not paper_id_match:
            continue
        paper_id, version = paper_id_match.group(1), paper_id_match.group(2)
        abstracts[paper_id] = {
            "title": " ".join((entry.findtext(f"{{{ATOM}}}title", default="") or "").split()),
            "abstract": " ".join((entry.findtext(f"{{{ATOM}}}summary", default="") or "").split()),
            "published": entry.findtext(f"{{{ATOM}}}published"),
            "updated": entry.findtext(f"{{{ATOM}}}updated"),
            "version": version,
            "authors": [a.findtext(f"{{{ATOM}}}name", default="") for a in entry.findall(f"{{{ATOM}}}author")],
            "categories": [c.attrib.get("term") for c in entry.findall(f"{{{ATOM}}}category")],
            "id_url": raw_id,
        }
    for row in sample["papers"]:
        paper_id = row["arxiv_id"]
        if paper_id in abstracts:
            row["abstract"] = abstracts[paper_id]["abstract"]
            row["arxiv_metadata"] = abstracts[paper_id]
            row["abstract_fetch"] = {"source": "export.arxiv.org/api/query", "http_status": feed.status_code, "batch_response_bytes": feed_bytes, "abstract_chars": len(abstracts[paper_id]["abstract"]), "result": "ok"}
            if abstracts[paper_id].get("version"):
                row["version"] = abstracts[paper_id]["version"]
            if abstracts[paper_id].get("title") and abstracts[paper_id]["title"].lower() != (row.get("title") or "").lower():
                row["arxiv_title_differs_from_local"] = abstracts[paper_id]["title"]
        else:
            row["abstract_fetch"] = {"source": "export.arxiv.org/api/query", "http_status": feed.status_code, "batch_response_bytes": feed_bytes, "result": "entry_missing"}

    pdf_outcomes = {}
    info_by_id = {}
    for paper_id in sample["pdf_candidate_ids"]:
        row = next((x for x in sample["papers"] if x["arxiv_id"] == paper_id), None)
        if row is None:
            continue
        version = row.get("version")
        versioned = f"{paper_id}v{version}" if version else paper_id
        pdf_url = f"https://arxiv.org/pdf/{versioned}"
        outcomes = []
        try:
            response, redirects = paced_get(session, pdf_url, stream=True)
            content_length = response.headers.get("content-length")
            chunks: list[bytes] = []
            total = 0
            oversized = False
            if response.status_code == 200:
                for chunk in response.iter_content(256 * 1024):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > MAX_PDF_BYTES:
                        oversized = True
                        chunks.clear()
                        break
                    chunks.append(chunk)
            else:
                for chunk in response.iter_content(16 * 1024):
                    total += len(chunk)
                    if total > MAX_PDF_BYTES:
                        break
            row_path = ROOT / "raw" / "pdfs" / f"{versioned}.pdf"
            if response.status_code == 200 and not oversized and total:
                data = b"".join(chunks)
                row_path.write_bytes(data)
                pdf_info = read_pdf_info(row_path)
                info_by_id[paper_id] = pdf_info
                outcome = {
                    "source_url": pdf_url, "http_status": response.status_code,
                    "redirects": redirects, "bytes": len(data),
                    "content_length_header": int(content_length) if content_length and content_length.isdigit() else None,
                    "result": "downloaded", "artifact": row_path.relative_to(ROOT).as_posix(),
                    "page_count": pdf_info["page_count"],
                    "text_pages": pdf_info["text_pages"],
                    "text_page_ratio": pdf_info["text_page_ratio"],
                    "image_count": pdf_info["image_count"],
                    "figure_reference_count": pdf_info["figure_reference_count"],
                    "table_reference_count": pdf_info["table_reference_count"],
                    "long_figure_or_table_heavy": pdf_info["long_figure_or_table_heavy"],
                    "heavy_reasons": pdf_info["heavy_reasons"],
                }
            elif oversized:
                outcome = {"source_url": pdf_url, "http_status": response.status_code, "redirects": redirects, "bytes_read_before_cap": total, "content_length_header": int(content_length) if content_length and content_length.isdigit() else None, "result": "skipped_over_25mb"}
            else:
                outcome = {"source_url": pdf_url, "http_status": response.status_code, "redirects": redirects, "response_bytes": total, "content_length_header": int(content_length) if content_length and content_length.isdigit() else None, "result": "http_failure"}
            pdf_outcomes[paper_id] = outcome
            row["pdf_fetch"] = outcome
        except Exception as exc:  # per-paper fail-continue; error is data
            outcome = {"source_url": pdf_url, "http_status": None, "result": "fetch_or_parse_error", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
            pdf_outcomes[paper_id] = outcome
            row["pdf_fetch"] = outcome

    sample["pdf_outcomes"] = pdf_outcomes
    sample["pdf_heavy_ids"] = [paper_id for paper_id, out in pdf_outcomes.items() if out.get("long_figure_or_table_heavy")]
    sample["pdf_heavy_count"] = len(sample["pdf_heavy_ids"])
    sample["abstract_fetch_batch"] = {"url": "https://export.arxiv.org/api/query?id_list=<24-arxiv-ids>", "http_status": feed.status_code, "response_bytes": feed_bytes, "redirects": feed_redirects, "entry_count": len(abstracts)}
    sample_path.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_payload = {paper_id: {key: value for key, value in entry.items() if key not in {"authors"}} for paper_id, entry in abstracts.items()}
    (ROOT / "raw" / "arxiv-abstracts.json").write_text(json.dumps(write_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Keep full extracted page text local for the bounded evaluation; it is
    # derived from the sampled PDFs and is not a searchable corpus/index.
    (ROOT / "scratch" / "pdf-text.json").write_text(json.dumps({k: v["page_text"] for k, v in info_by_id.items()}, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "scratch" / "pdf-info.json").write_text(json.dumps({k: {kk: vv for kk, vv in v.items() if kk not in {"page_text", "whole_text"}} for k, v in info_by_id.items()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"abstract_batch": sample["abstract_fetch_batch"], "pdf_downloaded": sum(x.get("result") == "downloaded" for x in pdf_outcomes.values()), "pdf_failures": {k: v for k, v in pdf_outcomes.items() if v.get("result") != "downloaded"}, "pdf_heavy_count": sample["pdf_heavy_count"], "pdf_heavy_ids": sample["pdf_heavy_ids"]}, indent=2))


if __name__ == "__main__":
    main()
