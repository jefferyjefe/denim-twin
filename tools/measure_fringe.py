#!/usr/bin/env python3
"""Measure a real frayed hem's coverage profile from a photo (close-up or registered after-wash image).

Given an image where the garment is above and background below (or any orientation given --rotate), find the
fabric edge per column (last row whose colour is close to the fabric body) and the fringe tip (last row whose
colour differs from the background), then compute coverage(d) = fraction of pixels that are 'thread' at distance d
below the fabric edge, normalised by the fringe depth. Output: JSON with depth_px, coverage profile (10 bins),
mean coverage, and a fitted falloff exponent for rawedge_v1 (coverage ≈ c0 * (1 - d/D)^k)."""
import argparse, json, sys
import numpy as np, cv2
p = argparse.ArgumentParser(); p.add_argument("image"); p.add_argument("--rotate", type=int, default=0, help="degrees to rotate so the hem hangs downward")
p.add_argument("--out"); a = p.parse_args()
img = cv2.imread(a.image); assert img is not None
if a.rotate: img = np.rot90(img, k=(a.rotate // 90) % 4)
lab = cv2.cvtColor(img.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB); H, W = lab.shape[:2]
bg = np.median(lab[-max(H // 20, 3):], axis=(0, 1))                       # background = bottom rows
body = np.median(lab[: max(H // 5, 3)], axis=(0, 1))                       # fabric body = top rows
d_bg = np.linalg.norm(lab - bg, axis=2); d_body = np.linalg.norm(lab - body, axis=2)
is_thing = d_bg > 12; is_fabric = (d_body < d_bg) & is_thing
edge = np.full(W, -1); tip = np.full(W, -1)
for x in range(W):
    f = np.nonzero(is_fabric[:, x])[0]; t = np.nonzero(is_thing[:, x])[0]
    if len(f) and len(t): edge[x] = f.max(); tip[x] = t.max()
ok = (edge > 0) & (tip > edge)
if ok.sum() < W * 0.2: print(json.dumps({"error": "could not find a hem edge (check --rotate)"})); sys.exit(1)
depth = (tip - edge)[ok]; D = float(np.median(depth))
bins = np.linspace(0, 1, 11); cov = np.zeros(10); cnt = np.zeros(10)
for x in np.nonzero(ok)[0]:
    for y in range(edge[x] + 1, min(edge[x] + int(D * 1.2), H)):
        b = min(int((y - edge[x]) / max(D, 1) * 10), 9); cov[b] += is_thing[y, x]; cnt[b] += 1
prof = (cov / np.maximum(cnt, 1)).tolist()
# fit coverage ≈ c0 (1 - d)^k over bins with d<1
d = (bins[:-1] + bins[1:]) / 2; y = np.clip(np.array(prof), 1e-3, 1); m = d < 0.95
k = float(np.polyfit(np.log(1 - d[m]), np.log(y[m]), 1)[0]) if m.sum() >= 3 else float("nan")
res = dict(image=a.image, width_px=W, depth_px_median=D, depth_px_p10=float(np.percentile(depth, 10)), depth_px_p90=float(np.percentile(depth, 90)),
           coverage_profile=prof, coverage_at_edge=prof[0], falloff_k=k, columns_used=int(ok.sum()))
print(json.dumps(res, indent=1))
if a.out: open(a.out, "w").write(json.dumps(res, indent=1))
