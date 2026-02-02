#!/usr/bin/env python3
"""Recover metric scale from a gridded cutting mat in the background (common in sewing blogs).
Detects the dominant periodicity of background rows/columns (FFT of a high-passed grayscale) outside the garment
mask and converts it to px per grid cell. Grid pitch defaults to 1 inch (25.4 mm); pass --pitch-mm for cm mats.
Usage: scale_from_grid.py IMAGE [--mask MASK.png] [--pitch-mm 25.4] -> prints JSON {px_per_cell, mm_per_px, confidence}."""
import argparse, json, sys
import numpy as np, cv2
p = argparse.ArgumentParser(); p.add_argument("image"); p.add_argument("--mask"); p.add_argument("--pitch-mm", type=float, default=25.4); p.add_argument("--min-cell-px", type=int, default=12)
a = p.parse_args()
img = cv2.imread(a.image); g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32); H, W = g.shape
bg = np.ones((H, W), bool)
if a.mask: bg = cv2.imread(a.mask, 0) < 127; bg = cv2.erode(bg.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
hp = g - cv2.GaussianBlur(g, (0, 0), 6)                      # high-pass: grid lines
hp[~bg] = 0
def dominant_period(profile, n):
    """Autocorrelation peak within [min_cell_px, n/6]: the grid pitch. SNR = peak height / median of the window."""
    x = profile - profile.mean(); x = x / (x.std() + 1e-6)
    ac = np.correlate(x, x, mode="full")[n - 1:] / n
    lo, hi = a.min_cell_px, max(n // 6, a.min_cell_px + 2)
    win = ac[lo:hi]
    if len(win) < 3: return np.nan, 0.0
    k = int(np.argmax(win)) + lo
    # refine: the true pitch is the FIRST strong peak, not a multiple; walk down to the smallest lag with >= 70% of the max
    cands = [i + lo for i, v in enumerate(win) if v >= 0.7 * win.max() and 0 < i < len(win) - 1 and win[i] >= win[i - 1] and win[i] >= win[i + 1]]
    k = min(cands) if cands else k
    return float(k), float(ac[k] / (np.median(np.abs(win)) + 1e-6))
# project |hp| along rows and columns (background only)
col_profile = np.abs(hp).sum(axis=0) / np.maximum(bg.sum(axis=0), 1); row_profile = np.abs(hp).sum(axis=1) / np.maximum(bg.sum(axis=1), 1)
px_c, snr_c = dominant_period(col_profile, W); px_r, snr_r = dominant_period(row_profile, H)
agree = abs(px_c - px_r) / max(px_c, px_r) < 0.15 if np.isfinite(px_c) and np.isfinite(px_r) else False
cell = float(np.mean([px_c, px_r])) if agree else float(px_c if snr_c > snr_r else px_r)
conf = min(snr_c, snr_r) if agree else 0.5 * max(snr_c, snr_r)
res = dict(px_per_cell=cell, px_per_cell_cols=float(px_c), px_per_cell_rows=float(px_r), snr_cols=snr_c, snr_rows=snr_r, axes_agree=bool(agree),
           mm_per_px=a.pitch_mm / cell if cell else None, confidence=float(conf), note="periodicity of background rows/cols; verify visually")
print(json.dumps(res, indent=1))
