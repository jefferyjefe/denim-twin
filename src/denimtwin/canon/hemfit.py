"""Per-leg hem estimation from a registered after-capture (found pairs: the cut isn't recorded, so the
fabric edge is recovered from the after-photo; only the fringe is predicted).

For each leg (split at the crotch x), per column: `edge` = last row where the real mask is locally solid
(≥ solid_frac of a (2w+1)-wide horizontal window is garment), `tip` = last garment row. A robust line is fitted
to the edge points (RANSAC) → per-leg cut line in IMAGE space; fringe depth = median(tip - edge) in px.
`cut_mask_from_lines` removes garment pixels below the fitted lines, giving an image-space cut that matches
angled tutorial cuts without going through the canonical raster.
"""
import numpy as np, cv2

def _fit_line_ransac(xs, ys, iters=300, tol=3.0, rng=None):
    rng = rng or np.random.default_rng(0); best = None; n = len(xs)
    if n < 2: return None
    for _ in range(iters):
        i, j = rng.choice(n, 2, replace=False)
        if xs[i] == xs[j]: continue
        m = (ys[j] - ys[i]) / (xs[j] - xs[i]); b = ys[i] - m * xs[i]
        inl = np.abs(ys - (m * xs + b)) < tol
        if best is None or inl.sum() > best[2]: best = (m, b, inl.sum(), inl)
    m, b, _, inl = best
    if inl.sum() >= 2: m, b = np.polyfit(xs[inl], ys[inl], 1)
    return float(m), float(b)

def fabric_vs_fringe(real_img, real_mask, lm_before, thresh_dE=None):
    """Split the real garment mask into fabric (colour close to the body of the garment) and fringe
    (lighter / desaturated hanging threads). Fabric colour = median Lab of mask pixels above the crotch."""
    lab = cv2.cvtColor(real_img.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    cy = int(lm_before["crotch"][1]); body = real_mask.copy(); body[cy:] = False
    ref = np.median(lab[body], axis=0) if body.any() else np.median(lab[real_mask], axis=0)
    d = np.linalg.norm(lab - ref, axis=2)
    if thresh_dE is None:   # Otsu on the distance within the mask
        d8 = np.clip(d[real_mask] * 2, 0, 255).astype(np.uint8); t, _ = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU); thresh_dE = max(t / 2, 8)
    fabric = real_mask & (d <= thresh_dE)
    fabric = cv2.morphologyEx(fabric.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
    return fabric, real_mask & ~fabric, float(thresh_dE)

def estimate_hems(real_mask, garment_before, lm_before, w=6, solid_frac=0.8, real_img=None):
    H, W = real_mask.shape; cx = int(lm_before["crotch"][0]); cy = int(lm_before["crotch"][1])
    k = np.ones((1, 2 * w + 1), np.float32) / (2 * w + 1)
    base = real_mask
    if real_img is not None:
        base, _, _ = fabric_vs_fringe(real_img, real_mask, lm_before)   # edge = end of FABRIC, tip = end of mask
    solid = cv2.filter2D(base.astype(np.float32), -1, k) >= solid_frac
    legs = {}
    for name, cols in (("left", range(0, cx)), ("right", range(cx, W))):
        ex, ey, tips = [], [], []
        for x in cols:
            col = garment_before[:, x]
            if col[cy:].sum() < 5: continue
            s = np.nonzero(solid[cy:, x] & base[cy:, x])[0]; t = np.nonzero(real_mask[cy:, x])[0]
            if len(s) == 0 or len(t) == 0: continue
            ex.append(x); ey.append(cy + s.max()); tips.append(cy + t.max())
        if len(ex) < 10: legs[name] = None; continue
        ex, ey, tips = map(np.array, (ex, ey, tips))
        line = _fit_line_ransac(ex.astype(float), ey.astype(float))
        depth = np.median(np.clip(tips - ey, 0, None))
        legs[name] = dict(line=line, edge_x=ex, edge_y=ey, tip_y=tips, fringe_depth_px=float(depth),
                          angle_deg=float(np.degrees(np.arctan(line[0]))) if line else None)
    return legs

def cut_mask_from_lines(garment_before, lm_before, legs):
    """Removal mask: garment pixels below each leg's fitted line (split at crotch x)."""
    H, W = garment_before.shape; cx = int(lm_before["crotch"][0]); rem = np.zeros_like(garment_before)
    ys = np.arange(H)[:, None]
    for name, cols in (("left", slice(0, cx)), ("right", slice(cx, W))):
        L = legs.get(name)
        if not L or not L["line"]: continue
        m, b = L["line"]; xs = np.arange(cols.start, cols.stop)
        rem[:, cols] = ys >= (m * xs + b)[None, :]
    return rem & garment_before
