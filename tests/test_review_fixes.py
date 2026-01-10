"""Regression tests from the 2026-08-28 adversarial review (each originally demonstrated a bug)."""
import sys, os, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2, pytest
from denimtwin.eval import identity as I
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.landmarks import CANONICAL, LANDMARKS
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.capture.quality import check_image
from test_canon import synthetic_jeans

ROOT = os.path.join(os.path.dirname(__file__), "..")

def test_delta_e_is_cie76_not_opencv_uint8_lab():
    # identity.py:23-25 -- cvtColor on uint8 gives L in [0,255], a/b offset 128. CIE76 white->black is 100.
    w = np.full((4, 4, 3), 255, np.uint8); k = np.zeros((4, 4, 3), np.uint8)
    assert abs(I.unchanged_color_delta_e(w, k, np.ones((4, 4), bool)) - 100.0) < 1.0

def test_warp_identity_landmarks_is_identity():
    # warp.py:31-36 -- coarse grid spans [0, W+step] but is resized onto [0, W): ~0.8% scale + ~2.5px offset.
    W, H = 1000, 1500
    lm = {n: (CANONICAL[n][0] * W, CANONICAL[n][1] * H) for n in LANDMARKS}
    cm = CanonicalMap(lm, (W, H))
    img = np.zeros((H, W, 3), np.uint8)
    img[1400:1403] = 255                      # a stripe near the hem
    out = cm.image_to_canon(img)
    ys = np.nonzero(out[:, 50, 0] > 127)[0]
    assert abs(ys.mean() - 1401.0) < 1.0     # observed: ~1393

def test_ssim_does_not_leak_cut_region_into_keep_region():
    # identity.py:11-18 -- SSIM windows straddling the keep boundary see the modified region.
    rng = np.random.default_rng(1)
    img = rng.integers(0, 255, (64, 64, 3), np.uint8)
    keep = np.ones((64, 64), bool); keep[20:44, 20:44] = False   # non-rectangular keep (hole)
    pred = img.copy(); pred[~keep] = 0                            # only the cut region touched
    assert I.unchanged_ssim(pred, img, keep) > 0.999              # observed: 0.95

def test_feature_retention_penalises_translation():
    # identity.py:35-46 -- ratio-test matches are never checked for spatial consistency;
    # a prediction shifted 40 px still 'retains' ~80% of features.
    real = cv2.imread(os.path.join(ROOT, "data/external/images/commons_c2024708ca53.jpg"))
    if real is None: pytest.skip("harvested image not present")
    real = cv2.resize(real, (800, int(800 * real.shape[0] / real.shape[1])))
    shifted = np.roll(real, 40, axis=1)
    assert I.feature_retention(shifted, real, np.ones(real.shape[:2], bool)) < 0.2

def test_cut_removes_garment_pixels_below_hem_landmarks():
    # cut2d.py:17-18 / landmarks.py hem y=0.98 -- garment pixels that map outside the 1000x1500
    # canonical raster (only 2% margin below the hem) get BORDER_CONSTANT=0 -> never removed.
    img, mask, lm = synthetic_jeans(jitter=0)
    ylo = int(lm["hem_left_outer"][1]); cols = np.nonzero(mask[ylo - 1])[0]
    img[ylo:ylo + 40, cols] = (90, 50, 30); mask[ylo:ylo + 40, cols] = True   # true hem 40 px below the clicks
    cm = CanonicalMap(lm)
    _, removed, _ = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    assert removed[ylo + 31:].sum() == mask[ylo + 31:].sum()   # observed: 0 of 2151 removed

def test_quality_detects_light_wash_on_light_background(tmp_path):
    # quality.py:51 -- foreground = |gray - bg| > 40. Both registered garments are 'light' wash.
    im = np.full((1000, 1000), 200, np.uint8); cv2.rectangle(im, (200, 100), (800, 900), 170, -1)
    im = np.clip(im + np.random.default_rng(0).normal(0, 6, im.shape), 0, 255).astype(np.uint8)
    p = tmp_path / "light.png"; cv2.imwrite(str(p), im)
    r = check_image(str(p))
    assert r.foreground_fraction > 0.3, r.reasons   # observed: 0.0 -> 'foreground too small'

def test_check_capture_runs_from_any_cwd(tmp_path):
    # check_capture.py:10 -- default --board is relative to cwd, not the repo.
    res = subprocess.run([sys.executable, os.path.join(ROOT, "tools/check_capture.py"),
                          os.path.join(ROOT, "protocol/charuco_board.png")], cwd=tmp_path, capture_output=True, text=True)
    assert "FileNotFoundError" not in res.stderr

def test_openverse_query_returns_results():
    # harvest_images.py:30 -- page_size=50 is rejected (401) for anonymous requests; every Openverse
    # call fails, the error is swallowed as a warning, manifest has 0 openverse records.
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import harvest_images as H
    try:
        recs = list(H.openverse("denim jeans"))
    except Exception as e:
        if "429" in str(e) or "urlopen" in str(e).lower() or "timed out" in str(e).lower():
            pytest.skip(f"openverse unavailable: {e}")
        pytest.fail(f"openverse() raised: {e}")
    assert len(recs) > 0
