"""The inseam fraction is not predictable from the garment (EXP_0035)."""
import json, os, sys
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _r(name):
    p = os.path.join(ROOT, "reports", name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not generated")
    return json.load(open(p))


def test_feature_selection_ignores_the_held_out_point():
    """BEHAVIOURAL guard on the leave-one-out discipline.

    The previous version of this test grepped the source for `X[k][tr], y[tr]` -- a substring that
    also occurs in the polyfit line -- so it passed even when feature selection was changed to read
    all rows including the held-out one. Review 7 demonstrated exactly that. This constructs a case
    where the two answers differ and asserts the in-fold one is returned.
    """
    import numpy as np
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from experiment_frac_predictable import choose_feature

    # 'clean' correlates perfectly with y on the first five rows and is the right in-fold answer.
    # 'trap' is flat over those five (r2 = 0) but the sixth row makes it look strong overall.
    y = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 40.0])
    X = {"clean": np.array([0.0, 1.0, 2.0, 3.0, 4.0, 0.0]),
         "trap":  np.array([1.0, 1.0, 1.0, 1.0, 1.0, 99.0])}
    tr = np.array([True, True, True, True, True, False])      # hold out the sixth row

    assert choose_feature(X, y, tr) == "clean", "feature selection is reading the held-out point"
    # sanity: with the held-out point included the answer really does flip, so the test has teeth
    allrows = np.ones(len(y), dtype=bool)
    assert choose_feature(X, y, allrows) == "trap"


def test_the_fold_loop_uses_the_extracted_selector():
    """Keeps the behavioural test wired to the real code path."""
    src = open(os.path.join(ROOT, "tools", "experiment_frac_predictable.py")).read()
    body = src.split("for i in range(n):")[1]
    assert "choose_feature(X, y, tr)" in body


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
