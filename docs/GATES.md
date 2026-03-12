# Phase Gates

- **Gate 0** — Research question in one sentence; protocol specific enough that two people perform the same experiment.
- **Gate 1** — Repeated captures of same garment align consistently; physical measurements reproducible within tolerance (set after pilot).
- **Gate 2** — 2D baseline preserves logos, pockets, seams, wash outside cut region. No 3D until this passes.
- **Gate 3** — Inseam/silhouette error below user-perception threshold (freeze after pilot user test).
- **Gate 4** — ≥80% held-out cut lines project without manual mesh repair; post-cut silhouette beats 2D baseline.
- **Gate 5** — Procedural fray beats global-average fray depth; threads align with observed weave.
- **Gate 6** — Learned residual improves real-outcome similarity without degrading unchanged-region identity.
- **Gate 7** — Full system beats generative + procedural baselines on physical matching AND identity.

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
