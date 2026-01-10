import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.canon.landmarks import CANONICAL, LANDMARKS
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.eval import identity as I

def synthetic_jeans(w=600, h=900, jitter=0.0, seed=0):
    """Draw a jeans-like silhouette; landmarks are CANONICAL scaled + optional jitter."""
    rng = np.random.default_rng(seed)
    lm = {n: (CANONICAL[n][0] * w * 0.9 + w * 0.05 + rng.normal(0, jitter),
              CANONICAL[n][1] * h * 0.9 + h * 0.05 + rng.normal(0, jitter)) for n in LANDMARKS}
    img = np.full((h, w, 3), 180, np.uint8)
    poly = np.array([lm[n] for n in ["waist_left", "waist_right", "hip_right", "knee_right_outer",
        "hem_right_outer", "hem_right_inner", "knee_right_inner", "crotch", "knee_left_inner",
        "hem_left_inner", "hem_left_outer", "knee_left_outer", "hip_left"]], np.int32)
    cv2.fillPoly(img, [poly], (90, 50, 30))
    mask = np.zeros((h, w), np.uint8); cv2.fillPoly(mask, [poly], 255)
    # a "logo" patch on the right hip that must survive
    cv2.rectangle(img, (int(lm["hip_right"][0]) - 60, int(lm["hip_right"][1])), (int(lm["hip_right"][0]) - 20, int(lm["hip_right"][1]) + 40), (200, 200, 30), -1)
    return img, mask > 0, lm

def test_roundtrip_points():
    img, mask, lm = synthetic_jeans(jitter=6)
    cm = CanonicalMap(lm)
    pts = np.array([lm[n] for n in LANDMARKS], np.float32)
    back = cm.points_to_image(cm.points_to_canon(pts))
    assert np.abs(back - pts).max() < 1.0

def test_cut_preserves_everything_above_line():
    img, mask, lm = synthetic_jeans(jitter=6)
    cm = CanonicalMap(lm)
    out, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    assert removed.sum() > 0.2 * mask.sum()                      # something meaningful was cut
    assert I.changed_pixel_fraction_outside(out, img, keep) == 0  # byte-identical outside cut
    assert I.changed_pixel_fraction_outside(out, img, ~mask) == 0 # background untouched
    # cut is at the requested height: removed pixels' min y ≈ 35% down the inseam
    crotch_y, hem_y = lm["crotch"][1], lm["hem_left_inner"][1]
    expected = crotch_y + 0.35 * (hem_y - crotch_y)
    assert abs(np.nonzero(removed)[0].min() - expected) < 1.5
