"""Geometry metrics (plan §6.1). All distances in mm when mm_per_px is given, else px."""
import numpy as np
from scipy.spatial import cKDTree

def _scale(x, mm_per_px): return x * (mm_per_px or 1.0)

def cut_line_error(pred_line, real_line, mm_per_px=None):
    """Mean perpendicular distance from real hem points to the predicted cut polyline.
    Lines are Nx2 arrays of (x, y) pixel coordinates."""
    d, _ = cKDTree(densify(pred_line)).query(np.asarray(real_line, float))
    return float(_scale(d.mean(), mm_per_px))

def densify(polyline, step=0.5):
    """Resample an Nx2 polyline so consecutive points are ≤ `step` px apart."""
    pts = np.asarray(polyline, float)
    out = []
    for a, b in zip(pts[:-1], pts[1:]):
        n = max(int(np.ceil(np.linalg.norm(b - a) / step)), 1)
        out.append(a + (b - a) * np.linspace(0, 1, n, endpoint=False)[:, None])
    out.append(pts[-1:])
    return np.concatenate(out)

def inseam_error(pred_inseam_cm, real_inseam_cm):
    return float(pred_inseam_cm - real_inseam_cm)

def silhouette_iou(pred_mask, real_mask):
    p, r = np.asarray(pred_mask, bool), np.asarray(real_mask, bool)
    u = (p | r).sum()
    return float((p & r).sum() / u) if u else 1.0

def boundary_chamfer(pred_boundary, real_boundary, mm_per_px=None):
    """Symmetric mean nearest-neighbour distance between two boundary point sets (Nx2)."""
    a, b = np.asarray(pred_boundary, float), np.asarray(real_boundary, float)
    d_ab, _ = cKDTree(b).query(a); d_ba, _ = cKDTree(a).query(b)
    return float(_scale(0.5 * (d_ab.mean() + d_ba.mean()), mm_per_px))

def landmark_displacement(pred_landmarks, real_landmarks, mm_per_px=None):
    """Per-landmark distance. Dicts name -> (x, y). Returns {name: dist}."""
    return {k: float(_scale(np.linalg.norm(np.subtract(pred_landmarks[k], real_landmarks[k])), mm_per_px))
            for k in pred_landmarks if k in real_landmarks}

def mask_boundary(mask):
    """Boundary pixels of a binary mask as Nx2 (x, y)."""
    from skimage.segmentation import find_boundaries
    ys, xs = np.nonzero(find_boundaries(np.asarray(mask, bool), mode="inner"))
    return np.stack([xs, ys], 1)

def symmetry_error(left_hem_y, right_hem_y, mm_per_px=None):
    """Difference in hem height between legs for a symmetric cut request."""
    return float(_scale(abs(np.mean(left_hem_y) - np.mean(right_hem_y)), mm_per_px))


def hem_zone(keep, garment_before, band_px=40):
    """Region where hem geometry lives: below the cut (within the original garment) plus a band above the cut."""
    import cv2
    d = cv2.distanceTransform(np.asarray(keep, np.uint8), cv2.DIST_L2, 3)
    return (~keep & garment_before) | (keep & (d <= band_px))

def hem_chamfer(pred_sil, real_sil, keep, garment_before, band_px=40, mm_per_px=None):
    """Hem profile error: per column, |lowest predicted garment pixel - lowest real garment pixel|, averaged over
    columns where both exist below the waist. A 40 px hem error reads as ~40, not averaged away over the outline."""
    p = np.asarray(pred_sil, bool); r = np.asarray(real_sil, bool)
    cols = np.nonzero(p.any(axis=0) & r.any(axis=0))[0]
    if len(cols) == 0: return float("nan")
    H = p.shape[0]; idx = np.arange(H)[:, None]
    bp = np.where(p[:, cols], idx, -1).max(axis=0); br = np.where(r[:, cols], idx, -1).max(axis=0)
    e = np.abs(bp - br).astype(float)
    return float(e.mean() * (mm_per_px or 1.0))

def fringe_iou(pred_sil, real_sil, keep, garment_before):
    """IoU of predicted vs real garment pixels BELOW the cut. pred_sil must only include fringe pixels that are
    mostly thread (coverage > 0.5) — see rawedge_v1 — otherwise an opaque block games it."""
    return silhouette_iou(pred_sil & ~keep & garment_before, real_sil & ~keep & garment_before)

def fringe_profile_distance(pred_img, real_img, keep, garment_before, removed, background, n_bins=10):
    """Coverage-vs-distance profile distance: mean |coverage_pred(d) - coverage_real(d)| over distance-from-cut bins,
    where coverage = fraction of pixels that differ from the background colour by > 25 (BGR L1/3). Appearance-based;
    not gamed by an opaque block (which has coverage 1 everywhere)."""
    import cv2
    d = cv2.distanceTransform((~keep).astype(np.uint8), cv2.DIST_L2, 3)
    zone = removed & garment_before
    def cov(img):
        diff = np.abs(img.astype(int) - np.asarray(background, int)[None, None, :]).mean(axis=2) > 25
        return diff
    cp, cr = cov(pred_img), cov(real_img)
    dmax = max(float(d[zone].max()) if zone.any() else 1.0, 1.0); edges = np.linspace(0, dmax, n_bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        b = zone & (d >= lo) & (d < hi)
        if b.sum() < 20: continue
        out.append(abs(cp[b].mean() - cr[b].mean()))
    return float(np.mean(out)) if out else float("nan")


def fringe_profile_distance_masks(pred_sil, real_sil, keep, garment_before, n_bins=10):
    """Mask-based coverage profile: per distance-from-cut bin (below the cut, inside the original garment),
    |fraction predicted-garment − fraction real-garment|, averaged. 0 = same fringe extent profile."""
    import cv2
    d = cv2.distanceTransform((~np.asarray(keep, bool)).astype(np.uint8), cv2.DIST_L2, 3)
    zone = ~np.asarray(keep, bool) & np.asarray(garment_before, bool)
    if not zone.any(): return float("nan")
    dmax = max(float(d[zone].max()), 1.0); edges = np.linspace(0, dmax, n_bins + 1); out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        b = zone & (d >= lo) & (d < hi)
        if b.sum() < 20: continue
        out.append(abs(np.asarray(pred_sil, bool)[b].mean() - np.asarray(real_sil, bool)[b].mean()))
    return float(np.mean(out)) if out else float("nan")
