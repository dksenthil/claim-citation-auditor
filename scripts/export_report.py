#!/usr/bin/env python3
"""Render the audit into a triage report (Markdown / CSV / JSON / HTML).

Deterministic export step. Takes the assessments the assistant produced (claim,
reference, verdict, evidence passage, fix) plus the evidence metadata, and emits
a report ranked by severity so the worst problems are read first.

Severity order (most severe first):
    fabricated/not_found  >  contradicts  >  metadata_mismatch  >
    partial/overreach/wrong-source  >  unverified  >  supports

Usage:
    python3 export_report.py assessments.json evidence.json --format md --out audit_report.md
    python3 export_report.py assessments.json evidence.json --format all --out audit_report

assessments.json schema (produced by the assistant; see references/evidence_rubric.md):
    [{"ref_key": "48", "claim": "...", "verdict": "CONTRADICTS|SUPPORTS|PARTIAL|UNSUPPORTED|UNVERIFIED",
      "evidence_quote": "...", "confidence": "high|medium|low", "rationale": "...",
      "suggested_fix": "..."}]
"""
from __future__ import annotations
import argparse
import csv
import html
import io
import json
from pathlib import Path

VERDICT_RANK = {
    "FABRICATED": 0, "NOT_FOUND": 0,
    "CONTRADICTS": 1,
    "METADATA_MISMATCH": 2,
    "PARTIAL": 3, "UNSUPPORTED": 3, "OVERREACH": 3, "WRONG_SOURCE": 3,
    "UNVERIFIED": 4,
    "SUPPORTS": 5,
}
VERDICT_LABEL = {
    "FABRICATED": "🔴 Fabricated / not found",
    "NOT_FOUND": "🔴 Not found",
    "CONTRADICTS": "🔴 Contradicts claim",
    "METADATA_MISMATCH": "🟠 Metadata error",
    "PARTIAL": "🟡 Partial support",
    "UNSUPPORTED": "🟡 Unsupported",
    "OVERREACH": "🟡 Over-reach",
    "WRONG_SOURCE": "🟡 Wrong source type",
    "UNVERIFIED": "⚪ Unverified",
    "SUPPORTS": "🟢 Supports",
}


def merge(assessments: list[dict], evidence: dict) -> list[dict]:
    """Attach metadata status from evidence.json and normalise verdicts."""
    ev_by_key = {r.get("key"): r for r in evidence.get("references", [])}
    rows = []
    for a in assessments:
        key = str(a.get("ref_key"))
        ev = ev_by_key.get(key, {})
        verdict = (a.get("verdict") or "UNVERIFIED").upper()
        # Promote to metadata/fabrication severity when evidence says so and the
        # assessor didn't already flag something worse.
        mstatus = ev.get("metadata_status")
        if mstatus == "not_found" and VERDICT_RANK.get(verdict, 9) > 0:
            verdict = "NOT_FOUND"
        elif mstatus == "mismatch" and VERDICT_RANK.get(verdict, 9) > 2:
            verdict = "METADATA_MISMATCH"
        rows.append({
            "ref_key": key,
            "verdict": verdict,
            "claim": a.get("claim", ""),
            "evidence_quote": a.get("evidence_quote", ""),
            "confidence": a.get("confidence", ""),
            "rationale": a.get("rationale", ""),
            "suggested_fix": a.get("suggested_fix", ""),
            "cited": (ev.get("cited") or {}).get("raw", ""),
            "metadata_status": mstatus or "",
            "mismatches": "; ".join(ev.get("mismatches", []) or []),
            "source": ev.get("source") or "",
        })
    rows.sort(key=lambda r: (VERDICT_RANK.get(r["verdict"], 9), r["ref_key"]))
    return rows


def summarize(rows: list[dict]) -> str:
    n = len(rows)
    fab = sum(r["verdict"] in ("FABRICATED", "NOT_FOUND") for r in rows)
    con = sum(r["verdict"] == "CONTRADICTS" for r in rows)
    meta = sum(r["verdict"] == "METADATA_MISMATCH" for r in rows)
    part = sum(r["verdict"] in ("PARTIAL", "UNSUPPORTED", "OVERREACH", "WRONG_SOURCE") for r in rows)
    clean = sum(r["verdict"] == "SUPPORTS" for r in rows)
    bits = []
    if fab: bits.append(f"{fab} fabricated/not-found")
    if con: bits.append(f"{con} contradicting")
    if meta: bits.append(f"{meta} metadata error(s)")
    if part: bits.append(f"{part} partial/over-reach")
    bits.append(f"{clean}/{n} clean")
    return "; ".join(bits)


def to_md(rows: list[dict]) -> str:
    out = io.StringIO()
    out.write("# Reference Audit Report\n\n")
    out.write(f"**Bottom line:** {summarize(rows)}\n\n")
    out.write("| # | Verdict | Claim | Reference | Evidence | Fix |\n")
    out.write("|---|---|---|---|---|---|\n")
    for r in rows:
        ev = r["evidence_quote"] or r["mismatches"]
        out.write("| {k} | {v} | {c} | {ref} | {e} | {fix} |\n".format(
            k=r["ref_key"],
            v=VERDICT_LABEL.get(r["verdict"], r["verdict"]),
            c=_md_cell(r["claim"]),
            ref=_md_cell(r["cited"][:90]),
            e=_md_cell(ev[:160]),
            fix=_md_cell(r["suggested_fix"]),
        ))
    return out.getvalue()


def _md_cell(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ").strip()


def to_csv(rows: list[dict]) -> str:
    out = io.StringIO()
    cols = ["ref_key", "verdict", "confidence", "claim", "cited", "evidence_quote",
            "metadata_status", "mismatches", "rationale", "suggested_fix", "source"]
    w = csv.DictWriter(out, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    return out.getvalue()


def to_html(rows: list[dict]) -> str:
    th = "".join(f"<th>{h}</th>" for h in ["#", "Verdict", "Claim", "Reference", "Evidence", "Fix"])
    trs = []
    for r in rows:
        ev = r["evidence_quote"] or r["mismatches"]
        cells = [r["ref_key"], VERDICT_LABEL.get(r["verdict"], r["verdict"]),
                 r["claim"], r["cited"], ev, r["suggested_fix"]]
        trs.append("<tr>" + "".join(f"<td>{html.escape(str(c))}</td>" for c in cells) + "</tr>")
    return (
        "<!doctype html><meta charset='utf-8'><title>Reference Audit</title>"
        "<style>body{font:14px/1.5 system-ui,sans-serif;margin:2rem;}"
        "table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ccc;"
        "padding:6px 8px;vertical-align:top;text-align:left;}th{background:#f3f3f3;}"
        "</style>"
        f"<h1>Reference Audit Report</h1><p><b>Bottom line:</b> {html.escape(summarize(rows))}</p>"
        f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(trs)}</tbody></table>"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render the reference audit as a triage report.")
    ap.add_argument("assessments", help="assessments.json (verdicts from the assistant)")
    ap.add_argument("evidence", help="evidence.json from retrieve_evidence.py")
    ap.add_argument("--format", default="md", choices=["md", "csv", "json", "html", "all"])
    ap.add_argument("--out", default="audit_report", help="Output path (extension added per format)")
    args = ap.parse_args(argv)

    assessments = json.loads(Path(args.assessments).read_text(encoding="utf-8"))
    evidence = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    rows = merge(assessments, evidence)

    renderers = {"md": (to_md, ".md"), "csv": (to_csv, ".csv"),
                 "html": (to_html, ".html"),
                 "json": (lambda r: json.dumps(r, indent=2, ensure_ascii=False), ".json")}
    fmts = list(renderers) if args.format == "all" else [args.format]
    base = Path(args.out)
    for fmt in fmts:
        render, ext = renderers[fmt]
        content = render(rows)
        target = base if base.suffix else base.with_suffix(ext)
        if args.format == "all":
            target = base.with_suffix(ext)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        print(f"Wrote {fmt} report to {target}")
    print("Bottom line:", summarize(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
