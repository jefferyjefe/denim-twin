"""The crop-only null is not independent of the model (EXP_0034)."""
import json, os
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _report(name):
    p = os.path.join(ROOT, "reports", name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not generated")
    return json.load(open(p))


def test_score_predict_feeds_the_null_the_models_own_keep_mask():
    """The defect itself, pinned so it cannot be quietly 'fixed' without updating EXP_0034:
    compare.py builds null:crop-only from --keep, and score_predict passes predict's own keep
    mask. Any change here invalidates every crop-only number in the repository."""
    sp = open(os.path.join(ROOT, "tools", "score_predict.py")).read()
    cp = open(os.path.join(ROOT, "tools", "compare.py")).read()
    assert '"--keep", f"{od}/keep_mask.png"' in sp
    assert '"null:crop-only": (np.where(keep[..., None], before, bg), keep)' in cp


def test_prediction_and_croponly_masks_are_the_same_object():
    s = _report("prediction_vs_croponly_masks.json")["summary"]
    assert s["median_iou_pred_vs_keep"] > 0.999
    assert s["max_keep_only_px"] == 0, "the null must never keep a pixel the prediction drops"


def test_product_path_beats_an_independent_null():
    s = _report("independent_null.json")["summary"]
    assert s["mean_advantage"] > 0.05
    assert s["n_pairs_product_wins"] >= 5


def test_the_advantage_clears_ground_truth_noise():
    s = _report("paired_uncertainty_loonull.json")["summary"]
    assert s["bench_diff"] > 3 * s["sd_of_bench_diff_paired"], "advantage must clear 3 sigma"


def test_cancellation_factor_distinguishes_a_real_comparison_from_a_degenerate_one():
    """The method's own control: registration noise cancels almost completely between two
    near-identical masks (crop-only, 132x) and barely at all between genuinely different ones
    (independent null, ~1.5x). A high cancellation factor is a warning, not a result."""
    croponly = _report("paired_uncertainty.json")["summary"]["cancellation_factor"]
    indep = _report("paired_uncertainty_loonull.json")["summary"]["cancellation_factor"]
    assert croponly > 20 * indep


def test_the_inseam_fraction_is_measured_from_the_after_photo():
    """Why the +0.095 is NOT evidence of prediction: the product path is handed a cut height
    fitted to the ground truth. If this ever stops being true, EXP_0034's caveat is obsolete."""
    src = open(os.path.join(ROOT, "tools", "run_pair.py")).read()
    assert "mod.inseam_fraction = float(np.clip((float(np.median(_cy))" in src


def test_score_predict_always_warns_that_crop_only_is_not_independent():
    """The caveat is unconditional -- a future run must not be able to publish a crop-only
    comparison without it."""
    src = open(os.path.join(ROOT, "tools", "score_predict.py")).read()
    assert "crop-only IoU is not an independent baseline" in src
    assert '"crop_only_is_independent_of_the_model": False' in src


def test_a_generated_summary_carries_the_caveat():
    import glob
    outs = glob.glob(os.path.join(ROOT, "experiments", "pairs_predict*", "SUMMARY.md"))
    fresh = [p for p in outs if "crop-only IoU is not an independent baseline" in open(p).read()]
    if not fresh:
        pytest.skip("no SUMMARY.md regenerated since the caveat was added")
    r = json.load(open(os.path.join(os.path.dirname(fresh[0]), "result.json")))
    assert r["crop_only_is_independent_of_the_model"] is False
    if r.get("loo_null"):
        assert r["loo_null"]["mean_advantage"] > 0.05
