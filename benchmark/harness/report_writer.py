"""Replace a single H2 body in the incremental benchmark report."""

from pathlib import Path

REPORT = Path.cwd() / "dq79-ai-papers-routing-eval.md"


def replace_section(title: str, body: str) -> None:
    text = REPORT.read_text(encoding="utf-8")
    marker = f"## {title}\n"
    start = text.index(marker) + len(marker)
    next_heading = text.find("\n## ", start)
    if next_heading < 0:
        end = len(text)
    else:
        end = next_heading + 1
    replacement = body.rstrip() + "\n\n"
    REPORT.write_text(text[:start] + replacement + text[end:], encoding="utf-8")
