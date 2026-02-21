#!/usr/bin/env python3
"""Fringe prior from usable pair runs (experiments/pairs/*): fringe depth and hem angle per pair, expressed
scale-free as depth / waist width. Writes data/priors/fringe.json and prints a leave-one-out evaluation:
for each pair, predict its depth from the OTHER pairs' mean and compare with its measured depth.
With n < 5 the prior is written but flagged 'insufficient'. run_pair.py --prior uses it instead of reading the
depth off the after-photo (which is circular)."""
import json, glob, re, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; OUT = ROOT / "data/priors"; OUT.mkdir(parents=True, exist_ok=True)
import hashlib as _h
RECS = {_h.sha1(json.loads(l)["page_url"].encode()).hexdigest()[:10]: json.loads(l) for l in (ROOT / "data/external/pairs.jsonl").read_text().splitlines() if l.strip()}
rows = []
EXCL = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines() if l.strip() and not l.startswith("#")} if (ROOT / "data/priors/exclude.txt").exists() else set()
for note in sorted(glob.glob(str(ROOT / "experiments/pairs/*/NOTE.md"))):
    txt = Path(note).read_text()
    if txt.splitlines()[0].startswith("# PAIR — rejected") or Path(note).parent.name in EXCL: continue
    lm = Path(note).parent / "landmarks.json"
    if not lm.exists(): continue
    L = json.load(open(lm))["before_used"]; ww = abs(L["waist_right"][0] - L["waist_left"][0])
    m = re.search(r"hem fit: left: angle ([-\d.]+)°, depth ([\d.]+) ?px, right: angle ([-\d.]+)°, depth ([\d.]+) ?px", txt) or re.search(r"hem fit: left: angle ([-\d.]+)°, depth ([\d.]+), right: angle ([-\d.]+)°, depth ([\d.]+)", txt)
    if m and " px" not in (m.group(0)) and "scale: given" in txt: print(f"  skip {Path(note).parent.name}: depth in NOTE is in mm (old run) — rerun the batch"); continue
    if not m or ww <= 0: continue
    # quality bar: only pairs whose cut geometry was reproduced (else the 'fringe depth' is registration garbage)
    mp = Path(note).parent / "cmp_median/metrics.json"
    if mp.exists():
        pr_ = {x["system"]: x for x in json.load(open(mp))["rows"]}["prediction"]
        if pr_["sil_iou_vs_real"] < 0.75 or pr_["hem_chamfer"] > 40: print(f"  skip {Path(note).parent.name}: sil IoU {pr_['sil_iou_vs_real']:.2f}, hem err {pr_['hem_chamfer']:.0f}"); continue
    al, dl, ar, dr = map(float, m.groups()); kind = "after_wash" if "after_wash" in txt else "after_cut"
    finish = RECS.get(Path(note).parent.name, {}).get("hem_finish", "unknown")
    if finish in ("cuffed", "hemmed", "serged"): dl = dr = 0.0            # finished hems have no fringe; a measured value is an artefact
    if finish == "raw" and kind == "after_cut": dl, dr = min(dl, 0.01 * ww), min(dr, 0.01 * ww)   # unwashed raw cut: ~no fringe yet
    rows.append(dict(pair=Path(note).parent.name, kind=kind, hem_finish=finish, waist_px=ww, depth_px=(dl + dr) / 2, depth_rel=(dl + dr) / 2 / ww, angle_l=al, angle_r=ar))
prior = {"n": len(rows), "insufficient": len(rows) < 5, "pairs": rows}
if rows:
    for k in ("depth_rel", "depth_px"):
        v = [r[k] for r in rows]; prior[k + "_mean"] = st.mean(v); prior[k + "_sd"] = st.pstdev(v) if len(v) > 1 else None
    for kind in ("after_wash", "after_cut"):
        v = [r["depth_rel"] for r in rows if r["kind"] == kind]
        if v: prior[f"depth_rel_mean_{kind}"] = st.mean(v); prior[f"n_{kind}"] = len(v)
    if len(rows) >= 2:
        print("leave-one-out depth prediction (px):")
        for i, r in enumerate(rows):
            others = [x["depth_rel"] for j, x in enumerate(rows) if j != i]; pred = st.mean(others) * r["waist_px"]
            print(f"  {r['pair']}: measured {r['depth_px']:.1f}, predicted {pred:.1f}, |err| {abs(pred - r['depth_px']):.1f}")
up = OUT / "fringe_unpaired.json"
if up.exists():
    u = json.load(open(up)); prior["unpaired"] = {"n": u["n"], "depth_rel_mean": u["depth_rel_mean"], "depth_rel_sd": u["depth_rel_sd"],
                                                  "samples": [{"pair": s_["pair"], "depth_rel": s_["depth_rel"]} for s_ in u.get("samples", []) if s_.get("status") == "ok"]}
    # unpaired samples are all AFTER-WASH: they only inform the after_wash prior
    if u["n"]:
        wp = prior.get("n_after_wash", 0); mp = prior.get("depth_rel_mean_after_wash", 0.0)
        prior["depth_rel_mean_after_wash_combined"] = (mp * wp + u["depth_rel_mean"] * u["n"]) / (wp + u["n"]); prior["n_after_wash_combined"] = wp + u["n"]
        prior["insufficient"] = prior["n_after_wash_combined"] < 5 or prior.get("n_after_cut", 0) < 3
(OUT / "fringe.json").write_text(json.dumps(prior, indent=1)); print(json.dumps({k: v for k, v in prior.items() if k != "pairs"}, indent=1))
