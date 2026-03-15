# Phase Gates

- **Gate 0** — Research question in one sentence; protocol specific enough that two people perform the same experiment.
- **Gate 1** — Repeated captures of same garment align consistently; physical measurements reproducible within tolerance (set after pilot).
- **Gate 2** — 2D baseline preserves logos, pockets, seams, wash outside cut region. No 3D until this passes.
- **Gate 3** — Inseam/silhouette error below user-perception threshold (freeze after pilot user test).
- **Gate 4** — ≥80% held-out cut lines project without manual mesh repair; post-cut silhouette beats 2D baseline.
- **Gate 5** — Procedural fray beats global-average fray depth; threads align with observed weave.
- **Gate 6** — Learned residual improves real-outcome similarity without degrading unchanged-region identity.
- **Gate 7** — Full system beats generative + procedural baselines on physical matching AND identity.

**Baseline rule (2026-08-29, EXP_0034):** a baseline a gate is claimed against must not be derived from the
model's own output. `null:crop-only` fails this: `compare.py` builds it from the `--keep` mask it is handed and
`score_predict.py` hands it predict's own keep mask, so it crops at the cut line the model predicted. With
`--wash none` the fringe is 0.0 px and the null and the prediction are the same object (median IoU 0.99954, one
pair bit-identical, and the null never keeps a pixel the prediction drops). It stays in the metrics table — it was
written to catch a gamed metric and it still does that — but **Gate 4's "beats 2D baseline" and Gate 7's baseline
comparison may not be claimed against it.**

The independent baseline is `score_predict.py --loo-null`: the cut placed at the leave-one-out median inseam
fraction of the other pairs, which sees nothing about the garment being scored. Current standing: product 0.8232
against 0.7278, +0.0954 (±0.0197, 4.8σ), winning 6 of 7.

Two things a baseline claim must also state, because the numbers above do not carry them:
- **Where the model's input came from.** The product path's only per-garment input is the inseam fraction, and
  `run_pair.py:263` measures it from the real after-photo. So +0.0954 says the pipeline renders a *supplied* cut
  height well. It is not evidence about choosing one.
- **The paired uncertainty**, not the unpaired one (EXP_0033). Registration error is common to both arms and
  cancels; quoting the unpaired ±0.030 on a paired difference overstates it by ~130×. `tools/experiment_paired_uncertainty.py`
  computes it, and its cancellation factor is a warning sign in its own right: a factor in the hundreds means the
  two arms are the same object, not that the comparison is precise.

**Gate 1 restatement (EXP_0034), answered (EXP_0035):** the first genuinely predictive question this bench could
pose was whether the pipeline can **choose** an inseam fraction from the before photo and beat 0.7278. It cannot:
nested leave-one-out over six shape features scores 0.6738 against the constant's 0.7278, losing on 6 of 7 pairs,
and the seven folds pick four different features. The cut height is a style choice, not a garment property, so
this gate should not be pursued as posed. What remains open is converting **stated user intent** into a fraction
(a named length, a length in mm, a line marked on the photo) — not a garment feature, untested here, and blocked
on the mm/px scale most found pairs lack.

**Tuning rule (2026-08-29):** heuristic thresholds in `canon/autolm.py`, `canon/hemfit.py`, `canon/upright.py` and `canon/warp.py`
change only when evaluated on ≥5 usable pairs with `tools/report_pairs.py` output attached to the commit.
`canon/upright.py` was added to the rule by EXP_0022, which changed the upright deadband from 8° to 0°; that
A/B (7 pairs, `tools/compare_upright_ab.py`) was **inconclusive on the pair metrics** and the change rests on a
directly measured defect (EXP_0021 Part C) plus the absence of any regression. A future change to these
thresholds needs the same two things, and saying which one is carrying the argument.

`canon/warp.py` joined the rule with EXP_0031. Its two conditions — the degenerate-correspondence separation and
the fold refusal — are numerical-conditioning conditions rather than thresholds fitted to outcomes, and both
A/Bs came back identical to the pixel; they are under the rule anyway, because that is not a distinction the
next person should have to take on trust.
