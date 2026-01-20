"""Review 2: heuristic landmarks on realistic found-photo masks (hanger; tilted garment). Expected to FAIL."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.autolm import landmarks_from_mask

def _hung_jeans():
    """Jeans on a hanger (EXP_0003's pair is exactly this): hook stem + triangle above the waistband, all in one mask."""
    img, mask, lm = synthetic_jeans(jitter=0)
    m = np.zeros((1100, 600), bool); m[200:] = mask
    lm = {k: (v[0], v[1] + 200) for k, v in lm.items()}
    top = int(lm["waist_left"][1]); cx = int(lm["waist_center"][0])
    m[top - 120:top, cx - 3:cx + 4] = True
    cv2.fillPoly(m.view(np.uint8), [np.array([[cx - 200, top - 5], [cx + 200, top - 5], [cx, top - 120]], np.int32)], 1)
    return m, lm

def test_waist_and_hips_ignore_a_hanger():
    # autolm.py:24-27 -- waist = extents 3% below the mask TOP, hips at 18% of mask height: with a hanger in the
    # mask the top is the hook, so 'waist' lands on the hanger and 'hips' shift up by ~1/4 of the garment.
    m, lm = _hung_jeans(); auto, _ = landmarks_from_mask(m)
    for k in ("waist_left", "waist_right", "hip_left", "hip_right"):
        err = np.hypot(auto[k][0] - lm[k][0], auto[k][1] - lm[k][1])
        assert err < 0.05 * m.shape[1], (k, auto[k], lm[k], err)   # observed: waist ~120px off, hips ~90px off

def test_waist_width_survives_a_15deg_tilt():
    # autolm.py:24 -- a single row at 3% of the bounding box only clips the raised corner of a tilted waistband.
    img, mask, lm = synthetic_jeans(jitter=0)
    M = cv2.getRotationMatrix2D((300, 450), 15, 0.9); rm = cv2.warpAffine(mask.astype(np.uint8), M, (600, 900)) > 0
    auto, _ = landmarks_from_mask(rm)
    w_true = 0.9 * np.hypot(lm["waist_left"][0] - lm["waist_right"][0], lm["waist_left"][1] - lm["waist_right"][1])
    w_auto = np.hypot(auto["waist_left"][0] - auto["waist_right"][0], auto["waist_left"][1] - auto["waist_right"][1])
    assert w_auto > 0.7 * w_true, (w_auto, w_true)                 # observed: 94 vs 214
