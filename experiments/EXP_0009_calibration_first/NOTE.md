# EXP_0009 — First calibration audit of fringe-depth prediction intervals (plan §4.9 / §6.4)

**Date:** 2026-08-29 07:15 UTC. **Intervals:** run_pair now emits an 80% interval for fringe depth per pair
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
