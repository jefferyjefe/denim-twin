"""Is this mask actually the garment? (plan §4.2)

`segment_garment_coarse` returns SAM's best-scoring plausible candidate, and SAM is confidently wrong often enough to
matter: on four real flat-lay photos inspected in EXP_0018 it segmented **a back pocket** (mask 4.4% of frame, score
0.906) and **the wall above the garment** (37.7%, score 0.992). Both then produced fringe and roughness numbers that
entered the prior. SAM's own score does not detect this, and neither does contour compactness — the wrong object can
have a perfectly clean outline.

These checks are cheap, object-level, and deliberately conservative: they reject, they never repair. Anything they
reject needs a human to look at the photo, which is the correct outcome for a research dataset.
"""
import numpy as np
import cv2

DEFAULTS = dict(min_area=0.06, max_area=0.75, min_fill_of_bbox=0.35, max_aspect=2.6, min_denim_frac=0.35,
                min_width_frac=0.25, max_border_frac=0.02)

def _denim_frac(image_bgr, m):
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    denimish = ((hsv[..., 0] >= 95) & (hsv[..., 0] <= 135) & (hsv[..., 1] >= 40)) | (hsv[..., 2] < 60)
    return float(denimish[m].mean()) if m.any() else 0.0

def check_garment_mask(image_bgr, mask, expect="shorts", **kw):
    """Return (ok, reasons, stats). `expect` is 'shorts', 'jeans' or None (either)."""
    p = {**DEFAULTS, **kw}
    m = np.asarray(mask, bool)
    H, W = m.shape
    reasons = []
    area = float(m.mean())
    ys, xs = np.nonzero(m)
    if not len(ys): return False, ["empty mask"], {"area": 0.0}
    h = ys.max() - ys.min() + 1; w = xs.max() - xs.min() + 1
    stats = {"area": area, "bbox_fill": float(m.sum() / (h * w)), "aspect": float(h / max(w, 1)),
             "width_frac": float(w / W), "denim_frac": _denim_frac(image_bgr, m),
             "border_frac": float((m[0].mean() + m[-1].mean() + m[:, 0].mean() + m[:, -1].mean()) / 4)}
    if area < p["min_area"]: reasons.append(f"mask covers only {area:.1%} of the frame — a detail, not a garment")
    if area > p["max_area"]: reasons.append(f"mask covers {area:.1%} of the frame — probably the backdrop")
    if stats["width_frac"] < p["min_width_frac"]: reasons.append(f"mask spans only {stats['width_frac']:.0%} of the frame width")
    if stats["bbox_fill"] < p["min_fill_of_bbox"]: reasons.append(f"mask fills only {stats['bbox_fill']:.0%} of its own bounding box")
    if stats["denim_frac"] < p["min_denim_frac"]: reasons.append(f"only {stats['denim_frac']:.0%} of the mask is denim-coloured")
    if stats["border_frac"] > p["max_border_frac"]: reasons.append(f"mask touches the frame border ({stats['border_frac']:.1%})")
    if expect == "shorts" and stats["aspect"] > p["max_aspect"]:
        reasons.append(f"mask is {stats['aspect']:.1f}x taller than wide — not a pair of shorts")
    # a flat-laid pair of shorts/jeans has ONE waistband run at the top and TWO legs lower down
    top = ys.min(); band = m[top:top + max(int(0.12 * h), 3)]
    runs_top = _runs(band.any(axis=0))
    low = m[ys.min() + int(0.75 * h):]
    runs_low = _runs(low.any(axis=0)) if low.any() else 0
    stats["runs_top"], stats["runs_low"] = runs_top, runs_low
    if runs_top != 1: reasons.append(f"{runs_top} separate runs across the top of the mask — not a single waistband")
    return (not reasons), reasons, stats

def _runs(row_bool, gap=3):
    x = np.nonzero(row_bool)[0]
    if not len(x): return 0
    return 1 + int((np.diff(x) > gap).sum())
