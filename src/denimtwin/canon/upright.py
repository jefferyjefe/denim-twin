"""Rotate a flat-lay photograph so the garment stands upright (plan §4.2).

Why this exists at all: `canon/autolm.landmarks_from_mask` measures axis-aligned extents — leftmost/rightmost pixel in
a horizontal band, lowest pixel in a column — so it is not rotation-invariant. EXP_0021 measured the cost on a
geometrically exact silhouette: a **5 degree tilt already moves every shape ratio by more than 5%**, and 8 degrees
moves them 18-33%, while the segmentation mask is still correct (IoU 0.994 at 8 degrees). Camera tilt is invisible in
the photograph, so it cannot be asked away in the capture instructions alone.

The estimate is the silhouette's principal axis. EXP_0022 measured it against known rotations of 16 real masks:
median error 0.00 degrees, p90 1.64, and in 176 cases correcting was never worse than not correcting. It has one
failure mode, and it is structural rather than incidental — on a **near-isotropic silhouette** (a squat pair of
shorts, elongation < 1.2) the two eigenvalues are nearly equal and the axis can swing:

    elongation >= 1.2   max error 0.02 deg at 3 deg of tilt, 0.81 at 15
    elongation <  1.2   max error 0.41 deg at 3 deg of tilt, 4.67 at 8, 10.45 at 15

which is why `unreliable()` exists and why the caller is expected to say so in its own output.

This is a CANONICALISATION, not a measurement of the garment's true orientation: it makes repeated measurements of one
garment agree (Gate 1), and claims nothing about which way the garment really lay.
"""
import numpy as np
import cv2

ISOTROPIC_ELONGATION = 1.2      # below this the principal axis is degenerate (EXP_0022)
UNRELIABLE_TILT_DEG = 5.0       # ... and above this tilt its error grows past a degree


def _wrap(d):
    """Angles are defined modulo 180 degrees: a garment rotated by 180 is still a garment, and a principal axis has
    no sign. Wrap into (-90, 90] or a 1-degree miss reads as 179."""
    return (float(d) + 90.0) % 180.0 - 90.0


def _axis_angle(v):
    a = np.degrees(np.arctan2(v[0], v[1]))
    return float((a + 90) % 180 - 90)


def waistband_angle(mask, min_inliers=0.45, min_span=0.45, tol_frac=0.01, iters=400, seed=0):
    """Tilt from the WAISTBAND edge, by RANSAC on the mask's top-edge points.

    The waistband is the one part of a flat-laid garment that is straight by construction: a stiff band with a sewn
    edge, spanning most of the garment's width. The legs are not — they splay, and asymmetric splay is exactly what
    biases the principal axis (EXP_0023: on 443d1d4658 the right leg hangs lower and the axis reads 4.8 degrees on a
    garment whose waistband is level).

    Returns (angle_deg, inlier_fraction), or (None, 0.0) when no line explains enough of the top edge — which is the
    correct answer for a garment photographed folded, or a mask with a hole in the waistband.
    """
    m = np.asarray(mask, bool)
    cols = np.nonzero(m.any(axis=0))[0]
    if len(cols) < 40: return None, 0.0
    xs = cols.astype(float)
    ys = np.array([np.nonzero(m[:, int(x)])[0].min() for x in cols], float)
    rows = np.nonzero(m.any(axis=1))[0]
    H = float(np.ptp(rows) + 1); W = float(np.ptp(cols) + 1)
    tol = max(tol_frac * H, 2.0)
    rng = np.random.default_rng(seed)
    best = (0, None)
    n = len(xs)
    for _ in range(iters):
        i, j = rng.integers(0, n, 2)
        if xs[j] == xs[i]: continue
        slope = (ys[j] - ys[i]) / (xs[j] - xs[i])
        if abs(slope) > 1.0: continue                       # a waistband is not steeper than 45 degrees
        inter = ys[i] - slope * xs[i]
        d = np.abs(ys - (slope * xs + inter))
        k = int((d <= tol).sum())
        if k > best[0]: best = (k, (slope, inter))
    if best[1] is None: return None, 0.0
    slope, inter = best[1]
    inl = np.abs(ys - (slope * xs + inter)) <= tol
    if inl.sum() < 3: return None, 0.0
    # least squares on the inliers, then one re-fit
    for _ in range(2):
        A = np.stack([xs[inl], np.ones(int(inl.sum()))], 1)
        sol, *_ = np.linalg.lstsq(A, ys[inl], rcond=None)
        inl = np.abs(ys - (sol[0] * xs + sol[1])) <= tol
        if inl.sum() < 3: return None, 0.0
    span = (xs[inl].max() - xs[inl].min()) / W
    frac = float(inl.mean())
    if frac < min_inliers or span < min_span: return None, frac
    # negated so the convention matches `tilt_angle`: the angle the GARMENT is tilted by, not the slope of its edge
    return _wrap(-np.degrees(np.arctan(sol[0]))), frac

def principal_axis_angle(mask):
    """(angle_deg, elongation) — the tilt of the garment, as the deviation from vertical of whichever principal axis
    is closer to vertical.

    It used to be the LONG axis unconditionally, and that is wrong for the project's own subject. A pair of shorts
    laid flat is usually **wider than tall** (9 of the 16 photographs measured in EXP_0021 have height/width 0.60-0.85),
    so its long axis runs left-to-right and the old function returned ~±88 degrees — outside `max_correctable_tilt`,
    so uprighting silently did nothing on exactly the garments this project is about. Reading the near-vertical axis
    instead turns those same nine photographs into tilts of -3.4 to +2.6 degrees, which is what they actually are.

    A consequence worth knowing: |angle| is now at most 45 degrees by construction, because at 45 the two axes swap
    roles. A garment genuinely lying at 50 degrees reads as -40, and nothing here can tell those apart from the
    silhouette alone.
    """
    ys, xs = np.nonzero(np.asarray(mask, bool))
    if not len(ys): return 0.0, 1.0
    pts = np.stack([xs, ys], 1).astype(np.float32); pts -= pts.mean(0)
    cov = pts.T @ pts / len(pts)
    w_, v_ = np.linalg.eigh(cov)
    angs = [_axis_angle(v_[:, i]) for i in (0, 1)]
    ang = min(angs, key=abs)
    return float(ang), float(np.sqrt(w_.max() / max(w_.min(), 1e-6)))


def tilt_estimate(mask, prefer_waistband=False):
    """(angle_deg, elongation, source). `prefer_waistband` takes the waistband-edge fit when it answers.

    **It is off by default, and EXP_0026 is why.** Measured against known rotations of 16 real masks the waistband
    estimator looks much better than the principal axis — p90 error 0.22° against 1.64°, never missing by a degree,
    though it declines on 38% of cases — and on the one case with independent ground truth (443d1d4658, whose
    cutting-mat grid shows the garment is square) it says -1.9° where the principal axis says +4.8°. Wired into the
    pipeline it is worse: silhouette IoU 0.858 -> 0.831 and hem error 8.5 -> 23.3 px over the usable pairs, 1 better
    and 4 worse. It fixes 443d1d4658 (IoU 0.857 -> 0.922) and breaks 2691c1a8d0 (0.736 -> 0.558, hem 11.5 -> 86.6 px)
    by rotating a before-photo the principal axis had declined to touch.

    Being more precise when it answers is not the same as answering about the waistband: on some photographs the
    straight line it finds across the top of the mask is a fold, a belt, or a shadow. Keeping it available and off is
    the honest state — the measurement is real, the improvement is not."""
    a, elong = principal_axis_angle(mask)
    if prefer_waistband:
        w, frac = waistband_angle(mask)
        if w is not None:
            return float(w), elong, "waistband"
    return float(a), elong, "principal_axis"


def tilt_angle(mask, prefer_waistband=False):
    """(angle_deg, elongation). See `tilt_estimate` for which estimator answered and why the waistband one is off."""
    a, e, _ = tilt_estimate(mask, prefer_waistband)
    return a, e


def max_correctable_tilt(elongation):
    """An elongated garment lying at 60 degrees is still a garment; a squat one at 60 degrees is more likely a mask
    error than a tilt, so the correction is not attempted that far out."""
    return 80.0 if elongation > 1.8 else 30.0


def unreliable(angle_deg, elongation):
    """Is this tilt estimate one the caller should warn about? (EXP_0022: the near-isotropic regime.)"""
    return bool(elongation < ISOTROPIC_ELONGATION and abs(angle_deg) >= UNRELIABLE_TILT_DEG)


def upright_decision(mask, deadband=0.0):
    """What upright() will do and why, without doing it.

    upright() returns an applied angle of 0.0 for THREE different situations -- a garment that is
    already straight, a correction skipped by the deadband, and a correction REFUSED because the
    estimate is beyond what max_correctable_tilt allows. Review 7 found that a refusal is therefore
    indistinguishable from a well-aligned photograph in the logs, and that two of the seven scored
    pairs are refusals (estimates -40.1 and -36.1 degrees against a 30 degree ceiling) recorded as
    "0.0 rotated" in their NOTE and in EXP_0037's and EXP_0040's rotation tables.

    Returns {status, angle_deg, elongation, ceiling_deg} where status is one of
    'applied' | 'straight' | 'below_deadband' | 'refused'.
    """
    m = np.asarray(mask, bool)
    ang, elong = tilt_angle(m)
    ceiling = max_correctable_tilt(elong)
    if abs(ang) > ceiling:
        status = "refused"
    elif abs(ang) < 0.05:
        status = "straight"
    elif abs(ang) < deadband:
        status = "below_deadband"
    else:
        status = "applied"
    return {"status": status, "angle_deg": float(ang), "elongation": float(elong),
            "ceiling_deg": float(ceiling)}


def upright(image_bgr, mask, deadband=0.0):
    """Rotate image and mask so the garment's principal axis is vertical.

    `deadband` skips the correction below that tilt. It was 8.0 until EXP_0022, which is the band where the estimate
    is most accurate and the un-corrected measurement error is already >5%; the default is now 0.0. Returns
    (image, mask, applied_angle_deg) — the angle is 0.0 when nothing was done.
    """
    m = np.asarray(mask, bool)
    ang, elong = tilt_angle(m)
    # A rotation this small is a no-op that still costs one resampling of the photograph, so it is skipped whatever
    # the deadband is. This is not a tuning threshold: below it the rotation matrix is the identity to within a pixel
    # on any image this project handles.
    if abs(ang) < 0.05 or abs(ang) < deadband or abs(ang) > max_correctable_tilt(elong):
        return image_bgr, m, 0.0
    h, w = m.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), -ang, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    M[0, 2] += nw / 2 - w / 2; M[1, 2] += nh / 2 - h / 2
    bgc = tuple(int(c) for c in np.median(image_bgr[~m], axis=0)) if (~m).any() else (128, 128, 128)
    img2 = cv2.warpAffine(image_bgr, M, (nw, nh), borderValue=bgc)
    mask2 = cv2.warpAffine(m.astype(np.uint8), M, (nw, nh)) > 0
    return img2, mask2, ang
