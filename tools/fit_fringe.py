#!/usr/bin/env python3
"""Fringe prior from usable pair runs (experiments/pairs/*): fringe depth and hem angle per pair, expressed
scale-free as depth / waist width. Writes data/priors/fringe.json and prints a leave-one-out evaluation:
for each pair, predict its depth from the OTHER pairs' mean and compare with its measured depth.
With n < 5 the prior is written but flagged 'insufficient'. run_pair.py --prior uses it instead of reading the
depth off the after-photo (which is circular)."""
import json, glob, re, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "data/priors"; OUT.mkdir(parents=True, exist_ok=True)
rows = []
EXCL = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines() if l.strip() and not l.startswith("#")} if (ROOT / "data/priors/exclude.txt").exists() else set()
for note in sorted(glob.glob(str(ROOT / "experiments/pairs/*/NOTE.md"))):
    txt = Path(note).read_text()
    if "rejected" in txt[:80] or Path(note).parent.name in EXCL: continue
    lm = Path(note).parent / "landmarks.json"
    if not lm.exists(): continue
    L = json.load(open(lm))["before_used"]; ww = abs(L["waist_right"][0] - L["waist_left"][0])
    m = re.search(r"hem fit: left: angle ([-\d.]+)°, depth ([\d.]+), right: angle ([-\d.]+)°, depth ([\d.]+)", txt)
    if not m or ww <= 0: continue
    # quality bar: only pairs whose cut geometry was reproduced (else the 'fringe depth' is registration garbage)
    mp = Path(note).parent / "cmp_median/metrics.json"
    if mp.exists():
        pr_ = {x["system"]: x for x in json.load(open(mp))["rows"]}["prediction"]
        if pr_["sil_iou_vs_real"] < 0.75 or pr_["hem_chamfer"] > 40: print(f"  skip {Path(note).parent.name}: sil IoU {pr_['sil_iou_vs_real']:.2f}, hem err {pr_['hem_chamfer']:.0f}"); continue
    al, dl, ar, dr = map(float, m.groups()); kind = "after_wash" if "after_wash" in txt else "after_cut"
    rows.append(dict(pair=Path(note).parent.name, kind=kind, waist_px=ww, depth_px=(dl + dr) / 2, depth_rel=(dl + dr) / 2 / ww, angle_l=al, angle_r=ar))
prior = {"n": len(rows), "insufficient": len(rows) < 5, "pairs": rows}
if rows:
    for k in ("depth_rel", "depth_px"):
        v = [r[k] for r in rows]; prior[k + "_mean"] = st.mean(v); prior[k + "_sd"] = st.pstdev(v) if len(v) > 1 else None
    washed = [r["depth_rel"] for r in rows if r["kind"] == "after_wash"]
    if washed: prior["depth_rel_mean_after_wash"] = st.mean(washed)
    if len(rows) >= 2:
        print("leave-one-out depth prediction (px):")
        for i, r in enumerate(rows):
            others = [x["depth_rel"] for j, x in enumerate(rows) if j != i]; pred = st.mean(others) * r["waist_px"]
            print(f"  {r['pair']}: measured {r['depth_px']:.1f}, predicted {pred:.1f}, |err| {abs(pred - r['depth_px']):.1f}")
up = OUT / "fringe_unpaired.json"
if up.exists():
    u = json.load(open(up)); prior["unpaired"] = {"n": u["n"], "depth_rel_mean": u["depth_rel_mean"], "depth_rel_sd": u["depth_rel_sd"]}
    if u["n"] and rows:
        w_p, w_u = len(rows), u["n"]; prior["depth_rel_mean_combined"] = (prior["depth_rel_mean"] * w_p + u["depth_rel_mean"] * w_u) / (w_p + w_u); prior["n_combined"] = w_p + w_u
        prior["insufficient"] = prior["n_combined"] < 5
(OUT / "fringe.json").write_text(json.dumps(prior, indent=1)); print(json.dumps({k: v for k, v in prior.items() if k != "pairs"}, indent=1))
