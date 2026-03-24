"""A garment that cannot fray must not have its hem measured from a fringe (EXP_0038)."""
import json, os
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_the_fringe_mask_is_gated_on_expects_fringe():
    """The bug: expects_fringe() was computed AFTER estimate_hems and used only to suppress
    RENDERING, so a spurious SAM fringe on a cuffed hem still decided where the fabric ends."""
    src = open(os.path.join(ROOT, "tools", "run_pair.py")).read()
    assert "fringe_mask=fr_before if _expects else None" in src
    # and the test must be computed before the fit, not after
    assert src.index("_expects = _CM(") < src.index("legs = estimate_hems("), (
        "expects_fringe() is computed after the hem fit again")


def test_ab_report_is_present_and_covers_every_scored_pair():
    """The tuning rule requires the A/B attached, on >=5 usable pairs."""
    p = os.path.join(ROOT, "reports", "fringe_gate_ab.json")
    # A committed report is not an optional artefact. Skipping here turns the guard into a
    # no-op exactly when the thing it guards has gone missing -- review 7's finding about
    # tests that pass by not running. Every report named below is tracked in git.
    assert os.path.exists(p), "fringe_gate_ab.json is missing; it is tracked in git -- restore it or run tools/make_reports.py --write --all"
    s = json.load(open(p))["summary"]
    assert s["n_pairs"] >= 5
    assert s["n_gated"] >= 1


def test_the_gate_improves_both_means():
    p = os.path.join(ROOT, "reports", "fringe_gate_ab.json")
    # A committed report is not an optional artefact. Skipping here turns the guard into a
    # no-op exactly when the thing it guards has gone missing -- review 7's finding about
    # tests that pass by not running. Every report named below is tracked in git.
    assert os.path.exists(p), "fringe_gate_ab.json is missing; it is tracked in git -- restore it or run tools/make_reports.py --write --all"
    s = json.load(open(p))["summary"]
    assert s["mean_sil_iou_delta"] > 0
    assert s["mean_hem_delta"] < 0


def test_the_regressions_are_recorded_not_hidden():
    """Three pairs got slightly worse. The NOTE must keep saying so and saying why -- on those the
    spurious fringe was landing closer than the colour split, which is a colour-split defect."""
    note = open(os.path.join(ROOT, "experiments", "EXP_0038_fringe_gate", "NOTE.md")).read()
    assert "three worsen slightly" in note
    assert "defect in the" in note and "colour split" in note


def test_no_baseline_was_refrozen_to_make_the_bench_green():
    """bench.py is green after this change without a re-freeze. If a future change needs a freeze,
    that is a deliberate act requiring its own report -- this asserts the current baseline still
    holds the pre-EXP_0038 numbers for the pair that moved most."""
    p = os.path.join(ROOT, "data", "bench", "baseline.json")
    if not os.path.exists(p):
        pytest.skip("no bench baseline")
    b = json.load(open(p))
    entry = b.get("443d1d4658")
    if entry is None:
        pytest.skip("pair not in baseline")
    assert abs(entry["hem_chamfer"] - 8.916) < 0.01, "the baseline was re-frozen"
