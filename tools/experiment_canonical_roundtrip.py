#!/usr/bin/env python3
"""EXP_0029 — does canonical space give the garment back?

`docs/PLAN_PROGRESS.md` records `canon/warp.py` as "sub-pixel round-trip; exact per-pixel maps". `CanonicalMap` fits
**two independent** thin-plate splines — one image->canonical, one canonical->image — from the same landmark
correspondences. Two independent fits agree exactly at the points they were fitted to and nowhere in particular
between them. Everything this project expresses in canonical space is expressed away from those points: the cut line,
`inseam_fraction`, the template, the wash.

    experiment_canonical_roundtrip.py [--pairs experiments/pairs] [--out reports/canonical_roundtrip.json]

Measures, per pair:
  point round trip   image -> canonical -> image, at the landmarks and over the garment mask
  region round trip  IoU of the removed mask with itself after the same journey
"""
import argparse, glob, json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2

from denimtwin.canon.warp import CanonicalMap

ROOT = Path(__file__).resolve().parents[1]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="experiments/pairs")
    ap.add_argument("--out", default="reports/canonical_roundtrip.json")
    ap.add_argument("--samples", type=int, default=600)
    a = ap.parse_args()
    excl = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines()
            if l.strip() and not l.startswith("#")}
    rows = []
    for f in sorted(glob.glob(str(ROOT / a.pairs / "*/before_lm.json"))):
        pid = Path(f).parent.name
        if pid in excl: continue
        note = Path(f).parent / "NOTE.md"
        if note.exists() and note.read_text().splitlines()[0].startswith("# PAIR — rejected"): continue
        lm = json.load(open(f))["landmarks"]
        bm = cv2.imread(str(Path(f).parent / "bmask.png"), 0)
        rm = cv2.imread(str(Path(f).parent / "removed_mask.png"), 0)
        if bm is None or rm is None: continue
        bm = bm > 127; rm = rm > 127
        try: cm = CanonicalMap(lm)
        except Exception as e:
            rows.append({"pair": pid, "error": f"{type(e).__name__}: {e}"}); continue
        ys, xs = np.nonzero(bm)
        idx = np.linspace(0, len(xs) - 1, min(a.samples, len(xs))).astype(int)
        P = np.stack([xs[idx], ys[idx]], 1).astype(np.float32)
        back = np.asarray(cm.points_to_image(np.asarray(cm.points_to_canon(P))))
        err = np.linalg.norm(back - P, axis=1)
        L = np.array([lm[n] for n in cm.names], np.float32)
        lerr = np.linalg.norm(np.asarray(cm.points_to_image(np.asarray(cm.points_to_canon(L)))) - L, axis=1)
        canon = np.asarray(cm.image_to_canon((rm.astype(np.uint8) * 255))) > 127
        again = np.asarray(cm.canon_to_image((canon.astype(np.uint8) * 255), rm.shape)) > 127
        iou = float((again & rm).sum() / max((again | rm).sum(), 1))
        leg = abs(lm["hem_left_outer"][1] - lm["crotch"][1]) if "hem_left_outer" in lm and "crotch" in lm else None
        rows.append({"pair": pid, "n_landmarks": len(cm.names),
                     "point_err_at_landmarks_px": float(np.median(lerr)),
                     "point_err_over_garment_px": float(np.median(err)),
                     "point_err_p90_px": float(np.percentile(err, 90)),
                     "point_err_max_px": float(err.max()),
                     "point_err_over_garment_pct_of_leg": (100 * float(np.median(err)) / leg) if leg else None,
                     "region_roundtrip_iou": iou})
    ok = [r for r in rows if "error" not in r]
    out = {"n_pairs": len(ok), "pairs": rows,
           "median_point_err_at_landmarks_px": float(np.median([r["point_err_at_landmarks_px"] for r in ok])) if ok else None,
           "median_point_err_over_garment_px": float(np.median([r["point_err_over_garment_px"] for r in ok])) if ok else None,
           "worst_point_err_px": float(max(r["point_err_max_px"] for r in ok)) if ok else None,
           "median_region_roundtrip_iou": float(np.median([r["region_roundtrip_iou"] for r in ok])) if ok else None,
           "worst_region_roundtrip_iou": float(min(r["region_roundtrip_iou"] for r in ok)) if ok else None,
           "pairs_with_faithful_region_roundtrip": sorted(r["pair"] for r in ok if r["region_roundtrip_iou"] >= 0.9),
           "n_pairs_with_faithful_region_roundtrip": sum(1 for r in ok if r["region_roundtrip_iou"] >= 0.9)}
    (ROOT / a.out).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / a.out).write_text(json.dumps(out, indent=1))
    print(f"{'pair':12s} {'at landmarks':>13s} {'over garment':>13s} {'p90':>8s} {'max':>9s} {'region IoU':>11s}")
    for r in ok:
        print(f"{r['pair']:12s} {r['point_err_at_landmarks_px']:13.2f} {r['point_err_over_garment_px']:13.2f} "
              f"{r['point_err_p90_px']:8.1f} {r['point_err_max_px']:9.1f} {r['region_roundtrip_iou']:11.3f}")
    print(f"\nmedian point error: {out['median_point_err_at_landmarks_px']:.2f} px at the landmarks, "
          f"{out['median_point_err_over_garment_px']:.2f} px over the garment (worst {out['worst_point_err_px']:.0f} px)")
    print(f"region round-trip IoU: median {out['median_region_roundtrip_iou']:.3f}, worst "
          f"{out['worst_region_roundtrip_iou']:.3f}; faithful (>=0.90) on "
          f"{out['n_pairs_with_faithful_region_roundtrip']} of {out['n_pairs']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
