#!/usr/bin/env python3
"""Run run_pair.py on every 'usable' page in data/external/pairs_validation.jsonl.
Picks the first whole-garment 'before' and the first whole-garment 'after_wash' (else 'after_cut').
Writes experiments/pairs/<pageid>/ and a summary table experiments/pairs/SUMMARY.md."""
import json, hashlib, subprocess, sys, os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; IMG = ROOT / "data/external/pair_images"; OUT = ROOT / "experiments/pairs"; OUT.mkdir(parents=True, exist_ok=True)
rows = []
for line in (ROOT / "data/external/pairs_validation.jsonl").read_text().splitlines():
    v = json.loads(line)
    if v["status"] != "usable": continue
    pid = hashlib.sha1(v["page_url"].encode()).hexdigest()[:10]
    pick = lambda roles: next((t["file"] for t in v["images"] if t["role"] in roles and t.get("tag") == "whole_garment_flat"), None)
    before = pick(("before",)); after = pick(("after_wash",)) or pick(("after_cut",)); kind = "after_wash" if pick(("after_wash",)) else "after_cut"
    if not before or not after: continue
    od = OUT / pid
    cmd = [sys.executable, str(ROOT / "tools/run_pair.py"), "--before", str(IMG / before), "--after", str(IMG / after), "--out", str(od)]
    if os.environ.get("PAIRS_USE_PRIOR") and (ROOT / "data/priors/fringe.json").exists(): cmd += ["--prior", str(ROOT / "data/priors/fringe.json"), "--exclude", pid]   # leave-one-out
    r = subprocess.run(cmd, capture_output=True, text=True)
    ok = r.returncode == 0
    metrics = None
    if ok and (od / "cmp_median/metrics.json").exists():
        m = json.load(open(od / "cmp_median/metrics.json"))["rows"]; metrics = {x["system"]: x for x in m}
    why = next((l for l in (r.stdout + r.stderr).splitlines() if l.startswith("REJECT") or "failed" in l), (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else "")
    rows.append((pid, v["title"][:40], kind, ok, metrics, why if not ok else ""))
    print(pid, v["title"][:40], kind, "OK" if ok else "FAIL")
md = "# Found-pair batch (auto pipeline)\n\n| page | title | after | status | sil IoU pred / crop / no-op | chamfer px pred / crop | edge ΔE pred / crop | fringe IoU pred / no-op |\n|---|---|---|---|---|---|---|---|\n"
for pid, t, k, ok, m, err in rows:
    if m: p, c, n = m["prediction"], m["null:crop-only"], m["null:no-op"]; md += f"| {pid} | {t} | {k} | ok | {p['sil_iou_vs_real']:.2f} / {c['sil_iou_vs_real']:.2f} / {n['sil_iou_vs_real']:.2f} | {p['hem_chamfer']:.0f} / {c['hem_chamfer']:.0f} | {p['dE_edge_band_vs_real']:.1f} / {c['dE_edge_band_vs_real']:.1f} | {p['fringe_iou_vs_real']:.2f} / {n['fringe_iou_vs_real']:.2f} |\n"
    else: md += f"| {pid} | {t} | {k} | FAIL: {err[:60]} | | | | |\n"
(OUT / "SUMMARY.md").write_text(md); print(md)
