"""Template v1 (Phase 3): a jeans outline polygon with a fixed vertex topology (the 13 canonical outline landmarks),
initialised from the heuristic landmarks and refined to the silhouette by minimising the boundary Chamfer distance
plus a shape prior (deviation from the canonical proportions, scaled to the garment). Unlike v0, every vertex is a
landmark, so the fit directly yields landmark coordinates, and the loss is on the boundary (where landmarks live),
not on area."""
import numpy as np, cv2
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from .landmarks import CANONICAL
OUTLINE = ["waist_left", "waist_right", "hip_right", "knee_right_outer", "hem_right_outer", "hem_right_inner", "knee_right_inner",
           "crotch", "knee_left_inner", "hem_left_inner", "hem_left_outer", "knee_left_outer", "hip_left"]

def _boundary_pts(mask, step=3):
    from skimage.segmentation import find_boundaries
    ys, xs = np.nonzero(find_boundaries(mask, mode="inner")); pts = np.stack([xs, ys], 1).astype(np.float32)
    return pts[::step]

def _poly_samples(verts, n_per_edge=12):
    out = []
    for a, b in zip(verts, np.roll(verts, -1, axis=0)):
        t = np.linspace(0, 1, n_per_edge, endpoint=False)[:, None]; out.append(a + (b - a) * t)
    return np.concatenate(out)

def fit(mask, init_landmarks, prior_weight=0.05, iters=60):
    """init_landmarks: dict with the OUTLINE names (e.g. from autolm). Returns (landmarks dict, residual px, verts)."""
    m = mask.astype(bool); bpts = _boundary_pts(m); tree = cKDTree(bpts)
    v0 = np.array([init_landmarks[n] for n in OUTLINE], np.float32)
    ys, xs = np.nonzero(m); h = float(ys.max() - ys.min()); w = float(xs.max() - xs.min())
    canon = np.array([CANONICAL[n] for n in OUTLINE], np.float32) * np.array([w, h], np.float32)   # canonical proportions at garment scale
    canon -= canon.mean(0); 
    def resid(x):
        v = x.reshape(-1, 2)
        s = _poly_samples(v); d, _ = tree.query(s)                          # polygon -> mask boundary
        d2, _ = cKDTree(s).query(bpts[::4])                                 # mask boundary -> polygon (symmetric)
        shape = ((v - v.mean(0)) - canon).ravel() * prior_weight             # stay near canonical proportions
        return np.concatenate([d, 0.5 * d2, shape])
    res = least_squares(resid, v0.ravel(), method="trf", max_nfev=iters, loss="soft_l1", f_scale=5.0)
    v = res.x.reshape(-1, 2); d, _ = tree.query(_poly_samples(v))
    lm = {n: (float(x), float(y)) for n, (x, y) in zip(OUTLINE, v)}
    lm["waist_center"] = ((lm["waist_left"][0] + lm["waist_right"][0]) / 2, (lm["waist_left"][1] + lm["waist_right"][1]) / 2)
    return lm, float(d.mean()), v
