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

def fabric_vs_fringe(real_img, real_mask, lm_before, thresh_dE=None, hem_zone_px=80):
    """Split the real garment mask into fabric (colour close to the body of the garment) and fringe
    (lighter / desaturated hanging threads). Fabric colour = median Lab of mask pixels above the crotch."""
    lab = cv2.cvtColor(real_img.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    cy = int(lm_before["crotch"][1]); body = real_mask.copy(); body[cy:] = False
    ref = np.median(lab[body], axis=0) if body.any() else np.median(lab[real_mask], axis=0)
    d = np.linalg.norm(lab - ref, axis=2)
    if thresh_dE is None:   # Otsu on the distance within the mask
        d8 = np.clip(d[real_mask] * 2, 0, 255).astype(np.uint8); t, _ = cv2.threshold(d8, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU); thresh_dE = max(t / 2, 8)
    fringe = real_mask & (d > thresh_dE)
    # fringe can only exist at the bottom of the garment: keep candidate pixels within `hem_zone_px` of each
    # column's lowest garment pixel, and require the pixel to be connected (through fringe/background) to the bottom
    H, W = real_mask.shape; bottom = np.full(W, -1)
    ys, xs = np.nonzero(real_mask); np.maximum.at(bottom, xs, ys)
    zone = (np.arange(H)[:, None] >= (bottom - hem_zone_px)[None, :]) & (bottom[None, :] >= 0)
    fringe &= zone
    fringe = cv2.morphologyEx(fringe.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
    fabric = real_mask & ~fringe
    fabric = cv2.morphologyEx(fabric.astype(np.uint8), cv2.MORPH_OPEN, np.ones((5, 5), np.uint8)).astype(bool)
    return fabric, real_mask & ~fabric, float(thresh_dE)

def _split_x(lm_before, real_mask):
    """Column that separates the legs: midpoint of the hips if available (robust to a mis-placed crotch x)."""
    if "hip_left" in lm_before and "hip_right" in lm_before: return int((lm_before["hip_left"][0] + lm_before["hip_right"][0]) / 2)
    return int(lm_before["crotch"][0])

def estimate_hems(real_mask, garment_before, lm_before, w=6, solid_frac=0.6, real_img=None, min_pts=6, fringe_mask=None):
    H, W = real_mask.shape; cx = _split_x(lm_before, real_mask)
    # scan from the HIP row, not the crotch: the per-column 'last fabric row' is unaffected by starting higher, and the
    # crotch estimate can be badly off when the legs touch (no gap) — starting there can miss the whole hem.
    cy = int(lm_before["hip_left"][1]) if "hip_left" in lm_before else int(lm_before["crotch"][1])
    cy = min(cy, int(np.nonzero(real_mask.any(axis=1))[0].max()) - 2) if real_mask.any() else cy
    k = np.ones((1, 2 * w + 1), np.float32) / (2 * w + 1)
    base = real_mask
    if fringe_mask is not None:                                   # SAM fringe mask (warped into the before frame): most reliable
        base = real_mask & ~fringe_mask
    elif real_img is not None:
        base, _, _ = fabric_vs_fringe(real_img, real_mask, lm_before)   # edge = end of FABRIC, tip = end of mask
        if base[cy:].sum() < 0.3 * real_mask[cy:].sum(): base = real_mask   # colour split failed (lighting): fall back to the mask
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
        if len(ex) < min_pts: legs[name] = None; continue
        ex, ey, tips = map(np.array, (ex, ey, tips))
        line = _fit_line_ransac(ex.astype(float), ey.astype(float))
        depth = np.median(np.clip(tips - ey, 0, None))
        legs[name] = dict(line=line, edge_x=ex, edge_y=ey, tip_y=tips, fringe_depth_px=float(depth),
                          angle_deg=float(np.degrees(np.arctan(line[0]))) if line else None)
    return legs

def cut_mask_from_lines(garment_before, lm_before, legs):
    """Removal mask: garment pixels below each leg's fitted line (split at crotch x)."""
    H, W = garment_before.shape; cx = _split_x(lm_before, garment_before); rem = np.zeros_like(garment_before)
    ys = np.arange(H)[:, None]
    for name, cols in (("left", slice(0, cx)), ("right", slice(cx, W))):
        L = legs.get(name)
        if not L or not L["line"]: continue
        m, b = L["line"]; xs = np.arange(cols.start, cols.stop)
        rem[:, cols] = ys >= (m * xs + b)[None, :]
    return rem & garment_before
