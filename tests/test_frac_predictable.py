"""The inseam fraction is not predictable from the garment (EXP_0035)."""
import json, os
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _r(name):
    p = os.path.join(ROOT, "reports", name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not generated")
    return json.load(open(p))


def test_feature_selection_happens_inside_the_fold():
    """The whole result turns on this. Choosing the feature on all seven pairs and then reporting
    leave-one-out error leaks the held-out pair into model selection and would make a null result
    look like a discovery."""
    src = open(os.path.join(ROOT, "tools", "experiment_frac_predictable.py")).read()
    assert "# feature choice happens INSIDE the fold" in src
    body = src.split("for i in range(n):")[1]
    assert "tr = np.arange(n) != i" in body
    assert "X[k][tr], y[tr]" in body, "feature r2 must be computed on the training rows only"


def test_predictor_does_not_beat_a_constant_on_mae():
    s = _r("frac_predictable.json")["summary"]
    assert s["model_beats_baseline"] is False
    assert s["loo_mae_model"] > s["loo_mae_median_baseline"]


def test_predictor_does_not_beat_a_constant_on_the_bench_metric():
    """MAE is not what the gate is written in; this is."""
    s = _r("frac_predictor_vs_constant.json")["summary"]
    assert s["predictor_beats_constant"] is False
    assert s["mean_iou_predictor"] < s["mean_iou_constant"]
    assert s["n_pairs_predictor_worse"] >= 5


def test_the_folds_disagree_about_which_feature_to_use():
    """Four different features across seven folds -- each fold fitting its own noise. If this ever
    collapses to one feature on more data, the negative result deserves re-testing."""
    s = _r("frac_predictable.json")["summary"]
    assert len(s["n_folds_choosing_each_feature"]) >= 3


def test_the_in_sample_r2_is_not_quoted_as_a_result():
    """r2 = 0.32 on 7 points with 6 candidate features is what noise produces. The NOTE must keep
    saying so."""
    note = open(os.path.join(ROOT, "experiments", "EXP_0035_frac_not_predictable", "NOTE.md")).read()
    assert "That number is the trap" in note
