#!/usr/bin/env python3
"""Score a prediction against the real after-capture, in the before-image frame.

Usage: compare.py --before B.jpg --before-lm B.json --pred PRED.png --keep KEEP.png --removed REMOVED.png \
                  --after A.jpg --after-lm A.json [--after-mask M.png] [--mm-per-px 0.34] --out DIR
Writes DIR/{real_registered.png, real_mask.png, metrics.json, metrics.md} including null baselines
(no-op, crop-only) so a gamed metric is visible. Also writes DIR/{orig,pred,keep_mask,real}.png for
tools/null_baselines.py and tools/judge_pairs.py."""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.canon.register import warp_after_to_before
from denimtwin.eval import identity as I, geometry as G

p = argparse.ArgumentParser()
for k in ("before", "before-lm", "pred", "keep", "removed", "after", "after-lm"): p.add_argument("--" + k, required=True)
p.add_argument("--after-mask"); p.add_argument("--pred-mask", help="predicted garment mask incl. fringe (default: keep)"); p.add_argument("--mm-per-px", type=float); p.add_argument("--out", required=True)
a = p.parse_args(); os.makedirs(a.out, exist_ok=True)
before = cv2.imread(a.before); pred = cv2.imread(a.pred); after = cv2.imread(a.after)
keep = cv2.imread(a.keep, 0) > 127; removed = cv2.imread(a.removed, 0) > 127
lmb = json.load(open(a.before_lm))["landmarks"]; lma = json.load(open(a.after_lm))["landmarks"]
if a.after_mask: amask = cv2.imread(a.after_mask, 0) > 127
else:
    from denimtwin.seg.sam import SamSegmenter
    amask, _ = SamSegmenter().segment(after, landmarks={**lma, **{k: lma.get(k, v) for k, v in lma.items()}}) if all(k in lma for k in ("hem_left_outer",)) else (None, None)
    if amask is None:
        g = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY); amask = np.abs(g.astype(int) - np.median(g[:8])) > 40
real, rmask, resid = warp_after_to_before(after, amask, lma, lmb, before.shape)
p.add_argument  # (no-op; keeps linters quiet)
real_raw = real.copy()
real = I.match_lighting(real, before, keep & rmask)      # normalise lighting on the unchanged region before scoring
garment_before = keep | removed
pm = (cv2.imread(a.pred_mask, 0) > 127) if a.pred_mask else keep   # predicted post-cut silhouette incl. fringe
bg = np.median(before[~garment_before], axis=0).astype(np.uint8) if (~garment_before).any() else np.zeros(3, np.uint8)
systems = {"prediction": (pred, pm), "null:no-op": (before, garment_before),
           "null:crop-only": (np.where(keep[..., None], before, bg), keep)}
rows = []
for name, (im, sil) in systems.items():
    r = dict(system=name,
             sil_iou_vs_real=G.silhouette_iou(sil, rmask),
             hem_chamfer=G.boundary_chamfer(G.mask_boundary(sil), G.mask_boundary(rmask), a.mm_per_px),
             ssim_keep_vs_real=I.unchanged_ssim(im, real, keep & rmask),
             dE_keep_vs_real=I.unchanged_color_delta_e(im, real, keep & rmask),
             feat_ret_keep_vs_real=I.feature_retention(im, real, keep & rmask),
             ssim_keep_vs_before=I.unchanged_ssim(im, before, keep))
    # edge-region appearance: band within ±15 mm (or 40 px) of the cut edge, BOTH sides, where either the
    # real or the predicted garment exists (so fringe pixels count). Also report plain SSIM there.
    band_px = int(15 / a.mm_per_px) if a.mm_per_px else 40
    d_in = cv2.distanceTransform(keep.astype(np.uint8), cv2.DIST_L2, 3); d_out = cv2.distanceTransform((~keep).astype(np.uint8), cv2.DIST_L2, 3)
    band = ((keep & (d_in <= band_px)) | (~keep & (d_out <= band_px))) & garment_before & (rmask | sil)
    r["ssim_edge_band_vs_real"] = I.unchanged_ssim(im, real, band) if band.sum() > 500 else float("nan")
    r["dE_edge_band_vs_real"] = I.unchanged_color_delta_e(im, real, band) if band.sum() > 500 else float("nan")
    r["fringe_iou_vs_real"] = G.silhouette_iou(sil & ~keep & garment_before, rmask & ~keep & garment_before)
    rows.append(r)
cols = list(rows[0]); md = f"registration residual (leave-one-landmark-out): {resid:.2f} px; lighting matched on kept region\n\n| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
for r in rows: md += "| " + " | ".join(r[c] if isinstance(r[c], str) else f"{r[c]:.4f}" for c in cols) + " |\n"
unit = "mm" if a.mm_per_px else "px"; md += f"\n(hem_chamfer in {unit})\n"
json.dump(dict(registration_residual_px=resid, rows=rows), open(f"{a.out}/metrics.json", "w"), indent=1)
open(f"{a.out}/metrics.md", "w").write(md); print(md)
cv2.imwrite(f"{a.out}/real_registered.png", real); cv2.imwrite(f"{a.out}/real_registered_raw.png", real_raw); cv2.imwrite(f"{a.out}/real_mask.png", rmask.astype(np.uint8) * 255)
cv2.imwrite(f"{a.out}/orig.png", before); cv2.imwrite(f"{a.out}/pred.png", pred); cv2.imwrite(f"{a.out}/keep_mask.png", keep.astype(np.uint8) * 255); cv2.imwrite(f"{a.out}/real.png", real); cv2.imwrite(f"{a.out}/removed_mask.png", removed.astype(np.uint8) * 255)
