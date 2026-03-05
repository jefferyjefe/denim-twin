#!/usr/bin/env python3
"""EXP_0021 Part A — two photographs of ONE garment, measured twice (Gate 1's actual question).

The dataset contains exactly one garment photographed twice: a front and a back view of the same pair of acid-wash
cut-offs, from one tutorial page (img_4536 / img_4540 -> b0576a1603 / de6740d5b9). EXP_0018 ran the pipeline on both
and got waist widths of 874 px and 191 px, because best-score SAM segmented a single back pocket at score 0.906.
EXP_0019 showed consensus segmentation returns the whole garment on that file. This re-runs the measurement under
both methods and reports what a *scale-free* comparison of the two views gives.

What the comparison can and cannot establish:
  - it CAN detect gross segmentation failure (the 4.6x waist discrepancy EXP_0018 found);
  - it CANNOT establish a measurement tolerance, because a front view and a back view of the same garment are not
    the same measurement: the back rise is longer than the front rise on real trousers, pockets change the outline,
    and the two photographs differ in distance, angle and lighting. Agreement here is necessary, not sufficient.
  - n = 1 garment. This is a sanity check with a sample size of one, and is reported as such.

    experiment_same_garment.py [--out reports/repeatability/same_garment.json]
"""
import argparse, json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2

from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse
from denimtwin.seg.validate import segment_garment_consensus
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.eval.hem_texture import hem_roughness, mask_compactness

ROOT = Path(__file__).resolve().parents[1]
IMGS = ROOT / "data/external/unpaired_images"

# The one same-garment pair in the dataset. Source: expressthrudress.wordpress.com DIY cut-off post, images
# img_4536.jpg (front) and img_4540.jpg (back) of one finished pair — sha1[:10] of the image URL is the local name.
SAME_GARMENT = {"garment": "expressthrudress_acidwash_cutoffs",
                "views": {"front": "b0576a1603", "back": "de6740d5b9"},
                "page": "https://expressthrudress.wordpress.com/2012/05/23/diy-create-your-own-denim-cut-off-shorts/"}

def measure(mask):
    m = np.asarray(mask, bool)
    out = {"area_frac": float(m.mean())}
    lm, conf = landmarks_from_mask(m)
    out["garment_type"] = conf.get("garment_type")
    if "waist_left" in lm and "waist_right" in lm:
        ww = float(lm["waist_right"][0] - lm["waist_left"][0]); out["waist_px"] = ww
        if ww > 4:
            ys = np.nonzero(m.any(axis=1))[0]
            top = float(lm["waist_left"][1]); bot = float(ys.max())
            out["height_over_waist"] = (bot - top) / ww
            if "hip_left" in lm: out["hip_over_waist"] = float(lm["hip_right"][0] - lm["hip_left"][0]) / ww
            if "crotch" in lm: out["rise_over_waist"] = (float(lm["crotch"][1]) - top) / ww
    r = hem_roughness(m, waist_px=out.get("waist_px"))
    out.update(rough_ok=bool(r.get("ok")), rough_p90_px=float(r.get("p90_px", 0.0)),
               rough_p90_rel=float(r.get("p90_rel", 0.0) or 0.0), rough_fraction=float(r.get("rough_fraction", 0.0)),
               compactness=float(mask_compactness(m)))
    return out

STATS = ["height_over_waist", "hip_over_waist", "rise_over_waist", "rough_p90_rel", "rough_fraction"]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/repeatability/same_garment.json")
    a = ap.parse_args()
    seg = SamSegmenter()
    res = {"garment": SAME_GARMENT["garment"], "page": SAME_GARMENT["page"], "n_garments": 1, "views": {}}
    for view, stem in SAME_GARMENT["views"].items():
        p = IMGS / f"{stem}.jpg"
        if not p.exists():
            res["views"][view] = {"error": f"image not on disk ({p.name}); fetch with tools/ingest_unpaired.py --fetch"}
            continue
        img = cv2.imread(str(p)); res["views"][view] = {"file": stem, "px": [img.shape[1], img.shape[0]]}
        mb, sc, _ = segment_garment_coarse(seg, img)
        mc, agr, info = segment_garment_consensus(seg, img, boundary="member")
        res["views"][view]["best"] = {"score": float(sc), **(measure(mb) if mb is not None else {})}
        res["views"][view]["consensus"] = {"agreement": float(agr), "denim_frac": info.get("denim_frac"),
                                           **(measure(mc) if mc is not None else {})}
        if mb is not None and mc is not None:
            i = (mb & mc).sum() / max((mb | mc).sum(), 1)
            res["views"][view]["iou_best_vs_consensus"] = float(i)
    # cross-view agreement, per method
    res["agreement_between_views"] = {}
    for meth in ("best", "consensus"):
        d = {}
        for k in STATS:
            vals = [res["views"][v][meth].get(k) for v in ("front", "back")
                    if meth in res["views"].get(v, {}) and res["views"][v][meth].get(k) is not None]
            if len(vals) == 2:
                lo, hi = min(vals), max(vals)
                d[k] = {"front": res["views"]["front"][meth].get(k), "back": res["views"]["back"][meth].get(k),
                        "abs_diff": hi - lo, "ratio": (hi / lo) if lo > 1e-9 else None}
        ww = [res["views"][v][meth].get("waist_px") for v in ("front", "back") if res["views"].get(v, {}).get(meth, {}).get("waist_px")]
        if len(ww) == 2: d["waist_px"] = {"front": ww[0], "back": ww[1], "ratio": max(ww) / min(ww)}
        res["agreement_between_views"][meth] = d
    out = ROOT / a.out; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    print(json.dumps(res["agreement_between_views"], indent=1))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
