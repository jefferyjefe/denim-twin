#!/usr/bin/env python3
"""Run the 2D cut baseline on a real photo. Usage: run_baseline.py IMAGE LANDMARKS.json --inseam-frac 0.35 [--mask MASK.png] [--out DIR]
Without --mask, a garment mask is estimated by GrabCut seeded from the landmark hull (pilot-quality; correct manually if wrong)."""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.eval import identity as I

p = argparse.ArgumentParser()
p.add_argument("image"); p.add_argument("landmarks"); p.add_argument("--inseam-frac", type=float, required=True)
p.add_argument("--mask"); p.add_argument("--out", default="experiments/baseline_out")
a = p.parse_args(); os.makedirs(a.out, exist_ok=True)
img = cv2.imread(a.image); lm = json.load(open(a.landmarks))["landmarks"]
if a.mask:
    mask = cv2.imread(a.mask, 0) > 127
else:
    # seed from the garment OUTLINE polygon (not the convex hull) so the gap between legs stays background
    outline = ["waist_left", "waist_right", "hip_right", "knee_right_outer", "hem_right_outer", "hem_right_inner",
               "knee_right_inner", "crotch", "knee_left_inner", "hem_left_inner", "hem_left_outer", "knee_left_outer", "hip_left"]
    poly = np.array([lm[n] for n in outline], np.float32).astype(np.int32)
    gc = np.full(img.shape[:2], cv2.GC_PR_BGD, np.uint8); cv2.fillPoly(gc, [poly], cv2.GC_PR_FGD)
    er = cv2.erode((gc == cv2.GC_PR_FGD).astype(np.uint8), np.ones((41, 41), np.uint8)); gc[er > 0] = cv2.GC_FGD
    cv2.grabCut(img, gc, None, np.zeros((1, 65)), np.zeros((1, 65)), 5, cv2.GC_INIT_WITH_MASK)
    mask = (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
    cv2.imwrite(os.path.join(a.out, "mask_auto.png"), mask.astype(np.uint8) * 255)
cm = CanonicalMap(lm)
out, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=a.inseam_frac))
cv2.imwrite(os.path.join(a.out, "canonical.png"), cm.image_to_canon(img))
cv2.imwrite(os.path.join(a.out, "cut.png"), out)
cv2.imwrite(os.path.join(a.out, "diff.png"), I.diff_map(out, img).astype(np.uint8) * 255)
print(json.dumps({"removed_px": int(removed.sum()), "garment_px": int(mask.sum()),
                  "changed_outside_cut": I.changed_pixel_fraction_outside(out, img, keep)}, indent=2))
