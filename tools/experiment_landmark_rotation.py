#!/usr/bin/env python3
"""EXP_0021 Part C — how much camera tilt does the landmark heuristic tolerate?

Part B found the scale-free shape ratios swing ~30% at an 8-degree rotation while the segmentation mask is still
essentially perfect (IoU 0.994). That means the swing is not segmentation: `canon/autolm.landmarks_from_mask` measures
axis-aligned extents (leftmost/rightmost pixel in a horizontal band, lowest pixel in a column), which are not
rotation-invariant. This isolates the effect completely: take a mask that is already correct, rotate the MASK, and
measure. No SAM, no photograph, no confound.

    experiment_landmark_rotation.py [--out reports/repeatability/landmark_rotation.json]

Reads the reference masks produced by tools/experiment_repeatability.py where available, and always includes a
synthetic silhouette so the result reproduces without the harvested photos.
"""
import argparse, json, os, sys, glob
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.canon.autolm import landmarks_from_mask

ROOT = Path(__file__).resolve().parents[1]
ANGLES = [0, 1, 2, 3, 5, 8, 12, 20]

def synthetic(H=1000, W=800, kind="shorts"):
    m = np.zeros((H, W), np.uint8)
    cx, top = W // 2, int(0.12 * H)
    ww = int(0.46 * W); hh = int(0.55 * H if kind == "shorts" else 0.80 * H)
    body = int(0.42 * (0.55 * H))
    cv2.rectangle(m, (cx - ww // 2, top), (cx + ww // 2, top + body), 255, -1)
    leg_w = int(ww * 0.44); gap = int(ww * 0.06)
    for s in (-1, 1):
        x0 = cx + s * gap // 2 - (leg_w if s < 0 else 0)
        cv2.rectangle(m, (x0, top + body), (x0 + leg_w, top + hh), 255, -1)
    return m > 0

def rotate(mask, deg):
    h, w = mask.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(mask.astype(np.uint8), M, (w, h), flags=cv2.INTER_NEAREST) > 0

def ratios(mask):
    lm, conf = landmarks_from_mask(mask)
    if "waist_left" not in lm: return {}
    ww = float(lm["waist_right"][0] - lm["waist_left"][0])
    if ww <= 4: return {}
    ys = np.nonzero(mask.any(axis=1))[0]
    top = float(lm["waist_left"][1]); bot = float(ys.max())
    out = {"waist_px": ww, "height_over_waist": (bot - top) / ww}
    if "hip_left" in lm: out["hip_over_waist"] = float(lm["hip_right"][0] - lm["hip_left"][0]) / ww
    if "crotch" in lm: out["rise_over_waist"] = (float(lm["crotch"][1]) - top) / ww
    out["garment_type"] = conf.get("garment_type")
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/repeatability/landmark_rotation.json")
    a = ap.parse_args()
    subjects = {"synthetic_shorts": synthetic(kind="shorts"), "synthetic_jeans": synthetic(kind="jeans")}
    for p in sorted(glob.glob(str(ROOT / "reports/repeatability/masks/*.png"))):
        subjects[Path(p).stem] = cv2.imread(p, 0) > 127
    res = {"angles_deg": ANGLES, "subjects": {}}
    for name, m in subjects.items():
        base = ratios(m)
        rowsub = {"base": base, "by_angle": {}}
        for d in ANGLES:
            rowsub["by_angle"][str(d)] = ratios(rotate(m, d))
        res["subjects"][name] = rowsub
    # summary: the largest tilt at which every ratio stays within 5% of its unrotated value
    tol = {}
    for k in ("height_over_waist", "hip_over_waist", "rise_over_waist"):
        per = {}
        for name, s in res["subjects"].items():
            b = s["base"].get(k)
            if b is None or abs(b) < 1e-9: continue
            worst = None
            for d in ANGLES:
                v = s["by_angle"][str(d)].get(k)
                if v is None: worst = d; break
                if abs(v - b) / abs(b) > 0.05: worst = d; break
            per[name] = {"base": b, "first_angle_over_5pct": worst,
                         "dev_at_8deg": (abs(s["by_angle"]["8"].get(k, float("nan")) - b) / abs(b)
                                         if s["by_angle"]["8"].get(k) is not None else None)}
        tol[k] = per
    res["tolerance"] = tol
    res["summary"] = {k: {"n_real_masks": sum(1 for n in per if not n.startswith("synthetic")),
                          "n_real_masks_over_5pct_by_5deg": sum(1 for n, v in per.items() if not n.startswith("synthetic")
                                                                and v["first_angle_over_5pct"] is not None
                                                                and v["first_angle_over_5pct"] <= 5)}
                      for k, per in tol.items()}
    out = ROOT / a.out; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    for k, per in tol.items():
        print(f"\n{k}")
        for n, v in per.items():
            d8 = v["dev_at_8deg"]
            print(f"  {n:22s} base {v['base']:.3f}  first tilt over 5%: {v['first_angle_over_5pct']}°  dev at 8°: "
                  + (f"{d8:.1%}" if d8 is not None else "landmark lost"))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
