# Evidence rubric — grading claim↔citation support

Use this scale when judging whether a cited source actually supports the claim it
is attached to. Assign exactly one verdict per **(claim, reference)** pair — never
per sentence, because one sentence often bundles several references and several
claims. Record a quoted passage for every non-trivial verdict.

## The scale

| Verdict | Meaning | When to use |
|---|---|---|
| `SUPPORTS` | The source directly substantiates the specific claim. | The abstract or full text states the claimed result for the claimed system. |
| `PARTIAL` | The source supports part of the claim, or supports it with caveats/in a different system. | Claim says "across systems" but the paper shows it in one; claim bundles two assertions and the source backs one. |
| `UNSUPPORTED` | The source is on-topic but does not actually state the claim. | Plausible-sounding pairing, but the specific result is not in the source (may be in a different paper). |
| `CONTRADICTS` | The source reports the opposite, or undercuts the claim. | Claim says a metric predicts an outcome; the cited paper reports no/negative association. |
| `WRONG_SOURCE` | Right topic, wrong source *type* for the claim's burden. | A review cited where a primary result is needed; a method paper cited for a broad field claim. |
| `OVERREACH` | Source supports a narrow point but is stretched to a sweeping one. | A single narrow study cited for a multi-factor general statement. |
| `UNVERIFIED` | Could not retrieve enough to judge. | Paywalled with no abstract; retrieval failed. Say so — do not guess from the title. |

Metadata problems (`METADATA_MISMATCH`, `NOT_FOUND`/fabricated) come from
`retrieve_evidence.py` and are merged automatically by `export_report.py`; you do
not assign those by hand, but do mention them in your rationale when relevant.

## Decision procedure

1. **Reduce the sentence to atomic claims.** "X raises expression and is cheaper to
   manufacture [12]" → claim A (expression) and claim B (manufacturability), both on [12].
2. **For each reference in the citation group, judge it individually.** The single
   most common real defect is a multi-reference bundle where one reference is about
   a different thing. Do not let a strong neighbour cover a weak one.
3. **Find the supporting sentence in the source.** Quote it. If the only evidence is
   the title, that is not support — mark `UNSUPPORTED` or `UNVERIFIED`.
4. **Check the system/scope match.** A result in *E. coli*, in a reporter library, or
   in a review's secondary summary may not substantiate a claim about therapeutic
   mRNA in vivo. Downgrade to `PARTIAL` and note the gap.
5. **Separate "absent from the abstract" from "absent from the paper."** Abstracts are
   lossy. If the claim is plausibly in the full text, say the check needs full text
   rather than declaring `UNSUPPORTED`.
6. **Confidence.** `high` = you quoted a decisive passage; `medium` = inference from an
   abstract; `low` = title/metadata only (then usually `UNVERIFIED`).

## Assessment record schema

Write `work/assessments.json` as a list of objects — one per (claim, reference) pair:

```json
[
  {
    "ref_key": "48",
    "claim": "CAI correlates weakly or not at all with measured protein expression",
    "verdict": "CONTRADICTS",
    "evidence_quote": "We found that mRNA secondary structure, not codon usage, was the primary determinant of functional half-life …",
    "confidence": "high",
    "rationale": "Paper is about structure/half-life and deliberately separates structure from codon usage; it does not report a weak CAI–expression correlation.",
    "suggested_fix": "Remove [48] from this bundle; re-cite for structure/half-life. Anchor the no-correlation claim on Kudla and the yield-reduction claim on Ranaghan."
  }
]
```

`export_report.py` ranks the report by verdict severity and merges the metadata
status, so a clean verdict here can still surface as a metadata error if the
reference failed validation.

## Worked examples

**SUPPORTS.** Claim: "nucleoside modification reduces innate immune activation [8]."
Source abstract: "Incorporation of modified nucleosides suppressed activation of
RNA sensors and increased translation." → `SUPPORTS`, high confidence, quote the sentence.

**CONTRADICTS.** Claim: "CAI correlates with expression [47]." Kudla 2009 abstract:
"codon bias did not correlate with gene expression." → `CONTRADICTS` for that phrasing;
the paper is the canonical *no-correlation* result.

**PARTIAL (scope).** Claim: "optimization models generalize across cell types [16]."
Source shows strong cross-cell-type correlation *but* a cargo-specific best performer.
→ `PARTIAL`: supports correlation, not unqualified generalization.

**WRONG_SOURCE.** Claim needs the primary prefusion-stabilization result but cites only
a review. → `WRONG_SOURCE`: suggest adding the primary paper (verify its DOI/PMID).

**NOT_FOUND / fabricated.** A guidance document whose title matches no real record and
whose "authors" are two agencies mashed together. → surfaced by retrieval as
`not_found`; recommend splitting into the real documents.
