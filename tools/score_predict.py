#!/usr/bin/env python3
"""Ablation: how much of the cut accuracy needs the after-photo? (plan §6.6 baselines)

`run_pair.py` fits the cut by looking at the real after-photo (per-leg hem lines, fringe split) — that is an
evaluation path, not a prediction. `predict.py` places the cut in canonical space from a single scalar (the inseam
fraction), which is what a user actually supplies. This runs the product path on every usable pair's BEFORE photo,
using the inseam fraction the evaluation path fitted, and scores it against the same registered after-photo.

    score_predict.py [--out experiments/pairs_predict] [--wash none]

Prints a table: product path vs evaluation path vs crop-only null, per pair.
"""
import argparse, json, os, subprocess, sys, glob
from pathlib import Path
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

p = argparse.ArgumentParser()
p.add_argument("--pairs", default=os.path.join(ROOT, "experiments/pairs"), help="evaluation-path run directory")
p.add_argument("--out", default=os.path.join(ROOT, "experiments/pairs_predict"))
p.add_argument("--wash", default="none", choices=["none", "conservative", "median", "aggressive"])
p.add_argument("--angle-source", default="none", choices=["none", "fitted"],
               help="fitted = pass the mean per-leg cut angle the evaluation path measured, as if the user specified it")
p.add_argument("--angle-sign", type=float, default=1.0, help="sign convention probe for the fitted-angle condition")
p.add_argument("--frac-source", default="recorded", choices=["recorded", "canonical"],
               help="recorded = the inseam_fraction run_pair wrote (image-space y between crotch and hem); "
                    "canonical = the canonical-space fraction of the real fitted cut (isolates cut PLACEMENT from the "
                    "parameterisation mismatch between the two paths)")
p.add_argument("--path-source", default="none", choices=["none", "fitted"],
               help="fitted = hand the product path the whole cut LINE the evaluation path fitted, as a canonical "
                    "polyline, instead of one height. Isolates the cut line from everything else (EXP_0028).")
p.add_argument("--path-points", type=int, default=16, help="--path-source fitted: samples along the canonical width")
p.add_argument("--include-excluded", action="store_true",
               help="also score pairs data/priors/exclude.txt bans (they are banned for reasons the pipeline cannot see)")
a = p.parse_args(); os.makedirs(a.out, exist_ok=True)

# data/priors/exclude.txt bans pairs for reasons the pipeline cannot see (a folded before-photo, two garments in the
# after shot, a legs-only crop). Review 6 found EXP_0016 scored two of them; this script had the same hole, and its
# published mean was over eleven pairs of which four are banned.
_ex = Path(ROOT) / "data/priors/exclude.txt"
EXCLUDE = {l.split()[0] for l in _ex.read_text().splitlines() if l.strip() and not l.startswith("#")} if _ex.exists() else set()

rows = []
for d in sorted(glob.glob(os.path.join(a.pairs, "*", "modification.json"))):
    pid = os.path.basename(os.path.dirname(d))
    src = os.path.dirname(d)
    if "rejected" in open(f"{src}/NOTE.md").readline(): continue
    if pid in EXCLUDE and not a.include_excluded: continue
    mod = json.load(open(d)); frac = mod.get("inseam_fraction")
    if frac is None: continue
    if a.frac_source == "canonical":
        import numpy as np, cv2
        from denimtwin.canon.warp import CanonicalMap
        from denimtwin.canon.landmarks import inseam_fraction_to_canonical_y
        lm = json.load(open(f"{src}/before_lm.json"))["landmarks"]; rm = cv2.imread(f"{src}/removed_mask.png", 0) > 127
        cm = CanonicalMap(lm)
        pts = np.array([(x, np.nonzero(rm[:, x])[0].min()) for x in range(rm.shape[1]) if rm[:, x].any()], np.float32)
        cy = cm.points_to_canon(pts)[:, 1] / cm.H
        y0, y1 = inseam_fraction_to_canonical_y(0.0), inseam_fraction_to_canonical_y(1.0)
        frac = float(np.clip((np.median(cy) - y0) / (y1 - y0), 0.0, 1.0))
    state = "after_wash" if mod.get("wash", {}).get("cycles", 0) >= 1 else "after_cut"
    od = os.path.join(a.out, pid); os.makedirs(od, exist_ok=True)
    cutpath = []
    if a.path_source == "fitted":
        # The cut LINE the evaluation path fitted, as a canonical polyline: the richest thing a user could specify
        # (they drew it on their own photo). If the product path reaches the evaluation path with this, then the
        # whole gap between them is the cut line and nothing else in the product path is losing accuracy.
        import numpy as np, cv2
        from denimtwin.canon.warp import CanonicalMap
        lm = json.load(open(f"{src}/before_lm.json"))["landmarks"]; rm = cv2.imread(f"{src}/removed_mask.png", 0) > 127
        cm = CanonicalMap(lm)
        pts = np.array([(x, np.nonzero(rm[:, x])[0].min()) for x in range(rm.shape[1]) if rm[:, x].any()], np.float32)
        c = cm.points_to_canon(pts); cx = c[:, 0] / cm.W; cy = c[:, 1] / cm.H
        keep_ = (cx >= 0) & (cx <= 1) & (cy >= 0) & (cy <= 1)
        cx, cy = cx[keep_], cy[keep_]
        if len(cx) >= 8:
            bins = np.linspace(0, 1, a.path_points + 1)
            pathpts = []
            for i in range(a.path_points):
                sel = (cx >= bins[i]) & (cx < bins[i + 1] + (1e-9 if i == a.path_points - 1 else 0))
                if sel.sum() >= 3:
                    pathpts.append([float((bins[i] + bins[i + 1]) / 2), float(np.median(cy[sel]))])
            if len(pathpts) >= 2:
                json.dump(pathpts, open(f"{od}/cut_path.json", "w"))
                cutpath = ["--cut-path", f"{od}/cut_path.json"]
    angle = []
    if a.angle_source == "fitted":
        import re
        m_ = re.search(r"hem fit: (.*)", open(f"{src}/NOTE.md").read())
        angs = [float(x) for x in re.findall(r"angle (-?\d+\.\d)", m_.group(1))] if m_ else []
        # per-leg angles are mirror images across the centre line; the user-facing --angle-deg is one signed number
        if angs: angle = ["--angle-deg", f"{np.mean([abs(x) for x in angs]) * a.angle_sign:.2f}"]
    # the photo as it came in, not run_pair's uprighted copy: predict uprights too, and correcting an already
    # corrected image is a second resampling at best and a 24-degree round trip at worst (EXP_0028, 2b0123d732).
    before_img = f"{src}/before_native.png" if os.path.exists(f"{src}/before_native.png") else f"{src}/before_used.png"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/predict.py"), "--image", before_img,
                        "--out", od, "--state", state, "--wash", a.wash,
                        "--edge-treatment", mod.get("edge_treatment", "raw")]
                       + (cutpath if cutpath else ["--inseam-fraction", f"{frac:.4f}"] + angle),
                       capture_output=True, text=True)
    if r.returncode != 0:
        rows.append((pid, state, None, None, None, (r.stdout + r.stderr).strip().splitlines()[-1][:80])); print(pid, "FAIL"); continue
    # compare in PREDICT's frame: it may rotate the before photo again, so its own orig.png + landmarks are the reference
    json.dump({"landmarks": json.load(open(f"{od}/landmarks.json"))["landmarks"]}, open(f"{od}/before_lm.json", "w"))
    c = subprocess.run([sys.executable, os.path.join(ROOT, "tools/compare.py"), "--before", f"{od}/orig.png",
                        "--before-lm", f"{od}/before_lm.json",
                        "--pred", f"{od}/pred_median.png", "--pred-mask", f"{od}/pred_median_mask.png",
                        "--keep", f"{od}/keep_mask.png", "--removed", f"{od}/removed_mask.png",
                        "--after", f"{src}/after_used.png", "--after-lm", f"{src}/after_lm.json", "--after-mask", f"{src}/amask.png",
                        "--out", f"{od}/cmp"], capture_output=True, text=True)
    if c.returncode != 0:
        rows.append((pid, state, None, None, None, (c.stdout + c.stderr).strip().splitlines()[-1][:80])); print(pid, "CMP FAIL"); continue
    m = {x["system"]: x for x in json.load(open(f"{od}/cmp/metrics.json"))["rows"]}
    e = {x["system"]: x for x in json.load(open(f"{src}/cmp_median/metrics.json"))["rows"]}
    rows.append((pid, state, m["prediction"], e["prediction"], m["null:crop-only"], ""))
    print(pid, f"product IoU {m['prediction']['sil_iou_vs_real']:.3f} hem {m['prediction']['hem_chamfer']:.1f} | "
               f"eval IoU {e['prediction']['sil_iou_vs_real']:.3f} hem {e['prediction']['hem_chamfer']:.1f}")

md = "| pair | state | product IoU | eval IoU | crop-only IoU | product hem | eval hem |\n|---|---|---|---|---|---|---|\n"
ok = [r for r in rows if r[2]]
for pid, state, m, e, n, why in rows:
    md += (f"| {pid} | {state} | {m['sil_iou_vs_real']:.3f} | {e['sil_iou_vs_real']:.3f} | {n['sil_iou_vs_real']:.3f} | "
           f"{m['hem_chamfer']:.1f} | {e['hem_chamfer']:.1f} |\n") if m else f"| {pid} | {state} | FAIL: {why} | | | | |\n"
if ok:
    mean = lambda f: sum(f(r) for r in ok) / len(ok)
    md += (f"\n**mean over {len(ok)} pairs** — product IoU {mean(lambda r: r[2]['sil_iou_vs_real']):.3f}, "
           f"evaluation IoU {mean(lambda r: r[3]['sil_iou_vs_real']):.3f}, crop-only IoU {mean(lambda r: r[4]['sil_iou_vs_real']):.3f}; "
           f"product hem {mean(lambda r: r[2]['hem_chamfer']):.1f} px, evaluation hem {mean(lambda r: r[3]['hem_chamfer']):.1f} px\n")
open(os.path.join(a.out, "SUMMARY.md"), "w").write(md); print(md)
# machine-readable, so a note quoting these numbers can be checked against them (tools/check_claims.py)
if ok:
    mean = lambda f: sum(f(r) for r in ok) / len(ok)
    json.dump({"n_pairs": len(ok), "excluded_honoured": not a.include_excluded, "frac_source": a.frac_source,
               "wash": a.wash, "angle_source": a.angle_source,
               "mean_sil_iou": {"product": mean(lambda r: r[2]["sil_iou_vs_real"]),
                                "evaluation": mean(lambda r: r[3]["sil_iou_vs_real"]),
                                "crop_only": mean(lambda r: r[4]["sil_iou_vs_real"])},
               "mean_hem_chamfer": {"product": mean(lambda r: r[2]["hem_chamfer"]),
                                    "evaluation": mean(lambda r: r[3]["hem_chamfer"])},
               "pairs": [{"pair": r[0], "state": r[1],
                          "product_sil_iou": r[2]["sil_iou_vs_real"], "evaluation_sil_iou": r[3]["sil_iou_vs_real"],
                          "crop_only_sil_iou": r[4]["sil_iou_vs_real"],
                          "product_hem": r[2]["hem_chamfer"], "evaluation_hem": r[3]["hem_chamfer"]} for r in ok],
               "product_beats_crop_only_on": sum(1 for r in ok if r[2]["sil_iou_vs_real"] > r[4]["sil_iou_vs_real"]),
               "product_loses_to_crop_only_on": sum(1 for r in ok if r[2]["sil_iou_vs_real"] < r[4]["sil_iou_vs_real"]),
               },
              open(os.path.join(a.out, "result.json"), "w"), indent=1)
