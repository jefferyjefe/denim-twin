#!/usr/bin/env python3
"""Calibration audit (Phase 7). Input: a JSONL of predictions {garment_id, stratum, metric, lo, hi, median, real, nominal}.
Reports coverage vs nominal overall and per stratum. Exit 1 if |coverage - nominal| > 0.1 on any stratum with n>=8."""
import json, sys, collections
sys.path.insert(0, __import__("os").path.join(__import__("os").path.dirname(__file__), "..", "src"))
from denimtwin.eval import uncertainty as U
rows = [json.loads(l) for l in open(sys.argv[1]) if l.strip()]
groups = collections.defaultdict(list)
for r in rows: groups["ALL"].append(r); groups[r.get("stratum", "?")].append(r)
bad = 0
for g, rs in groups.items():
    cov = U.interval_coverage([r["lo"] for r in rs], [r["hi"] for r in rs], [r["real"] for r in rs]); nom = rs[0]["nominal"]
    flag = len(rs) >= 8 and abs(cov - nom) > 0.1; bad += flag
    print(f"{g:12s} n={len(rs):3d} coverage={cov:.2f} nominal={nom:.2f} {'MISCALIBRATED' if flag else ''}")
sys.exit(1 if bad else 0)
