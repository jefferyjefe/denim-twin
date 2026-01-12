#!/usr/bin/env python3
"""Null-baseline enforcer. For an experiment dir containing:
   orig.png  pred.png  keep_mask.png (255=unchanged region)  [real.png = registered real after-capture]
computes identity (and, if real.png exists, geometry/appearance) metrics for the prediction AND for
trivial systems: no-op (return orig), crop-only (orig with ~keep set to background), blur-pred.
Appends a markdown table to NOTE.md and exits 1 if the prediction fails to beat no-op on any
metric that is supposed to discriminate. Usage: null_baselines.py experiments/EXP_xxxx"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.eval import identity as I, geometry as G

d = sys.argv[1]
orig = cv2.imread(f"{d}/orig.png"); pred = cv2.imread(f"{d}/pred.png"); keep = cv2.imread(f"{d}/keep_mask.png", 0) > 127
real = cv2.imread(f"{d}/real.png") if os.path.exists(f"{d}/real.png") else None
rmask = cv2.imread(f"{d}/real_mask.png", 0) > 127 if os.path.exists(f"{d}/real_mask.png") else None
removed = cv2.imread(f"{d}/removed_mask.png", 0) > 127 if os.path.exists(f"{d}/removed_mask.png") else ~keep
bg = np.median(orig[~keep], axis=0) if (~keep).any() else np.array([0, 0, 0])
systems = {"prediction": (pred, keep), "null:no-op": (orig.copy(), keep | removed),
           "null:crop-only": (np.where(keep[..., None], orig, bg.astype(np.uint8)), keep),
           "null:blurred-pred": (cv2.GaussianBlur(pred, (0, 0), 2), keep)}
rows = []
for name, (im, sil) in systems.items():
    row = dict(system=name, ssim_keep=I.unchanged_ssim(im, orig, keep), dE_keep=I.unchanged_color_delta_e(im, orig, keep),
               feat_ret=I.feature_retention(im, orig, keep), changed_out=I.changed_pixel_fraction_outside(im, orig, keep))
    if real is not None:
        if rmask is not None: row["sil_iou_vs_real"] = G.silhouette_iou(sil, rmask)
        row["ssim_vs_real_cut"] = I.unchanged_ssim(im, real, ~keep) if (~keep).any() else float("nan")
    rows.append(row)
cols = list(rows[0]); md = "| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
for r in rows: md += "| " + " | ".join(r[c] if isinstance(r[c], str) else f"{r[c]:.4f}" for c in cols) + " |\n"
verdict = []
if real is not None:
    p, n = rows[0], rows[1]
    for m in ("sil_iou_vs_real", "ssim_vs_real_cut"):
        if m in p and p[m] <= n[m]: verdict.append(f"prediction does NOT beat no-op on {m}")
else:
    verdict.append("no real.png: identity metrics alone are UNINFORMATIVE (no-op scores perfectly by construction)")
note = f"\n\n## Null baselines (auto)\n{md}\n" + ("\n".join("- " + v for v in verdict) or "- prediction beats no-op on all outcome metrics") + "\n"
open(f"{d}/NOTE.md", "a").write(note); print(note)
sys.exit(1 if any("NOT" in v for v in verdict) else 0)
