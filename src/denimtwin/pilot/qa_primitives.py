"""Capture-QA primitives that `capture/quality.py` does not provide, and what they can honestly say.

Three of the checks the pilot needs have no implementation in this repository, and two of them are
easy to get wrong in the direction that matters -- returning PASS when the evidence does not support
one. Each primitive here therefore ships with the measurement that justifies its thresholds
(EXP_0043, reproduced by tools/experiment_capture_primitives.py) and, where the honest answer is
"this cannot be decided from the pixels", it returns that instead of a verdict.

1. CAMERA TILT. `capture/board.mm_per_pixel` takes the MEDIAN spacing of adjacent chessboard
   corners. On a tilted board that median is a biased estimate of scale, and the bias is large well
   before the tilt is visible: at a keystone warp that a person would call "nearly overhead", the
   scale it returns is already ~12% wrong. A fray depth of 5 mm read to 0.5 mm is a 10% measurement,
   so a 12% scale error is not a detail -- it is larger than the quantity being measured.

   The observable is `scale_range_ratio`: the 95th over the 5th percentile of local corner spacing
   across the board. It is 1.0 for a fronto-parallel board, needs no camera intrinsics, and is
   exactly the quantity that invalidates a single-number mm/px. `approx_tilt_deg` is also offered,
   but it requires an ASSUMED focal length and is reported as approximate for that reason.

2. RELAY INDEPENDENCE -- "are these five photographs five independent re-lays, or one photograph
   five times?" The measured answer (EXP_0043) is that image-similarity metrics CANNOT decide this.
   Genuine re-lays of one garment scored NCC 0.9915-0.9934 against each other, while the same
   garment photographed twice WITHOUT being moved scored 0.9935 -- higher than the genuine relays.
   A dHash separates them no better. So similarity is used only for what it can prove -- that a file
   is the SAME FRAME resubmitted -- and relay independence is decided on garment displacement, which
   does separate them cleanly (0.00 px when the garment was not moved, 3.1-9.2 px when it was),
   corroborated by capture timestamps, and otherwise referred to a human. A displacement below the
   floor is evidence AGAINST a relay; a displacement above it is not by itself proof of one.

3. DUPLICATE CONTENT. Exact content hash catches the copied file. Near-duplicate NCC catches the
   re-encoded or brightness-shifted copy (>= 0.999 measured against 0.9934 for genuine relays).
   Anything between is referred to a human rather than guessed.
"""
import hashlib
import math

import cv2
import numpy as np

# --- thresholds, all from EXP_0043; see reports/pilot_qa_primitives.json ---------------------

#: Fronto-parallel boards measured a scale_range_ratio of 1.033 (median) to 1.049 (max) purely from
#: corner-detection noise, so a PASS band cannot sit below ~1.05 without failing level captures.
SRR_NOISE_FLOOR = 1.049
#: <= this, measured scale error stayed under ~6%.
SRR_PASS = 1.06
#: > this, measured scale error exceeded 12%. Between the two the estimator and the error overlap,
#: which is a band where the honest answer is "look at it", not a verdict.
SRR_RETAKE = 1.10

#: Centroid corroboration. Measured gap: a garment that was NOT moved reproduced its centroid to
#: within 0.038 mm, while independent re-lays never landed closer than 0.367 mm to each other. The
#: floor is the geometric midpoint of that gap, so neither side is close to it.
RELAY_MIN_CENTROID_MM = 0.10
RELAY_MIN_ROT_DEG = 0.25

#: The primary relay signal: correlation of the garment INTERIOR after aligning the two captures on
#: centroid and principal axis. Cloth that was never moved is in the same creases and correlates
#: 0.985-1.000; cloth lifted and laid out again fell to 0.72 at best and usually far below.
#: At or above this, the two captures are the same lay.
RELAY_SAME_CLOTH_NCC = 0.95
#: Below RELAY_SAME_CLOTH_NCC but above this is the band no measurement resolved; a human decides.
RELAY_AMBIGUOUS_NCC = 0.80
#: A genuine re-lay takes at least this long in the real world (lift, shake out, lay, smooth).
#: Used only as corroboration, never alone.
RELAY_MIN_SECONDS = 20.0

#: NCC at or above this was only ever produced by the same frame re-encoded or brightness-shifted.
NEAR_DUPLICATE_NCC = 0.999
#: Genuine independent relays measured at most 0.9934; between that and NEAR_DUPLICATE_NCC is the
#: band where a human decides.
DISTINCT_NCC_MAX = 0.9940


# --- board geometry --------------------------------------------------------------------------

def _corner_spacings(corners, ids, spec):
    """Distances between horizontally and vertically adjacent detected chessboard corners."""
    cols = spec["cols"] - 1
    pts = {int(i): c for i, c in zip(np.asarray(ids).ravel(), np.asarray(corners).reshape(-1, 2))}
    out = []
    for i, p in pts.items():
        r, c = divmod(i, cols)
        for j in (i + 1 if c + 1 < cols else None, i + cols):
            if j is not None and j in pts:
                out.append(float(np.linalg.norm(p - pts[j])))
    return out


def scale_range_ratio(corners, ids, spec):
    """How much local scale varies across the board. 1.0 = fronto-parallel. None if too few corners.

    Intrinsic-free, and it is the quantity that decides whether ONE mm/px describes the frame.
    """
    d = _corner_spacings(corners, ids, spec)
    if len(d) < 8:
        return None
    v = np.asarray(d)
    lo = float(np.percentile(v, 5))
    if lo <= 0:
        return None
    return float(np.percentile(v, 95) / lo)


def approx_tilt_deg(corners, ids, spec, width, height, assumed_hfov_deg=64.0):
    """Angle between the board normal and the optical axis, ASSUMING a horizontal field of view.

    The assumption is the whole caveat: without the phone's real intrinsics this is an estimate, and
    it is offered as context for a human, never as the thing a gate turns on. `scale_range_ratio` is
    the gate, because it assumes nothing.
    """
    cols = spec["cols"] - 1
    pts = {int(i): c for i, c in zip(np.asarray(ids).ravel(), np.asarray(corners).reshape(-1, 2))}
    if len(pts) < 8:
        return None
    obj, img = [], []
    for i, p in pts.items():
        r, c = divmod(i, cols)
        obj.append([(c + 1) * spec["square_mm"], (r + 1) * spec["square_mm"]])
        img.append(p)
    H, _ = cv2.findHomography(np.asarray(obj, np.float32), np.asarray(img, np.float32),
                              cv2.RANSAC, 3.0)
    if H is None:
        return None
    f = (max(width, height) / 2.0) / math.tan(math.radians(assumed_hfov_deg / 2.0))
    K = np.array([[f, 0, width / 2.0], [0, f, height / 2.0], [0, 0, 1.0]])
    M = np.linalg.inv(K) @ H
    r1, r2 = M[:, 0], M[:, 1]
    n = (np.linalg.norm(r1) + np.linalg.norm(r2)) / 2.0
    if not np.isfinite(n) or n <= 0:
        return None
    r3 = np.cross(r1 / n, r2 / n)
    return float(math.degrees(math.acos(min(1.0, abs(float(r3[2]))))))


def tilt_verdict(srr):
    """PASS / HUMAN / RETAKE / UNAVAILABLE for a scale_range_ratio. Absence is never a pass."""
    if srr is None:
        return "UNAVAILABLE_CHECK", "board not detected well enough to measure scale variation"
    if srr <= SRR_PASS:
        return "PASS", "scale varies %.1f%% across the board" % (100 * (srr - 1))
    if srr > SRR_RETAKE:
        return "RETAKE_REQUIRED", (
            "scale varies %.1f%% across the board; a single mm/px does not describe this frame "
            "(measured scale error exceeds 12%% here). Re-aim the camera directly overhead."
            % (100 * (srr - 1)))
    return "HUMAN_VERIFICATION_REQUIRED", (
        "scale varies %.1f%% across the board, in the band where the estimator and the resulting "
        "scale error overlap. Confirm the camera is square to the surface, or re-shoot." % (100 * (srr - 1)))


# --- garment pose ----------------------------------------------------------------------------

def garment_pose(img, exclude_rect=None):
    """Centroid, principal-axis angle and area of the largest foreground blob, in pixels/degrees.

    Foreground is separated the same way `capture/quality.check_image` does it -- Lab distance from
    the border-sampled background, Otsu-thresholded -- so a pose and a quality report describe the
    same blob. Returns None when there is no plausible garment.
    """
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    lab = cv2.cvtColor(img.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    valid = np.ones(gray.shape, bool)
    if exclude_rect:
        x, y, w, h = [int(v) for v in exclude_rect]
        valid[max(0, y - 8):y + h + 8, max(0, x - 8):x + w + 8] = False
    b = 8
    bm = np.zeros_like(valid)
    bm[:b] = bm[-b:] = True
    bm[:, :b] = bm[:, -b:] = True
    bm &= valid
    if not bm.any() or not valid.any():
        return None
    bg = np.median(lab[bm], axis=0)
    dist = np.linalg.norm(lab - bg, axis=2)
    d8 = np.clip(dist * 2.0, 0, 255).astype(np.uint8)
    t, _ = cv2.threshold(d8[valid], 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    fg = ((dist > max(t / 2.0, 6.0)) & valid).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((9, 9), np.uint8))
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n < 2:
        return None
    k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    m = (lbl == k).astype(np.uint8)
    mo = cv2.moments(m)
    if mo["m00"] <= 0:
        return None
    cx, cy = mo["m10"] / mo["m00"], mo["m01"] / mo["m00"]
    mu20, mu02, mu11 = mo["mu20"] / mo["m00"], mo["mu02"] / mo["m00"], mo["mu11"] / mo["m00"]
    ang = math.degrees(0.5 * math.atan2(2 * mu11, mu20 - mu02)) % 180.0
    ys, xs = np.where(m > 0)
    return {"cx": float(cx), "cy": float(cy), "angle_deg": float(ang),
            "area_px": float(m.sum()), "area_fraction": float(m.mean()),
            "bbox": [int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1),
                     int(ys.max() - ys.min() + 1)]}


def _angle_delta(a, b):
    """Principal-axis angles are modulo 180 degrees, so 179 and 1 differ by 2, not 178."""
    d = abs(float(a) - float(b)) % 180.0
    return min(d, 180.0 - d)


# --- similarity ------------------------------------------------------------------------------

def content_sha256(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def dhash_bits(img, n=16):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    r = cv2.resize(g, (n + 1, n), interpolation=cv2.INTER_AREA)
    return np.packbits(r[:, 1:] > r[:, :-1]).tobytes()


def hamming(a, b):
    return sum(bin(x ^ y).count("1") for x, y in zip(bytearray(a), bytearray(b)))


def ncc(img_a, img_b, n=256):
    """Zero-mean normalised cross-correlation on a fixed-size resample. Exposure-invariant."""
    a = cv2.resize(cv2.cvtColor(img_a, cv2.COLOR_BGR2GRAY), (n, n)).astype(np.float64)
    b = cv2.resize(cv2.cvtColor(img_b, cv2.COLOR_BGR2GRAY), (n, n)).astype(np.float64)
    a -= a.mean()
    b -= b.mean()
    den = math.sqrt(float((a * a).sum()) * float((b * b).sum()))
    if den <= 0:
        return None
    return float((a * b).sum() / den)


def duplicate_verdict(sha_a, sha_b, ncc_ab):
    """Is B the same frame as A? Never guesses in the ambiguous band."""
    if sha_a and sha_b and sha_a == sha_b:
        return "RETAKE_REQUIRED", "byte-identical file already recorded under another shot id"
    if ncc_ab is None:
        return "UNAVAILABLE_CHECK", "images could not be compared"
    if ncc_ab >= NEAR_DUPLICATE_NCC:
        return "RETAKE_REQUIRED", (
            "correlates %.5f with an image already recorded -- at or above the level only produced "
            "by re-encoding or brightening the same frame" % ncc_ab)
    if ncc_ab > DISTINCT_NCC_MAX:
        return "HUMAN_VERIFICATION_REQUIRED", (
            "correlates %.5f with an image already recorded, between the highest measured for "
            "genuinely independent relays (%.4f) and the near-duplicate level (%.3f)"
            % (ncc_ab, DISTINCT_NCC_MAX, NEAR_DUPLICATE_NCC))
    return "PASS", "distinct from the images already recorded (ncc %.5f)" % ncc_ab


def relay_verdict(pose_a, pose_b, mm_per_px, interior_ncc=None, seconds_apart=None,
                  operator_confirmed=False):
    """Were these two captures separated by a genuine re-lay of the garment?

    The primary evidence is the crease field, because that is the thing a re-lay actually changes.
    Measured (EXP_0043): the same lay photographed again correlates 0.985-1.000 on the registered
    interior; independent re-lays of the same garment reached 0.72 at most and usually under 0.1.
    Whole-image similarity does NOT separate these cases -- every case measured 0.9967-1.0000 -- so
    it is not used for this decision.

    This function never returns PASS on geometry alone. A displacement and a decorrelated interior
    are consistent with a re-lay; they do not prove the operator lifted the garment rather than
    dragging it, so the operator's confirmation is still required and is recorded as an assertion.

    LIMITATION, stated because the threshold sits on it: the separation above was measured on
    synthesised captures whose crease field is a model. On real photographs the same-lay figure will
    fall (sensor noise, lighting drift) and the re-lay figure may rise (a carefully reproduced lay).
    Re-derive both from the first real session before relying on the band edges. The fallback in the
    unresolved band is HUMAN_VERIFICATION_REQUIRED, so a mis-set threshold costs an extra
    confirmation, never a false pass.
    """
    ev = {"centroid_shift_mm": None, "centroid_shift_px": None, "rotation_delta_deg": None,
          "interior_ncc": None if interior_ncc is None else round(float(interior_ncc), 5),
          "seconds_apart": seconds_apart, "operator_confirmed": bool(operator_confirmed)}
    if pose_a is None or pose_b is None:
        return "UNAVAILABLE_CHECK", "garment outline could not be measured in one of the captures", ev
    if not mm_per_px:
        return "UNAVAILABLE_CHECK", "no metric scale, so displacement cannot be judged in mm", ev
    d_px = math.hypot(pose_b["cx"] - pose_a["cx"], pose_b["cy"] - pose_a["cy"])
    d_mm = d_px * float(mm_per_px)
    d_rot = _angle_delta(pose_a["angle_deg"], pose_b["angle_deg"])
    ev["centroid_shift_mm"] = round(d_mm, 4)
    ev["centroid_shift_px"] = round(d_px, 3)
    ev["rotation_delta_deg"] = round(d_rot, 3)

    if interior_ncc is None:
        return "UNAVAILABLE_CHECK", (
            "the garment interiors could not be aligned and compared, so whether the cloth was "
            "re-laid is undecided -- it is not a pass"), ev
    if interior_ncc >= RELAY_SAME_CLOTH_NCC:
        return "RETAKE_REQUIRED", (
            "the cloth is in the same creases as the previous capture (registered interior "
            "correlation %.4f, at or above the %.2f only produced by photographing one lay twice). "
            "This is not an independent repeat: lift the garment, shake it out and lay it again."
            % (interior_ncc, RELAY_SAME_CLOTH_NCC)), ev
    if d_mm < RELAY_MIN_CENTROID_MM and d_rot < RELAY_MIN_ROT_DEG:
        return "RETAKE_REQUIRED", (
            "the garment is in the same place to %.3f mm and %.3f deg. A re-lay did not once "
            "reproduce a position that closely; this is the previous lay again." % (d_mm, d_rot)), ev
    if interior_ncc > RELAY_AMBIGUOUS_NCC:
        return "HUMAN_VERIFICATION_REQUIRED", (
            "registered interior correlation %.4f sits between an independent re-lay and the same "
            "lay photographed twice. Confirm the garment was fully lifted and laid out again, or "
            "re-lay it." % interior_ncc), ev
    if seconds_apart is not None and seconds_apart < RELAY_MIN_SECONDS:
        return "HUMAN_VERIFICATION_REQUIRED", (
            "the cloth changed but the two captures are only %.0f s apart, less than a re-lay "
            "takes. Confirm what happened between them." % seconds_apart), ev
    if not operator_confirmed:
        return "HUMAN_VERIFICATION_REQUIRED", (
            "the garment moved %.1f mm and the creases changed (interior correlation %.3f), which "
            "is consistent with a re-lay but does not prove one. Confirm the re-lay."
            % (d_mm, interior_ncc)), ev
    return "PASS", ("garment displaced %.1f mm, creases changed (interior correlation %.3f), and "
                    "the re-lay was confirmed by the operator" % (d_mm, interior_ncc)), ev


def registered_interior_ncc(img_a, img_b, pose_a, pose_b, n=256):
    """Correlate the garment interiors AFTER aligning them by centroid and principal axis.

    This is the check that centroid displacement alone is too thin for. Two photographs of a garment
    that was never moved are the same cloth in the same creases, so once aligned their interiors
    correlate almost perfectly. A garment lifted and laid out again falls into a DIFFERENT crease
    field, and the interiors decorrelate even though the silhouette is nearly identical -- which is
    exactly the signal that separates "five relays" from "one photograph five times", and the reason
    whole-image similarity fails at it (the silhouette and background dominate that number).

    Returns None when either pose is missing: no pose, no alignment, no verdict.
    """
    if img_a is None or img_b is None or not pose_a or not pose_b:
        return None
    out = []
    for img, ps in ((img_a, pose_a), (img_b, pose_b)):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
        h, w = g.shape
        M = cv2.getRotationMatrix2D((float(ps["cx"]), float(ps["cy"])),
                                    float(ps["angle_deg"]), 1.0)
        M[0, 2] += w / 2.0 - float(ps["cx"])
        M[1, 2] += h / 2.0 - float(ps["cy"])
        r = cv2.warpAffine(g, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=0.0)
        bw, bh = ps["bbox"][2], ps["bbox"][3]
        half_w, half_h = int(bw * 0.30), int(bh * 0.30)
        x0, y0 = int(w / 2 - half_w), int(h / 2 - half_h)
        crop = r[max(0, y0):y0 + 2 * half_h, max(0, x0):x0 + 2 * half_w]
        if crop.size == 0 or min(crop.shape) < 8:
            return None
        c = cv2.resize(crop, (n, n)).astype(np.float64)
        # high-pass: creases are the mid-frequency content; removing the slow shading gradient stops
        # a global exposure difference from masking a genuine crease change
        c = c - cv2.GaussianBlur(c, (0, 0), n / 16.0)
        c -= c.mean()
        out.append(c)
    a, b = out
    den = math.sqrt(float((a * a).sum()) * float((b * b).sum()))
    if den <= 0:
        return None
    return float((a * b).sum() / den)
