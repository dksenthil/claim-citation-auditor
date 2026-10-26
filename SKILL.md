---
name: claim-citation-auditor
description: Audit scientific manuscripts by mapping each claim to the citation(s) that support it, validating reference metadata (DOI/PMID/title/authors/year), retrieving the cited sources, and judging whether each source actually supports the claim. Use this whenever a user wants to check references in a paper, verify that citations say what the manuscript claims they say, find fabricated/garbled/mismatched citations, prepare for a reviewer's "check every reference" request, or audit a .docx/.md/.tex/.pdf manuscript before submission. Trigger on phrases like "audit the references", "check the citations", "do these references support the claims", "verify the bibliography", "reference check", "are any citations fabricated", or when a reviewer asks for a line-by-line citation check.
license: MIT
version: 0.1.0
metadata:
  author: HeDS Platform, McGill University
  spec: https://agentskills.io
  homepage: https://github.com/your-org/claim-citation-auditor
---

# Claim–Citation Auditor

## What this skill does

Reviewers increasingly ask authors to confirm that **every reference actually supports the statement it is attached to** — not just that the DOI resolves. This skill runs that audit end to end:

1. **Extract** each in-text citation and the exact claim it supports (claim↔citation map).
2. **Parse** the bibliography into structured references and pull DOIs/PMIDs.
3. **Validate** each reference's metadata against the real record (Crossref + NCBI E-utilities).
4. **Retrieve** the source (title/abstract, and full text when available) for the claim it backs.
5. **Judge** support on a graded scale — `SUPPORTS` / `PARTIAL` / `UNSUPPORTED` / `CONTRADICTS` — with the exact evidence passage and location.
6. **Export** a triage report (Markdown/CSV/JSON/HTML) ranked by severity.

## Division of labor (important)

**Python handles the deterministic work; you (the assistant) handle the judgement.** Keep this split — it is what makes the audit reproducible and the verdicts trustworthy.

- **Python (`scripts/`):** parsing manuscripts, extracting citation markers, splitting the bibliography, regex-matching DOIs/PMIDs, calling Crossref/NCBI, and diffing retrieved metadata against the cited metadata. Deterministic, testable, no model judgement.
- **You (Claude):** turning each cited sentence into one or more *atomic claims*, and deciding whether the retrieved abstract/full text actually substantiates each claim. This is interpretation and must be done with explicit uncertainty and a quoted supporting passage. Never outsource the support verdict to a string match.

## Workflow

Work through these steps. Run scripts with `python3 scripts/<name>.py --help` to see options.

### 1. Map claims to citations
```bash
python3 scripts/extract_claims.py <manuscript> --out work/claims.json
```
Supports `.docx`, `.md`, `.tex`, `.pdf`. Produces, per citing passage: the sentence(s), the citation keys/numbers, and a location anchor.

**DOCX caveat:** manuscripts using EndNote/Mendeley/Zotero field codes store author names inside base64 `fldData`, so a raw read misses them and the in-text numbers may not render. If `extract_claims.py` reports suspiciously few citations from a `.docx`, convert first with `pandoc in.docx -t markdown -o work/manuscript.md` (which resolves the fields to display text) and run the extractor on the Markdown. The script warns when it detects unresolved field codes.

Then **you** refine each sentence into atomic claims — a sentence like "X increases Y and is cheaper to make [12]" carries two claims. Record them in the claims file (keep the location anchor).

### 2. Parse the bibliography
```bash
python3 scripts/parse_references.py <manuscript> --out work/references.json
```
Produces one record per reference: raw string, parsed authors/title/journal/year/volume/pages, and extracted `doi`/`pmid` where present. For numbered styles the record key is the number; for author–year it is the citation key.

### 3. Validate metadata + retrieve sources
```bash
python3 scripts/retrieve_evidence.py work/references.json --out work/evidence.json --email you@example.org
```
For each reference this validates the cited metadata against the real record and fetches an abstract:
- **DOI → Crossref** (`api.crossref.org`); **PMID → NCBI E-utilities** (`esummary` + `efetch`); if only a title is present it searches Crossref/PubMed to resolve one.
- It flags `metadata_ok` / `metadata_mismatch` (title, year, author, journal diffs) and marks `not_found` references (candidate fabrications — like a confabulated guidance-document citation).
- Pass `--email` (NCBI etiquette) and optionally `--api-key` for higher NCBI rate limits. The script self-throttles; no key is required.

### 4. Assess support (your judgement)
For every (claim, reference) pair, read the retrieved abstract/full text in `work/evidence.json` and assign a verdict using `references/evidence_rubric.md`. Record, per pair: the verdict, a **quoted supporting (or contradicting) passage**, your confidence, and a one-line rationale. Where a claim bundles several references, judge each reference *individually* — the most common real defect is a multi-reference bundle in which one reference is about something else (e.g., a structure/half-life paper cited for a codon-usage claim). Follow `references/verification_guidelines.md` for the harder cases (reviews vs primary sources, preprints, cross-species or cross-system over-generalization, "not reported in the abstract" vs genuinely absent).

Write the assessments to `work/assessments.json` in the schema shown in `references/evidence_rubric.md`.

### 5. Export the report
```bash
python3 scripts/export_report.py work/assessments.json work/evidence.json --format md --out audit_report.md
# --format also accepts csv, json, html; pass --format all to emit every format
```
The report is ranked most-severe first: fabricated/not-found refs and `CONTRADICTS`, then metadata errors, then `PARTIAL`/over-reach, then clean. Each row carries the claim, the reference, the verdict, the evidence passage, and the suggested fix.

## Output format

Always present findings as a triage table ordered by severity, and lead with a one-line bottom line (e.g. "1 fabricated citation, 1 claim/citation mismatch, 3 metadata errors; 54/62 clean"). Group as: **(A) fabricated / not-found**, **(B) claim↔citation mismatch or contradiction**, **(C) metadata errors**, **(D) partial / over-reach / wrong source type**, **(E) clean**. For every non-clean item give the specific fix (correct metadata, split a bundled citation, re-anchor to the right paper, add a primary source, or flag for author follow-up).

## Guardrails

- **Never invent evidence.** If you cannot retrieve a source, say so and mark the pair `unverified` — do not infer support from the title alone.
- **Quote, don't paraphrase, the supporting passage.** The value of the audit is traceability; a verdict without a locatable quote is not auditable.
- **Do not silently "fix" citations.** Propose replacements; the author (and their reference manager) applies them. When you suggest a replacement reference, verify it exists the same way (DOI/PMID), and say when you could not confirm it.
- **Distinguish "absent from the abstract" from "the paper doesn't support this."** Abstracts are lossy; if a claim is plausibly in the full text, say the check needs full text rather than declaring a mismatch.

## Files

- `scripts/extract_claims.py` — manuscript → claim↔citation map (DOCX/MD/LaTeX/PDF).
- `scripts/parse_references.py` — bibliography → structured references + DOI/PMID.
- `scripts/retrieve_evidence.py` — metadata validation + abstract retrieval (Crossref + NCBI).
- `scripts/export_report.py` — assessments → Markdown/CSV/JSON/HTML triage report.
- `references/evidence_rubric.md` — the support scale, assessment schema, worked examples.
- `references/verification_guidelines.md` — how to handle the hard cases.
- `examples/sample_manuscript.md` — a tiny manuscript to try the workflow on.
- `benchmark/` — a labelled manuscript (valid / overstated / contradicted / unsupported / fabricated claims) with gold verdicts for regression testing.
