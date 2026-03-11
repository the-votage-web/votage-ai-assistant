from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

import requests
from bs4 import BeautifulSoup, Tag


DEFAULT_URLS = [
    "https://thevotagechurch.org/home",
    "https://thevotagechurch.org/about",
    "https://thevotagechurch.org/connect",
    "https://thevotagechurch.org/sermons",
    "https://thevotagechurch.org/contact",
    "https://thevotagechurch.org/growth-track",
]


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _question_from_heading(heading: str) -> str:
    h = _clean_text(heading).rstrip(":")
    if not h:
        return ""
    if h.endswith("?"):
        return h
    return f"What should I know about {h}?"


def _extract_answer_from_heading(heading: Tag, limit: int = 900) -> str:
    parts: list[str] = []
    for sibling in heading.find_all_next():
        if sibling is heading:
            continue
        if sibling.name in {"h1", "h2", "h3"}:
            break
        if sibling.name in {"p", "li"}:
            txt = _clean_text(sibling.get_text(" ", strip=True))
            if txt:
                parts.append(txt)
        if len(" ".join(parts)) >= limit:
            break
    return " ".join(parts)[:limit].strip()


def scrape_faq(urls: Iterable[str]) -> list[tuple[str, str]]:
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    headers = {"User-Agent": "church-ai-rag-bot/1.0"}

    for url in urls:
        res = requests.get(url, headers=headers, timeout=20)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # Remove noise and boilerplate sections before extracting Q/A.
        for tag in soup.select("script, style, nav, footer, form, noscript"):
            tag.decompose()

        for heading in soup.select("h1, h2, h3"):
            q = _question_from_heading(heading.get_text(" ", strip=True))
            if not q:
                continue
            a = _extract_answer_from_heading(heading)
            if len(a) < 30:
                continue
            if q.lower() in seen:
                continue
            seen.add(q.lower())
            entries.append((q, a))

    return entries


def write_markdown(entries: list[tuple[str, str]], output: Path, urls: Iterable[str]) -> None:
    lines = ["# Church FAQ", ""]
    for q, a in entries:
        lines.append(f"Q: {q}")
        lines.append(f"A: {a}")
        lines.append("")

    lines.append("## Sources")
    for url in urls:
        lines.append(f"- {url}")
    lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape church website pages and build church_faq.md for RAG ingest."
    )
    parser.add_argument(
        "--url",
        action="append",
        dest="urls",
        help="Page URL to scrape (repeat flag for multiple pages).",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "church_faq.md"),
        help="Output Markdown path. Default: backend/app/rag/church_faq.md",
    )
    args = parser.parse_args()

    urls = args.urls or DEFAULT_URLS
    entries = scrape_faq(urls)
    if not entries:
        raise RuntimeError("No FAQ entries extracted. Try different URLs or update selectors.")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_markdown(entries, output, urls)
    print(f"Wrote {len(entries)} FAQ entries to {output}")


if __name__ == "__main__":
    main()
