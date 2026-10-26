"""Offline unit tests for the deterministic parsing scripts.

Run: pytest -q   (or: python -m pytest tests/ -q)
These tests require no network.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import extract_claims as ec  # noqa: E402
import parse_references as pr  # noqa: E402

BENCH = ROOT / "benchmark" / "benchmark_manuscript.md"


def test_expand_numeric_ranges():
    assert ec.expand_numeric("12-14") == ["12", "13", "14"]
    assert ec.expand_numeric("20, 47-49") == ["20", "47", "48", "49"]
    assert ec.expand_numeric("5") == ["5"]


def test_extract_claims_finds_all_citations():
    text = BENCH.read_text(encoding="utf-8")
    body = ec.strip_references_section(text)
    passages, n = ec.extract(body, "numeric")
    # Seven numbered in-text citations [1]..[7] in the body.
    found = sorted({c for p in passages for c in p["citations"]}, key=int)
    assert found == ["1", "2", "3", "4", "5", "6", "7"], found
    assert n == 7


def test_strip_references_excludes_bibliography():
    text = BENCH.read_text(encoding="utf-8")
    body = ec.strip_references_section(text)
    # The DOI strings live only in the reference list, which must be stripped.
    assert "10.1126/science.1170160" not in body


def test_parse_references_extracts_doi_and_year():
    recs = [pr.parse_entry(k, r) for k, r in
            pr.split_entries(pr.find_references_section(BENCH.read_text(encoding="utf-8")))]
    by_key = {r["key"]: r for r in recs}
    assert len(recs) == 7, [r["key"] for r in recs]
    assert by_key["1"]["doi"] == "10.1016/j.immuni.2005.06.008"
    assert by_key["2"]["year"] == "2009"
    # The fabricated entry [6] has no DOI.
    assert "doi" not in by_key["6"]
    # Walsh entry [7] cited as 2020 in the bibliography.
    assert by_key["7"]["year"] == "2020"


def test_parse_references_titles():
    recs = [pr.parse_entry(k, r) for k, r in
            pr.split_entries(pr.find_references_section(BENCH.read_text(encoding="utf-8")))]
    by_key = {r["key"]: r for r in recs}
    assert "Coding-sequence determinants" in by_key["2"].get("title", "")


if __name__ == "__main__":
    # Allow running without pytest.
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    sys.exit(1 if failed else 0)
