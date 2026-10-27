#!/usr/bin/env python3
"""Map in-text citations to the claims (sentences) they support.

Deterministic first pass of the claim-citation-auditor skill. It finds every
in-text citation marker in the body of a manuscript and captures the sentence(s)
around it, producing a claim↔citation map. Claude then refines each sentence into
atomic claims downstream — this script does NOT interpret meaning.

Supports numbered styles ([12], [12-14], [12, 15]) and LaTeX \\cite{key}.
Author-year in-text styles ("(Smith et al., 2021)") are detected heuristically.

Usage:
    python3 extract_claims.py MANUSCRIPT [--out claims.json] [--style auto|numeric|latex|authoryear]

Output JSON:
    {"passages": [
        {"id": 1, "sentence": "...", "citations": ["12","13","14"],
         "char_offset": 1234, "needs_atomic_split": true}
     ],
     "stats": {"n_passages": N, "n_citations": M, "unresolved_fields": false}}
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

from manuscript_io import read_manuscript_text  # noqa: E402

# [12], [12-14], [12, 15, 18], with en-dashes tolerated.
NUMERIC_CITE_RE = re.compile(r"\[(\d{1,3}(?:\s*[-–,]\s*\d{1,3})*)\]")
LATEX_CITE_RE = re.compile(r"\\cite[a-z]*\{([^}]+)\}")
AUTHORYEAR_RE = re.compile(r"\(([^()]*?(?:19|20)\d{2}[a-z]?)\)")
# Sentence splitter: split on . ! ? followed by space+capital/open-bracket.
SENT_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[(])")


def expand_numeric(group: str) -> list[str]:
    """'12-14, 18' -> ['12','13','14','18']."""
    out: list[str] = []
    for part in re.split(r"\s*,\s*", group):
        m = re.match(r"(\d+)\s*[-–]\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if a <= b and b - a < 100:
                out.extend(str(n) for n in range(a, b + 1))
            else:
                out.append(part)
        elif part.strip():
            out.append(part.strip())
    return out


def strip_references_section(text: str) -> str:
    """Drop the bibliography so we don't mine the reference list as 'claims'."""
    pat = re.compile(
        r"(?im)^\s*(?:#+\s*|\d+\.?\s*)?\**\s*(references|bibliography|literature cited)\s*\**\s*$"
    )
    matches = list(pat.finditer(text))
    if matches:
        return text[: matches[-1].start()]
    return text


def sentences_with_offsets(text: str):
    """Yield (sentence, char_offset) over a paragraph-joined text."""
    # Work paragraph by paragraph so offsets stay meaningful and sentences
    # don't bleed across headings.
    offset = 0
    for para in re.split(r"\n{1,}", text):
        if para.strip():
            base = text.find(para, offset)
            if base < 0:
                base = offset
            for sent in SENT_SPLIT_RE.split(para):
                s = sent.strip()
                if s:
                    yield s, text.find(s, base)
        offset += len(para) + 1


def detect_style(body: str) -> str:
    if LATEX_CITE_RE.search(body):
        return "latex"
    if NUMERIC_CITE_RE.search(body):
        return "numeric"
    if AUTHORYEAR_RE.search(body):
        return "authoryear"
    return "numeric"


def extract(body: str, style: str):
    passages = []
    pid = 0
    n_cites = 0
    for sent, off in sentences_with_offsets(body):
        cites: list[str] = []
        if style == "latex":
            for m in LATEX_CITE_RE.finditer(sent):
                cites.extend(k.strip() for k in m.group(1).split(","))
        elif style == "authoryear":
            cites.extend(m.group(1).strip() for m in AUTHORYEAR_RE.finditer(sent))
        else:  # numeric
            for m in NUMERIC_CITE_RE.finditer(sent):
                cites.extend(expand_numeric(m.group(1)))
        if cites:
            pid += 1
            n_cites += len(cites)
            # Flag likely-compound sentences for Claude to split into atomic claims.
            compound = bool(re.search(r"\b(and|whereas|while|however|yet|but)\b", sent)) or len(cites) > 1
            passages.append({
                "id": pid,
                "sentence": sent,
                "citations": cites,
                "char_offset": off,
                "needs_atomic_split": compound,
            })
    return passages, n_cites


def main(argv=None):
    ap = argparse.ArgumentParser(description="Map in-text citations to the sentences they support.")
    ap.add_argument("manuscript", help="Path to .docx/.md/.tex/.pdf manuscript")
    ap.add_argument("--out", default="-", help="Output JSON path (default: stdout)")
    ap.add_argument("--style", default="auto", choices=["auto", "numeric", "latex", "authoryear"])
    args = ap.parse_args(argv)

    path = Path(args.manuscript)
    text = read_manuscript_text(path)
    body = strip_references_section(text)
    # Pandoc Markdown (the recommended route for reference-manager .docx files)
    # backslash-escapes brackets, so an in-text citation renders as "\[1\]" and a
    # naive "\[\d+\]" match finds nothing. Unescape bracket pairs for non-LaTeX
    # inputs before matching. (.tex keeps "\[" as display-math, handled via \cite.)
    pre_style = detect_style(body) if args.style == "auto" else args.style
    if pre_style != "latex":
        body = re.sub(r"\\([\[\]])", r"\1", body)
    style = detect_style(body) if args.style == "auto" else args.style
    passages, n_cites = extract(body, style)

    unresolved = False
    if path.suffix.lower() == ".docx":
        from manuscript_io import docx_has_unresolved_fields
        unresolved = docx_has_unresolved_fields(path)

    result = {
        "style": style,
        "passages": passages,
        "stats": {
            "n_passages": len(passages),
            "n_citations": n_cites,
            "unresolved_fields": unresolved,
        },
    }
    if unresolved and n_cites < 10:
        print(
            "WARNING: few citations found and the .docx has reference-manager field codes. "
            "Convert with pandoc and re-run on the Markdown for complete results.",
            file=sys.stderr,
        )

    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(out)
    else:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"Wrote {len(passages)} citing passages ({n_cites} citations) to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
