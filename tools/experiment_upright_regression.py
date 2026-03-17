"""EXP_0037: 443d1d4658's bench regression -- cause confirmed, documented mechanism disconfirmed.

The README attributes this pair's regression to uprighting, "because before and after are uprighted
independently". The attribution to uprighting is right; the mechanism is not supported by the data.

Emits three tables:
  arms         -- the pair re-run with uprighting on and off
  rotation     -- |before angle - after angle| against hem error, across the scored pairs
  asymmetry    -- |left hem angle + right hem angle| against hem error (a flat-laid garment's two
                  legs should cut at mirror-image angles, so this is a ground-truth-free diagnostic)

Usage: python tools/experiment_upright_regression.py --on DIR --off DIR
"""
import argparse, glob, json, re
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _pred(d):
    m = {x["system"]: x for x in json.load(open(Path(d) / "cmp_median/metrics.json"))["rows"]}
    return m["prediction"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--on", required=True, help="run directory with uprighting enabled")
    ap.add_argument("--off", required=True, help="run directory with uprighting disabled")
    ap.add_argument("--pairs", default=str(ROOT / "experiments/pairs"))
    a = ap.parse_args()

    ex = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines()
          if l.strip() and not l.startswith("#")}
    arms = {}
    for lab, d in (("upright_on", a.on), ("upright_off", a.off)):
        p = _pred(d)
        note = (Path(d) / "NOTE.md").read_text()
        m = re.search(r"hem fit: left: angle (-?[\d.]+)°.*?right: angle (-?[\d.]+)°", note)
        arms[lab] = {"sil_iou": round(p["sil_iou_vs_real"], 4), "hem_chamfer": round(p["hem_chamfer"], 2),
                     "left_angle": float(m.group(1)) if m else None,
                     "right_angle": float(m.group(2)) if m else None}

    rot, asym = [], []
    for f in sorted(glob.glob(f"{a.pairs}/*/NOTE.md")):
        d = Path(f).parent
        if "rejected" in open(f).readline() or d.name in ex or not (d / "modification.json").exists():
            continue
        t = open(f).read()
        p = _pred(d)
        b = re.search(r"before: rotated (-?[\d.]+)° to upright", t)
        aa = re.search(r"after: rotated (-?[\d.]+)° to upright", t)
        rot.append({"pair": d.name, "before_deg": float(b.group(1)) if b else 0.0,
                    "after_deg": float(aa.group(1)) if aa else 0.0,
                    "hem_chamfer": round(p["hem_chamfer"], 2), "sil_iou": round(p["sil_iou_vs_real"], 4)})
        rot[-1]["abs_rotation_difference"] = round(abs(rot[-1]["before_deg"] - rot[-1]["after_deg"]), 2)
        m = re.search(r"hem fit: left: angle (-?[\d.]+)°.*?right: angle (-?[\d.]+)°", t)
        if m:
            la, ra = float(m.group(1)), float(m.group(2))
            asym.append({"pair": d.name, "left_angle": la, "right_angle": ra,
                         "abs_angle_sum": round(abs(la + ra), 2),
                         "hem_chamfer": round(p["hem_chamfer"], 2)})

    def corr(rows, k):
        x = np.array([r[k] for r in rows], float)
        y = np.array([r["hem_chamfer"] for r in rows], float)
        return round(float(np.corrcoef(x, y)[0, 1]), 3)

    summary = {
        "pair": "443d1d4658",
        "arms": arms,
        "upright_off_restores_baseline": bool(abs(arms["upright_off"]["hem_chamfer"] - 8.916) < 0.5
                                              and abs(arms["upright_off"]["sil_iou"] - 0.918) < 0.005),
        "corr_rotation_difference_vs_hem": corr(rot, "abs_rotation_difference"),
        "corr_angle_asymmetry_vs_hem": corr(asym, "abs_angle_sum"),
        "worst_hem_pair": max(rot, key=lambda r: r["hem_chamfer"])["pair"],
        "largest_rotation_difference_pair": max(rot, key=lambda r: r["abs_rotation_difference"])["pair"],
        "largest_asymmetry_pair": max(asym, key=lambda r: r["abs_angle_sum"])["pair"],
    }
    print(json.dumps({"summary": summary, "rotation": rot, "asymmetry": asym}, indent=2))


if __name__ == "__main__":
    main()
