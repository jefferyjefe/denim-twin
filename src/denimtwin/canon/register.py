"""Register a post-modification capture into the before-capture's image frame.

Both photos are flat-lays of the same garment, re-laid between captures, so the mapping is a
smooth non-rigid warp. We use the landmarks that survive the cut (waist, hips, crotch, knees if
above the cut) to fit a TPS from the AFTER image to the BEFORE image, then refine with ECC on the
kept region. Returns the warped after-image, its garment mask in the before frame, and a
registration-quality score (mean landmark residual in px after warp)."""
import numpy as np, cv2

SURVIVING = ["waist_left", "waist_center", "waist_right", "hip_left", "hip_right", "crotch",
             "knee_left_outer", "knee_left_inner", "knee_right_inner", "knee_right_outer"]

def _tps(src_pts, dst_pts):
    t = cv2.createThinPlateSplineShapeTransformer()
    m = [cv2.DMatch(i, i, 0) for i in range(len(src_pts))]
    # OpenCV: estimateTransformation(X, Y) -> applyTransformation maps X-coords to Y-coords (same as warp.py)
    t.estimateTransformation(np.asarray(src_pts, np.float32)[None], np.asarray(dst_pts, np.float32)[None], m)
    return t

def warp_after_to_before(after_img, after_mask, lm_after, lm_before, before_shape, use=SURVIVING):
    names = [n for n in use if n in lm_after and n in lm_before]
    assert len(names) >= 4, "need >=4 shared landmarks"
    a = np.array([lm_after[n] for n in names], np.float32); b = np.array([lm_before[n] for n in names], np.float32)
    H, W = before_shape[:2]
    # for each BEFORE pixel, where does it come from in AFTER? -> TPS mapping before->after
    t_b2a = _tps(b, a)   # applyTransformation maps before coords -> after coords
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    pts = np.stack([gx.ravel(), gy.ravel()], 1); out = np.empty_like(pts)
    for i in range(0, len(pts), 200_000):
        _, m = t_b2a.applyTransformation(pts[i:i + 200_000][None]); out[i:i + 200_000] = m[0]
    mx, my = out[:, 0].reshape(H, W), out[:, 1].reshape(H, W)
    warped = cv2.remap(after_img, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    wmask = cv2.remap(after_mask.astype(np.uint8) * 255, mx, my, cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT) > 127
    # residual: LEAVE-ONE-OUT — fit the TPS without landmark i, map it, compare to its true position.
    # (The in-sample residual is ~0 by construction and says nothing.)
    resid = heldout_residual(a, b)
    return warped, wmask, resid

def heldout_residual(a, b):
    """Mean leave-one-landmark-out prediction error (px) of the after->before TPS. Needs >= 5 landmarks; else nan."""
    a = np.asarray(a, np.float32); b = np.asarray(b, np.float32); n = len(a)
    if n < 5: return float("nan")
    errs = []
    for i in range(n):
        keep = np.arange(n) != i
        t = _tps(a[keep], b[keep]); _, pred = t.applyTransformation(a[i:i + 1][None])
        errs.append(float(np.linalg.norm(pred[0][0] - b[i])))
    return float(np.mean(errs))

def refine_ecc(before_gray, warped_gray, keep_mask, iters=50):
    """Optional affine ECC refinement restricted to the unchanged region. Returns 2x3 warp or None."""
    try:
        m = (keep_mask.astype(np.uint8) * 255)
        crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, iters, 1e-5)
        warp = np.eye(2, 3, dtype=np.float32)
        cv2.findTransformECC(before_gray, warped_gray, warp, cv2.MOTION_AFFINE, crit, m, 5)
        return warp
    except cv2.error:
        return None
