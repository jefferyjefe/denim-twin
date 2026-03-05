"""Phase 3 (plan §4.3, Representation B precursor): a category-specific PARAMETRIC 2D jeans template fitted to
an observed silhouette. Parameters are garment measurements (in canonical units of image height), so the fit yields
metric-style descriptors once a scale is known, and consistent landmarks that do not depend on heuristics.

Template (front, flat): a symmetric polygon controlled by
  waist_w, hip_w, hip_y, rise (crotch y below waist), thigh_w (per leg at crotch), knee_w, leg_len, hem_w, leg_spread
Fitted by maximising IoU with the garment mask using Nelder–Mead from a mask-derived initial guess."""
import numpy as np, cv2
from scipy.optimize import minimize

NAMES = ["cx", "top", "waist_w", "hip_w", "hip_dy", "rise", "thigh_w", "knee_w", "leg_len", "hem_w", "spread"]

def polygon(p):
    cx, top, waist_w, hip_w, hip_dy, rise, thigh_w, knee_w, leg_len, hem_w, spread = p
    y0 = top; yh = top + hip_dy; yc = top + rise; yk = yc + 0.47 * leg_len; yb = yc + leg_len
    L = []
    # left half, top to hem (outer edge), then inner edge back up to crotch; mirrored for the right leg
    left = [(cx - waist_w / 2, y0), (cx - hip_w / 2, yh), (cx - thigh_w - spread / 2, yc), (cx - knee_w - spread / 2 - 0.3 * spread, yk), (cx - hem_w - spread / 2 - 0.6 * spread, yb),
            (cx - spread / 2 - 0.6 * spread, yb), (cx - spread / 2 - 0.3 * spread, yk), (cx, yc)]
    right = [(2 * cx - x, y) for x, y in reversed(left[:-1])]
    pts = left + right
    return np.array(pts, np.float32)

def render(p, H, W):
    m = np.zeros((H, W), np.uint8); cv2.fillPoly(m, [polygon(p).astype(np.int32)], 1); return m.astype(bool)

def init_from_mask(mask):
    ys, xs = np.nonzero(mask); top, bot = ys.min(), ys.max(); h = bot - top
    row = lambda f: (lambda r: (r.min(), r.max()) if len(r) else (xs.min(), xs.max()))(np.nonzero(mask[min(top + int(f * h), bot)])[0])
    w0 = row(0.02); wh = row(0.18); cx = (w0[0] + w0[1]) / 2
    hem = row(0.98); legw = (hem[1] - hem[0]) / 2
    return np.array([cx, top, w0[1] - w0[0], wh[1] - wh[0], 0.16 * h, 0.28 * h, 0.22 * (wh[1] - wh[0]) * 1.0, legw * 0.9, 0.70 * h, legw * 0.85, 0.06 * (hem[1] - hem[0])], float)

def gap_mask(m):
    """Background enclosed between the legs (bounded left/right by garment on the same row)."""
    H, W = m.shape; g = np.zeros_like(m)
    first = np.argmax(m, axis=1); last = W - 1 - np.argmax(m[:, ::-1], axis=1); has = m.any(axis=1)
    for y in np.nonzero(has)[0]:
        row = m[y, first[y]:last[y] + 1]
        if not row.all(): g[y, first[y]:last[y] + 1] = ~row
    return g

def fit(mask, iters=400):
    H, W = mask.shape; m = mask.astype(bool); p0 = init_from_mask(m); gm = gap_mask(m)
    ys = np.nonzero(m)[0]; h = ys.max() - ys.min()
    scale = np.maximum(np.abs(p0), 1.0)
    def loss(q):
        p = q * scale
        if p[2] <= 0 or p[6] <= 0 or p[8] <= 0 or p[9] <= 0 or p[5] <= 0: return 2.0
        pen = 0.0                                              # soft plausibility bounds (fractions of garment height)
        pen += max(0, 0.08 * h - p[4]) + max(0, p[4] - 0.25 * h)   # hip_dy
        pen += max(0, 0.18 * h - p[5]) + max(0, p[5] - 0.45 * h)   # rise
        r = render(p, H, W); inter = (r & m).sum(); union = (r | m).sum()
        gr = gap_mask(r); gi = (gr & gm).sum(); gu = (gr | gm).sum()
        gap_term = 1.0 - gi / gu if gu else 0.0                # the between-leg gap pins the crotch height
        return (1.0 - inter / max(union, 1)) + 0.5 * gap_term + pen / h
    res = minimize(loss, p0 / scale, method="Nelder-Mead", options={"maxiter": iters, "xatol": 1e-3, "fatol": 1e-4})
    p = res.x * scale; r = render(p, H, W); iou = float((r & m).sum() / max((r | m).sum(), 1))   # a real IoU, not 1 - loss
    return dict(zip(NAMES, map(float, p))), iou, p

def landmarks_from_params(p):
    cx, top, waist_w, hip_w, hip_dy, rise, thigh_w, knee_w, leg_len, hem_w, spread = p
    yc = top + rise; yk = yc + 0.47 * leg_len; yb = yc + leg_len
    return {"waist_left": (cx - waist_w / 2, top), "waist_center": (cx, top), "waist_right": (cx + waist_w / 2, top),
            "hip_left": (cx - hip_w / 2, top + hip_dy), "hip_right": (cx + hip_w / 2, top + hip_dy), "crotch": (cx, yc),
            "knee_left_outer": (cx - knee_w - 0.8 * spread, yk), "knee_left_inner": (cx - 0.8 * spread, yk), "knee_right_inner": (cx + 0.8 * spread, yk), "knee_right_outer": (cx + knee_w + 0.8 * spread, yk),
            "hem_left_outer": (cx - hem_w - 1.1 * spread, yb), "hem_left_inner": (cx - 1.1 * spread, yb), "hem_right_inner": (cx + 1.1 * spread, yb), "hem_right_outer": (cx + hem_w + 1.1 * spread, yb)}
