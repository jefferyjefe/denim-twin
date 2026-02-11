#!/usr/bin/env python3
"""Recover metric scale from a coin placed on the backdrop next to the garment (CONTRIBUTING_PAIRS.md asks for it).
Hough circles on the background (outside the garment mask), pick the most coin-like candidate (circular, uniform,
metallic/bright), and convert its diameter to mm/px given the coin type.
Usage: scale_from_coin.py IMAGE --coin us_quarter [--mask MASK.png] -> JSON {diameter_px, mm_per_px, confidence, center}"""
import argparse, json, sys
import numpy as np, cv2
import os; sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))
from denimtwin.util.coins import COINS_MM
p = argparse.ArgumentParser(); p.add_argument("image"); p.add_argument("--coin", required=True, choices=sorted(COINS_MM)); p.add_argument("--mask"); p.add_argument("--out")
a = p.parse_args()
img = cv2.imread(a.image); g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY); H, W = g.shape
bg = np.ones((H, W), bool)
if a.mask: bg = cv2.dilate((cv2.imread(a.mask, 0) > 127).astype(np.uint8), np.ones((25, 25), np.uint8)) == 0
gb = cv2.GaussianBlur(g, (0, 0), 1.5)
# coins are 1–6% of the frame's short side in typical contributor photos
rmin, rmax = max(int(0.006 * min(H, W)), 6), int(0.05 * min(H, W))
circles = cv2.HoughCircles(gb, cv2.HOUGH_GRADIENT, dp=1.2, minDist=rmax, param1=120, param2=28, minRadius=rmin, maxRadius=rmax)
cands = []
if circles is not None:
    for x, y, r in circles[0]:
        x, y, r = int(x), int(y), int(r)
        if not (0 <= y < H and 0 <= x < W) or not bg[y, x]: continue
        m = np.zeros_like(g); cv2.circle(m, (x, y), max(r - 2, 1), 255, -1); ring = np.zeros_like(g); cv2.circle(ring, (x, y), r + 6, 255, 4)
        inside = g[m > 0]; outside = g[ring > 0]
        if len(inside) < 20 or len(outside) < 20: continue
        contrast = abs(float(inside.mean()) - float(outside.mean())); uniform = 1.0 / (1.0 + float(inside.std()) / 25.0)
        # edge support: fraction of the circle perimeter that has strong gradient
        edges = cv2.Canny(gb, 60, 140); per = np.zeros_like(g); cv2.circle(per, (x, y), r, 255, 2); support = float((edges[per > 0] > 0).mean())
        cands.append((support * (0.5 + 0.5 * uniform) * min(contrast / 40.0, 1.0), x, y, r, contrast, support))
if not cands: print(json.dumps({"error": "no coin-like circle found", "n_circles": 0 if circles is None else len(circles[0])})); sys.exit(1)
s, x, y, r, contrast, support = max(cands)
res = dict(center=[x, y], diameter_px=2 * r, mm_per_px=COINS_MM[a.coin] / (2 * r), coin=a.coin, confidence=float(s), edge_support=support, contrast=contrast, n_candidates=len(cands), note="verify visually; Hough radius is ±1–2 px")
print(json.dumps(res, indent=1))
if a.out: open(a.out, "w").write(json.dumps(res, indent=1))
