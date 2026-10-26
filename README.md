# claim-citation-auditor

An [Agent Skill](https://agentskills.io) that audits scientific manuscripts the way a
careful reviewer does: it maps every **claim** to the **citation(s)** that support it,
validates each reference's metadata against the real record, retrieves the cited
sources, and judges whether each source *actually supports the claim it is attached to* —
catching fabricated citations, metadata errors, and claim↔citation mismatches.

It was distilled from a real manuscript audit in which a hand review found a fabricated
regulatory citation, a structure/half-life paper mis-cited for a codon-usage claim, and
several over-reaching review citations. This skill packages that workflow so it is
repeatable and reviewable.

## Why it is more than a prompt

The architecture deliberately splits the work:

- **Python does the deterministic part** — parsing manuscripts, extracting citation
  markers, splitting the bibliography, pulling DOIs/PMIDs, calling Crossref and NCBI
  E-utilities, and diffing retrieved metadata against what the manuscript cited.
- **The agent (Claude or any compatible assistant) does the judgement** — turning
  sentences into atomic claims and deciding, with a quoted passage and explicit
  uncertainty, whether the retrieved source supports each claim.

That separation is what makes the verdicts traceable and the metadata checks
reproducible, and it is why a shipped skill beats a one-off prompt.

## Install

### Claude Code
Copy or symlink this directory into your skills folder:
```bash
git clone https://github.com/your-org/claim-citation-auditor
ln -s "$PWD/claim-citation-auditor" ~/.claude/skills/claim-citation-auditor
```
It will trigger on requests like "audit the references in this paper" or "do these
citations actually support the claims?"

### Claude.ai
Zip the folder **with the `claim-citation-auditor/` directory as the archive root** and
upload via Customize → Skills:
```bash
cd .. && zip -r claim-citation-auditor.zip claim-citation-auditor \
  -x '*/__pycache__/*' '*/.git/*' '*/work/*'
```

### Other Agent-Skills-compatible agents
The skill conforms to the open [Agent Skills specification](https://agentskills.io):
a `SKILL.md` with YAML frontmatter (`name`, `description`, `license`, `version`,
`metadata`) as the entry point, progressive-disclosure `references/`, and executable
`scripts/`. Point your agent's skill loader at this directory. The scripts are plain
Python 3.10+ CLIs with no required third-party dependencies, so they run anywhere.

## Using it in a Claude Code session

Once the skill is installed (symlinked into `~/.claude/skills/` as above), you don't run
any scripts yourself — just describe the task and Claude invokes the skill, runs the
scripts, makes the support judgements, and hands you the report. Start a session **in the
folder with your manuscript** (or give Claude the absolute path).

**Typical prompts that trigger it:**
```
> Audit the references in manuscript.docx — do the citations actually support the claims?
> A reviewer wants us to check every reference against the source. Run that on paper.tex.
> Are any citations in this draft fabricated or mismatched? Check ./review_v3.docx
> Verify the bibliography in examples/sample_manuscript.md and give me a triage report.
```

**What Claude does once triggered:**
1. Runs `extract_claims.py` and `parse_references.py` on your file, then refines each
   cited sentence into atomic claims.
2. Runs `retrieve_evidence.py` to validate metadata (Crossref/NCBI) and pull abstracts.
   It will ask for (or use a placeholder) contact email for NCBI etiquette.
3. Reads each abstract/source and assigns a graded verdict
   (`SUPPORTS` / `PARTIAL` / `UNSUPPORTED` / `CONTRADICTS` / `WRONG_SOURCE` / …) with a
   quoted supporting passage, following `references/evidence_rubric.md`.
4. Runs `export_report.py` and gives you a severity-ranked triage table plus a one-line
   bottom line (e.g. *"1 fabricated citation, 1 claim/citation mismatch, 3 metadata
   errors; 54/62 clean"*).

**Tips for a good run in-session:**
- **`.docx` with EndNote/Mendeley/Zotero citations:** tell Claude to convert with pandoc
  first (`pandoc paper.docx -t markdown -o paper.md`) — reference-manager field codes
  otherwise hide author names and in-text numbers. The skill warns when it detects this.
- **Scope it** if you only care about part of the paper ("just audit the Methods
  citations") — Claude can filter the claim map.
- **Network:** metadata validation needs outbound access to `api.crossref.org` and
  `eutils.ncbi.nlm.nih.gov`. If a reference can't be resolved, Claude marks it
  `unverified` rather than guessing.
- **Verify before you trust:** every non-clean verdict carries a quoted passage and a
  suggested fix. Claude will not edit your manuscript or "fix" citations unless you ask —
  it proposes; you (and your reference manager) apply.

To confirm the skill is installed and visible, type `/` in the session and look for
`claim-citation-auditor`, or just ask *"do you have a reference-audit skill available?"*

## Manual / CLI quick start

You can also drive the scripts directly without the skill:

```bash
# 0. (optional) create a working dir
mkdir -p work

# 1. map claims to citations
python3 scripts/extract_claims.py examples/sample_manuscript.md --out work/claims.json

# 2. parse the bibliography
python3 scripts/parse_references.py examples/sample_manuscript.md --out work/references.json

# 3. validate metadata + fetch abstracts (needs network)
python3 scripts/retrieve_evidence.py work/references.json --out work/evidence.json --email you@example.org

# 4. the agent assesses support -> work/assessments.json  (see references/evidence_rubric.md)

# 5. render the report
python3 scripts/export_report.py work/assessments.json work/evidence.json --format all --out work/audit_report
```

For a `.docx` with EndNote/Mendeley/Zotero field codes, convert first so citations
resolve: `pandoc paper.docx -t markdown -o paper.md` and run on `paper.md`.

## Repository layout

```
claim-citation-auditor/
├── SKILL.md                      # entry point + workflow (Agent Skills spec)
├── scripts/
│   ├── manuscript_io.py          # manuscript reading (docx/md/tex/pdf), stdlib-only core
│   ├── extract_claims.py         # in-text citations -> claim↔citation map
│   ├── parse_references.py       # bibliography -> structured references + DOI/PMID
│   ├── retrieve_evidence.py      # Crossref + NCBI metadata validation + abstracts
│   └── export_report.py          # assessments -> md/csv/json/html triage report
├── references/
│   ├── evidence_rubric.md        # support scale, assessment schema, examples
│   └── verification_guidelines.md# the hard cases (reviews, preprints, scope, bundles)
├── examples/sample_manuscript.md
├── benchmark/                    # labelled fixture + gold verdicts (regression)
├── tests/                        # offline unit tests + network-gated integration test
├── pyproject.toml · LICENSE · README.md
```

## Benchmark

`benchmark/benchmark_manuscript.md` contains seven claims engineered to exercise each
verdict class — well-supported, contradicted, over-reaching, a metadata (wrong-year)
error, and a fabricated reference — with gold labels in `benchmark_gold.json`. Use it to
check that changes to the scripts or rubric don't regress detection. The references are
real (so retrieval resolves them) except the deliberately fabricated entry.

## Tests

```bash
pip install -e ".[test]"
pytest -q                               # offline unit tests
RUN_NETWORK_TESTS=1 pytest -q           # also runs Crossref/NCBI integration tests
```

## Limitations

- Abstracts are lossy; a `needs full text` verdict is honest, not a failure.
- Metadata retrieval depends on Crossref/NCBI coverage; some books, standards, and
  grey-literature items won't resolve and must be checked by hand.
- The agent's support verdicts are judgement calls — always keep the quoted passage so a
  human can check them. This tool assists review; it does not replace it.

## License

MIT — see [LICENSE](LICENSE).
