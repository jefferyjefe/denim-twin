"""Direct measurement of raw-edge fringe depth from a flat-lay photo (plan §4.7 / §6.3).

Why not SAM: `seg.segment_fringe` prompts SAM with a band at the hem and takes the returned mask as "fringe". On real
after-wash photos of cut-offs it returns whole regions of *fabric* — 0.10–0.61 of **waist width** across the ten photos
in EXP_0015 (16–31% of garment height on the harvested ones), which is why `run_pair` gates it as implausible. The threads themselves
lie OUTSIDE the coarse garment mask — SAM's garment mask stops at the solid fabric edge — so they can be measured
directly, per column, in the strip just below that edge.

Method, per column x:
  * y0 = the lowest garment-mask row (the solid fabric edge),
  * a background model (median, sd in Lab) from the deepest quarter of a search band below y0,
  * a pixel is *thread* if it is at least as light as that backdrop (z_L > 0.8) or clearly off-hue (chroma z > 3),
    AND overall far from it (‖z‖ > 2.5). The lightness condition is what separates threads from the garment's own
    drop shadow, which is otherwise the dominant false positive (it inflated depth ~3x in the first prototype),
  * depth = the deepest thread pixel still connected to the fabric edge through gaps of at most `max_gap` (expressed
    as a fraction of waist width, so that resolving the gaps between threads at higher resolution does not truncate
    the walk — with a fixed pixel gap a 3x enlargement measured 20 px where 60 px was the truth; review 5, finding 7).

**This measurement is not validated and should not be read as a fray depth.** Review 5 showed it returns, with
`ok=True` and full coverage: the garment-mask boundary error 1 px for 1 px on a fringe-free garment; 4–16 px for a drop
shadow that does not touch the hem; and 12–20 px for a mottled backdrop behind a clean edge. To make that visible
rather than implicit, every call now re-measures with the garment mask eroded and dilated by one pixel and reports the
spread as `sensitivity_px`; when the spread is not small against the depth the result is marked `ok=False`. Use
`eval/hem_texture.hem_roughness` for a fray signal that survives its negative control; keep this one for diagnostics.
"""
import numpy as np
import cv2

DEFAULTS = dict(band_frac=0.12, max_gap_frac=0.004, light_z=0.8, chroma_z=3.0, dist_z=2.5, min_columns=20,
                max_sensitivity_ratio=0.5)

def _measure_once(img, m, waist_px, band_frac, max_gap, light_z, chroma_z, dist_z, min_columns, return_mask):
    H, W = m.shape
    band = int(round(band_frac * (waist_px if waist_px else 0.5 * W)))
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    depths, cols = [], 0
    tmask = np.zeros((H, W), bool) if return_mask else None
    for x in range(W):
        col = np.nonzero(m[:, x])[0]
        if not len(col): continue
        cols += 1                                   # every garment column counts in the denominator (review 5, #8):
        y0 = int(col.max()); lo = min(y0 + band + 1, H)
        if lo - y0 < 8: continue                    # a column with no room below the garment is measured as no fringe
        tail = max((lo - y0) // 4, 3)
        bg = lab[lo - tail:lo, x]
        if len(bg) < 3: continue
        mu = np.median(bg, axis=0); sd = np.maximum(np.std(bg, axis=0), 3.0)
        z = (lab[y0 + 1:lo, x] - mu) / sd
        chroma = np.hypot(z[:, 1], z[:, 2])
        thread = ((z[:, 0] > light_z) | (chroma > chroma_z)) & (np.sqrt((z ** 2).sum(axis=1)) > dist_z)
        depth = 0; gap = 0
        for i, t in enumerate(thread):
            if t: depth = i + 1; gap = 0
            else:
                gap += 1
                if gap > max_gap: break
        if depth:
            depths.append(depth)
            if return_mask: tmask[y0 + 1:y0 + 1 + depth, x] = True
    out = {"n_columns": cols, "n_columns_with_fringe": len(depths),
           "coverage": (len(depths) / cols) if cols else 0.0,
           "median_px": float(np.median(depths)) if depths else 0.0,
           "mean_px": float(np.mean(depths)) if depths else 0.0,
           "p90_px": float(np.percentile(depths, 90)) if depths else 0.0,
           "enough_columns": bool(len(depths) >= min_columns)}
    if waist_px: out["depth_rel"] = out["median_px"] / float(waist_px)
    if return_mask: out["mask"] = tmask
    return out


def measure_fringe_depth(img, garment_mask, waist_px=None, band_frac=DEFAULTS["band_frac"],
                         max_gap_frac=DEFAULTS["max_gap_frac"], light_z=DEFAULTS["light_z"],
                         chroma_z=DEFAULTS["chroma_z"], dist_z=DEFAULTS["dist_z"],
                         min_columns=DEFAULTS["min_columns"], return_mask=False,
                         max_sensitivity_ratio=DEFAULTS["max_sensitivity_ratio"]):
    """Median/mean/p90 fringe depth in px (and relative to `waist_px`), plus `sensitivity_px`: how far the answer moves
    when the garment mask is eroded or dilated by one pixel. A result whose sensitivity exceeds
    `max_sensitivity_ratio` of the depth is reported with `ok=False` and a reason — that is the case where the number
    is mask error rather than fringe (review 5, finding 1). `garment_mask` must be the SOLID fabric mask."""
    m = np.asarray(garment_mask, bool)
    if m.shape != img.shape[:2]:
        return {"ok": False, "reason": f"mask {m.shape} does not match image {img.shape[:2]}",
                "median_px": 0.0, "mean_px": 0.0, "p90_px": 0.0, "n_columns": 0, "n_columns_with_fringe": 0,
                "coverage": 0.0, "sensitivity_px": float("inf")}
    w = float(waist_px) if waist_px else 0.5 * m.shape[1]
    max_gap = max(int(round(max_gap_frac * w)), 3)
    args = (waist_px, band_frac, max_gap, light_z, chroma_z, dist_z, min_columns)
    out = _measure_once(img, m, *args, return_mask)
    k = np.ones((3, 3), np.uint8)
    er = cv2.erode(m.astype(np.uint8), k) > 0; di = cv2.dilate(m.astype(np.uint8), k) > 0
    alt = [_measure_once(img, mm, *args, False)["median_px"] for mm in (er, di)]
    out["sensitivity_px"] = float(max(abs(v - out["median_px"]) for v in alt))
    out["max_gap_px"] = max_gap
    out["ok"] = bool(out.pop("enough_columns"))
    if out["ok"] and out["sensitivity_px"] > max_sensitivity_ratio * max(out["median_px"], 1e-6):
        out["ok"] = False
        out["reason"] = (f"depth {out['median_px']:.1f}px moves by {out['sensitivity_px']:.1f}px when the garment mask "
                         f"shifts one pixel: this is mask error, not a fringe")
    return out

def overlay(img, garment_mask, waist_px=None, **kw):
    """QA image: the measured thread pixels painted over the photo. Presentation only."""
    r = measure_fringe_depth(img, garment_mask, waist_px, return_mask=True, **kw)
    vis = img.copy(); vis[r["mask"]] = (0, 255, 255)
    return vis, {k: v for k, v in r.items() if k != "mask"}
