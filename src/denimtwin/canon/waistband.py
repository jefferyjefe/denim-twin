"""The garment's top edge, as a correspondence registration can be given.

`register.SURVIVING` tops out at the waist landmarks, which `autolm` places 2% of the garment
height *below* the top edge. Everything above them is thin-plate-spline extrapolation constrained
by no correspondence at all, and EXP_0040 measured what that costs: the registered after-garment's
top lands below the prediction's on 7 of 7 pairs (p = 0.0156, median +14 px), and the displacement
tracks registration residual (r = +0.781) and waistband IoU (r = -0.646).

The waistband edge is the obvious candidate correspondence: cutting the legs does not touch it, and
it is the one horizontal edge `autolm` already has to find (to place the waist landmarks at all).
This module exposes that row and its two corners so an experiment can test whether adding them to
the landmark set helps -- WITHOUT changing what `autolm.landmarks_from_mask` returns. Adding keys
to that dict would change `len(lmb)` and flip `run_pair.py`'s `>= 14` landmark-refinement branch,
so a measurement of the correspondence would also be a change of the thing being measured.

`clean_mask` and `top_edge_row` are `autolm`'s own steps, moved here so there is one implementation
rather than two that can drift; `autolm` calls them. `tests/test_waistband.py` pins the landmarks
of every real pair mask against `landmarks.json` to show the move changed nothing.
"""
import numpy as np, cv2

NAMES = ("waistband_left", "waistband_center", "waistband_right")

def clean_mask(mask):
    """Drop thin protrusions (hanger hooks, loose threads) before measuring a horizontal edge.

    Falls back to the raw mask when the opening eats more than half of it -- a thin garment on a
    wide frame, where the structuring element is larger than the thing it is cleaning."""
    m0 = np.asarray(mask).astype(bool)
    if not m0.any():
        return m0
    k = max(int(0.03 * m0.shape[1]), 3)
    m = cv2.morphologyEx(m0.astype(np.uint8), cv2.MORPH_OPEN, np.ones((k, k), np.uint8)).astype(bool)
    return m0 if m.sum() < 0.5 * m0.sum() else m


def top_edge_row(m):
    """Row index of the garment's top edge in a cleaned mask.

    Two rules, and it is worth knowing which one actually runs. The first looks for a horizontal
    edge: the LAST row in the top 30% whose width jumps by >= 30% of the reference width relative to
    the row above, on the reasoning that a hanger hook or a triangle of fabric above the waistband
    widens gradually and produces no such jump. The second is the fallback for a garment with no
    such edge -- the first row reaching half the reference width.

    On this project's data the FALLBACK is the normal path: the jump rule fires on 6% of the masks
    in `experiments/` (193 of 3240) and on 3 of the 26 masks in `experiments/pairs`. A real flat-lay
    photograph almost never presents a step change in width at the waistband, because the first
    nonzero row is a few dozen pixels of a corner rather than a full waistband. Both EXP_0040 and
    the first draft of EXP_0041 described the jump rule as *the* detector; it is the minority case.
    `tests/test_waistband.py` measures the split rather than restating it."""
    ys = np.nonzero(m.any(axis=1))[0]
    if not len(ys):
        raise ValueError("empty mask")
    widths = m.sum(axis=1)
    bot, y0 = int(ys.max()), int(ys.min())
    n30 = max(int(0.30 * (bot - y0)), 3)
    top30 = widths[y0: y0 + n30].astype(int)
    wref = top30.max()
    prev = np.concatenate([[0], top30[:-1]])
    jumps = np.nonzero(top30 - prev >= 0.3 * wref)[0]
    if len(jumps):
        return int(y0 + jumps.max())
    return int(y0 + np.nonzero(top30 >= 0.5 * wref)[0].min())


def waistband_corners(mask, tol=10):
    """The three points on the top edge: (left, centre, right), or None if the row is unusable.

    Returns a dict with the same shape as `autolm`'s output so it can be merged into a landmark
    dict for a registration A/B. These are NOT emitted by `landmarks_from_mask` -- see the module
    docstring for why.

    `tol` is defensive only. Both branches of `top_edge_row` return a row whose width is at least
    30% of the reference width, so `m[top]` is never empty and the scan returns at `dy == 0` on
    every mask in this repository -- it exists so a future top-edge rule that can return a ragged
    row does not silently index nothing. The corners are the extremes of the first usable row at or
    below the top edge, so the two photographs of one garment measure the same physical edge."""
    m = clean_mask(mask)
    if not m.any():
        return None
    top = top_edge_row(m)
    H = m.shape[0]
    for dy in range(0, tol + 1):
        y = min(top + dy, H - 1)
        xs = np.nonzero(m[y])[0]
        if len(xs):
            return {"waistband_left": (int(xs.min()), int(y)),
                    "waistband_center": (int((xs.min() + xs.max()) // 2), int(y)),
                    "waistband_right": (int(xs.max()), int(y))}
    return None
