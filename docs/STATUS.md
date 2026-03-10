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
- 2026-08-29: EXP_0016/0017 (both CORRECTED after review 6) — resolution does not rescue fringe depth: the mask-boundary floor scales with the image at 58% of the signal's rate (the first version said 80%, computed on two pairs `exclude.txt` bans). **Hem roughness** separates frayed from finished hems — 0 false positives on 9 high-resolution controls with consensus segmentation and no gate; the contour-compactness gate introduced earlier was removed after review 6 showed it is a garment-shape statistic that refuses full-length jeans (3.95) and the deepest frays. Scored on the pairs (RETRACTED — see EXP_0017: the quoted 6-3-2 / p=0.51 was not in the artefacts; corrected to 4-1-2 on 7 decidable pairs at the time, and after switching to a scale-free metric only 2 pairs are decidable at p=1.0).
- 2026-08-29 (review 5): fringe DEPTH withdrawn as evidence project-wide — it returns mask-boundary error, displaced drop shadows and patterned backdrops as fringe. The prior now declares itself unvalidated and insufficient regardless of sample count, exposes which of its numbers are rule outputs, and carries one sourced assumption (12.7 mm, tutorial-stated, fray arrested by a stitch line). Leave-one-out excludes by photograph, not page id; the contributor TEST record was deleted for duplicating a tutorial's image. Hem roughness is the surviving fray observable.
- 2026-08-29: 9 high-resolution finished-hem controls harvested and measured. Hem roughness: 0 false positives in 11 accepted control measurements, 6/8 frayed detected — but 2 of the 9 needed a new mask-quality gate (contour compactness > 3.0 is refused) because SAM's broken masks read exactly like fray. Rolled cuffs remain untested at high resolution.
- 2026-08-29: EXP_0018 — segmentation is the real bottleneck. Two photos of the same garment give waist 874 px vs 191 px (SAM segmented a pocket, score 0.906); elsewhere it segmented a wall at 0.992. Five automatic validity checks all fail on at least one real photo, so human mask verification is now required before any measurement enters a prior. Gate 1 is recorded as failed with this as the reason.
- 2026-08-29 (review 6, 12 findings): the contour-compactness gate was removed — it is a garment-shape statistic that refuses full-length jeans and silently zeroes the deepest frays. EXP_0017 retracted (its numbers were not in the artefacts); EXP_0016 recomputed without two pairs `exclude.txt` bans. Requiring explicit single-wash evidence cut the harvested channel from 7 candidates to 1 and the after-wash prior to n=2 — the evidence was always this thin. Nine all-rights-reserved retailer photos were committed and untracked the same hour. New: `tools/check_claims.py` + `tests/test_experiment_claims.py` re-derive every quoted number from its artefact, so notes cannot drift from their data again.

- 2026-08-29: EXP_0021 — **repeatability, and the first tolerance numbers this project has.** Three parts.
  (A) The one same-garment pair (front and back of one pair of cut-offs) agrees to 8% on rise/waist under consensus
  segmentation, against a 2.16x disagreement and a 4.58x waist-width disagreement under best-score: **EXP_0018's
  Gate 1 failure was a segmentation failure and it is fixed**. (B) 16 photographs x 14 simulated re-captures x 2
  methods = 480 segmentations. Best-score SAM returns a *different object* on 16 of 96 runs where nothing but the
  JPEG quality or the exposure changed; consensus does so on **0**. Over all 224 runs per method: 48 vs **9** below
  IoU 0.8, and consensus's 10 refusals are mostly one cause — a 1.15x zoom pushes the garment past a hard 75%
  area ceiling, and the refusal used to say "prompt sets disagree" when the prompts agreed perfectly. (C) The
  ~30% swing in shape ratios at 8° of tilt is **not** segmentation: rotating an already-correct mask reproduces it,
  and on an exact synthetic silhouette a 5° tilt already costs more than 5%. `predict.py`/`run_pair.py` only correct
  tilt above 8°, which is on the wrong side of the effect (left unchanged: it needs its own A/B).
- 2026-08-29: EXP_0021 also puts a number on the fray metric's reproducibility, and it is bad. Re-encoding the same
  photograph at JPEG 15 changes hem roughness by 80% of its value; the fray *verdict* flips on **6 of 16 photos**,
  and **2 of the 9 high-resolution finished-hem controls read "frayed"** under at least one perturbation. EXP_0016's
  "0 false positives on 9 controls" is a statement about one photograph each and does not survive a re-encode.
  `p90 > 0` was also shown to be exactly `rough_fraction > 0.10` (verified on all 239 real measurements), which names
  the detection limit: a fray touching fewer than a tenth of the hem columns is invisible, and real finished hems
  already deviate on up to 7.3% — a 2.7-point margin. The threshold is NOT moved; 16 photographs cannot set it.
- 2026-08-29: the product path (`tools/predict.py`) gained `--seg consensus` — it could not use the segmentation that
  fixes catastrophic object-identity failures — and every prediction now records which segmentation produced it.
- 2026-08-29: review 5 and review 6's test files are now **in the repository and green** (they were local and
  excluded from git). The remaining findings were fixed rather than argued: the wash/fray evidence gate is one
  implementation shared by both intake channels (`denimtwin/evidence.py`) instead of two that disagreed, with the
  polarity bug ("the hem did not fray" read as evidence of fray) fixed; the control-roughness artefact that EXP_0016
  cites now has a script that produces it (`tools/measure_controls.py`) instead of being an ad-hoc leftover that
  still described a removed gate; and one finding stands as an accepted, documented limitation (a scalloped hem reads
  as fray) marked xfail with its reason.
- 2026-08-29: `tests/test_no_dead_parameters.py` — a declared parameter that the body never reads is a silent lie to
  the caller. It found five, including `hem_chamfer(band_px=40)`: `tools/compare.py` computed a 15 mm band and passed
  it positionally for nothing on every pair report ever produced.
- 2026-08-29: EXP_0022 — the tilt correction was switched off exactly where it was needed. Measured against known
  rotations of 16 real masks, the principal-axis estimate has median error **0.00°**, p90 1.64°, and correcting was
  never worse than not correcting (0 of 176). Its one failure mode is structural: on a near-isotropic silhouette
  (a squat pair of shorts, elongation < 1.2) it is off by up to 4.67° at 8° of tilt and 10.45° at 15°, against
  ≤0.41° below 3°. So the old **8° deadband skipped the band where the estimate is reliable and the un-corrected
  measurement error is already >5%, and acted in the band where the estimate is not**. Two alternative estimators
  (a waistband-edge line fit, a flattest-top search) were tried and are much worse. The deadband is now **0.0**
  (`canon/upright.py`, one implementation shared by `run_pair.py` and `predict.py`; pass `--upright-deadband 8.0`
  for the old behaviour), a near-isotropic tilt ≥5° is flagged in the output, and `tests/test_upright.py` pins the
  invariance the change is for: shape ratios stable within 5% from −20° to +20° of tilt.
  The A/B on 7 pairs is **inconclusive and is not the reason for the change**: silhouette IoU 0.8372 → 0.8365,
  hem 13.35 → 13.31 px, fringe IoU 0.0570 → 0.0746 (3 better, 0 worse, 4 tied, p = 0.25). `bench.py` shows no
  regression on any tracked metric, and the baseline is deliberately **not** re-frozen — the older baseline is the
  stricter test.
- 2026-08-29: two problems found while committing EXP_0022, both bigger than the experiment.
  **(1) 2035 derived images were tracked in git.** `.gitignore` covered `experiments/pairs/` and two siblings but not
  `pairs_wash/`, `pairs_consensus/`, `pairs_predict*/`, nor `experiments/pairs/*/panel.jpg` (the `*.png` rule misses
  it by extension). Every render, mask, diff and side-by-side panel built from the found-pair tutorial photographs was
  in the repository — the same policy review 6 found broken with nine files, at ten times the scale. Untracked and
  ignored properly; EXP_0022's own two A/B arms would have added 926 more and were kept out of history. **They remain
  in the pushed history on GitHub**, and purging them means rewriting public history — the owner's decision, recorded
  here rather than done silently.
  **(2) The test suite rewrote the prior.** `tests/test_reports.py` ran `tools/fit_fringe.py` with no arguments, and
  that tool writes `data/priors/fringe.json` — so running the tests replaced the prior every prediction depends on
  with whatever the local pair artefacts said that minute, and in a fresh clone would have written an empty one.
  `fit_fringe.py` now takes `--out-dir`, the test uses a temporary one, and
  `tests/test_tools_do_not_touch_tracked_data.py` fails if a tool given an explicit destination touches the tracked
  prior anyway. The committed prior has since been regenerated deliberately from the re-run pairs.
- 2026-08-29: EXP_0023 — EXP_0022's fix did not fire on this project's own subject. Re-measuring EXP_0021's numbers
  with uprighting on showed 8 of 16 photographs unchanged, because `tilt_angle` read the silhouette's **long** axis,
  and a pair of shorts laid flat is **wider than tall** (9 of 16 photographs have height/width 0.60–0.85), so the
  long axis runs sideways and the estimate came back at ~±88° — outside the correctable range, so uprighting silently
  did nothing. Reading the near-vertical axis instead: the tilt term disappears from the repeatability suite (rise/waist
  deviation at 8° of tilt **29.6% → 0.5%**; every geometric perturbation now ≤1.5%), and 11 of 16 masks never lose 5%
  at any tilt up to 20°. On the pairs: silhouette IoU 0.8365 → **0.8566**, hem error 13.31 → **7.85 px**, fringe IoU
  0.0746 → 0.1004 (4/2/1, p = 0.688) — with **one pair regressing past the bench tolerance** (443d1d4658, IoU −0.052,
  hem +19.6 px), recorded and left visible rather than tuned away. Its cause is named: before and after are uprighted
  independently and end up 8.4° apart. The fix is for `run_pair` to put the after photo in the before's frame using
  the registration it already computes — the next experiment.
- 2026-08-29: EXP_0024 — **hem roughness measures the resampler.** It counts pixel-scale deviations of the hem
  boundary; a mask rotated by anything but a multiple of 90° has a boundary that steps by a pixel. Rotate the twelve
  reference masks that read p90 = 0 and nothing else: at 3° **7 of 12** read frayed, at 8° **12 of 12**, median false
  p90/waist **0.00194**. EXP_0017's headline is 0.00194 for the prediction against 0.00231 for the crop-only null —
  the artefact is the size of the whole quantity and **five times the margin**, and it has a direction: `compare.py`
  warps the real mask into the prediction's frame and synthesises the prediction there, so the real hem is measured
  as rougher than it is and a system that renders *some* roughness scores closer. That is EXP_0017's exact comparison.
  It does not prove the ordering wrong; it means the experiment cannot distinguish its result from its resampler.
  `hem_roughness` now takes `resampled=` and marks such results `valid_for_fray: false`; every pair `metrics.json`
  carries the flag. **EXP_0016's control result is unaffected** — those masks were measured in the frame they were
  segmented in, which is why they read zero.
- 2026-08-29: EXP_0025 — **EXP_0017 retracted in full, for the second time and for a better reason.** Roughness is
  scale-free, so the two sides never needed a shared frame; `run_pair` now keeps the after mask as segmented and
  `compare.py` measures the real hem on it. The registration warp had been inflating the real garment's roughness
  **six-fold** (mean 0.00043 native against 0.00260 warped, rougher on 5 of 7 pairs). Scored natively the ordering
  reverses — prediction 0.00376 against the crop-only null's 0.00240, 1-3-3, p = 0.625 — but that is not the finding.
  The finding is that **6 of the 7 real frayed hems measure exactly zero** at 241–389 px of waistband, below the
  600–1000 px EXP_0016 established this statistic needs. A comparison against a floor measures which system renders
  less texture, and a clean cut renders none. Both the original ordering and its reversal are that artefact seen from
  two sides. `hem_rough_*` is a diagnostic until an after-photo with ≥600 px of waistband exists — which is what
  `CONTRIBUTING_PAIRS.md` and the issue form already ask for.
- 2026-08-29: EXP_0026 — a better tilt estimator that makes the pipeline worse, and is therefore not adopted. Fitting
  a line to the waistband edge by RANSAC beats the principal axis on every measurement of the estimator itself
  (p90 error **0.22° against 1.64°**, never missing by a degree, though it declines on 38% of masks) and gets the one
  case with independent ground truth right (−1.9° against +4.8° on 443d1d4658, whose cutting-mat grid shows the
  garment is square). Wired into `run_pair` it loses: silhouette IoU 0.858 → 0.831, hem error 8.5 → 23.3 px, 1 better
  and 4 worse. It fixes 443d1d4658 (0.857 → **0.922**, better than before EXP_0023 touched it) and breaks 2691c1a8d0
  (0.736 → 0.558, hem 11.5 → 86.6 px) by rotating a before-photo the principal axis had declined to touch. Being more
  precise when it answers is not the same as answering about the waistband — sometimes the straight line across the
  top of a mask is a fold, a belt or a shadow. `tilt_estimate(prefer_waistband=True)` is kept, tested and **off**.
  The 443d1d4658 bench regression stands; what this rules out is the cheap fix.
- 2026-08-29: EXP_0027 — the product path recomputed. `tools/score_predict.py` never read `data/priors/exclude.txt`,
  so EXP_0014's headline was over 11 pairs of which 4 are banned; it is the third experiment in this repo caught doing
  that. On the 7 pairs the list allows, and after the tilt fix: **product path 0.8026 silhouette IoU against a
  crop-only null of 0.8026** — a dead heat, winning on 2 pairs and losing on 4 by thousandths. What a user gets is
  indistinguishable from cropping their own photograph at the same height on this metric, which is what EXP_0014
  already implied (0.768 against 0.771) and this sharpens. The evaluation path did improve: 0.819 → **0.857** IoU and
  48.4 → **7.8 px** of hem error, mostly from the tilt fix. The 0.857-vs-0.803 gap between reading the after-photo and
  predicting without it is the actual research problem, and it is larger than any appearance work downstream of it.
- 2026-08-29: EXP_0028 — the product path's remaining gap is **not the cut specification**. `predict.py` gained
  `--cut-path`, the cut as a polyline in canonical coordinates — the most a user interface can carry — and
  `score_predict.py --path-source fitted` hands it the line the evaluation path fitted to the real garment. The
  ladder: one canonical height **0.8232**, + the fitted angle 0.8168, + the whole fitted cut line 0.8190, against the
  evaluation path's 0.8566. Giving away the exact answer about the cut recovers none of the gap. On 5 of 7 pairs the
  two paths already produce the same garment (predicted-silhouette IoU 0.952–0.997) and score within 0.03 of each
  other; the aggregate gap is carried by 2 pairs where the same canonical cut removes a different region. Registration
  is identical on all seven, so it is not that either.
  Found on the way: `score_predict.py` was feeding `predict.py` the photograph `run_pair` had **already uprighted**,
  which was harmless while the deadband was 8° and became a second correction on every pair once EXP_0022 set it to 0
  — a −23.5° then +24.3° round trip on 2b0123d732. Cost: 0.020 IoU and 11 px of hem. `run_pair` now writes
  `before_native.png`/`after_native.png` and the harness uses them; EXP_0027's headline is corrected 0.803 → **0.823**
  (the null moves with it, so the dead heat stands); and `tests/test_upright.py` pins the invariant that broke —
  uprighting an already-uprighted image, re-segmenting in between, must not rotate it again.
- 2026-08-29: EXP_0029 — **canonical space does not give the garment back.** `docs/PLAN_PROGRESS.md` has recorded
  `canon/warp.py` since Phase 1 as "sub-pixel round-trip; exact per-pixel maps". True — at the landmarks.
  `CanonicalMap` fits **two independent** thin-plate splines, image→canonical and canonical→image, from the same
  correspondences; two independent fits agree exactly where they were fitted and nowhere in particular between.
  Measured on the seven usable pairs: median **0.00 px at the landmarks and 10.7 px over the garment**, worst case
  **835 px**; send the removed *region* on the same journey and it returns with a median IoU of **0.638** with itself,
  and **0.074** on 2b0123d732 — 93% of it gone. This reframes EXP_0028: handing the product path the exact canonical
  *region* (rather than a polyline) and restricting to the two pairs whose round-trip is faithful, the product path
  scores **0.8735 against the evaluation path's 0.8750** — it matches. e97924ad2d reproduces it exactly, 0.893 vs
  0.893 and 1.3 px vs 1.3 px of hem. So the product path's gap is not the cut interface and not the renderer: it is
  that the representation the cut is expressed in does not survive being used. The fix — one TPS inverted numerically
  instead of two fitted independently — changes every canonical coordinate in the project and is the most valuable
  experiment on the board.
- 2026-08-29: EXP_0030 — the canonical inverse is fixed (round trip over the garment **10.7 px → 0.02 px**, region
  IoU 0.638 → 0.972, faithful on 5 of 7 pairs instead of 2) **and nothing in the pipeline uses it**. Grepping every
  caller of the canonical→image direction finds `run_baseline.py`, the measurement tools, and tests — not `run_pair`
  and not `predict`, because `apply_cut` maps garment pixels *forward* into canonical space and looks the cut up
  there. Switching `--canonical-inverse approx|exact` changes **0 pixels** in every rendered prediction, with the flag
  verifiably recorded either way. **EXP_0029's causal claim is corrected**: the round-trip error is real and no
  production path pays it. What does reach the pipeline is the **forward map folding** — two garment pixels landing on
  one canonical coordinate — over **40.1% and 37.2%** of two of the seven garments, which are exactly the two whose
  region does not survive. `predict.py` now refuses above 20% fold with a re-shoot instruction, flags above 2%, and
  records the fraction; on the found-pair set that is **2 of 7 garments refused outright**. That refusal is why the
  A/B scores 5 pairs, and its numbers are **not comparable** with the seven-pair means in EXP_0027/0028 — a mistake
  made once here before it was caught.
