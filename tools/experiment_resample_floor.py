#!/usr/bin/env python3
"""EXP_0023 Part D — what does rotating a mask do to a hem-texture measurement?

Hem roughness is the only fray observable that has ever passed its negative control (EXP_0016). It measures how far
the garment's lower boundary deviates from its own local median, in pixels. A binary mask rotated by anything other
than a multiple of 90 degrees has a boundary that steps up and down by a pixel — and that is precisely the quantity.

Every mask in the evaluation path is rotated at least once: uprighting (EXP_0022/0023) and the registration warp that
brings the real after-photo into the prediction's frame. This measures the false roughness those rotations create, on
masks whose true answer is known — nine finished-hem controls that read exactly zero unrotated.

    experiment_resample_floor.py [--out reports/repeatability/resample_floor.json]

Reads the reference masks written by tools/experiment_repeatability.py (regenerate them if absent).
"""
import argparse, glob, json, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2

from denimtwin.eval.hem_texture import hem_roughness
from denimtwin.canon.autolm import landmarks_from_mask

ROOT = Path(__file__).resolve().parents[1]
ANGLES = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 8.0]
MODES = {"nearest": cv2.INTER_NEAREST, "linear": cv2.INTER_LINEAR}

def waist(mask):
    lm, _ = landmarks_from_mask(mask)
    return float(lm["waist_right"][0] - lm["waist_left"][0]) if "waist_left" in lm else None

def rotate(mask, deg, mode="nearest"):
    if deg == 0: return np.asarray(mask, bool)
    h, w = mask.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    if mode == "nearest":
        return cv2.warpAffine(mask.astype(np.uint8), M, (w, h), flags=cv2.INTER_NEAREST) > 0
    return cv2.warpAffine(mask.astype(np.float32), M, (w, h), flags=cv2.INTER_LINEAR) > 0.5

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--masks", default="reports/repeatability/masks")
    ap.add_argument("--out", default="reports/repeatability/resample_floor.json")
    a = ap.parse_args()
    files = sorted(glob.glob(str(ROOT / a.masks / "*.png")))
    if not files:
        print(f"no masks in {a.masks} (they are gitignored — regenerate with tools/experiment_repeatability.py)")
        return 1
    rows = []
    for f in files:
        m0 = cv2.imread(f, 0) > 127
        w0 = waist(m0)
        base = hem_roughness(m0, waist_px=w0)
        for mode in MODES:
            for d in ANGLES:
                m = rotate(m0, d, mode)
                w_ = waist(m) or w0
                r = hem_roughness(m, waist_px=w_)
                rows.append({"mask": Path(f).stem, "mode": mode, "deg": d,
                             "p90_rel": float(r.get("p90_rel", 0.0) or 0.0),
                             "rough_fraction": float(r["rough_fraction"]),
                             "base_p90_rel": float(base.get("p90_rel", 0.0) or 0.0),
                             "base_rough_fraction": float(base["rough_fraction"]),
                             "reads_as_frayed": bool(r.get("reads_as_frayed")),
                             "base_reads_as_frayed": bool(base.get("reads_as_frayed"))})
    smooth = sorted({r["mask"] for r in rows if r["base_p90_rel"] == 0.0})
    induced = [r["p90_rel"] for r in rows if r["mask"] in smooth and r["deg"] > 0 and r["mode"] == "nearest"]
    flipped = sorted({r["mask"] for r in rows if r["mask"] in smooth and r["deg"] > 0 and r["reads_as_frayed"]})
    out = {"angles_deg": ANGLES, "rows": rows,
           "masks_reading_zero_unrotated": smooth,
           "n_masks_reading_zero_unrotated": len(smooth),
           "n_of_those_that_read_frayed_after_a_rotation": len(flipped),
           "which_flip": flipped,
           "induced_p90_rel_median": float(np.median(induced)) if induced else None,
           # most rotations of most masks induce nothing; the number that matters is how big the artefact is WHEN it
           # fires, because that is what lands in a metric and gets averaged with real measurements
           "induced_p90_rel_median_when_it_fires": (float(np.median([x for x in induced if x > 0]))
                                                    if any(x > 0 for x in induced) else None),
           "n_readings_that_fire": int(sum(1 for x in induced if x > 0)), "n_readings": len(induced),
           "induced_p90_rel_max": float(max(induced)) if induced else None,
           "induced_p90_rel_at_1deg": float(np.median([r["p90_rel"] for r in rows if r["mask"] in smooth
                                                       and r["deg"] == 1.0 and r["mode"] == "nearest"]))}
    (ROOT / a.out).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / a.out).write_text(json.dumps(out, indent=1))
    print(f"{len(smooth)} masks read p90 = 0 unrotated; {len(flipped)} of them read FRAYED after a rotation")
    print(f"induced p90_rel: median {out['induced_p90_rel_median']:.5f}, max {out['induced_p90_rel_max']:.5f}, "
          f"at 1 degree {out['induced_p90_rel_at_1deg']:.5f}")
    for mode in MODES:
        v = [r["p90_rel"] for r in rows if r["mask"] in smooth and r["deg"] > 0 and r["mode"] == mode]
        print(f"  {mode:8s} median induced {np.median(v):.5f}  frayed readings {sum(1 for x in v if x > 0)}/{len(v)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
