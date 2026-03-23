"""443d1d4658's regression: cause confirmed, mechanism INCONCLUSIVE (EXP_0037, corrected by review 7)."""
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


def test_the_independent_rotation_mechanism_is_inconclusive_not_disconfirmed():
    """Corrected by review 7. This note first reported r = +0.092 and called the mechanism
    disconfirmed; that correlation was computed on hem values EXP_0038 later changed. Recomputed it
    is r = +0.459 (p = 0.30, n = 7) -- the direction the mechanism predicts, too weak to resolve at
    this sample size. The strict dose-response still fails: the largest applied rotation is not the
    worst hem. This test pins 'inconclusive', so neither 'disconfirmed' nor 'confirmed' can be
    restated without it failing."""
    s = _r()["summary"]
    r = s["corr_rotation_difference_vs_hem"]
    assert 0.2 < r < 0.8, f"r={r} no longer supports the 'inconclusive' reading"
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


def test_a_refused_correction_is_distinguishable_from_a_straight_photo():
    """upright() returns an applied angle of 0.0 for a REFUSED correction exactly as for a
    photograph that needed none, so two of the seven pairs (-40.1 and -36.1 degrees, beyond the
    30-degree ceiling) were logged as '0.0 rotated'. upright_decision() must keep them apart."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from denimtwin.canon.upright import upright_decision
    s = _r()["summary"]
    assert s["n_pairs_with_a_refused_correction"] >= 1
    assert set(s["refused_pairs"]) >= {"2691c1a8d0", "26b1041d00"}
    src = open(os.path.join(ROOT, "src", "denimtwin", "canon", "upright.py")).read()
    assert "def upright_decision" in src
    for st in ("refused", "straight", "below_deadband", "applied"):
        assert f'"{st}"' in src


def test_run_pair_logs_a_refusal():
    src = open(os.path.join(ROOT, "tools", "run_pair.py")).read()
    assert "tilt correction REFUSED" in src


def test_applied_and_estimated_rotation_are_reported_separately():
    """A refusal rotates nothing, so it contributes 0 to the APPLIED difference however tilted the
    garment is. Conflating the two was what made the corrected correlation ambiguous."""
    s = _r()["summary"]
    assert "corr_rotation_difference_vs_hem" in s
    assert "corr_estimated_tilt_difference_vs_hem" in s
    assert s["corr_rotation_difference_vs_hem"] != s["corr_estimated_tilt_difference_vs_hem"]
