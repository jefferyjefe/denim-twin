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
