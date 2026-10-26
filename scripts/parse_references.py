#!/usr/bin/env python3
"""Parse a manuscript's bibliography into structured references.

Deterministic step of the claim-citation-auditor skill. Extracts the reference
list from a .docx / .md / .tex / .pdf manuscript (or a plain references file),
splits it into individual entries, and pulls out DOI, PMID, year, and a best-effort
title/authors/journal for each. No model judgement happens here.

Usage:
    python3 parse_references.py MANUSCRIPT [--out references.json] [--section-title References]

Output: JSON list of records:
    {"key": "12", "raw": "...", "authors": "...", "title": "...",
     "journal": "...", "year": "2023", "volume": "...", "pages": "...",
     "doi": "10.x/...", "pmid": "123456"}
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

# Shared manuscript-reading helpers live in manuscript_io.py (zero third-party
# deps for docx/md/tex; pdf uses pdfplumber if installed).
from manuscript_io import read_manuscript_text  # noqa: E402

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", re.I)
PMID_RE = re.compile(r"\bPMID:?\s*(\d{4,9})\b", re.I)
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
# Numbered-style entry start: "[12]" or "12." at line start.
NUM_BRACKET_RE = re.compile(r"^\s*\[(\d{1,3})\]\s+")
NUM_DOT_RE = re.compile(r"^\s*(\d{1,3})\.\s+")


def _strip_trailing_punct(doi: str) -> str:
    # DOIs greedily capture trailing punctuation from prose; trim common ones.
    return doi.rstrip(").,;]")


def find_references_section(text: str, section_title: str = "References") -> str:
    """Return the text from the bibliography heading to the end of the document."""
    # Match a heading line like "References", "## References", "REFERENCES",
    # "Bibliography", optionally numbered.
    pat = re.compile(
        rf"(?im)^\s*(?:#+\s*|\d+\.?\s*)?\**\s*(references|bibliography|literature cited)\s*\**\s*$"
    )
    matches = list(pat.finditer(text))
    if not matches:
        # Fall back: whole document (user may have passed a references-only file).
        return text
    # Use the LAST such heading (the real bibliography, not a mention in prose).
    start = matches[-1].end()
    return text[start:]


def split_entries(bib_text: str) -> list[tuple[str, str]]:
    """Split a bibliography blob into (key, raw_entry) tuples.

    Handles numbered styles ([n] or n.) and falls back to blank-line-separated
    blocks for author-year styles.
    """
    lines = bib_text.splitlines()
    entries: list[tuple[str, str]] = []
    cur_key: str | None = None
    cur_lines: list[str] = []

    def flush():
        nonlocal cur_lines, cur_key
        if cur_lines:
            raw = " ".join(l.strip() for l in cur_lines if l.strip())
            if raw.strip():
                entries.append((cur_key if cur_key is not None else str(len(entries) + 1), raw))
        cur_lines = []

    numbered = False
    for line in lines:
        mb = NUM_BRACKET_RE.match(line)
        md = NUM_DOT_RE.match(line)
        m = mb or md
        if m:
            numbered = True
            flush()
            cur_key = m.group(1)
            cur_lines = [line[m.end():]]
        else:
            cur_lines.append(line)
    flush()

    if not numbered:
        # Author-year: re-split on blank lines instead.
        entries = []
        blocks = re.split(r"\n\s*\n", bib_text)
        for i, block in enumerate(blocks, 1):
            raw = " ".join(l.strip() for l in block.splitlines() if l.strip())
            if len(raw) > 20:  # skip stray short lines
                entries.append((str(i), raw))
    return entries


def parse_entry(key: str, raw: str) -> dict:
    rec: dict = {"key": key, "raw": raw}
    doi_m = DOI_RE.search(raw)
    if doi_m:
        rec["doi"] = _strip_trailing_punct(doi_m.group(0))
    pmid_m = PMID_RE.search(raw)
    if pmid_m:
        rec["pmid"] = pmid_m.group(1)
    years = re.findall(r"\b(?:19|20)\d{2}\b", raw)
    if years:
        # Use the last 4-digit year in the entry (publication year usually trails).
        rec["year"] = years[-1]
    # Best-effort title: text inside the first pair of straight/curly double quotes.
    title_m = re.search(r'[\"“]([^\"”]{8,})[\"”]', raw)
    if title_m:
        rec["title"] = title_m.group(1).strip().rstrip(",.")
    # Best-effort authors: text before the first quote or before the year.
    head = raw[: title_m.start()] if title_m else raw
    head = head.strip().rstrip(",")
    if head:
        rec["authors"] = head
    # Best-effort journal: italic markdown *Journal,* after the title, else None.
    jour_m = re.search(r"[\*”]\s*,?\s*\*?([A-Z][A-Za-z&.\- ]{3,60})\*?,", raw[title_m.end():] if title_m else raw)
    if jour_m:
        rec["journal"] = jour_m.group(1).strip()
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="Parse a manuscript bibliography into structured references.")
    ap.add_argument("manuscript", help="Path to .docx/.md/.tex/.pdf manuscript or references file")
    ap.add_argument("--out", default="-", help="Output JSON path (default: stdout)")
    ap.add_argument("--section-title", default="References", help="Bibliography heading to look for")
    args = ap.parse_args(argv)

    text = read_manuscript_text(Path(args.manuscript))
    bib = find_references_section(text, args.section_title)
    entries = split_entries(bib)
    records = [parse_entry(k, r) for k, r in entries]

    out = json.dumps(records, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(out)
    else:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"Wrote {len(records)} references to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
