import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from test_canon import synthetic_jeans
from denimtwin.canon.autolm import landmarks_from_mask

def test_auto_landmarks_close_to_truth_on_synthetic():
    img, mask, lm = synthetic_jeans(jitter=0)
    auto, conf = landmarks_from_mask(mask)
    assert conf["crotch"] == "gap" and len(auto) == 14
    for k in ("crotch", "waist_left", "waist_right", "hem_left_outer", "hem_right_outer", "hem_left_inner", "hem_right_inner"):
        err = np.hypot(auto[k][0] - lm[k][0], auto[k][1] - lm[k][1]); assert err < 0.05 * mask.shape[1], (k, err)

def test_shorts_without_gap_fall_back():
    img, mask, lm = synthetic_jeans(jitter=0)
    cut = mask.copy(); cut[int(lm["crotch"][1]) - 5:] = False      # cut above the crotch: no gap
    auto, conf = landmarks_from_mask(cut)
    assert conf["crotch"] == "no_gap_shorts" and "hem_left_outer" in auto and "knee_left_outer" not in auto
