#!/usr/bin/env python3
"""Regression benchmark over the usable found pairs. Compares the current experiments/pairs/*/cmp_median metrics
against data/bench/baseline.json. `--freeze` writes the current numbers as the new baseline (do this only with a
report attached, per docs/GATES.md). Exit 1 if any tracked metric regresses beyond tolerance."""
import json, sys, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; B = ROOT / "data/bench/baseline.json"
TRACK = {"sil_iou_vs_real": ("up", 0.03), "hem_chamfer": ("down", 5.0), "fringe_iou_vs_real": ("up", 0.05)}
EXCL = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines() if l.strip() and not l.startswith("#")}
cur = {}
for f in sorted(glob.glob(str(ROOT / "experiments/pairs/*/cmp_median/metrics.json"))):
    pid = f.split("/")[-3]; note = Path(f).parents[1] / "NOTE.md"
    if pid in EXCL or (note.exists() and note.read_text().splitlines()[0].startswith("# PAIR — rejected")): continue
    r = {x["system"]: x for x in json.load(open(f))["rows"]}
    if "prediction" in r: cur[pid] = {k: r["prediction"].get(k) for k in TRACK}
if "--freeze" in sys.argv:
    old = json.loads(B.read_text()) if B.exists() else {}
    regress = [(pid, k) for pid, m in cur.items() for k, (d, tol) in TRACK.items() if pid in old and old[pid].get(k) is not None and m.get(k) is not None and ((m[k] < old[pid][k] - tol) if d == "up" else (m[k] > old[pid][k] + tol))]
    if regress and "--force" not in sys.argv: print("refusing to freeze over regressions (use --force with a report attached):", regress); sys.exit(2)
    B.parent.mkdir(exist_ok=True); B.write_text(json.dumps(cur, indent=1)); print(f"baseline frozen: {len(cur)} pairs" + (" (FORCED over regressions)" if regress else "")); sys.exit(0)
base = json.loads(B.read_text()) if B.exists() else {}
bad = 0
print(f"| pair | metric | baseline | current | status |\n|---|---|---|---|---|")
for pid, m in cur.items():
    for k, (d, tol) in TRACK.items():
        b = base.get(pid, {}).get(k); c = m.get(k)
        if b is None or c is None: continue
        reg = (c < b - tol) if d == "up" else (c > b + tol)
        bad += reg; print(f"| {pid} | {k} | {b:.3f} | {c:.3f} | {'REGRESSION' if reg else 'ok'} |")
missing = [p for p in base if p not in cur]
if missing: print("missing from current run (now rejected?):", missing); bad += len(missing)
unknown = [p for p in cur if p not in base]
if unknown: print("pairs with NO baseline entry (freeze a baseline with a report attached):", unknown); bad += len(unknown)
sys.exit(1 if bad else 0)
