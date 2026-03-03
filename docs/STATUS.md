# Status — 2026-08-29 (end of first autonomous hour)

## Gates
gate_0 ✔, **gate_2 ✔ for the pixel-copy configuration (nothing outside the cut changes). It does NOT cover `predict.py --wash median`, whose shrink/dye-loss terms alter kept pixels by design — that run reports `changed_fraction_of_kept_region` instead**. Phase 3 started: template v0 (EXP_0010) and v1 boundary-Chamfer refinement (EXP_0011, mixed A/B on 7 pairs, opt-in only).

## What exists and works
- One-command pair pipeline `tools/run_pair.py`: coarse SAM garment pick → mask landmarks (cut-invariant) → registration
  (landmarks + optional SIFT) → per-leg hem fit → fringe render (v1 density band) → scoring vs null baselines → rejection with reason.
- Batch + aggregate: `run_pairs_batch.py`, `report_pairs.py`, `fit_fringe.py` (scale-free fringe prior, LOO), `run_pair.py --prior`.
- Data intake: found-pair manifest + CLIP role check (`tutorial_pairs.py`, `validate_pairs.py`), GitHub issue form + `ingest_submissions.py`.
- Local automation (launchd): capture-QA (5 min), pairs-daily (03:30), harvest curator (daily).
- 44 tests incl. two adversarial reviews' regression tests; fresh-clone verified (`reports/repro/`).

## What the numbers say
- Cut geometry is reproduced automatically on the one usable found pair (sil IoU ~0.8 vs 0.35 no-op).
- Fringe: with SAM fringe segmentation (04:45 UTC) the prediction beats crop-only on pair1 for the first time (hem error 17.5 vs 22.7 px, fringe IoU 0.27 vs 0.00) — depth still *measured* on that pair; `--prior --exclude` makes it a held-out prediction once n ≥ 5 (EXP_0004).
- Found tutorial pairs: 1/14 usable (EXP_0005). CC image harvest: no garments for the task (EXP_0007).
- Registration on shorts is underdetermined (leave-one-out residual ~50–160 px on 512-px images).

## What does not work
- Cloud routines never execute in this environment (all runs stall after "Claude Code process started", even a no-tool test).
  Harvester + smoke tests disabled; dailies left enabled for inspection at https://claude.ai/code/routines.

## The lever
Contributed pairs with a coin/ruler in frame: `CONTRIBUTING_PAIRS.md` + `discovery/OUTREACH.md`. Every downstream step
(fringe prior, fabric/fringe classifier, calibrated depth) is gated on ≥5 usable pairs (`docs/GATES.md` tuning rule).

- 2026-08-29 (morning): procedural wash v0 added (`canon/wash.py`, off by default). Shrinkage is a prior, not measured: found-photo landmarks are ~50× too noisy (EXP_0013). Identity metrics need an alignment-aware version before any wash preset can be judged.
- 2026-08-29: `tools/predict.py` — the thesis' actual product path (one photo + a cut spec -> three renders + an 80% fringe interval + provenance, no after-photo). It runs; its numbers rest on an unvalidated prior and uncalibrated intervals, and it says so in every output. (Superseded 2026-08-29 by review 5: fringe depth withdrawn as evidence — see the entry below.)
- 2026-08-29: EXP_0014 — the product path (what a user actually gets) scores mean silhouette IoU **0.768** on the 11 found pairs, against 0.819 for the evaluation path that reads the real after-photo, and 0.771 for crop-only. Also found: `inseam_fraction` means different things in run_pair (image space) and modification.py (canonical), differing by up to 0.21 of the leg.
- 2026-08-29: EXP_0015 — fringe depth has never actually been measured here. SAM's fringe mask measures fabric (10–50x too deep, confirmed by eye); the new direct thread measurement (`eval/fringe_measure.py`) paints the right pixels but scores finished-hem controls (0.0081 mean depth_rel) the same as frayed washed garments (0.0077), so it has no discriminative power at found-photo resolution. All fringe numbers, including EXP_0008's held-out comparison, are void until a resolvable photo exists.
- 2026-08-29: EXP_0016/0017 — resolution does not rescue fringe depth (the mask-boundary floor scales with the image at 80% of the signal's rate), but **hem roughness** does separate frayed from finished hems with 0/14 false positives on controls, reliably above ~600–1000 px of waistband. Scored on all 11 pairs the fringe renderer beats crop-only 6-3-2 (mean |error| 0.91 vs 1.27 px, sign test p=0.51): directionally right, statistically nothing.
- 2026-08-29 (review 5): fringe DEPTH withdrawn as evidence project-wide — it returns mask-boundary error, displaced drop shadows and patterned backdrops as fringe. The prior now declares itself unvalidated and insufficient regardless of sample count, exposes which of its numbers are rule outputs, and carries one sourced assumption (12.7 mm, tutorial-stated, fray arrested by a stitch line). Leave-one-out excludes by photograph, not page id; the contributor TEST record was deleted for duplicating a tutorial's image. Hem roughness is the surviving fray observable.
