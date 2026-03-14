"""The README's headline numbers are claim-checked like an experiment note (EXP_0034).

The crop-only comparison was wrong in the README for months while every experiment note passed
check_claims, because the checker only ever read experiments/*/NOTE.md. The README is the
most-read document in the repository; a stale number there costs the most.
"""
import json, os, subprocess, sys
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_readme_claims_file_exists_and_is_non_empty():
    p = os.path.join(ROOT, "docs", "claims", "readme.json")
    assert os.path.exists(p), "README claims file is missing"
    claims = json.load(open(p))
    assert len(claims) >= 5
    assert all(c.get("note") == "README.md" for c in claims)


def test_check_claims_reads_the_readme():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_claims.py")],
                       capture_output=True, text=True, cwd=ROOT)
    assert "docs:readme" in r.stdout, "check_claims is no longer covering the README"
    assert " 0 failed," in r.stdout, r.stdout[-800:]


def test_a_wrong_readme_number_actually_fails():
    """Negative control on the checker itself: without this, a regex that stopped matching would
    read as a pass and the coverage would be theatre."""
    from pathlib import Path
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import check_claims as cc
    claims = json.load(open(os.path.join(ROOT, "docs", "claims", "readme.json")))
    c = next(x for x in claims if "independent null IoU" in x["claim"])
    status, why, claimed, actual = cc.check_one(ROOT, c)
    assert status == "OK", f"baseline claim should pass: {why}"
    bad = dict(c, tol=0.0)
    bad["source"] = "reports/independent_null.json"
    bad["path"] = "summary.mean_iou_product"          # deliberately the wrong field
    status2, _, _, _ = cc.check_one(ROOT, bad)
    assert status2 == "FAIL", "checker did not notice a number pointing at the wrong artefact field"
