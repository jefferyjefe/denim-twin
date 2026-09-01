# EXP_0009 — First calibration audit of fringe-depth prediction intervals (plan §4.9 / §6.4)

**Step:** 9 **Intervals:** run_pair now emits an 80% interval for fringe depth per pair
(median = state-conditional leave-one-out prior × waist width; half-width = 1.28 × prior sd × waist width).
**Audit:** `tools/calibration_audit.py` on 8 LOO runs.

| stratum | n | coverage | nominal | verdict |
|---|---|---|---|---|
| ALL | 8 | 0.38 | 0.80 | over-confident |
| after_cut | 6 | 0.33 | 0.80 | (reals are cuff artefacts → not meaningful) |
| after_wash | 2 | 0.50 | 0.80 | n=2 |

## Read
The machinery (intervals → audit → per-stratum coverage) works end to end; the numbers say the intervals are
too narrow, and — more importantly — half the "real" depths are measurement artefacts on finished hems. Calibration
cannot be claimed or refuted with n=2 real fray pairs. Keep the interval output (never imply certainty) but label it
"uncalibrated" in every report until n ≥ 10 after-wash pairs. Charter claim on calibration stays deferred.

## Correction after review 3
Intervals now use the leave-one-out, per-state sd and px units in both branches; non-prior runs no longer report a
"real" equal to their own median. Re-audit on 10 LOO runs: **coverage 0.00** (nominal 0.80) — with n=2–4 the sd is
near zero and every interval is a point. Same conclusion, stronger: calibration needs ≥10 after-wash pairs.
