"""Hem roughness — a fray signal that survives its negative control (plan §6.3).

EXP_0015 showed that fringe *depth* measured from a flat-lay photo cannot separate a frayed hem from a cuffed one:
the depth we measure is dominated by garment-mask boundary error, and EXP_0016 showed that error grows with image
resolution about as fast as the signal does, so a bigger photo does not rescue it.

Roughness is a different observable with a better asymmetry. A finished hem (cuffed, sewn, serged) is a smooth curve:
its mask boundary is locally flat at pixel scale whatever the resolution. A frayed hem is jagged — threads and notches
push the boundary up and down by a few pixels within a few pixels of run. So instead of asking "how deep is the
fringe", ask "how far does the hem boundary deviate from its own local median".

    y(x)        = lowest garment-mask row in column x, over the hem region (lower part of the garment)
    smooth(x)   = median of y over a window of `window_frac` of the waist width
    residual(x) = |y(x) - smooth(x)|
    roughness   = the p90 of residual (px), and its mean; both also reported relative to waist width

On the 21 photos available on 2026-08-29 — 8 frayed, 13 finished-hem controls including 9 at 2048–2500 px — the p90 was
0 px on every control whose mask passed the quality gate (11/11) and non-zero on 6 of 8 frayed garments. The two
controls that read "frayed" both had visibly broken segmentation masks, which the compactness gate now refuses; that
gate is the load-bearing part, and its margin on this data is 2.10 (worst good mask) against 3.96 (best broken one).
See EXP_0016 for what this does and does not establish. No parameter here is fitted: the window, hem region and
compactness bound were each chosen from an inspected failure and then left alone.
"""
import numpy as np
import cv2
from scipy.ndimage import median_filter

DEFAULTS = dict(window_frac=0.06, hem_region=0.6, min_columns=50, solid_frac=0.02, max_compactness=3.0)

def mask_compactness(garment_mask):
    """perimeter^2 / (4*pi*area) of the largest connected component: 1.0 for a disc, ~1.5-2.1 for a clean garment
    silhouette (measured over 21 real photos), and much higher for a speckled or torn segmentation whose outline
    wanders. This is the only reliable separator we found between "this hem is frayed" and "this mask is broken":
    the two false positives among nine high-resolution finished-hem controls scored 3.96 and 4.05, against <= 2.10
    for every other photo in the set, frayed or finished (EXP_0016 addendum)."""
    u = np.asarray(garment_mask, bool).astype(np.uint8)
    cnts, _ = cv2.findContours(u, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts: return float("inf")
    c = max(cnts, key=cv2.contourArea); area = cv2.contourArea(c)
    if area < 1: return float("inf")
    return float(cv2.arcLength(c, True) ** 2 / (4 * np.pi * area))


def hem_profile(garment_mask, hem_region=DEFAULTS["hem_region"], solid_px=0):
    """(x, y) of the garment's lower boundary in the hem region: for each column, the lowest mask row, kept only where
    that row lies in the bottom `1 - hem_region` of the garment's vertical extent (so side seams and the waistband,
    whose 'lowest row' is the hem anyway, do not dominate).

    `solid_px` drops columns whose mask is not unbroken for that many pixels above the lowest row. Speckled masks —
    SAM sometimes drops holes in a strongly patterned or shadowed leg — otherwise present a ragged lower boundary that
    reads exactly like fray: 2 of 9 high-resolution FINISHED-hem controls were called frayed for this reason
    (EXP_0016 addendum). A real hem boundary has solid fabric above it."""
    m = np.asarray(garment_mask, bool)
    xs = [x for x in range(m.shape[1]) if m[:, x].any()]
    if not xs: return np.array([]), np.array([])
    y = np.array([np.nonzero(m[:, x])[0].max() for x in xs], float)
    rows = np.nonzero(m.any(axis=1))[0]
    lo = rows.min() + hem_region * (rows.max() - rows.min())
    keep = y > lo
    if solid_px >= 1:
        k = int(solid_px)
        solid = np.array([m[max(int(yy) - k, 0):int(yy) + 1, x].all() for x, yy in zip(xs, y)])
        keep &= solid
    return np.array(xs)[keep], y[keep]

def hem_roughness(garment_mask, waist_px=None, window_frac=DEFAULTS["window_frac"],
                  hem_region=DEFAULTS["hem_region"], min_columns=DEFAULTS["min_columns"],
                  solid_frac=DEFAULTS["solid_frac"], max_compactness=DEFAULTS["max_compactness"]):
    """Roughness of the hem boundary. Returns p90/mean absolute residual in px (and relative to `waist_px`),
    plus the fraction of hem columns that deviate at all. Columns whose mask is not solid for `solid_frac` of the
    waist width above the boundary are dropped (see `hem_profile`)."""
    _w = waist_px if waist_px else 0.5 * np.asarray(garment_mask).shape[1]
    comp = mask_compactness(garment_mask)
    x, y = hem_profile(garment_mask, hem_region, solid_px=max(round(solid_frac * _w), 2))
    out = {"n_columns": int(len(y)), "ok": bool(len(y) >= min_columns), "compactness": comp,
           "p90_px": 0.0, "mean_px": 0.0, "rough_fraction": 0.0}
    if comp > max_compactness:
        # a broken mask has a ragged outline that is indistinguishable from fray. Refuse rather than guess.
        out.update(ok=False, reason=f"mask outline too ragged to judge (compactness {comp:.2f} > {max_compactness})")
        return out
    if len(y) < min_columns:
        out["reason"] = f"only {len(y)} usable hem columns"
        return out
    w = _w
    k = int(max(round(window_frac * w), 5)) | 1
    k = min(k, (len(y) - 1) | 1)
    if k < 3: return out
    r = np.abs(y - median_filter(y, size=k, mode="nearest"))
    out.update(p90_px=float(np.percentile(r, 90)), mean_px=float(r.mean()),
               rough_fraction=float((r > 0).mean()), window_px=int(k))
    if waist_px:
        out["p90_rel"] = out["p90_px"] / float(waist_px)
        out["mean_rel"] = out["mean_px"] / float(waist_px)
    return out
