"""Mask edge vs colour split for non-fraying garments: tested, not adopted (EXP_0039)."""
import json, os
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _r():
    p = os.path.join(ROOT, "reports", "hem_edge_source_ab.json")
    # A committed report is not an optional artefact. Skipping here turns the guard into a
    # no-op exactly when the thing it guards has gone missing -- review 7's finding about
    # tests that pass by not running. Every report named below is tracked in git.
    assert os.path.exists(p), "hem_edge_source_ab.json is missing; it is tracked in git -- restore it or run tools/make_reports.py --write --all"
    return json.load(open(p))["summary"]


def test_the_change_was_not_adopted():
    assert _r()["adopted"] is False


def test_the_experimental_knob_was_reverted():
    """A default-off env switch nobody sets is a dead parameter."""
    src = open(os.path.join(ROOT, "tools", "run_pair.py")).read()
    assert "HEM_EDGE" not in src


def test_better_on_more_pairs_but_worse_on_the_mean():
    """Both framings are the same data. The NOTE has to keep carrying both, because quoting only
    'better on 5 of 7' would turn this null into a result."""
    s = _r()
    assert s["n_hem_improved"] > s["n_hem_worsened"]
    assert s["mean_hem_delta"] > 0
    note = open(os.path.join(ROOT, "experiments", "EXP_0039_hem_edge_source", "NOTE.md")).read()
    assert "Better on 5 of 7 pairs" in note and "worse" in note


def test_one_pair_decides_the_result():
    s = _r()
    assert s["worst_regression_hem_px"] > 15
    assert s["worst_regression_pair"] == "2b0123d732"


def test_the_regression_is_localised_to_one_band_on_one_pair():
    """Not spread across the hem: 78 columns of a garment spanning 156-425. If a future change
    spreads it, the 'one deciding pair' framing in EXP_0039 no longer holds."""
    p = os.path.join(ROOT, "reports", "hem_edge_localisation.json")
    # A committed report is not an optional artefact. Skipping here turns the guard into a
    # no-op exactly when the thing it guards has gone missing -- review 7's finding about
    # tests that pass by not running. Every report named below is tracked in git.
    assert os.path.exists(p), "hem_edge_localisation.json is missing; it is tracked in git -- restore it or run tools/make_reports.py --write --all"
    s = json.load(open(p))["summary"]
    assert s["n_pairs_systematically_affected"] == 1
    assert s["affected_pair"] == "2b0123d732"


def test_gap_fraction_does_not_explain_the_band():
    """Falsified directly: the pair with the LEAST between-leg gap near the hem has the smallest
    shift. Kept as a test so the explanation is not quietly revived."""
    p = os.path.join(ROOT, "reports", "hem_edge_localisation.json")
    # A committed report is not an optional artefact. Skipping here turns the guard into a
    # no-op exactly when the thing it guards has gone missing -- review 7's finding about
    # tests that pass by not running. Every report named below is tracked in git.
    assert os.path.exists(p), "hem_edge_localisation.json is missing; it is tracked in git -- restore it or run tools/make_reports.py --write --all"
    d = json.load(open(p))
    rows = {r["pair"]: r for r in d["rows"]}
    least_gap = min((r for r in d["rows"] if r["gap_pct_near_hem"] is not None),
                    key=lambda r: r["gap_pct_near_hem"])
    assert least_gap["n_cols_shift_over_40"] < rows["2b0123d732"]["n_cols_shift_over_40"]


def test_the_note_records_the_band_as_unexplained():
    note = open(os.path.join(ROOT, "experiments", "EXP_0039_hem_edge_source", "NOTE.md")).read()
    assert "localised but unexplained" in note
