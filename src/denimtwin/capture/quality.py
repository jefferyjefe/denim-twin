"""Capture-quality checks: blur, exposure, cropping, board presence."""
from dataclasses import dataclass, field
from typing import Optional
import cv2, numpy as np
from .board import detect, mm_per_pixel

@dataclass
class Report:
    path: str
    ok: bool = True
    reasons: list = field(default_factory=list)
    blur_score: float = 0.0
    mean_intensity: float = 0.0
    clipped_fraction: float = 0.0
    border_fraction: float = 0.0
    background_level: float = 0.0
    foreground_fraction: float = 0.0
    cutout_background: bool = False
    board_corners: int = 0
    mm_per_px: Optional[float] = None
    def fail(self, why): self.ok = False; self.reasons.append(why)

def check_image(path, board=None, spec=None, *, blur_min=80.0, clip_max=0.02,
                border_max=0.03, mean_range=(40, 220), min_corners=12):
    img = cv2.imread(str(path))
    r = Report(str(path))
    if img is None:
        r.fail("unreadable"); return r
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # calibration board first, so its region can be excluded from exposure stats
    valid = np.ones_like(gray, bool)
    if board is not None:
        corners, ids = detect(gray, board)
        r.board_corners = 0 if ids is None else len(ids)
        if r.board_corners < min_corners: r.fail(f"board corners {r.board_corners} < {min_corners}")
        else:
            r.mm_per_px = mm_per_pixel(corners, ids, board, spec)
            hull = cv2.convexHull(corners.astype(np.float32)).astype(np.int32)
            m = np.zeros_like(gray); cv2.fillConvexPoly(m, hull, 255)
            pad = int(2.5 * spec['square_mm'] / r.mm_per_px) + 2 * int(10 / r.mm_per_px)  # outer squares + paper margin
            m = cv2.dilate(m, np.ones((pad | 1, pad | 1), np.uint8))
            valid = m == 0
    # blur: variance of Laplacian (whole frame)
    r.blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    if r.blur_score < blur_min: r.fail(f"blurry ({r.blur_score:.0f} < {blur_min})")
    # background estimate from the frame border (excluding board); foreground = pixels far from it
    b = 8
    border_px = np.concatenate([gray[:b][valid[:b]], gray[-b:][valid[-b:]], gray[:, :b][valid[:, :b]], gray[:, -b:][valid[:, -b:]]])
    bg = float(np.median(border_px)) if border_px.size else float(np.median(gray[valid]))
    r.background_level = bg
    fg = (np.abs(gray.astype(int) - bg) > 40) & valid
    r.foreground_fraction = float(fg.mean())
    if r.foreground_fraction < 0.05: r.fail(f"foreground too small ({r.foreground_fraction:.1%})")
    # cutout detection: near-uniform pure white/black background is a seller cutout, not a photo — informational
    if border_px.size and border_px.std() < 3 and (bg >= 250 or bg <= 5):
        r.cutout_background = True
    # exposure stats on the GARMENT only (background clipping is irrelevant to capture quality)
    g = gray[fg] if fg.any() else gray[valid]
    r.mean_intensity = float(g.mean())
    r.clipped_fraction = float(((g <= 2) | (g >= 253)).mean())
    if not mean_range[0] <= r.mean_intensity <= mean_range[1]: r.fail(f"garment exposure out of range (mean {r.mean_intensity:.0f})")
    if r.clipped_fraction > clip_max: r.fail(f"garment clipping {r.clipped_fraction:.1%}")
    # cropping proxy: foreground pixels touching the frame border
    border = np.concatenate([fg[:b].ravel(), fg[-b:].ravel(), fg[:, :b].ravel(), fg[:, -b:].ravel()])
    r.border_fraction = float(border.mean())
    if r.border_fraction > border_max: r.fail(f"foreground touches frame edge ({r.border_fraction:.1%})")
    return r
