"""Feature-augmented registration: landmarks give a coarse after->before warp; SIFT matches inside the
garment (pockets, fly, stitching, fades) that are consistent with that warp are added as correspondences,
and the TPS is refit. Reduces the underdetermination when only ~6 landmarks survive the cut."""
import numpy as np, cv2
from .register import _tps, heldout_residual, SURVIVING

def feature_correspondences(after_img, before_img, after_mask, before_mask, lm_after, lm_before, max_pts=60, tol_frac=0.06, min_sep=12.0):
    names = [n for n in SURVIVING if n in lm_after and n in lm_before]
    a = np.array([lm_after[n] for n in names], np.float32); b = np.array([lm_before[n] for n in names], np.float32)
    coarse = _tps(a, b)                                      # after -> before
    sift = cv2.SIFT_create(4000)
    ga = cv2.cvtColor(after_img, cv2.COLOR_BGR2GRAY); gb = cv2.cvtColor(before_img, cv2.COLOR_BGR2GRAY)
    ka, da = sift.detectAndCompute(ga, after_mask.astype(np.uint8) * 255); kb, db = sift.detectAndCompute(gb, before_mask.astype(np.uint8) * 255)
    if da is None or db is None or len(ka) < 8 or len(kb) < 8: return np.zeros((0, 2)), np.zeros((0, 2))
    m = cv2.BFMatcher(cv2.NORM_L2).knnMatch(da, db, k=2)
    good = [p[0] for p in m if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if not good: return np.zeros((0, 2)), np.zeros((0, 2))
    pa = np.array([ka[g.queryIdx].pt for g in good], np.float32); pb = np.array([kb[g.trainIdx].pt for g in good], np.float32)
    _, pred = coarse.applyTransformation(pa[None]); pred = pred[0]
    scale = max(before_img.shape[:2]); ok = np.linalg.norm(pred - pb, axis=1) < tol_frac * scale   # consistent with the coarse warp
    pa, pb = pa[ok], pb[ok]
    # second pass: matches must agree with a locally-consistent (affine) mapping — kills residual mismatches
    if len(pa) >= 6:
        _, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=4.0)
        if inl is not None and inl.sum() >= 4: pa, pb = pa[inl.ravel() > 0], pb[inl.ravel() > 0]
    # drop near-duplicates (ill-conditioned TPS) and points within min_sep of a landmark
    keep_i = []
    for i in range(len(pb)):
        if all(np.linalg.norm(pb[i] - pb[j]) >= min_sep for j in keep_i) and np.min(np.linalg.norm(b - pb[i], axis=1)) >= min_sep: keep_i.append(i)
    pa, pb = pa[keep_i], pb[keep_i]
    if len(pa) > max_pts:                                    # spread them out: greedy farthest-point subsample
        sel = [int(np.argmin(pb[:, 1]))]
        d = np.linalg.norm(pb - pb[sel[0]], axis=1)
        while len(sel) < max_pts:
            i = int(np.argmax(d)); sel.append(i); d = np.minimum(d, np.linalg.norm(pb - pb[i], axis=1))
        pa, pb = pa[sel], pb[sel]
    return pa, pb

def warp_after_to_before_feat(after_img, after_mask, lm_after, lm_before, before_img, before_mask):
    names = [n for n in SURVIVING if n in lm_after and n in lm_before]
    a = np.array([lm_after[n] for n in names], np.float32); b = np.array([lm_before[n] for n in names], np.float32)
    fa, fb = feature_correspondences(after_img, before_img, after_mask, before_mask, lm_after, lm_before)
    A = np.concatenate([a, fa]).astype(np.float32); B = np.concatenate([b, fb]).astype(np.float32)
    H, W = before_img.shape[:2]
    t_b2a = _tps(B, A)
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32)); pts = np.stack([gx.ravel(), gy.ravel()], 1); out = np.empty_like(pts)
    for i in range(0, len(pts), 200_000):
        _, mm = t_b2a.applyTransformation(pts[i:i + 200_000][None]); out[i:i + 200_000] = mm[0]
    mx, my = out[:, 0].reshape(H, W), out[:, 1].reshape(H, W)
    warped = cv2.remap(after_img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    wmask = cv2.remap((np.asarray(after_mask) > 0).astype(np.uint8) * 255, mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT) > 127
    # held-out residual over the LANDMARKS only (features stay in the fit): how well does the augmented warp predict each landmark?
    errs = []
    for i in range(len(a)):
        keep = np.ones(len(A), bool); keep[i] = False
        t = _tps(A[keep], B[keep]); _, pred = t.applyTransformation(a[i:i + 1][None]); errs.append(float(np.linalg.norm(pred[0][0] - b[i])))
    return warped, wmask, float(np.mean(errs)), len(fa)
