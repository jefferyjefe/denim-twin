"""The fringe render is not benchable on the found-pair set (EXP_0036)."""
import json, os
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _r(name):
    p = os.path.join(ROOT, "reports", name)
    # A committed report is not an optional artefact. Skipping here turns the guard into a
    # no-op exactly when the thing it guards has gone missing -- review 7's finding about
    # tests that pass by not running. Every report named below is tracked in git.
    assert os.path.exists(p), f"{name} is missing; it is tracked in git -- restore it or run tools/make_reports.py --write --all"
    return json.load(open(p))


def test_only_one_pair_can_show_a_fringe():
    """A fringe needs a raw edge AND an after-wash capture. If a contributed pair ever changes
    this, EXP_0036's conclusion should be revisited -- that is the point of the test."""
    s = _r("fringe_capable_pairs.json")["summary"]
    assert s["n_can_show_a_fringe"] == 1, (
        f"the fringe-capable pair count changed to {s['n_can_show_a_fringe']}; re-run EXP_0036")


def test_wash_moves_only_the_fringe_capable_pair():
    rows = _r("wash_effect_paired.json")["rows"]
    moved = [r for r in rows if r["diff_baseline"] != 0.0]
    assert len(moved) == 1, f"expected exactly one pair to respond to wash, got {[r['pair'] for r in moved]}"
    assert moved[0]["pair"] == "4bfef03bd7"


def test_the_wash_effect_is_not_significant():
    """1.9 sigma on one garment. Any claim that the fringe render improves fidelity rests on n=1
    and must say so."""
    s = _r("wash_effect_paired.json")["summary"]
    assert s["bench_diff"] < 3 * s["sd_of_bench_diff_paired"]


def test_contributing_guidance_asks_for_raw_edges():
    """A cuffed after-wash contribution adds nothing to this question, however good the photo."""
    # Committed, so the old pytest.skip here could only fire if someone deleted the contribution
    # guidance -- which is precisely when this check matters.
    p = os.path.join(ROOT, "CONTRIBUTING_PAIRS.md")
    assert os.path.exists(p), "CONTRIBUTING_PAIRS.md is committed and must be present"
    t = open(p).read().lower()
    assert "raw" in t and "hem" in t, "contribution guidance does not ask for raw (unfinished) hems"
