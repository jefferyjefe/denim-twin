"""End-to-end product path (tools/predict.py): one photo + a cut spec -> prediction with an interval, no ground truth.
Skipped where SAM's checkpoint or torch is unavailable (CI installs neither)."""
import sys, os, json, subprocess, tempfile
import pytest
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans

pytestmark = pytest.mark.needs("sam_checkpoint", "torch")

def _photo(path):
    img, mask, lm = synthetic_jeans(jitter=0)
    rng = np.random.default_rng(0)
    bg = np.clip(200 + cv2.GaussianBlur(rng.normal(0, 40, img.shape).astype(np.float32), (0, 0), 2.0), 0, 255).astype(np.uint8)
    scene = np.where(mask[..., None], img, bg)
    scene = cv2.copyMakeBorder(scene, 60, 60, 60, 60, cv2.BORDER_REPLICATE)     # margins: the frame-edge gate must pass
    cv2.imwrite(path, scene); return scene

def _run(tmp, *extra):
    _photo(f"{tmp}/jeans.png")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "predict.py"), "--image", f"{tmp}/jeans.png",
                        "--out", f"{tmp}/out", "--inseam-fraction", "0.35", *extra], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.load(open(f"{tmp}/out/prediction.json"))

def test_prediction_declares_its_own_uncertainty_and_provenance():
    with tempfile.TemporaryDirectory() as tmp:
        pred = _run(tmp)
        f = pred["fringe_depth"]
        assert f["lo"] <= f["median"] <= f["hi"] and f["calibrated"] is False and f["nominal_coverage"] == 0.8
        assert "prior" in f["source"] and f["n"] >= 0
        assert pred["scale"]["mm_per_px"] is None and "UNKNOWN" in pred["scale"]["source"] and f["unit"] == "px"
        assert 0.01 <= pred["cut"]["removed_fraction_of_garment"] <= 0.85
        for n in ("pred_median.png", "pred_conservative.png", "pred_aggressive.png", "diff.png", "modification.json", "panel.jpg", "NOTE.md"):
            assert os.path.exists(f"{tmp}/out/{n}"), n
        assert "prediction, not a measurement" in open(f"{tmp}/out/NOTE.md").read()

def test_finished_hems_are_predicted_not_to_fray():
    with tempfile.TemporaryDirectory() as tmp:
        pred = _run(tmp, "--edge-treatment", "hemmed")
        assert pred["fringe_depth"]["median"] == 0.0 and "does not fray" in pred["fringe_depth"]["source"]

def test_metric_scale_is_required_for_a_centimetre_cut():
    with tempfile.TemporaryDirectory() as tmp:
        _photo(f"{tmp}/jeans.png")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "predict.py"), "--image", f"{tmp}/jeans.png",
                            "--out", f"{tmp}/out", "--target-inseam-cm", "12"], capture_output=True, text=True)
        assert r.returncode == 3 and "metric scale" in r.stdout

def test_untouched_pixels_are_byte_identical_outside_the_cut_when_wash_is_off():
    with tempfile.TemporaryDirectory() as tmp:
        _run(tmp, "--wash", "none", "--state", "after_cut")
        orig = cv2.imread(f"{tmp}/out/orig.png"); pred = cv2.imread(f"{tmp}/out/pred_median.png")
        removed = cv2.imread(f"{tmp}/out/removed_mask.png", 0) > 127
        d = np.abs(orig.astype(int) - pred.astype(int)).max(axis=2)
        outside = d[~removed] > 8
        assert outside.mean() < 0.01, outside.mean()      # only the abraded band at the cut may touch kept fabric


def test_seg_consensus_is_available_on_the_product_path_and_records_its_agreement():
    """EXP_0021: the product path could not use the segmentation that fixes catastrophic object-identity failures.
    `--seg consensus` now exists there, and every prediction records which segmentation produced it."""
    with tempfile.TemporaryDirectory() as tmp:
        pred = _run(tmp, "--seg", "consensus")
        s = pred["segmentation"]
        assert s["method"] == "consensus" and 0.0 <= s["agreement"] <= 1.0
        assert any("consensus" in f for f in pred["flags"])

def test_default_segmentation_warns_that_sam_score_does_not_detect_a_wrong_object():
    with tempfile.TemporaryDirectory() as tmp:
        pred = _run(tmp)
        assert pred["segmentation"]["method"] == "coarse" and "score" in pred["segmentation"]
        assert any("0.906" in f or "confidently wrong" in f for f in pred["flags"]), pred["flags"]
