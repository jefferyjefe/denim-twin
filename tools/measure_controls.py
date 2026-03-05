#!/usr/bin/env python3
"""Measure hem roughness on the finished-hem control set, and write the artefact the notes cite.

The addendum to EXP_0016 publishes a control table — nine high-resolution finished-hem denim shorts, measured under
consensus segmentation with no mask-quality gate, zero false positives — and no script in the repo produced it.
`reports/fringe_methods/controls_roughness.json` was left behind by an ad-hoc run and still records the
contour-compactness gate that review 6 removed ("mask outline too ragged to judge (compactness 3.96 > 3.0)"), so the
artefact and the note disagreed about what code they describe. This makes the table reproducible.

    measure_controls.py [--seg consensus|coarse] [--out reports/fringe_methods/controls_roughness.json]

Controls are all-rights-reserved retailer photographs (`data/external/control_candidates.jsonl`); the images live in
data/external/control_images/ and are gitignored. Only derived numbers are written.
"""
import argparse, json, os, sys, glob
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2

from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse
from denimtwin.seg.validate import segment_garment_consensus
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.eval.hem_texture import hem_roughness, mask_compactness

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "data/external/control_images"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seg", choices=["consensus", "coarse"], default="consensus")
    ap.add_argument("--out", default="reports/fringe_methods/controls_roughness.json")
    a = ap.parse_args()
    files = sorted(glob.glob(str(IMG / "*.jpg"))) + sorted(glob.glob(str(IMG / "*.jpeg")))
    if not files:
        print(f"no control images in {IMG} (gitignored; harvest with tools/harvest_images.py)"); return 1
    seg = SamSegmenter()
    rows = []
    for f in files:
        img = cv2.imread(f); stem = Path(f).stem
        if a.seg == "consensus":
            m, agr, info = segment_garment_consensus(seg, img, boundary="member")
            prov = {"segmentation": "consensus", "agreement": float(agr), "reason": info.get("reason")}
        else:
            m, sc, info = segment_garment_coarse(seg, img)
            prov = {"segmentation": "coarse", "score": float(sc) if m is not None else None}
        if m is None:
            rows.append({"id": stem, "file": Path(f).name, "ok": False, "hem_finish": "finished",
                         "reason": "segmentation refused", **prov}); continue
        lm, _ = landmarks_from_mask(m)
        ww = float(lm["waist_right"][0] - lm["waist_left"][0]) if "waist_left" in lm else None
        r = hem_roughness(m, waist_px=ww)
        rows.append({"id": stem, "file": Path(f).name, "hem_finish": "finished", "px": [img.shape[1], img.shape[0]],
                     "waist_px": ww, "ok": bool(r["ok"]), "rough_p90": float(r["p90_px"]),
                     "rough_p90_rel": float(r.get("p90_rel", 0.0) or 0.0), "rough_fraction": float(r["rough_fraction"]),
                     "compactness": float(mask_compactness(m)), "n_columns": int(r["n_columns"]),
                     "reason": r.get("reason"), "called_frayed": bool(r["ok"] and r["p90_px"] > 0), **prov})
    out = ROOT / a.out; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=1))
    ok = [r for r in rows if r["ok"]]
    fp = [r for r in ok if r["called_frayed"]]
    print(f"{len(rows)} controls, {len(ok)} measured, {len(fp)} called frayed (false positives)"
          f"{': ' + ', '.join(r['id'] for r in fp) if fp else ''}")
    print(f"waist widths {min((r['waist_px'] for r in ok if r['waist_px']), default=0):.0f}"
          f"–{max((r['waist_px'] for r in ok if r['waist_px']), default=0):.0f} px")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
