#!/usr/bin/env python3
"""One command per found/contributed pair: before + after images -> prediction, registration, scoring.

Usage: run_pair.py --before B.jpg --after A.jpg --out experiments/PAIR_x [--before-lm B.json] [--after-lm A.json]
                   [--mm-per-px 1.0] [--seed 1]
Landmarks default to the mask-based heuristic (canon/autolm.py); pass JSON files to override.
Writes: masks, landmarks (auto/used), cut, fringe predictions (3 presets), registered real, metrics for each preset
with null baselines, a panel.jpg, and NOTE.md."""
import argparse, json, os, sys, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.canon.register import warp_after_to_before, SURVIVING
from denimtwin.canon.hemfit import estimate_hems, cut_mask_from_lines
from denimtwin.canon.rawedge_v1 import render_three

p = argparse.ArgumentParser()
p.add_argument("--before", required=True); p.add_argument("--after", required=True); p.add_argument("--out", required=True)
p.add_argument("--before-lm"); p.add_argument("--after-lm"); p.add_argument("--mm-per-px", type=float, default=None); p.add_argument("--seed", type=int, default=1)
a = p.parse_args(); os.makedirs(a.out, exist_ok=True); O = a.out
bf = cv2.imread(a.before); af = cv2.imread(a.after); assert bf is not None and af is not None
seg = SamSegmenter()
# masks: first pass with a coarse box (whole image minus margins), then refine with auto landmarks
def coarse(img):
    m, sc, info = segment_garment_coarse(seg, img)
    if m is None: print("coarse segmentation failed"); sys.exit(2)
    print(f"coarse mask score {sc:.3f} area {info['area']:.2f} border {info['border_frac']:.2f}"); return m
bmask = coarse(bf); amask = coarse(af)
lmb_auto, cb = landmarks_from_mask(bmask); lma_auto, ca = landmarks_from_mask(amask)
lmb = json.load(open(a.before_lm))["landmarks"] if a.before_lm else lmb_auto
lma = json.load(open(a.after_lm))["landmarks"] if a.after_lm else lma_auto
if not a.before_lm and len(lmb) >= 14: bmask, _ = seg.segment(bf, landmarks=lmb)          # refine with landmark prompts
json.dump({"before_auto": lmb_auto, "after_auto": lma_auto, "before_used": lmb, "after_used": lma, "conf": {"before": cb, "after": ca}}, open(f"{O}/landmarks.json", "w"), indent=1, default=int)
mmpp = a.mm_per_px or 1.0; scale_note = "given" if a.mm_per_px else "UNKNOWN (1.0 placeholder; mm values are px)"
real, rmask, resid = warp_after_to_before(af, amask, lma, lmb, bf.shape, use=[n for n in SURVIVING if n in lma and n in lmb])
legs = estimate_hems(rmask, bmask, lmb, real_img=real)
if not any(L and L["line"] for L in legs.values()): print("hem fit failed"); sys.exit(2)
removed = cut_mask_from_lines(bmask, lmb, legs); keep = bmask & ~removed
bg = np.median(bf[~bmask], axis=0); cut = bf.copy(); cut[removed] = bg
depth_px = np.mean([L["fringe_depth_px"] for L in legs.values() if L]); depth_mm = depth_px * mmpp
res = render_three(cut, removed, bmask, mmpp, seed=a.seed, depth_override={"conservative": depth_mm * 0.5, "median": depth_mm, "aggressive": depth_mm * 1.5})
for k, (im, ch) in res.items():
    cv2.imwrite(f"{O}/pred_{k}.png", im); cv2.imwrite(f"{O}/pred_{k}_mask.png", ((keep | (ch & removed)).astype(np.uint8) * 255))
for n, im in (("orig", bf), ("cut", cut), ("keep_mask", keep.astype(np.uint8) * 255), ("removed_mask", removed.astype(np.uint8) * 255), ("bmask", bmask.astype(np.uint8) * 255), ("amask", amask.astype(np.uint8) * 255), ("real", real), ("real_mask", rmask.astype(np.uint8) * 255)):
    cv2.imwrite(f"{O}/{n}.png", im)
cv2.imwrite(f"{O}/pred.png", res["median"][0]); json.dump({"landmarks": lmb}, open(f"{O}/before_lm.json", "w")); json.dump({"landmarks": lma}, open(f"{O}/after_lm.json", "w"))
rows = {}
for k in res:
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "compare.py"), "--before", a.before, "--before-lm", f"{O}/before_lm.json", "--pred", f"{O}/pred_{k}.png", "--pred-mask", f"{O}/pred_{k}_mask.png",
                        "--keep", f"{O}/keep_mask.png", "--removed", f"{O}/removed_mask.png", "--after", a.after, "--after-lm", f"{O}/after_lm.json", "--after-mask", f"{O}/amask.png", "--out", f"{O}/cmp_{k}"] + (["--mm-per-px", str(mmpp)] if a.mm_per_px else []), capture_output=True, text=True)
    rows[k] = json.load(open(f"{O}/cmp_{k}/metrics.json"))["rows"]
# panel
y0 = int(np.nonzero(removed)[0].min()) if removed.any() else bf.shape[0] // 2; H = bf.shape[0]
crop = lambda im: im[max(y0 - int(0.15 * H), 0): min(y0 + int(0.2 * H), H)]
tiles = [crop(bf), crop(res["median"][0]), crop(real)]
for t, n in zip(tiles, ("before", f"pred median (depth {depth_mm:.0f} {'mm' if a.mm_per_px else 'px'})", "real registered")): cv2.putText(t, n, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
cv2.imwrite(f"{O}/panel.jpg", np.concatenate(tiles, 1))
def row(name, r): return f"| {name} | {r['sil_iou_vs_real']:.3f} | {r['hem_chamfer']:.1f} | {r['dE_edge_band_vs_real']:.1f} | {r['fringe_iou_vs_real']:.3f} |"
md = f"# PAIR — auto pipeline\n\nbefore: {a.before}\nafter: {a.after}\nscale: {scale_note}\nlandmarks: {'manual' if a.before_lm else 'auto'} / {'manual' if a.after_lm else 'auto'} (crotch: {cb.get('crotch')} / {ca.get('crotch')})\n"
md += f"hem fit: " + ", ".join(f"{k}: angle {L['angle_deg']:.1f}°, depth {L['fringe_depth_px']*mmpp:.0f}" for k, L in legs.items() if L) + f"\nregistration residual (landmarks, not held-out): {resid:.2f}px\n\n"
md += "| system | sil IoU | chamfer | edge ΔE | fringe IoU |\n|---|---|---|---|---|\n"
for k in res:
    for r in rows[k]:
        if r["system"] == "prediction": md += row(f"pred {k}", r) + "\n"
for r in rows["median"]:
    if r["system"] != "prediction": md += row(r["system"], r) + "\n"
open(f"{O}/NOTE.md", "w").write(md); print(md)
