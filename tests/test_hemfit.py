import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.hemfit import estimate_hems, cut_mask_from_lines, fabric_vs_fringe

def _angled_real(img, mask, lm, slope_l=0.25, slope_r=-0.25, depth=30):
    """Build a fake 'real' after-image: garment cut along per-leg lines through the mid-thigh, plus a pale fringe band."""
    H, W = mask.shape; cx = int(lm["crotch"][0]); ys = np.arange(H)[:, None]; xs = np.arange(W)[None, :]
    y0 = lm["crotch"][1] + 0.4 * (lm["hem_left_inner"][1] - lm["crotch"][1])
    line = np.where(xs < cx, y0 + slope_l * (xs - cx), y0 + slope_r * (xs - cx))
    fabric = mask & (ys < line); fringe = mask & (ys >= line) & (ys < line + depth)
    real = img.copy(); real[~fabric] = (180, 180, 180); real[fringe] = (225, 228, 232)   # pale fringe
    return real, fabric | fringe, fabric, line

def test_hem_fit_recovers_angles_and_depth():
    img, mask, lm = synthetic_jeans(jitter=0)
    real, rmask, fabric, line = _angled_real(img, mask, lm)
    legs = estimate_hems(rmask, mask, lm, real_img=real)
    assert abs(legs["left"]["line"][0] - 0.25) < 0.03 and abs(legs["right"]["line"][0] + 0.25) < 0.03
    for L in legs.values(): assert abs(L["fringe_depth_px"] - 30) < 4, L["fringe_depth_px"]
    removed = cut_mask_from_lines(mask, lm, legs)
    keep = mask & ~removed
    iou = (keep & fabric).sum() / (keep | fabric).sum(); assert iou > 0.97, iou

def test_fabric_fringe_split_is_colour_based():
    img, mask, lm = synthetic_jeans(jitter=0)
    real, rmask, fabric, _ = _angled_real(img, mask, lm)
    fab, fr, t = fabric_vs_fringe(real, rmask, lm)
    assert (fab & fabric).sum() / fabric.sum() > 0.95 and (fr & ~fabric).sum() / max(fr.sum(), 1) > 0.95
