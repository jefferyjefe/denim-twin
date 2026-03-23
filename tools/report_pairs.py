#!/usr/bin/env python3
"""Aggregate experiments/pairs/*/cmp_<preset>/metrics.json into the table the tuning rule needs.

Review 7 found two defects here, both material because this is the evidence the
'no threshold changes without >=5 pairs' rule requires attached to a commit:

  * it never read data/priors/exclude.txt, so it averaged 11 pairs of which 4 are banned -- the
    third time this repository has been caught averaging over banned pairs (EXP_0014, EXP_0016,
    score_predict were the others). Pass --include-excluded to get the old behaviour deliberately.
  * it presented "prediction - crop-only" as the headline delta. EXP_0034 showed null:crop-only is
    built from the model's own keep mask, so that delta is the model against itself. It is kept in
    the per-pair table (it still catches a gamed metric, which is what it was written for) but is
    no longer offered as a baseline the prediction can beat.

fringe_iou_vs_real deserves its own warning: the crop-only null's mask IS `keep`, and the metric
scores `pred & ~keep`, so the null's fringe set is empty and its score is identically 0.00 for any
input. "Fringe IoU 0.17 against the null's 0.00" was never a comparison.
"""
import json, sys, glob, os, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; preset = sys.argv[1] if len(sys.argv) > 1 else "median"; PAIRS = os.environ.get("PAIRS_OUT", "experiments/pairs")
INCLUDE_EXCLUDED = "--include-excluded" in sys.argv
_ex = ROOT / "data/priors/exclude.txt"
EXCLUDE = {l.split()[0] for l in _ex.read_text().splitlines()
           if l.strip() and not l.startswith("#")} if _ex.exists() else set()
rows, skipped = [], []
for f in sorted(glob.glob(str(ROOT / f"{PAIRS}/*/cmp_{preset}/metrics.json"))):
    pid = f.split("/")[-3]; note = Path(f).parents[1] / "NOTE.md"
    if note.exists() and note.read_text().splitlines()[0].startswith("# PAIR — rejected"): continue                 # stale cmp dirs from before a rejection
    if pid in EXCLUDE and not INCLUDE_EXCLUDED: skipped.append(pid); continue
    d = json.load(open(f)); r = {x["system"]: x for x in d["rows"]}
    if "prediction" not in r: continue
    rows.append((pid, d.get("registration_residual_px"), r))
METRICS = ["sil_iou_vs_real", "hem_chamfer", "dE_edge_band_vs_real", "fringe_iou_vs_real", "fringe_profile_dist"]
print(f"# pairs: {len(rows)} (preset {preset})"
      + (f" — {len(skipped)} banned by exclude.txt not counted: {', '.join(sorted(skipped))}" if skipped else "")
      + ("  **--include-excluded: BANNED PAIRS ARE IN THIS TABLE**" if INCLUDE_EXCLUDED and EXCLUDE else "") + "\n")
print("> `null:crop-only` is built from the model's own keep mask (EXP_0034) — it is a gamed-metric\n"
      "> detector, NOT a baseline the prediction can be said to beat. `fringe_iou_vs_real` for that\n"
      "> null is identically 0.00 by construction: its mask is `keep`, and the metric scores\n"
      "> `pred & ~keep`. Use `score_predict.py --loo-null` for an independent baseline.\n")
print("| pair | reg resid | " + " | ".join(f"{m} pred / crop / no-op" for m in METRICS) + " |"); print("|---|---|" + "---|" * len(METRICS))
for pid, res, r in rows:
    cells = []
    for m in METRICS:
        v = lambda s: r[s].get(m, float("nan")); cells.append(f"{v('prediction'):.2f} / {v('null:crop-only'):.2f} / {v('null:no-op'):.2f}")
    print(f"| {pid} | {res if res is None else round(res, 1)} | " + " | ".join(cells) + " |")
if len(rows) >= 2:
    print("\n## Means (the crop-only column is the model against itself — see the caveat above)")
    for m in METRICS:
        p = [r["prediction"].get(m) for _, _, r in rows]; c = [r["null:crop-only"].get(m) for _, _, r in rows]
        p = [x for x in p if x is not None and x == x]; c = [x for x in c if x is not None and x == x]
        if p and c:
            forced = "  [crop-only forced to 0 by construction]" if m == "fringe_iou_vs_real" and not any(c) else ""
            print(f"- {m}: pred {st.mean(p):.3f}, crop {st.mean(c):.3f}, Δ {st.mean(p) - st.mean(c):+.3f} (n={len(p)}){forced}")
print(f"\nRule: heuristic thresholds (hemfit/autolm) change only with n >= 5 and this table attached.")
