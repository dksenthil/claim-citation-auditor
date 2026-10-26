"""Manuscript reading helpers shared across the auditor scripts.

Core formats (.docx / .md / .tex / plain text) read with the Python standard
library only — no third-party dependencies. PDF reading uses `pdfplumber` if it
is installed and raises a clear error otherwise.

DOCX note: Word stores runs as separate XML nodes and reference-manager
citations (EndNote/Mendeley/Zotero) as field codes whose display text lives in
`w:instrText` / `w:fldSimple`. We concatenate visible `w:t` text in document
order, which is enough for reference-list extraction and for most in-text
citation numbers, but author names buried in base64 `w:fldData` are not
recovered. When that matters, convert with pandoc first (see SKILL.md).
"""
from __future__ import annotations
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_docx_text(path: Path) -> str:
    """Extract visible text from a .docx, one paragraph per line."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    lines: list[str] = []
    for para in root.iter(f"{W_NS}p"):
        parts: list[str] = []
        for node in para.iter():
            tag = node.tag
            if tag in (f"{W_NS}t", f"{W_NS}instrText") and node.text:
                # instrText holds field codes; keep only the human-readable
                # DISPLAYTEXT-looking fragments, skip ADDIN/EndNote machinery.
                if tag == f"{W_NS}instrText":
                    continue
                parts.append(node.text)
            elif tag == f"{W_NS}tab":
                parts.append("\t")
        line = "".join(parts)
        lines.append(line)
    return "\n".join(lines)


def docx_has_unresolved_fields(path: Path) -> bool:
    """True if the docx contains EndNote/Mendeley/Zotero field codes.

    Used to warn that citations may be under-counted and pandoc conversion is
    advisable before extracting claims.
    """
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "ignore")
    return bool(re.search(r"ADDIN\s+(EN\.CITE|CSL_CITATION|Mendeley|ZOTERO)", xml))


def read_pdf_text(path: Path) -> str:
    try:
        import pdfplumber  # type: ignore
    except ImportError as e:  # pragma: no cover - env dependent
        raise RuntimeError(
            "Reading PDF requires pdfplumber. Install with `pip install pdfplumber`, "
            "or convert the PDF to text/Markdown first."
        ) from e
    out: list[str] = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            out.append(page.extract_text() or "")
    return "\n".join(out)


def read_manuscript_text(path: Path) -> str:
    """Dispatch on file extension and return plain text.

    .md/.tex/.txt are returned as-is (callers strip markup as needed).
    """
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix == ".docx":
        if docx_has_unresolved_fields(path):
            print(
                "WARNING: this .docx contains reference-manager field codes. "
                "In-text citations and author names may be under-counted. "
                "Consider `pandoc in.docx -t markdown -o out.md` and run on the Markdown.",
                file=sys.stderr,
            )
        return read_docx_text(path)
    if suffix == ".pdf":
        return read_pdf_text(path)
    # .md, .tex, .txt, or anything else: read as UTF-8 text.
    return path.read_text(encoding="utf-8", errors="replace")
