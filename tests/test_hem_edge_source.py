"""Mask edge vs colour split for non-fraying garments: tested, not adopted (EXP_0039)."""
import json, os
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _r():
    p = os.path.join(ROOT, "reports", "hem_edge_source_ab.json")
    if not os.path.exists(p):
        pytest.skip("hem_edge_source_ab.json not generated")
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
