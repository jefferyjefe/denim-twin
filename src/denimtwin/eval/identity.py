"""Identity-preservation metrics (plan §6.2). Evaluated ONLY inside `keep_mask`
(the region that should be unchanged)."""
import numpy as np
import cv2
from skimage.metrics import structural_similarity

def _masked_bbox(mask):
    ys, xs = np.nonzero(mask)
    return slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1)

def unchanged_ssim(pred, orig, keep_mask):
    """SSIM over the unchanged region (mean of per-pixel SSIM map inside mask)."""
    keep = np.asarray(keep_mask, bool)
    ys, xs = _masked_bbox(keep)
    # neutralise the modified region so SSIM windows straddling the keep boundary don't leak it
    p2 = pred.copy(); p2[~keep] = orig[~keep]
    a = cv2.cvtColor(p2[ys, xs], cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(orig[ys, xs], cv2.COLOR_BGR2GRAY)
    _, smap = structural_similarity(a, b, full=True, data_range=255)
    return float(smap[keep[ys, xs]].mean())

def unchanged_color_delta_e(pred, orig, keep_mask):
    """Mean CIE76 ΔE in the unchanged region (BGR uint8 inputs)."""
    keep = np.asarray(keep_mask, bool)
    # float input -> true CIE L*a*b* (L in 0..100); uint8 input would give L*2.55 and a/b+128
    la = cv2.cvtColor(pred.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB).astype(float)
    lb = cv2.cvtColor(orig.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB).astype(float)
    d = np.linalg.norm(la - lb, axis=2)
    return float(d[keep].mean())

def changed_pixel_fraction_outside(pred, orig, keep_mask, thresh=8):
    """Fraction of unchanged-region pixels that differ by more than `thresh` (max channel abs diff).
    Zero means the system touched nothing it shouldn't have."""
    keep = np.asarray(keep_mask, bool)
    diff = np.abs(pred.astype(int) - orig.astype(int)).max(axis=2)
    return float((diff[keep] > thresh).mean())

def feature_retention(pred, orig, keep_mask, ratio=0.75, max_shift_px=5.0):
    """Fraction of ORB keypoints in the original's unchanged region that find a ratio-test
    match in the prediction AT (nearly) THE SAME LOCATION (within max_shift_px).
    Proxy for logo/stitch/pocket preservation that a translated/warped garment cannot game."""
    keep = (np.asarray(keep_mask, bool) * 255).astype(np.uint8)
    orb = cv2.ORB_create(2000)
    k1, d1 = orb.detectAndCompute(orig, keep)
    k2, d2 = orb.detectAndCompute(pred, keep)
    if d1 is None or d2 is None or len(k1) == 0:
        return 0.0
    m = cv2.BFMatcher(cv2.NORM_HAMMING).knnMatch(d1, d2, k=2)
    good = 0
    for pair in m:
        if len(pair) == 2 and pair[0].distance < ratio * pair[1].distance:
            a, b = k1[pair[0].queryIdx].pt, k2[pair[0].trainIdx].pt
            if np.hypot(a[0] - b[0], a[1] - b[1]) <= max_shift_px: good += 1
    return float(good / len(k1))

def diff_map(pred, orig, thresh=8):
    """Boolean map of pixels the system changed. Shown to users alongside the render."""
    return np.abs(pred.astype(int) - orig.astype(int)).max(axis=2) > thresh


def match_lighting(src, ref, mask):
    """Return `src` with per-channel Lab mean/std inside `mask` matched to `ref`'s. Use before comparing a
    re-photographed garment to the original so SSIM/ΔE reflect the garment, not the lighting."""
    m = np.asarray(mask, bool)
    if m.sum() < 100: return src.copy()
    ls = cv2.cvtColor(src.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB); lr = cv2.cvtColor(ref.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    out = ls.copy()
    for c in range(3):
        ms, ss = ls[..., c][m].mean(), ls[..., c][m].std() + 1e-6; mr, sr = lr[..., c][m].mean(), lr[..., c][m].std() + 1e-6
        out[..., c] = (ls[..., c] - ms) * (sr / ss) + mr
    out[..., 0] = np.clip(out[..., 0], 0, 100); out[..., 1:] = np.clip(out[..., 1:], -127, 127)
    return np.clip(cv2.cvtColor(out, cv2.COLOR_LAB2BGR) * 255.0, 0, 255).astype(np.uint8)


def cut_region_similarity(pred, real, keep, removed, real_mask):
    """Similarity over the region that actually changed (removed fabric ∪ real garment below the cut):
    0.5*SSIM + 0.5*max(0, 1 - ΔE/25). SSIM alone is blind to a flat colour change (white vs grey scores 0.94)."""
    zone = np.asarray(removed, bool) | (np.asarray(real_mask, bool) & ~np.asarray(keep, bool))
    if not zone.any(): return float("nan")
    return 0.5 * unchanged_ssim(pred, real, zone) + 0.5 * max(0.0, 1.0 - unchanged_color_delta_e(pred, real, zone) / 25.0)

cut_region_ssim = cut_region_similarity   # backwards-compatible alias


def _decompose(A):
    """(scale_x, scale_y, rotation_deg, shear_deg) of a 2x2 linear part, in image (x, y) order."""
    a, b, c, d = float(A[0, 0]), float(A[0, 1]), float(A[1, 0]), float(A[1, 1])
    sx = float(np.hypot(a, c))                                   # length of the image of the x axis
    rot = float(np.degrees(np.arctan2(c, a)))
    shear = float(np.degrees(np.arctan2(a * b + c * d, a * d - b * c)))   # angle between the two mapped axes, minus 90°
    sy = float((a * d - b * c) / max(sx, 1e-9))                  # signed area / sx
    return sx, sy, rot, shear


def _moment_affine(pm, rm, max_scale_change):
    """Diagonal-scale + translation from the two masks' centroids and second central moments.
    Returns (M, clipped): `clipped` is True when the requested scale exceeded the bound and was cut back to it —
    the caller must treat a clipped alignment as a refusal, not as a successful alignment (review 4, finding 10)."""
    ys, xs = np.nonzero(pm); yr, xr = np.nonzero(rm)
    if len(ys) < 50 or len(yr) < 50: return None, False
    rx = (xr.std() + 1e-6) / (xs.std() + 1e-6); ry = (yr.std() + 1e-6) / (ys.std() + 1e-6)
    sx = float(np.clip(rx, 1 - max_scale_change, 1 + max_scale_change)); sy = float(np.clip(ry, 1 - max_scale_change, 1 + max_scale_change))
    clipped = bool(abs(rx - sx) > 1e-6 or abs(ry - sy) > 1e-6)
    return np.array([[sx, 0, xr.mean() - sx * xs.mean()], [0, sy, yr.mean() - sy * ys.mean()]], np.float32), clipped


def align_to_reference(pred, pred_mask, ref, ref_mask=None, max_scale_change=0.15, ref_moment_mask=None,
                       max_rotation_deg=2.0, max_shear_deg=2.0):
    """Estimate a BOUNDED affine transform taking `pred` onto `ref`; return (pred_warped, pred_mask_warped, info).
    A wash that shrinks the garment is a legitimate change, not an identity loss, so identity metrics are computed
    after this alignment (EXP_0013). What alignment may absorb is deliberately narrow:

      * per-axis scale within `max_scale_change` (default ±15%) — the shrinkage the wash model produces,
      * rotation within `max_rotation_deg` and shear within `max_shear_deg` (default 2° each) — re-lay jitter only.

    A rotated garment is NOT the same garment presented differently for our purposes: the earlier version bounded only
    the singular values, which are (1, 1) for any rotation, so every rotation was accepted and a 15° rotation scored
    0.98 (review 4, finding 2). Out-of-bounds estimates are refused: `info["refused"]` lists why, and the transform
    falls back to the last in-bounds estimate (moments, or the identity), so the metrics see the unaligned prediction.

    `info["axis_scales"]` is always [scale_x, scale_y] in image order — never sorted — so the anisotropy direction
    (weft vs warp) is recoverable (review 4, finding 6)."""
    pm = np.asarray(pred_mask, bool)
    mm = np.asarray(ref_moment_mask, bool) if ref_moment_mask is not None else (np.asarray(ref_mask, bool) if ref_mask is not None else pm)
    H, W = ref.shape[:2]
    info = {"method": "identity", "scale": 1.0, "axis_scales": [1.0, 1.0], "rotation_deg": 0.0, "shear_deg": 0.0,
            "ecc": None, "refused": [], "bound_hit": False}
    M, clipped = _moment_affine(pm, mm, max_scale_change)
    if M is None:
        return pred.copy(), pm.copy(), info
    if clipped:
        # the masks differ in size by more than the bound: this is not a wash shrink, so do not pretend to align it
        info["refused"].append("moment_scale_out_of_bounds"); info["bound_hit"] = True
        M = np.array([[1, 0, 0], [0, 1, 0]], np.float32)
    else:
        sx, sy, rot, sh = _decompose(M)
        info.update(method="moments", axis_scales=[sx, sy], scale=float(np.sqrt(abs(sx * sy))), rotation_deg=rot, shear_deg=sh)
    g1 = cv2.cvtColor(pred, cv2.COLOR_BGR2GRAY).astype(np.float32); g2 = cv2.cvtColor(ref, cv2.COLOR_BGR2GRAY).astype(np.float32)
    try:
        crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 60, 1e-5)
        # ECC convention: template=pred, input=ref -> the returned matrix is the one warpAffine(pred, M) needs.
        cc, M2 = cv2.findTransformECC(g1, g2, M.copy(), cv2.MOTION_AFFINE, crit, (pm.astype(np.uint8) * 255), 5)
        sx, sy, rot, sh = _decompose(M2)
        why = []
        if not all(abs(v - 1.0) <= max_scale_change for v in (sx, sy)): why.append(f"ecc_scale {sx:.3f},{sy:.3f}")
        if abs(rot) > max_rotation_deg: why.append(f"ecc_rotation {rot:.1f}deg")
        if abs(sh) > max_shear_deg: why.append(f"ecc_shear {sh:.1f}deg")
        if why: info["refused"] += why; info["bound_hit"] = True
        else:
            M = M2; info.update(method="moments+ecc", axis_scales=[sx, sy], scale=float(np.sqrt(abs(sx * sy))),
                                rotation_deg=rot, shear_deg=sh, ecc=float(cc))
    except cv2.error:
        info["refused"].append("ecc_did_not_converge")
    out = cv2.warpAffine(pred, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    om = cv2.warpAffine(pm.astype(np.uint8), M, (W, H), flags=cv2.INTER_NEAREST) > 0
    return out, om, info


def aligned_identity(pred, pred_keep, ref, ref_keep, ref_mask=None, **kw):
    """Identity metrics (SSIM, CIE76 ΔE, location-checked feature retention) after a bounded affine alignment of
    `pred` to `ref`, evaluated over the WHOLE reference keep region.

    Scoring the intersection of the two masks would let a system raise its identity score by destroying fabric and
    not claiming it (review 4, finding 3). Reference-kept pixels the prediction does not claim are therefore filled
    with the reference's median backdrop colour before scoring, i.e. counted as missing content, and their share is
    reported as `claimed`."""
    pw, kw_mask, info = align_to_reference(pred, pred_keep, ref, ref_mask, ref_moment_mask=ref_keep, **kw)
    zone = np.asarray(ref_keep, bool)
    if zone.sum() < 200: return {"ssim": float("nan"), "dE": float("nan"), "feat_ret": float("nan"), "claimed": 0.0, "align": info}
    unclaimed = zone & ~kw_mask
    scored = pw.copy()
    if unclaimed.any():
        gm = np.asarray(ref_mask, bool) if ref_mask is not None else zone
        bg = np.median(ref[~gm], axis=0) if (~gm).any() else np.zeros(3)
        scored[unclaimed] = bg.astype(scored.dtype)
    return {"ssim": unchanged_ssim(scored, ref, zone), "dE": unchanged_color_delta_e(scored, ref, zone),
            "feat_ret": feature_retention(scored, ref, zone), "claimed": float(1.0 - unclaimed.sum() / zone.sum()), "align": info}
