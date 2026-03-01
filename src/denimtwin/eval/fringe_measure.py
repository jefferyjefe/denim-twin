"""Direct measurement of raw-edge fringe depth from a flat-lay photo (plan §4.7 / §6.3).

Why not SAM: `seg.segment_fringe` prompts SAM with a band at the hem and takes the returned mask as "fringe". On real
after-wash photos of cut-offs it returns whole regions of *fabric* (measured 15–21% of garment height on four
harvested photos, EXP_0015), which is why `run_pair` has a plausibility gate that rejects it. The threads themselves
lie OUTSIDE the coarse garment mask — SAM's garment mask stops at the solid fabric edge — so they can be measured
directly, per column, in the strip just below that edge.

Method, per column x:
  * y0 = the lowest garment-mask row (the solid fabric edge),
  * a background model (median, sd in Lab) from the deepest quarter of a search band below y0,
  * a pixel is *thread* if it is at least as light as that backdrop (z_L > 0.8) or clearly off-hue (chroma z > 3),
    AND overall far from it (‖z‖ > 2.5). The lightness condition is what separates threads from the garment's own
    drop shadow, which is otherwise the dominant false positive (it inflated depth ~3x in the first prototype),
  * depth = the deepest thread pixel still connected to the fabric edge through gaps of at most `max_gap` px.

Output is scale-free (depth / waistband width) so it is commensurable across photos with no metric scale, exactly as
the fringe prior requires. Nothing here is fitted to data; the thresholds are fixed and stated.
"""
import numpy as np
import cv2

DEFAULTS = dict(band_frac=0.12, max_gap=3, light_z=0.8, chroma_z=3.0, dist_z=2.5, min_columns=20)

def measure_fringe_depth(img, garment_mask, waist_px=None, band_frac=DEFAULTS["band_frac"], max_gap=DEFAULTS["max_gap"],
                         light_z=DEFAULTS["light_z"], chroma_z=DEFAULTS["chroma_z"], dist_z=DEFAULTS["dist_z"],
                         min_columns=DEFAULTS["min_columns"], return_mask=False):
    """Return a dict with median/mean/p90 fringe depth in px (and relative to `waist_px` if given), the fraction of
    garment columns that show any fringe, and optionally the boolean thread mask.
    `garment_mask` must be the SOLID fabric mask (threads excluded) — the coarse SAM mask is exactly that."""
    m = np.asarray(garment_mask, bool)
    H, W = m.shape
    band = int(round(band_frac * (waist_px if waist_px else 0.5 * W)))
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    depths, cols = [], 0
    tmask = np.zeros((H, W), bool) if return_mask else None
    for x in range(W):
        col = np.nonzero(m[:, x])[0]
        if not len(col): continue
        y0 = int(col.max()); lo = min(y0 + band + 1, H)
        if lo - y0 < 8: continue
        cols += 1
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
           "ok": bool(len(depths) >= min_columns)}
    if waist_px: out["depth_rel"] = out["median_px"] / float(waist_px)
    if return_mask: out["mask"] = tmask
    return out

def overlay(img, garment_mask, waist_px=None, **kw):
    """QA image: the measured thread pixels painted over the photo. Presentation only."""
    r = measure_fringe_depth(img, garment_mask, waist_px, return_mask=True, **kw)
    vis = img.copy(); vis[r["mask"]] = (0, 255, 255)
    return vis, {k: v for k, v in r.items() if k != "mask"}
