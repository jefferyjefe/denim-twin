"""The ground-truth registration and its error bar (EXP_0033)."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import numpy as np
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _report(name):
    p = os.path.join(ROOT, "reports", name)
    if not os.path.exists(p):
        pytest.skip(f"{name} not generated")
    return json.load(open(p))


def test_registration_tps_does_not_fold_on_any_scored_pair():
    """0.0000 on all seven. If this ever becomes non-zero the ground truth is duplicating
    garment content and every IoU in the bench is suspect."""
    s = _report("registration_fold.json")["summary"]
    assert s["n_pairs"] == 7
    assert s["max_fold"] == 0.0
    assert s["n_over_20pct"] == 0


def test_zero_perturbation_reproduces_the_baseline_exactly():
    """The null control for the uncertainty harness: with the error magnitudes scaled to zero,
    refitting the TPS and re-warping must give back the baseline mask bit-for-bit. Without this,
    a coordinate bug in the harness would look like ground-truth noise."""
    import subprocess
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "experiment_groundtruth_uncertainty.py"),
                        "--draws", "3", "--scale", "0"],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        pytest.skip("pair artefacts unavailable")
    rows = json.loads(r.stdout)["rows"]
    if not rows:
        pytest.skip("no scored pairs present")
    for x in rows:
        assert x["iou_sd"] == 0.0, f"{x['pair']}: harness adds noise at zero perturbation"
        assert x["iou_mean"] == x["iou_baseline"], f"{x['pair']}: zero perturbation moved the score"


def test_paired_comparison_is_far_more_sensitive_than_unpaired():
    """EXP_0033's correction. Both methods are scored against the SAME perturbed ground truth,
    so the registration error cancels. Quoting the unpaired spread as the error bar on a method
    DIFFERENCE overstates it by two orders of magnitude."""
    s = _report("paired_uncertainty.json")["summary"]
    assert s["sd_of_bench_diff_paired"] < s["sd_of_bench_diff_unpaired"] / 10
    assert s["cancellation_factor"] > 10


def test_product_minus_croponly_is_a_null_not_a_noise_floor():
    """The measured difference is smaller than the resolution limit, and the resolution limit is
    itself tiny -- so this is a real null, not an unresolvable comparison."""
    s = _report("paired_uncertainty.json")["summary"]
    assert abs(s["bench_diff"]) < 2 * s["sd_of_bench_diff_paired"]
    assert s["sd_of_bench_diff_paired"] < 0.001, "bench can resolve method differences below 0.001"
