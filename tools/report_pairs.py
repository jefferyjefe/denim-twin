#!/usr/bin/env python3
"""Aggregate all experiments/pairs/*/cmp_<preset>/metrics.json into one table with per-metric means and the
prediction-minus-null deltas. This is the view the 'no threshold changes without >=5 pairs' rule needs."""
import json, sys, glob, os, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; preset = sys.argv[1] if len(sys.argv) > 1 else "median"; PAIRS = os.environ.get("PAIRS_OUT", "experiments/pairs")
rows = []
for f in sorted(glob.glob(str(ROOT / f"{PAIRS}/*/cmp_{preset}/metrics.json"))):
    pid = f.split("/")[-3]; note = Path(f).parents[1] / "NOTE.md"
    if note.exists() and note.read_text().splitlines()[0].startswith("# PAIR — rejected"): continue                 # stale cmp dirs from before a rejection
    d = json.load(open(f)); r = {x["system"]: x for x in d["rows"]}
    if "prediction" not in r: continue
    rows.append((pid, d.get("registration_residual_px"), r))
METRICS = ["sil_iou_vs_real", "hem_chamfer", "dE_edge_band_vs_real", "fringe_iou_vs_real", "fringe_profile_dist"]
print(f"# pairs: {len(rows)} (preset {preset})\n")
print("| pair | reg resid | " + " | ".join(f"{m} pred / crop / no-op" for m in METRICS) + " |"); print("|---|---|" + "---|" * len(METRICS))
for pid, res, r in rows:
    cells = []
    for m in METRICS:
        v = lambda s: r[s].get(m, float("nan")); cells.append(f"{v('prediction'):.2f} / {v('null:crop-only'):.2f} / {v('null:no-op'):.2f}")
    print(f"| {pid} | {res if res is None else round(res, 1)} | " + " | ".join(cells) + " |")
if len(rows) >= 2:
    print("\n## Means and prediction − crop-only deltas")
    for m in METRICS:
        p = [r["prediction"].get(m) for _, _, r in rows]; c = [r["null:crop-only"].get(m) for _, _, r in rows]
        p = [x for x in p if x is not None and x == x]; c = [x for x in c if x is not None and x == x]
        if p and c: print(f"- {m}: pred {st.mean(p):.3f}, crop {st.mean(c):.3f}, Δ {st.mean(p) - st.mean(c):+.3f} (n={len(p)})")
print(f"\nRule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.")
