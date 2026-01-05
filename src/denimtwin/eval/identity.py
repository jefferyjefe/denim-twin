"""Identity-preservation metrics (plan §6.2). Evaluated ONLY inside `keep_mask`
(the region that should be unchanged)."""
import numpy as np
import cv2
from skimage.metrics import structural_similarity

def _masked_bbox(mask):
    ys, xs = np.nonzero(mask)
    return slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1)

def unchanged_ssim(pred, orig, keep_mask):
    """SSIM over the unchanged region (mean of per-pixel SSIM map inside mask)."""
    keep = np.asarray(keep_mask, bool)
    ys, xs = _masked_bbox(keep)
    a = cv2.cvtColor(pred[ys, xs], cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(orig[ys, xs], cv2.COLOR_BGR2GRAY)
    _, smap = structural_similarity(a, b, full=True, data_range=255)
    return float(smap[keep[ys, xs]].mean())

def unchanged_color_delta_e(pred, orig, keep_mask):
    """Mean CIE76 ΔE in the unchanged region (BGR uint8 inputs)."""
    keep = np.asarray(keep_mask, bool)
    la = cv2.cvtColor(pred, cv2.COLOR_BGR2LAB).astype(float)
    lb = cv2.cvtColor(orig, cv2.COLOR_BGR2LAB).astype(float)
    d = np.linalg.norm(la - lb, axis=2)
    return float(d[keep].mean())

def changed_pixel_fraction_outside(pred, orig, keep_mask, thresh=8):
    """Fraction of unchanged-region pixels that differ by more than `thresh` (max channel abs diff).
    Zero means the system touched nothing it shouldn't have."""
    keep = np.asarray(keep_mask, bool)
    diff = np.abs(pred.astype(int) - orig.astype(int)).max(axis=2)
    return float((diff[keep] > thresh).mean())

def feature_retention(pred, orig, keep_mask, ratio=0.75):
    """Fraction of ORB keypoints in the original's unchanged region that find a
    ratio-test match in the prediction. Proxy for logo/stitch/pocket preservation."""
    keep = (np.asarray(keep_mask, bool) * 255).astype(np.uint8)
    orb = cv2.ORB_create(2000)
    k1, d1 = orb.detectAndCompute(orig, keep)
    k2, d2 = orb.detectAndCompute(pred, keep)
    if d1 is None or d2 is None or len(k1) == 0:
        return 0.0
    m = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d1, d2, k=2)
    good = sum(1 for pair in m if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance)
    return float(good / len(k1))

def diff_map(pred, orig, thresh=8):
    """Boolean map of pixels the system changed. Shown to users alongside the render."""
    return np.abs(pred.astype(int) - orig.astype(int)).max(axis=2) > thresh
