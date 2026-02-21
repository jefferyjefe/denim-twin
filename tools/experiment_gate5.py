#!/usr/bin/env python3
"""One-command Gate 5 evidence (plan §7 Phase 5): 'the procedural model predicts average fray depth better than a
single global average' — evaluated leave-one-out on the after-wash pairs, plus calibration coverage and the bench.
Run when >= 10 after-wash pairs exist; before that it prints INSUFFICIENT and the current numbers."""
import json, os, subprocess, sys, glob, statistics as st
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; env = dict(os.environ, PAIRS_OUT="experiments/pairs_prior", PAIRS_USE_PRIOR="1")
subprocess.run([sys.executable, str(ROOT / "tools/run_pairs_batch.py")], env=env, capture_output=True, text=True)
rows = []
for n in glob.glob(str(ROOT / "experiments/pairs_prior/*/NOTE.md")):
    t = Path(n).read_text()
    if "rejected" in t[:80] or "after_wash" not in t: continue
    import re; m = re.search(r"fringe depth used: ([\d.]+) px from prior\[after_wash\].*?measured on after-photo: ([\d.]+) px", t)
    if m: rows.append((Path(n).parent.name, float(m.group(1)), float(m.group(2))))
n = len(rows); print(f"after-wash pairs with LOO prediction: {n}")
if n:
    pred_err = st.mean(abs(p - r) for _, p, r in rows); gmean = st.mean(r for _, _, r in rows)
    glob_err = st.mean(abs(gmean - r) for _, _, r in rows)          # 'single global average' baseline (in-sample, generous to the baseline)
    print(f"mean |error|: prior (LOO) {pred_err:.1f} px vs global-average {glob_err:.1f} px")
    for pid, p, r in rows: print(f"  {pid}: predicted {p:.1f}, measured {r:.1f}")
ints = ROOT / "experiments/pairs_prior/intervals_all.jsonl"
with open(ints, "w") as f:
    for p in glob.glob(str(ROOT / "experiments/pairs_prior/*/intervals.jsonl")): f.write(open(p).read())
subprocess.run([sys.executable, str(ROOT / "tools/calibration_audit.py"), str(ints)])
b = subprocess.run([sys.executable, str(ROOT / "tools/bench.py")], capture_output=True, text=True); print("bench:", "OK" if b.returncode == 0 else "REGRESSIONS")
verdict = "INSUFFICIENT (need >= 10 after-wash pairs)" if n < 10 else ("PASS" if pred_err < glob_err else "FAIL")
print(f"GATE 5 verdict: {verdict}")
(ROOT / "docs/GATE5_LAST.md").write_text(f"# Gate 5 last run\n\nafter-wash pairs: {n}\nverdict: {verdict}\n")
