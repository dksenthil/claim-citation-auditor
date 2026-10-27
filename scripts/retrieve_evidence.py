#!/usr/bin/env python3
"""Validate reference metadata and retrieve source abstracts.

Deterministic evidence-gathering step of the claim-citation-auditor skill. For
each reference produced by parse_references.py it:
  1. resolves a record from Crossref (by DOI, else by title search) and/or
     NCBI PubMed (by PMID, else by title search);
  2. diffs the retrieved metadata against the cited metadata (title/year/authors);
  3. fetches an abstract for Claude to judge claim support against.

Uses only the Python standard library (urllib). No API key required; pass
--email for NCBI etiquette and optionally --api-key for higher NCBI limits.
The script self-throttles to stay within public rate limits.

Usage:
    python3 retrieve_evidence.py references.json --out evidence.json --email you@example.org

Output JSON: one record per reference with keys:
    key, cited (echo of input), resolved (crossref/pubmed metadata),
    metadata_status (ok|mismatch|not_found|no_identifier),
    mismatches (list), abstract, source ("crossref"|"pubmed"|null), notes
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

CROSSREF = "https://api.crossref.org/works"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
USER_AGENT = "claim-citation-auditor/0.1 (https://github.com/; mailto:{email})"


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _get(url: str, email: str, api_key: str | None = None, retries: int = 3) -> bytes:
    headers = {"User-Agent": USER_AGENT.format(email=email or "anonymous@example.org")}
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read()
        except Exception as e:  # noqa: BLE001 - surface after retries
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"request failed: {url}: {last_err}")


# ---------- Crossref ----------

def crossref_by_doi(doi: str, email: str) -> dict | None:
    url = f"{CROSSREF}/{urllib.parse.quote(doi)}"
    try:
        data = json.loads(_get(url, email))
    except Exception:
        return None
    return data.get("message")


# Derivative Crossref records that share a paper's title but are not the paper.
_DERIVATIVE_RE = re.compile(
    r"faculty opinions recommendation|^correction(s)? to|^corrigendum|^erratum|"
    r"author correction|^retraction|^comment on|^reply to", re.I)


def crossref_by_title(title: str, email: str, rows: int = 5, min_sim: float = 0.80) -> dict | None:
    """Return the best genuine title match from Crossref, or None.

    Fetches several candidates (rows>1) because the top hit is often a derivative
    record (Faculty Opinions recommendation, correction, erratum). Skips those and
    returns the highest-similarity real article above `min_sim`.
    """
    q = urllib.parse.urlencode({"query.bibliographic": title, "rows": rows})
    try:
        data = json.loads(_get(f"{CROSSREF}?{q}", email))
    except Exception:
        return None
    best, best_sim = None, 0.0
    for it in data.get("message", {}).get("items", []):
        t = (it.get("title") or [""])[0]
        if not t or _DERIVATIVE_RE.search(t):
            continue
        sim = _similar(title, t)
        if sim > best_sim:
            best, best_sim = it, sim
    return best if best_sim >= min_sim else None


def crossref_fields(msg: dict) -> dict:
    title = (msg.get("title") or [""])[0]
    year = None
    for k in ("published-print", "published-online", "issued", "created"):
        parts = (msg.get(k) or {}).get("date-parts")
        if parts and parts[0] and parts[0][0]:
            year = str(parts[0][0])
            break
    authors = []
    for a in msg.get("author", [])[:3]:
        fam = a.get("family", "")
        if fam:
            authors.append(fam)
    return {
        "title": title,
        "year": year,
        "authors": authors,
        "journal": (msg.get("container-title") or [""])[0],
        "doi": msg.get("DOI"),
        "type": msg.get("type"),
        "abstract": _clean_jats(msg.get("abstract", "")),
    }


def _clean_jats(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


# ---------- PubMed ----------

def pubmed_esummary(pmid: str, email: str, api_key: str | None) -> dict | None:
    extra = f"&api_key={api_key}" if api_key else ""
    url = f"{EUTILS}/esummary.fcgi?db=pubmed&id={pmid}&retmode=json{extra}"
    try:
        data = json.loads(_get(url, email, api_key))
    except Exception:
        return None
    return data.get("result", {}).get(pmid)


def pubmed_search_title(title: str, email: str, api_key: str | None) -> str | None:
    extra = f"&api_key={api_key}" if api_key else ""
    # Try a Title-field search first (precise), then fall back to free text.
    for term in (f"{title}[Title]", title):
        q = urllib.parse.quote(term)
        url = f"{EUTILS}/esearch.fcgi?db=pubmed&term={q}&retmode=json&retmax=1{extra}"
        try:
            data = json.loads(_get(url, email, api_key))
        except Exception:
            continue
        ids = data.get("esearchresult", {}).get("idlist", [])
        if ids:
            return ids[0]
    return None


def pubmed_abstract(pmid: str, email: str, api_key: str | None) -> str:
    extra = f"&api_key={api_key}" if api_key else ""
    url = f"{EUTILS}/efetch.fcgi?db=pubmed&id={pmid}&rettype=abstract&retmode=text{extra}"
    try:
        return _get(url, email, api_key).decode("utf-8", "replace").strip()
    except Exception:
        return ""


def pubmed_fields(summary: dict, pmid: str, email: str, api_key: str | None) -> dict:
    authors = [a.get("name", "").split()[0] for a in summary.get("authors", [])[:3] if a.get("name")]
    year = (summary.get("pubdate", "") or "")[:4]
    return {
        "title": summary.get("title", "").rstrip("."),
        "year": year if year.isdigit() else None,
        "authors": authors,
        "journal": summary.get("fulljournalname") or summary.get("source", ""),
        "pmid": pmid,
        "doi": next((x.get("value") for x in summary.get("articleids", []) if x.get("idtype") == "doi"), None),
        "abstract": pubmed_abstract(pmid, email, api_key),
    }


# ---------- metadata diff ----------

def diff_metadata(cited: dict, resolved: dict) -> list[str]:
    mismatches = []
    ct, rt = cited.get("title"), resolved.get("title")
    if ct and rt and _similar(ct, rt) < 0.75:
        mismatches.append(f"title: cited “{ct[:60]}…” vs found “{rt[:60]}…”")
    cy, ry = cited.get("year"), resolved.get("year")
    if cy and ry and cy != ry:
        mismatches.append(f"year: cited {cy} vs found {ry}")
    # Author surname check: does the cited authors string contain the resolved 1st-author surname?
    ra = resolved.get("authors") or []
    if ra and cited.get("authors"):
        first = ra[0].lower()
        if first and first not in cited["authors"].lower():
            mismatches.append(f"first author: found {ra[0]} not in cited author string")
    return mismatches


def resolve_one(ref: dict, email: str, api_key: str | None, throttle: float) -> dict:
    out = {"key": ref.get("key"), "cited": ref, "resolved": None,
           "metadata_status": "no_identifier", "mismatches": [], "abstract": "",
           "source": None, "notes": ""}
    resolved = None
    source = None

    if ref.get("doi"):
        msg = crossref_by_doi(ref["doi"], email)
        time.sleep(throttle)
        if msg:
            resolved, source = crossref_fields(msg), "crossref"
    if resolved is None and ref.get("pmid"):
        summ = pubmed_esummary(ref["pmid"], email, api_key)
        time.sleep(throttle)
        if summ and not summ.get("error"):
            resolved, source = pubmed_fields(summ, ref["pmid"], email, api_key), "pubmed"
    if resolved is None and ref.get("title"):
        # No usable identifier — resolve by title. crossref_by_title already picks
        # the best non-derivative match above threshold, so trust its result.
        msg = crossref_by_title(ref["title"], email)
        time.sleep(throttle)
        if msg:
            resolved, source = crossref_fields(msg), "crossref(title)"
        else:
            pmid = pubmed_search_title(ref["title"], email, api_key)
            time.sleep(throttle)
            if pmid:
                summ = pubmed_esummary(pmid, email, api_key)
                time.sleep(throttle)
                if summ and _similar(ref["title"], summ.get("title", "")) >= 0.8:
                    resolved, source = pubmed_fields(summ, pmid, email, api_key), "pubmed(title)"

    if resolved is None:
        # Could not resolve at all. If there was no identifier and no title match,
        # this is a candidate fabrication / badly garbled citation.
        out["metadata_status"] = "not_found"
        had_title = bool(ref.get("title"))
        if had_title:
            out["notes"] = ("Title did not confidently match any Crossref/PubMed record "
                            "(no DOI/PMID to anchor on). Could be a non-indexed venue, a "
                            "garbled/paraphrased title, or a genuine fabrication — VERIFY "
                            "MANUALLY before concluding fabrication.")
        else:
            out["notes"] = ("No DOI/PMID and no usable title extracted, so nothing to "
                            "resolve. Verify the citation manually.")
        return out

    abstract = resolved.get("abstract", "") or ""
    # Abstract fallback: Crossref often lacks abstracts (esp. older papers). If we
    # resolved metadata but got no abstract, try PubMed by DOI/title to fetch one,
    # without overriding the already-validated metadata.
    if not abstract:
        pmid = ref.get("pmid")
        if not pmid:
            lookup_title = resolved.get("title") or ref.get("title")
            if lookup_title:
                pmid = pubmed_search_title(lookup_title, email, api_key)
                time.sleep(throttle)
        if pmid:
            abstract = pubmed_abstract(pmid, email, api_key)
            time.sleep(throttle)
            if abstract and source and "pubmed" not in source:
                source = f"{source}+pubmed(abstract)"

    out["resolved"] = {k: v for k, v in resolved.items() if k != "abstract"}
    out["abstract"] = abstract
    out["source"] = source
    mismatches = diff_metadata(ref, resolved)
    out["mismatches"] = mismatches
    out["metadata_status"] = "mismatch" if mismatches else "ok"
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate reference metadata and fetch abstracts.")
    ap.add_argument("references", help="references.json from parse_references.py")
    ap.add_argument("--out", default="-", help="Output JSON path (default: stdout)")
    ap.add_argument("--email", default="", help="Contact email (NCBI etiquette; recommended)")
    ap.add_argument("--api-key", default=None, help="NCBI API key (optional; higher rate limit)")
    ap.add_argument("--throttle", type=float, default=0.4, help="Seconds between API calls")
    ap.add_argument("--limit", type=int, default=0, help="Only process first N refs (debug)")
    args = ap.parse_args(argv)

    refs = json.loads(Path(args.references).read_text(encoding="utf-8"))
    if args.limit:
        refs = refs[: args.limit]
    results = []
    for i, ref in enumerate(refs, 1):
        print(f"[{i}/{len(refs)}] ref {ref.get('key')}…", file=sys.stderr)
        try:
            results.append(resolve_one(ref, args.email, args.api_key, args.throttle))
        except Exception as e:  # noqa: BLE001
            results.append({"key": ref.get("key"), "cited": ref, "resolved": None,
                            "metadata_status": "error", "notes": str(e), "abstract": ""})

    summary = {
        "n": len(results),
        "ok": sum(r["metadata_status"] == "ok" for r in results),
        "mismatch": sum(r["metadata_status"] == "mismatch" for r in results),
        "not_found": sum(r["metadata_status"] == "not_found" for r in results),
    }
    payload = {"summary": summary, "references": results}
    out = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out == "-":
        print(out)
    else:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"Wrote evidence for {len(results)} refs to {args.out} "
              f"(ok={summary['ok']}, mismatch={summary['mismatch']}, not_found={summary['not_found']})",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
