"""Geometric consistency of a landmark set, before it reaches the canonical map.

Two severities, because they have different causes and different remedies:

  inverted   a strict ordering the garment cannot violate is violated (the crotch ABOVE the
             hips, the legs swapped at the hem). Nothing downstream can repair this; the
             landmark set describes a garment that does not exist.
  degenerate two landmarks that should be separated coincide (or nearly). The garment is fine;
             the extractor collapsed a region to zero height or zero width. A thin-plate spline
             fitted through coincident correspondences folds -- this is the same defect
             EXP_0031 found downstream in warp.py, seen here at its source.

`tol_frac` is a fraction of the landmark-set bounding-box diagonal; pairs closer than that
count as degenerate. 0.01 matches warp.py's `min_sep_frac`, so what this reports as degenerate
is what warp.py would drop.
"""
import numpy as np

# (a, b, axis, why) -- expected a strictly before b along axis
_ORDER = [
    ("waist_left",      "waist_right",     "x", "waist left/right swapped"),
    ("hip_left",        "hip_right",       "x", "hip left/right swapped"),
    ("hem_left_outer",  "hem_left_inner",  "x", "left leg inside-out"),
    ("hem_right_inner", "hem_right_outer", "x", "right leg inside-out"),
    ("hem_left_inner",  "hem_right_inner", "x", "legs swapped at the hem"),
    ("waist_left",      "hip_left",        "y", "hips above the waist"),
    ("hip_left",        "crotch",          "y", "crotch above the hips"),
    ("crotch",          "hem_left_outer",  "y", "left hem above the crotch"),
    ("crotch",          "hem_right_outer", "y", "right hem above the crotch"),
]


def check_landmarks(lm, tol_frac=0.01):
    """Return a list of {pair, axis, why, severity, gap_px} for a name -> (x, y) dict.

    Empty list means the set is geometrically consistent. Landmarks that are absent are
    skipped, not reported: a missing knee is normal on shorts.
    """
    pts = {k: v for k, v in lm.items() if v is not None and k != "confidence"}
    if len(pts) < 2:
        return []
    a = np.array([[float(p[0]), float(p[1])] for p in pts.values()])
    span = float(np.linalg.norm(a.max(axis=0) - a.min(axis=0))) or 1.0
    tol = tol_frac * span
    out = []
    for na, nb, axis, why in _ORDER:
        if na not in pts or nb not in pts:
            continue
        i = 0 if axis == "x" else 1
        gap = float(pts[nb][i]) - float(pts[na][i])          # expected strictly positive
        if gap < -tol:
            sev = "inverted"
        elif gap <= tol:
            sev = "degenerate"
        else:
            continue
        out.append({"pair": (na, nb), "axis": axis, "why": why,
                    "severity": sev, "gap_px": round(gap, 2)})
    return out


def worst_severity(findings):
    """'inverted' > 'degenerate' > None, for a single go/no-go decision."""
    if any(f["severity"] == "inverted" for f in findings):
        return "inverted"
    if findings:
        return "degenerate"
    return None
