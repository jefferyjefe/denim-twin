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

**What p90 == 0 does and does not mean.** p90 of an integer residual is 0 whenever fewer than 10% of hem columns
deviate at all, at any depth (review 6: 8 px notches on 5% and 8% of columns both give p90 0). So a zero is "no
widespread deviation", not "provably a finished hem" — `rough_fraction` is the companion number and separates those
cases (0.009 vs 0.075). Both are reported; neither is a fray classifier on its own.

**What it responds to.** A hem that deviates from its own local median over a window of 6% of waist width. A smooth
but *decorative* hem (scallops with a period near that window) reads as fray at 1–2 px, inside the range real frayed
garments measure. It is a spatial-frequency statistic, not a fray detector, and it is only meaningful on a mask that
has been verified to be the garment (EXP_0018/0019).

Measured on the photos available 2026-08-29 with consensus segmentation: p90 > 0 on 0 of 9 high-resolution
finished-hem controls and 4 of 7 frayed garments.
"""
import numpy as np
import cv2
from scipy.ndimage import median_filter

DEFAULTS = dict(window_frac=0.06, hem_region=0.6, min_columns=50, solid_frac=0.02, max_compactness=None)

def mask_compactness(garment_mask):
    """perimeter^2 / (4*pi*area) of the largest connected component. Reported for information; **not a validity test**.

    It was briefly used as one, because the two broken masks among nine high-resolution controls scored 3.96 and 4.05
    against <= 2.10 for every good mask in that set. Review 6 showed that is a coincidence of garment shape: an exact,
    noise-free silhouette scores 2.33 for shorts, **3.95 for full-length jeans** and 4.72 for skinny jeans, so the
    threshold refuses the project's own subject; and because a frayed outline is longer, compactness rises with fray
    depth (2.33 -> 4.13 as notch depth goes 0 -> 16 px), making the gate a fray-depth cutoff that silently zeroes the
    deepest frays. Mask validity comes from consensus segmentation (`seg/validate.segment_garment_consensus`) and
    human verification (`data/external/mask_verdicts.json`) instead."""
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
    if max_compactness is not None and comp > max_compactness:
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
