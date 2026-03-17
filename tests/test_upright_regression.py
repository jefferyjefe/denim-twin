"""443d1d4658's regression: cause confirmed, mechanism disconfirmed (EXP_0037)."""
import json, os
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _r():
    p = os.path.join(ROOT, "reports", "upright_regression.json")
    if not os.path.exists(p):
        pytest.skip("upright_regression.json not generated")
    return json.load(open(p))


def test_disabling_uprighting_restores_the_frozen_baseline():
    s = _r()["summary"]
    assert s["upright_off_restores_baseline"] is True
    assert s["arms"]["upright_off"]["hem_chamfer"] < s["arms"]["upright_on"]["hem_chamfer"]


def test_the_independent_rotation_mechanism_is_not_supported():
    """The README claimed the regression follows from before and after being uprighted
    independently. That predicts a dose-response and there is none: r = +0.09, and the pair with
    the largest relative rotation has nearly the best hem error."""
    s = _r()["summary"]
    assert abs(s["corr_rotation_difference_vs_hem"]) < 0.4
    assert s["largest_rotation_difference_pair"] != s["worst_hem_pair"]


def test_hem_angle_asymmetry_is_not_a_usable_diagnostic():
    """Tested and rejected, so nobody re-derives it: the most asymmetric fit in the set is the pair
    with nearly the best hem error."""
    s = _r()["summary"]
    assert abs(s["corr_angle_asymmetry_vs_hem"]) < 0.4
    assert s["largest_asymmetry_pair"] != s["worst_hem_pair"]


def test_the_readme_no_longer_states_the_disconfirmed_mechanism():
    t = open(os.path.join(ROOT, "README.md")).read()
    assert "because before and after are uprighted independently" not in t, (
        "the README still gives the mechanism EXP_0037 disconfirmed")
