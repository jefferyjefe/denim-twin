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

On the 12 photos available on 2026-08-29 the p90 was exactly 0 px on all four finished-hem controls (waist 241–914 px)
and 0–9 px on the eight frayed garments. That is a real separation but a small sample with an unbalanced resolution
range; see EXP_0016 for what it does and does not establish. Nothing here is fitted to that data — the only parameters
are the window and the hem region, both fixed and stated.
"""
import numpy as np
from scipy.ndimage import median_filter

DEFAULTS = dict(window_frac=0.06, hem_region=0.6, min_columns=50)

def hem_profile(garment_mask, hem_region=DEFAULTS["hem_region"]):
    """(x, y) of the garment's lower boundary in the hem region: for each column, the lowest mask row, kept only where
    that row lies in the bottom `1 - hem_region` of the garment's vertical extent (so side seams and the waistband,
    whose 'lowest row' is the hem anyway, do not dominate)."""
    m = np.asarray(garment_mask, bool)
    xs = [x for x in range(m.shape[1]) if m[:, x].any()]
    if not xs: return np.array([]), np.array([])
    y = np.array([np.nonzero(m[:, x])[0].max() for x in xs], float)
    rows = np.nonzero(m.any(axis=1))[0]
    lo = rows.min() + hem_region * (rows.max() - rows.min())
    keep = y > lo
    return np.array(xs)[keep], y[keep]

def hem_roughness(garment_mask, waist_px=None, window_frac=DEFAULTS["window_frac"],
                  hem_region=DEFAULTS["hem_region"], min_columns=DEFAULTS["min_columns"]):
    """Roughness of the hem boundary. Returns p90/mean absolute residual in px (and relative to `waist_px`),
    plus the fraction of hem columns that deviate at all."""
    x, y = hem_profile(garment_mask, hem_region)
    out = {"n_columns": int(len(y)), "ok": bool(len(y) >= min_columns),
           "p90_px": 0.0, "mean_px": 0.0, "rough_fraction": 0.0}
    if len(y) < min_columns: return out
    w = waist_px if waist_px else 0.5 * np.asarray(garment_mask).shape[1]
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
