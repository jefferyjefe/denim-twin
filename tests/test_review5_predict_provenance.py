"""Review 5 — tools/predict.py's machine-readable output presents an unvalidated placeholder as a prior with
n=8, and its only remaining guard switches itself off on a big enough photo.

data/priors/fringe.json (written by tools/fit_fringe.py:38-39) carries
    "validated": false,
    "validation_note": "EXP_0015: this measurement scores finished-hem controls the same as frayed hems; the
                        depths below are NOT evidence of fray depth"
tools/predict.py:139-142 reads only the mean/sd/n from that file:
    rel, n_eff, sd_rel = predict_depth_rel(pr, a.state, None)
    src = f"prior[{a.state}] n={n_eff}" + (" - INSUFFICIENT (<5 samples)..." if n_eff < 5 else "")
    if n_eff < 5: FLAGS.append(...)
and tools/predict.py:178-180 writes prediction.json with no `validated` key.
"""
import sys, os, json, subprocess, tempfile
import pytest
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans

pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(ROOT, "models", "sam_vit_b_01ec64.pth")) or __import__("importlib").util.find_spec("torch") is None,
    reason="needs the SAM checkpoint and torch")


def _scene(scale=1.0):
    img, mask, lm = synthetic_jeans(jitter=0)
    rng = np.random.default_rng(0)
    bg = np.clip(200 + cv2.GaussianBlur(rng.normal(0, 40, img.shape).astype(np.float32), (0, 0), 2.0), 0, 255).astype(np.uint8)
    s = cv2.copyMakeBorder(np.where(mask[..., None], img, bg), 60, 60, 60, 60, cv2.BORDER_REPLICATE)
    return s if scale == 1.0 else cv2.resize(s, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)


def _predict(tmp, scale=1.0, *extra):
    cv2.imwrite(f"{tmp}/jeans.png", _scene(scale))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "predict.py"), "--image", f"{tmp}/jeans.png",
                        "--out", f"{tmp}/out", "--inseam-fraction", "0.35", *extra], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.load(open(f"{tmp}/out/prediction.json"))


def test_prediction_json_carries_the_priors_own_validated_false():
    """prediction.json is the machine-readable provenance record ("prediction.json | machine-readable
    prediction + provenance", predict.py:204). It reports calibrated=false but nothing about validation, so
    a consumer sees `{"median": 1.76, "lo": 0.77, "hi": 2.76, "n": 8, "source": "prior[after_wash] n=8"}`
    -- a prior that looks measured. The prose caveat exists only in NOTE.md.

    observed fringe_depth keys: unit, median, lo, hi, below_render_resolution, nominal_coverage, calibrated,
                                n, source
    expected: `validated: false` (or the validation_note) propagated from data/priors/fringe.json."""
    prior = json.load(open(os.path.join(ROOT, "data/priors/fringe.json")))
    assert prior["validated"] is False, "prior no longer says validated:false; update this test"
    with tempfile.TemporaryDirectory() as tmp:
        f = _predict(tmp)["fringe_depth"]
    assert f.get("validated") is False or "validation" in json.dumps(f).lower(), (
        f"data/priors/fringe.json says validated:false, prediction.json says {json.dumps(f)}")


def test_a_high_resolution_photo_still_gets_a_fringe_warning():
    """The only machine-readable warning left after the prior rebuild is
        below_render_resolution = depth_px < 5.0            (predict.py:149-151, 179)
    Both the n<5 INSUFFICIENT string and its FLAG are dead: the rebuilt prior has n=8 for after_wash
    (data/priors/fringe.json n_after_wash_combined). Since depth_px = 0.00719 * waist_px, any photo with a
    waistband wider than ~695 px crosses 5.0 px and the warning vanishes entirely.

    observed at 4x (waist ~980 px): {"median": 7.06, "lo": 3.07, "hi": 11.06, "below_render_resolution":
        false, "calibrated": false, "n": 8, "source": "prior[after_wash] n=8"}, flags: [mask score,
        wash preset] -- not one word about the fringe.
    expected: a photo with more pixels must not silence the EXP_0015 caveat."""
    with tempfile.TemporaryDirectory() as tmp:
        pred = _predict(tmp, 4.0)
    f = pred["fringe_depth"]
    fringe_flags = [x for x in pred["flags"] if "fringe" in x.lower() or "EXP_0015" in x]
    assert fringe_flags, (
        f"no fringe caveat at all in prediction.json: fringe_depth={json.dumps(f)}, flags={pred['flags']}")
