"""Heuristic landmarks from a flat-lay FRONT garment mask (jeans or shorts), no learning.

waist_left/right   = leftmost/rightmost mask pixels in the top 12% of the garment height
waist_center       = midpoint of those, on the top edge
hip_left/right     = widest extent in the 15–35% height band
crotch             = lowest point of the between-leg background gap (topmost background pixel that is
                     enclosed left/right by garment and connects downward to the bottom); for shorts with
                     no visible gap, the bottom-centre of the mask
knee_*             = leg edges at 60% of crotch→hem (for shorts: absent → None)
hem_*              = leg outer/inner edges at the last row where each leg exists
Returns dict name -> (x, y) and a 'confidence' dict; missing landmarks are omitted.
"""
import numpy as np, cv2

def _row_extent(mask, y):
    xs = np.nonzero(mask[y])[0]; return (int(xs.min()), int(xs.max())) if len(xs) else None

def landmarks_from_mask(mask):
    m = mask.astype(bool); ys, xs = np.nonzero(m)
    if len(ys) == 0: return {}, {}
    top, bot = ys.min(), ys.max(); h = bot - top; out = {}; conf = {}; H, W = m.shape
    # waist: extents at 3% below the top edge; hips: extents at 18%
    def ext_at(frac):
        y = min(top + int(frac * h), bot); e = _row_extent(m, y)
        for dy in range(1, 10):                       # tolerate thin rows
            if e: break
            e = _row_extent(m, min(y + dy, bot))
        return e, y
    e, y = ext_at(0.03); out["waist_left"] = (e[0], y); out["waist_right"] = (e[1], y); out["waist_center"] = ((e[0] + e[1]) // 2, top + int(0.02 * h))
    e, y = ext_at(0.18); out["hip_left"] = (e[0], y); out["hip_right"] = (e[1], y)
    # crotch: first row below the hips where the mask splits into two runs with a gap near the centre
    cx = (out["hip_left"][0] + out["hip_right"][0]) // 2; half = (out["hip_right"][0] - out["hip_left"][0]) // 2
    crotch = None
    for y in range(top + int(0.2 * h), bot):
        row = m[y]; xs_ = np.nonzero(row)[0]
        if len(xs_) < 2: continue
        d = np.diff(xs_); gaps = np.nonzero(d > 3)[0]
        for g in gaps:
            gx = (xs_[g] + xs_[g + 1]) // 2
            if abs(gx - cx) < 0.5 * half:
                crotch = (int(gx), int(y)); break
        if crotch: break
    wmax = xs.max() - xs.min(); shorts = h < 1.3 * wmax          # jeans are ~2x taller than wide; shorts ~1x
    conf["garment_type"] = "shorts" if shorts else "jeans"
    if crotch and (shorts or crotch[1] <= top + 0.45 * h): out["crotch"] = crotch; conf["crotch"] = "gap"
    elif crotch: out["crotch"] = (cx, top + int(0.30 * h)); conf["crotch"] = "prior_legs_touching"   # jeans, gap too low: legs touch
    elif shorts: out["crotch"] = (cx, int(bot)); conf["crotch"] = "no_gap_shorts"
    else: out["crotch"] = (cx, top + int(0.30 * h)); conf["crotch"] = "prior_no_gap_jeans"
    cyx, cyy = out["crotch"]
    # per-leg hems and knees
    for side, sl in (("left", slice(0, cyx)), ("right", slice(cyx, W))):
        sub = m[:, sl]; rows = np.nonzero(sub.any(axis=1))[0]
        if len(rows) == 0: continue
        yb = rows.max(); e = _row_extent(sub, max(int(yb - 0.02 * h), rows.min()))   # 2% above the tip: full-width row
        if e is None: continue
        off = sl.start or 0
        outer, inner = ((e[0] + off, e[1] + off) if side == "left" else (e[1] + off, e[0] + off))
        out[f"hem_{side}_outer"] = (outer, int(yb)); out[f"hem_{side}_inner"] = (inner, int(yb))
        yk = int(cyy + 0.47 * (yb - cyy)); ek = _row_extent(sub, yk)
        if ek and yb - cyy > 0.15 * h:
            ok, ik = ((ek[0] + off, ek[1] + off) if side == "left" else (ek[1] + off, ek[0] + off))
            out[f"knee_{side}_outer"] = (ok, yk); out[f"knee_{side}_inner"] = (ik, yk)
    return {k: (int(v[0]), int(v[1])) for k, v in out.items()}, conf
