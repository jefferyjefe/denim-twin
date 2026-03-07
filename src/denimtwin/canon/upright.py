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


def _axis_angle(v):
    a = np.degrees(np.arctan2(v[0], v[1]))
    return float((a + 90) % 180 - 90)


def tilt_angle(mask):
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


def max_correctable_tilt(elongation):
    """An elongated garment lying at 60 degrees is still a garment; a squat one at 60 degrees is more likely a mask
    error than a tilt, so the correction is not attempted that far out."""
    return 80.0 if elongation > 1.8 else 30.0


def unreliable(angle_deg, elongation):
    """Is this tilt estimate one the caller should warn about? (EXP_0022: the near-isotropic regime.)"""
    return bool(elongation < ISOTROPIC_ELONGATION and abs(angle_deg) >= UNRELIABLE_TILT_DEG)


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
