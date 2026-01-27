# Status — 2026-08-29 (end of first autonomous hour)

## What exists and works
- One-command pair pipeline `tools/run_pair.py`: coarse SAM garment pick → mask landmarks (cut-invariant) → registration
  (landmarks + optional SIFT) → per-leg hem fit → fringe render (v1 density band) → scoring vs null baselines → rejection with reason.
- Batch + aggregate: `run_pairs_batch.py`, `report_pairs.py`, `fit_fringe.py` (scale-free fringe prior, LOO), `run_pair.py --prior`.
- Data intake: found-pair manifest + CLIP role check (`tutorial_pairs.py`, `validate_pairs.py`), GitHub issue form + `ingest_submissions.py`.
- Local automation (launchd): capture-QA (5 min), pairs-daily (03:30), harvest curator (daily).
- 44 tests incl. two adversarial reviews' regression tests; fresh-clone verified (`reports/repro/`).

## What the numbers say
- Cut geometry is reproduced automatically on the one usable found pair (sil IoU ~0.8 vs 0.35 no-op).
- Fringe prediction is NOT yet better than crop-only (fringe IoU 0.07); appearance parameters are guesses (EXP_0003/0004/0006).
- Found tutorial pairs: 1/14 usable (EXP_0005). CC image harvest: no garments for the task (EXP_0007).
- Registration on shorts is underdetermined (leave-one-out residual ~50–160 px on 512-px images).

## What does not work
- Cloud routines never execute in this environment (all runs stall after "Claude Code process started", even a no-tool test).
  Harvester + smoke tests disabled; dailies left enabled for inspection at https://claude.ai/code/routines.

## The lever
Contributed pairs with a coin/ruler in frame: `CONTRIBUTING_PAIRS.md` + `discovery/OUTREACH.md`. Every downstream step
(fringe prior, fabric/fringe classifier, calibrated depth) is gated on ≥5 usable pairs (`docs/GATES.md` tuning rule).
