"""Synthetic capture images with a real ChArUco board at a known, exact scale.

The point of this module is that the quality checks get exercised against a board OpenCV can
actually detect, at an mm/px the test knows independently. A mocked `check_image` proves the
plumbing and nothing else; the defect that matters here -- a check that passes when its input is
absent or wrong -- only shows up when a real detector runs on a real board.

Every image is a deterministic function of its arguments (seeded RNG, no clock, no global state),
because `tests/conftest.py` and the repository's reproducibility rules both require a fixture to
be re-derivable from its parameters alone.

Scale is set exactly: a square is `square_mm / mm_per_px` pixels wide by construction, so a test
can assert the detected mm/px against the value it asked for rather than against another
measurement of the same image.
"""
import json
import math
import os
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BOARD_SPEC = ROOT / "protocol" / "charuco_board.json"

# Denim in BGR. Not a measurement -- a plausible mid-indigo so foreground/background separation in
# capture.quality behaves like it does on a real frame.
DENIM_BGR = (92, 62, 44)
BACKDROP_BGR = (48, 66, 40)          # the dark matte green PROTOCOL.md 1 recommends
LABEL_BGR = (232, 230, 226)


def _board_image(spec, mm_per_px):
    """Render the board so one square is exactly square_mm / mm_per_px pixels."""
    d = cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, spec["dictionary"]))
    board = cv2.aruco.CharucoBoard((spec["cols"], spec["rows"]),
                                   spec["square_mm"] / 1000.0, spec["marker_mm"] / 1000.0, d)
    sq_px = spec["square_mm"] / float(mm_per_px)
    w = int(round(spec["cols"] * sq_px))
    h = int(round(spec["rows"] * sq_px))
    img = board.generateImage((w, h), marginSize=0)
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def load_spec(path=None):
    return json.loads(Path(path or DEFAULT_BOARD_SPEC).read_text())


def _fabric(shape, rng, base_bgr, weave_mm_per_px=None, strength=14):
    """Denim-ish texture: noise plus a faint twill diagonal, so blur has something to destroy."""
    h, w = shape
    img = np.zeros((h, w, 3), np.float32)
    img[:] = np.array(base_bgr, np.float32)
    img += rng.normal(0.0, strength * 0.5, (h, w, 1))
    if weave_mm_per_px:
        # 0.5 mm warp yarn pitch -> a diagonal ripple whose period is set by the image scale.
        period_px = max(2.0, 0.5 / float(weave_mm_per_px))
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        img += (strength * np.sin(2 * math.pi * (xx + yy) / period_px))[:, :, None]
    return img


def _jeans_polygon(w, h, side="front", legs_touching=False):
    """A flat-lay jeans silhouette in a w x h frame. Returns the outer contour and the crotch height.

    `side` mirrors the outline horizontally, because turning a garment over swaps which side of the
    frame each leg is on. The region map's convention note says the same thing and warns not to
    'fix' it: on the front view the wearer's left is at large x, and on the back view it is at small
    x. A fixture that drew both views identically would make a left/right mix-up invisible.
    """
    cx = w / 2.0
    top = h * 0.06
    waist_half = w * 0.20
    hip_half = w * 0.235
    hem_half = w * 0.085
    crotch_y = top + (h * 0.94 - top) * 0.34
    bottom = h * 0.95
    gap = w * 0.004 if legs_touching else w * 0.030
    outer = [
        (cx - waist_half, top), (cx + waist_half, top),
        (cx + hip_half, crotch_y * 0.75), (cx + hem_half + w * 0.02, bottom),
        (cx + gap, bottom), (cx + gap * 0.6, crotch_y),
        (cx - gap * 0.6, crotch_y), (cx - gap, bottom),
        (cx - hem_half - w * 0.02, bottom), (cx - hip_half, crotch_y * 0.75),
    ]
    if str(side).startswith("back"):
        # Turning the garment over reflects it about the frame's vertical centre line.
        outer = [(2.0 * cx - x, y) for (x, y) in outer][::-1]
    return np.array([outer], np.int32), crotch_y


def reshoot(src, dest, *, sensor_sigma=3.0, shake_px=1.5, seed=0):
    """What photographing the SAME LAY again actually produces.

    Not a new render: the cloth is in the same place with the same creases, and only the sensor
    noise and a pixel or two of camera shake differ. Modelling it as a fresh render with a new
    texture seed was wrong in the direction that flattered the relay check -- it changed the cloth's
    own micro-texture, which is exactly the thing that does NOT change when nobody touches the
    garment.
    """
    img = cv2.imread(str(src))
    if img is None:
        raise IOError("cannot read %s" % src)
    rng = np.random.default_rng(int(seed))
    out = img.astype(np.float32) + rng.normal(0.0, float(sensor_sigma), img.shape)
    if shake_px:
        dx, dy = rng.normal(0, shake_px), rng.normal(0, shake_px)
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        out = cv2.warpAffine(out, M, (img.shape[1], img.shape[0]),
                             borderMode=cv2.BORDER_REPLICATE)
    out = np.clip(out, 0, 255).astype(np.uint8)
    if not cv2.imwrite(str(dest), out):
        raise IOError("could not write %s" % dest)
    return {"path": str(dest), "sensor_sigma": float(sensor_sigma), "shake_px": float(shake_px)}


def synth_capture(path, *, mm_per_px=0.5, size=(1600, 1200), subject="jeans_front",
                  board=True, board_corner="tr", blur_sigma=0.0, exposure=1.0,
                  seed=0, crop_subject=False, legs_touching=False, ruler=False,
                  tilt_deg=0.0, board_spec=None, jpeg_quality=None, extra_marks=(),
                  relay=None):
    """Write one synthetic capture and return the ground truth used to build it.

    size is (width, height). `subject` is one of jeans_front, jeans_back, hem_macro,
    fabric_macro, care_label, blank_backdrop.
    """
    spec = board_spec if isinstance(board_spec, dict) else load_spec(board_spec)
    w, h = int(size[0]), int(size[1])
    rng = np.random.default_rng(seed)
    img = _fabric((h, w), rng, BACKDROP_BGR, strength=4)

    # Where the board will go, decided BEFORE the garment is drawn. PROTOCOL.md 1 puts the board on
    # the same surface as the garment and in the same corner of every frame -- beside it, not on top
    # of it. Pasting it last put it OVER the garment, and at a fine scale a 200 x 275 mm board covers
    # most of the frame, so the only garment left to measure was whatever stuck out. Every
    # measurement of the subject was then a measurement of that sliver.
    board_box = None
    subject_box = (0, 0, w, h)
    if board:
        _b = _board_image(spec, mm_per_px)
        _bh, _bw = _b.shape[:2]
        _k = 1.0
        if _bh >= h * 0.92 or _bw >= w * 0.92:
            _k = min((h * 0.9) / float(_bh), (w * 0.9) / float(_bw))
            _bh, _bw = int(_bh * _k), int(_bw * _k)
        _m = max(2, int(0.01 * min(h, w)))
        _y0 = _m if board_corner[0] == "t" else max(0, h - _bh - _m)
        _x0 = _m if board_corner[1] == "l" else max(0, w - _bw - _m)
        board_box = (_x0, _y0, _bw, _bh, _k)
        # The subject gets the larger of the two strips the board does not occupy.
        free_w = w - (_bw + 2 * _m)
        free_h = h - (_bh + 2 * _m)
        if free_w >= free_h:
            sx = 0 if board_corner[1] == "r" else (_bw + 2 * _m)
            subject_box = (sx, 0, max(8, free_w), h)
        else:
            sy = 0 if board_corner[0] == "b" else (_bh + 2 * _m)
            subject_box = (0, sy, w, max(8, free_h))

    truth = {"mm_per_px": float(mm_per_px), "width": w, "height": h, "subject": subject,
             "board": bool(board), "seed": int(seed)}

    if subject in ("jeans_front", "jeans_back"):
        sx, sy, sw, sh = subject_box[0], subject_box[1], subject_box[2], subject_box[3]
        poly, crotch_y = _jeans_polygon(sw, sh, subject.split("_")[1], legs_touching)
        poly = poly + np.array([int(sx), int(sy)], np.int32)
        crotch_y = crotch_y + sy
        if relay is not None:
            # What a genuine re-lay looks like: the garment is lifted and put down again, so it
            # lands a centimetre or two off and a degree or two rotated, and the cloth falls into a
            # different set of creases. `relay` is the relay index; the displacement is a
            # deterministic function of it, so a test can reproduce the same "independent" capture.
            rr = np.random.default_rng(1000 + int(relay))
            dx = float(rr.normal(0, 18.0 / max(mm_per_px, 1e-6) * 0.06))
            dy = float(rr.normal(0, 18.0 / max(mm_per_px, 1e-6) * 0.06))
            ang = float(rr.normal(0, 1.6))
            M = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), ang, 1.0)
            M[0, 2] += dx; M[1, 2] += dy
            pf = poly.reshape(-1, 2).astype(np.float32)
            poly = cv2.transform(pf.reshape(1, -1, 2), M).reshape(1, -1, 2).astype(np.int32)
            truth["relay"] = {"index": int(relay), "dx_px": dx, "dy_px": dy, "rot_deg": ang}
            truth["_relay_rng"] = int(relay)
        if crop_subject:
            poly = poly + np.array([0, int(h * 0.10)], np.int32)   # push it off the bottom edge
        mask = np.zeros((h, w), np.uint8)
        cv2.fillPoly(mask, poly, 255)
        fab = _fabric((h, w), rng, DENIM_BGR, weave_mm_per_px=mm_per_px, strength=16)
        if relay is not None:
            # The physical fact the relay check turns on: cloth lifted and laid down again does not
            # fall into the same creases. The crease field is a deterministic function of the relay
            # index, so "the same lay photographed twice" and "two independent lays" are different
            # images in the one way that a real garment makes them different.
            cr = np.random.default_rng(5000 + int(relay))
            shade = np.zeros((h, w), np.float32)
            for _ in range(14):
                x0, y0 = cr.uniform(0, w), cr.uniform(0, h)
                L = cr.uniform(0.12, 0.45) * max(w, h)
                th = cr.uniform(0, np.pi)
                x1, y1 = x0 + L * np.cos(th), y0 + L * np.sin(th)
                cv2.line(shade, (int(x0), int(y0)), (int(x1), int(y1)),
                         float(cr.uniform(-16, 16)),
                         max(2, int(round(cr.uniform(3.0, 9.0) / max(mm_per_px, 1e-6)))))
            shade = cv2.GaussianBlur(shade, (0, 0), max(1.0, 2.0 / max(mm_per_px, 1e-6)))
            fab = fab + shade[:, :, None]
        img = np.where(mask[:, :, None] > 0, fab, img)
        # waistband band, so a "waistband spans >= N px" check has something real to measure
        wb_h = max(2, int(round(38.0 / mm_per_px)))
        top = int(sy + sh * 0.06)
        cv2.rectangle(img, (0, top), (w, top + wb_h), (0, 0, 0), 0)
        band = np.zeros((h, w), np.uint8)
        cv2.rectangle(band, (0, top), (w, top + wb_h), 255, -1)
        band = cv2.bitwise_and(band, mask)
        img = np.where(band[:, :, None] > 0, np.clip(fab * 1.18, 0, 255), img)
        xs = np.where(band.any(axis=0))[0]
        truth["waistband_span_px"] = int(xs.max() - xs.min() + 1) if xs.size else 0
        truth["subject_mask_fraction"] = float(mask.mean() / 255.0)
        if subject == "jeans_back":     # two back pockets: the only automatic front/back cue
            for sx in (-1, 1):
                px_ = int(w / 2 + sx * w * 0.115)
                py_ = int(crotch_y - h * 0.10)
                sz = int(round(140.0 / mm_per_px))
                cv2.rectangle(img, (px_ - sz // 2, py_), (px_ + sz // 2, py_ + sz),
                              (40, 30, 22), max(1, int(round(2.0 / mm_per_px))))
    elif subject in ("hem_macro", "fabric_macro"):
        fab = _fabric((h, w), rng, DENIM_BGR, weave_mm_per_px=mm_per_px, strength=18)
        img = fab.copy()
        if subject == "hem_macro":
            edge_y = int(h * 0.55)
            img[edge_y:] = np.array(BACKDROP_BGR, np.float32) + rng.normal(0, 3, (h - edge_y, w, 1))
            # frayed threads: deterministic lengths from the seeded rng
            for x in range(0, w, max(1, int(round(0.8 / mm_per_px)))):
                ln = int(abs(rng.normal(6.0, 2.0)) / mm_per_px)
                cv2.line(img, (x, edge_y), (x + int(rng.normal(0, 2)), edge_y + ln),
                         (110, 96, 84), 1)
            truth["hem_edge_y"] = edge_y
    elif subject == "care_label":
        img[:] = np.array(BACKDROP_BGR, np.float32)
        pad = int(min(w, h) * 0.18)
        cv2.rectangle(img, (pad, pad), (w - pad, h - pad), LABEL_BGR, -1)
        for i, line in enumerate(["100% COTTON", "MADE IN JAPAN", "MACHINE WASH COLD", "SIZE 32"]):
            cv2.putText(img, line, (pad + 20, pad + 60 + i * 55), cv2.FONT_HERSHEY_SIMPLEX,
                        min(w, h) / 900.0, (20, 20, 20), 2, cv2.LINE_AA)
    elif subject == "blank_backdrop":
        # A real matte cloth backdrop has a weave, and that texture is what a blur check measures.
        # A perfectly flat synthetic field has no detail at any focus, so a sharp frame of it scored
        # as blurred -- a property of the fixture, not of the photograph.
        img = _fabric((h, w), rng, BACKDROP_BGR, weave_mm_per_px=mm_per_px, strength=9)
    else:
        raise ValueError("unknown subject: %r" % (subject,))

    for (x0, y0, x1, y1, bgr) in extra_marks:
        cv2.line(img, (int(x0), int(y0)), (int(x1), int(y1)), bgr, max(1, int(round(1.5 / mm_per_px))))

    if ruler:
        # a 150 mm steel rule along the bottom, with mm ticks -- gives ruler-visibility checks a target
        rl = int(round(150.0 / mm_per_px))
        x0 = max(0, (w - rl) // 2)
        y0 = int(h * 0.88)
        rh = max(4, int(round(20.0 / mm_per_px)))
        cv2.rectangle(img, (x0, y0), (min(w - 1, x0 + rl), y0 + rh), (200, 200, 205), -1)
        for mm in range(0, 151):
            tx = x0 + int(round(mm / mm_per_px))
            if tx >= w:
                break
            tl = rh if mm % 10 == 0 else (rh // 2 if mm % 5 == 0 else rh // 3)
            cv2.line(img, (tx, y0), (tx, y0 + tl), (30, 30, 30), 1)
        truth["ruler_mm"] = 150.0

    if board and board_box is not None:
        x0, y0, bw, bh, k = board_box
        b = _board_image(spec, mm_per_px).astype(np.float32)
        if k != 1.0:
            b = cv2.resize(b, (bw, bh), interpolation=cv2.INTER_AREA)
            truth["mm_per_px"] = float(mm_per_px) / k
        bh2, bw2 = b.shape[:2]
        img[y0:y0 + bh2, x0:x0 + bw2] = b[:min(bh2, h - y0), :min(bw2, w - x0)]
        truth["board_rect"] = [x0, y0, bw2, bh2]

    if tilt_deg:
        # A perspective warp about the horizontal axis: this is what a non-overhead camera does to
        # the board, and it is what the tilt check must recover. Small angles only.
        f = math.tan(math.radians(tilt_deg)) * 0.5
        src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
        dst = np.float32([[w * f, 0], [w * (1 - f), 0], [w, h], [0, h]])
        img = cv2.warpPerspective(img, cv2.getPerspectiveTransform(src, dst), (w, h),
                                  borderValue=tuple(float(c) for c in BACKDROP_BGR))
        truth["tilt_deg"] = float(tilt_deg)

    if blur_sigma:
        k = int(blur_sigma * 6) | 1
        img = cv2.GaussianBlur(img, (k, k), blur_sigma)
        truth["blur_sigma"] = float(blur_sigma)
    if exposure != 1.0:
        img = img * float(exposure)
        truth["exposure"] = float(exposure)

    out = np.clip(img, 0, 255).astype(np.uint8)
    path = str(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    params = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)] if jpeg_quality else []
    if not cv2.imwrite(path, out, params):
        raise IOError("could not write %s" % path)
    truth["path"] = path
    return truth
