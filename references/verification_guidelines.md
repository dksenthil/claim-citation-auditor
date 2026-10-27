# Verification guidelines — the hard cases

The rubric (`evidence_rubric.md`) covers the verdict scale. This file is for the
judgement calls that trip up reference audits. Read it before assessing a
manuscript whose claims lean on reviews, preprints, or cross-system evidence.

## Reviews vs primary sources

A review can support a *framing* or *overview* claim ("X is an active area with
several competing approaches"). It should **not** be the sole support for a
specific empirical result ("X increased titre 10-fold in mice"). When a specific
result is cited only to a review, mark `WRONG_SOURCE` and recommend the primary
paper. Conversely, don't penalise a review cited for what reviews are for.

## Multi-reference bundles

`[20, 47-49]` is four independent claims of support. Judge each. The failure mode
to catch: three references genuinely support the point and a fourth was swept in
because it is topically adjacent but reports something else. Split the bundle in
your suggested fix and name which reference anchors which half of the claim.

## Cross-system / cross-species over-generalization

Evidence in *E. coli*, yeast, a reporter library, or a cell line does not
automatically support a claim about therapeutic mRNA in vivo or in humans.
This is not necessarily wrong — foundational mechanism papers are often bacterial
— but the manuscript should signal the scope. Downgrade to `PARTIAL` and note the
system gap; suggest the authors either add the caveat or cite an in-context study.

## "Not in the abstract" ≠ "not in the paper"

Abstracts omit most results. If a claim is specific (a number, a subgroup, a
secondary finding) and plausibly lives in the full text, say the verdict needs
full-text confirmation rather than declaring `UNSUPPORTED`. Reserve `UNSUPPORTED`
for cases where the source's scope makes the claim implausible, or where you read
the full text and it is absent. State which you did.

## Preprints and "in press"

A preprint can support a claim but is weaker evidence; flag when a major claim
rests solely on a non–peer-reviewed source, and recommend citing the published
version once available. Verify the preprint exists (DOI on bioRxiv/arXiv) — a
preprint citation is still falsifiable.

## Metadata mismatches worth escalating

`retrieve_evidence.py` flags title/year/author diffs. Treat these as:
- **Title mismatch** (low similarity): often a wrong-paper citation or a mangled
  title — check whether the DOI points somewhere else entirely.
- **Year off by 1**: usually online-vs-issue year; low severity, note but don't alarm.
- **First author absent from the cited author string**: possible wrong reference or
  an "et al." that dropped the lead author — verify.
- **`not_found`**: no identifier and no title match anywhere. This is the fabrication
  signal. Before declaring fabrication, try a manual search (the title may be
  garbled); if still nothing, recommend the authors supply a DOI or remove it.

## Grey literature is not fabrication (check the issuer's own site)

Crossref and PubMed index journal articles, not most **regulatory guidance,
standards, white papers, agency reports, or consortium documents**. A `not_found`
on one of these means the *auto-resolver* couldn't confirm it — **not** that it is
fabricated. Before ever writing "fabricated," do a direct check: search the
issuing body's own website (fda.gov, ema.europa.eu, who.int, ich.org, iso.org,
nist.gov, etc.) or the exact title in a general web search. Regulatory documents
are frequently **joint** (e.g. an EMA–FDA guidance), so a corporate-author string
that looks "merged" is usually a reference-manager parsing artifact of two real
co-issuers, not a sign of confabulation.

Real example this rule comes from: a manuscript cited *"Guiding principles of good
AI practice in drug development," 2026* with a garbled author
(`U. F. European Medicines Agency and D. Administration.`). The auditor marked it
`not_found` and an over-eager verdict called it fabricated — but it is a genuine
joint **EMA–FDA** document (January 2026) hosted on ema.europa.eu. The only real
defect was the mangled corporate author. Treat such cases as a **metadata /
formatting fix** (clean the author, add the URL), not a fabrication, and never
recommend "split into two documents" for what is a single joint publication
without first confirming that two separate documents actually exist.

Reserve a `FABRICATED` verdict for the case where the title matches **nothing** on
the issuer's site or the open web after a genuine manual check.

## Suggesting replacement citations

When you propose a replacement, you are making a claim too — hold yourself to the
same standard. Give the full citation with a DOI/PMID and verify it resolves
(`retrieve_evidence.py` on a one-line references file works). If you cannot confirm
a specific replacement the reviewer named (e.g. "Lee et al. 2025" with no DOI),
say so plainly and list the closest verifiable candidates rather than inserting a
guess.

## Scope discipline

Audit what is cited, not what you wish were cited. It is fine to note "this claim
would be stronger with a primary source," but the verdict is about whether the
*current* citation supports the *current* claim. Keep opinions about the
manuscript's argument out of the support verdict; put them in `rationale` if useful.
