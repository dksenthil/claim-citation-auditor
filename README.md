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

## Quick start

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
│   ├── _io.py                    # manuscript reading (docx/md/tex/pdf), stdlib-only core
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
