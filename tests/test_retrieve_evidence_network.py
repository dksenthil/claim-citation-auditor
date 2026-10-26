"""Network-gated integration test for retrieve_evidence.py.

Skipped unless RUN_NETWORK_TESTS=1 is set, so the default test run stays offline
and fast. When enabled, it checks that a real DOI resolves via Crossref and that
a fabricated reference is reported as not_found.

Run: RUN_NETWORK_TESTS=1 pytest -q tests/test_retrieve_evidence_network.py
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import retrieve_evidence as re_mod  # noqa: E402

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="set RUN_NETWORK_TESTS=1 to run network integration tests",
)

EMAIL = os.environ.get("AUDITOR_EMAIL", "ci@example.org")


def test_real_doi_resolves_crossref():
    ref = {"key": "1", "doi": "10.1126/science.1170160",
           "title": "Coding-sequence determinants of gene expression in Escherichia coli",
           "year": "2009", "authors": "G. Kudla"}
    out = re_mod.resolve_one(ref, EMAIL, None, throttle=0.4)
    assert out["metadata_status"] in ("ok", "mismatch")
    assert out["resolved"] and "gene expression" in (out["resolved"]["title"] or "").lower()


def test_fabricated_reference_not_found():
    ref = {"key": "6",
           "title": "Guiding principles of a single unified binding global law of good AI practice in drug manufacturing",
           "year": "2026",
           "authors": "U. F. European Medicines Agency and D. Administration"}
    out = re_mod.resolve_one(ref, EMAIL, None, throttle=0.4)
    assert out["metadata_status"] == "not_found", out
