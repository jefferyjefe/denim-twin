#!/usr/bin/env python3
"""Fringe prior from usable pair runs (experiments/pairs/*): fringe depth and hem angle per pair, expressed
scale-free as depth / waist width. Writes data/priors/fringe.json and prints a leave-one-out evaluation:
for each pair, predict its depth from the OTHER pairs' mean and compare with its measured depth.
With n < 5 the prior is written but flagged 'insufficient'. run_pair.py --prior uses it instead of reading the
depth off the after-photo (which is circular)."""
import argparse, json, glob, re, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
_ap = argparse.ArgumentParser(description=__doc__)
_ap.add_argument("--out-dir", default=str(ROOT / "data/priors"),
                 help="where to WRITE fringe.json and fringe_unpaired.json. Inputs are always read from "
                      "data/priors. Point this at a temporary directory to compute the prior without replacing the "
                      "tracked one — tests/test_reports.py ran this tool with no argument and silently rewrote the "
                      "prior that every prediction depends on, so a green test run left modified tracked data behind.")
_args = _ap.parse_args()
IN = ROOT / "data/priors"
OUT = Path(_args.out_dir); OUT.mkdir(parents=True, exist_ok=True)
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
    # EXP_0015: the hem-fit/SAM depths in the NOTE measure fabric, not threads. Prefer the direct measurement.
    mj = Path(note).parent / "measure.json"
    if mj.exists():
        _d = json.load(open(mj))
        if _d.get("depth_direct_px_before_frame") is not None: dl = dr = float(_d["depth_direct_px_before_frame"])
    finish = RECS.get(Path(note).parent.name, {}).get("hem_finish", "unknown")
    measured = (dl + dr) / 2
    rule = None
    if finish in ("cuffed", "hemmed", "serged"): dl = dr = 0.0; rule = "finished hem -> 0 by rule"
    elif finish == "raw" and kind == "after_cut":
        cap = 0.01 * ww
        if min(dl, dr) > cap or max(dl, dr) > cap: rule = f"unwashed raw cut -> capped at 0.01*waist ({cap:.1f}px) by rule"
        dl, dr = min(dl, cap), min(dr, cap)
    rows.append(dict(pair=Path(note).parent.name, kind=kind, hem_finish=finish, waist_px=ww,
                     depth_px=(dl + dr) / 2, depth_rel=(dl + dr) / 2 / ww,
                     depth_px_measured=measured, depth_rel_measured=measured / ww, rule_applied=rule,
                     angle_l=al, angle_r=ar))
prior = {
    "n": len(rows),
    "insufficient": True,          # ALWAYS: no depth measurement in this project has passed a control (EXP_0015/0016)
    "validated": False,
    "measurement_method": "none — depth measurements below are diagnostics, not evidence",
    "validation_note": ("EXP_0015/0016 and review 5: the direct measurement returns garment-mask boundary error, "
                        "displaced drop shadows and mottled backdrops as 'fringe' with full coverage, and cannot "
                        "separate a cuffed hem from a frayed one. Rows carry both the rule-adjusted depth and the raw "
                        "measurement (depth_*_measured) so the difference is visible. Do not fit anything to them."),
    # what a renderer should use until a validated measurement exists: a depth stated in a tutorial, not measured by us
    "assumed_depth": {
        "value_mm": 12.7,
        "basis": ("itsalwaysautumn.com frayed method: a straight stitch is sewn 1/2 in (12.7 mm) above the raw cut "
                  "edge before washing, and after ONE wash/dry the page states the fray 'formed up to stitch line'."),
        "source_pair": "c94c958696",
        "caveat": ("the fray was ARRESTED by the stitching, so 12.7 mm is what one wash reached against a stop, not a "
                   "free fray depth; and it is one garment, one fabric, one machine."),
    },
    "pairs": rows,
}
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
# unpaired after-wash samples come from two channels: images already in pairs.jsonl, and the harvested web set
_web = IN / "fringe_unpaired_web.json"
if _web.exists():
    _w = json.load(open(_web)); _u = json.load(open(IN / "fringe_unpaired.json")) if (IN / "fringe_unpaired.json").exists() else {"samples": []}
    # REPLACE the web channel rather than append to it: a sample that no longer qualifies (a tightened gate, a
    # rejected mask) must disappear from the prior, not survive as a stale row (review 6, finding 7).
    _u["samples"] = [s_ for s_ in _u["samples"] if s_.get("channel") != "web"]
    for s_ in _w["samples"]:
        if s_.get("file"): _u["samples"].append({**s_, "channel": "web"})
    _ok = [s_ for s_ in _u["samples"] if s_.get("status") == "ok"]
    _u["n"] = len(_ok)
    _u["depth_rel_mean"] = st.mean([s_["depth_rel"] for s_ in _ok]) if _ok else None
    _u["depth_rel_sd"] = st.pstdev([s_["depth_rel"] for s_ in _ok]) if len(_ok) > 1 else None
    (OUT / "fringe_unpaired.json").write_text(json.dumps(_u, indent=1))
up = OUT / "fringe_unpaired.json" if (OUT / "fringe_unpaired.json").exists() else IN / "fringe_unpaired.json"
if up.exists():
    u = json.load(open(up)); prior["unpaired"] = {"n": u["n"], "depth_rel_mean": u["depth_rel_mean"], "depth_rel_sd": u["depth_rel_sd"],
                                                  "samples": [{"pair": s_.get("pair") or s_.get("page_url") or s_.get("file"), "depth_rel": s_["depth_rel"],
                          "channel": s_.get("channel", "pairs_manifest")} for s_ in u.get("samples", []) if s_.get("status") == "ok"]}
    # unpaired samples are all AFTER-WASH: they only inform the after_wash prior
    if u["n"]:
        wp = prior.get("n_after_wash", 0); mp = prior.get("depth_rel_mean_after_wash", 0.0)
        prior["depth_rel_mean_after_wash_combined"] = (mp * wp + u["depth_rel_mean"] * u["n"]) / (wp + u["n"]); prior["n_after_wash_combined"] = wp + u["n"]
(OUT / "fringe.json").write_text(json.dumps(prior, indent=1)); print(json.dumps({k: v for k, v in prior.items() if k != "pairs"}, indent=1))
