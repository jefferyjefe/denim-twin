# EXP_0008 — Is fringe depth predictable from a prior, held out? (first attempt: no)

**Date:** 2026-02-19 06:45 UTC. **Prior:** `data/priors/fringe.json` = paired runs (4 passing the quality bar) + 8 unpaired
after-wash samples (`tools/fringe_unpaired.py`, SAM fringe mask, depth / waist width), **conditional on state**
(after_cut vs after_wash) after the unconditional version over-predicted fringe on cut-only pairs by 10×.
**Protocol:** `run_pairs_batch.py` with `PAIRS_USE_PRIOR=1` → `run_pair --prior --exclude <self> --state <kind>` (leave-one-out).

| pair | state | depth used (prior, LOO) | depth measured on after-photo | fringe IoU prior / measured / no-op |
|---|---|---|---|---|
| 4bfef03bd7 | after_wash | 66.7 px (n=8) | 23.0 | 0.46 / 0.26 / 0.04 |
| 8d9f0df4ad | after_cut | 61.4 px (n=2) | 4.0 (cuffed) | 0.33 / 0.11 / 0.02 |
| 443d1d4658 | after_cut | 32.5 px (n=2) | 7.8 (cuffed) | 0.14 / 0.14 / 0.00 |
| 26b1041d00 | after_cut | 3.5 px (n=2) | 45.0 (cuff measured as fringe) | 0.01 / 0.30 / 0.48 |
| 2691c1a8d0 | after_cut | 20.4 px (n=3) | 31.8 | 0.30 / 0.39 / 0.10 |

## Read
- **Not predictive yet.** Per-state n is 2–3; the after_cut "measured depths" are cuff/colour-split artefacts
  (a cuffed hem has no fringe; the measurement should be ≈0), so the after_cut prior is fitting noise.
- The after_wash prior (0.17 × waist width, n=8 unpaired + 1 paired) over-predicts pair1 (67 vs 23 px). Either pair1's
  registered depth is under-measured (plausible: the SAM fringe mask on the *registered* image is holey) or the unpaired
  samples skew deep (Mr Kate / niftythrifty are heavily distressed). Both are likely.
- Fringe IoU "improving" under the prior on some pairs (0.46 vs 0.26) is **not** evidence: a deeper predicted fringe
  covers more of the real garment below the cut; the profile distance is the metric to trust, and it is nan/weak here.
- Correct next step is not more tuning: (1) measure depth in the *after-photo's own frame* (before warping), (2) treat
  cuffed/serged hems as depth 0 by rule (record hem_finish in the manifest), (3) get ≥5 real after-wash pairs.
This is the first time the pipeline has produced a genuine held-out prediction end to end; the answer is "not yet".

## Update 06:50 UTC — hem_finish rule + after-frame depth
- `hem_finish` recorded per page (cuffed / raw / frayed); cuffed/hemmed/serged pairs contribute depth 0 to the
  after_cut prior → the after_cut prior is now 0 and the LOO prediction on cut-only pairs equals crop-only (fringe IoU
  0.01–0.04), which is the correct behaviour for a finished hem.
- Depth now measured in the after-photo's own frame (SAM fringe mask on the un-warped image, scaled by waist-width
  ratio): pair1 23 → 36.5 px (registered-frame measurement was under-reading, as suspected). Bastelfrau (raw cut, no
  wash) reads 120 px — a false fringe: SAM's hem-band prompt grabs a strip of fabric when there is no fringe. Raw-cut
  unwashed hems need the same rule as cuffed ones (depth ≈ 0–2 mm) rather than a measurement.
- after_wash prior: 1 paired + 8 unpaired samples, mean 0.17 × waist width; predicts 67 px on pair1 vs 36.5 measured.
  Still not evidence of predictiveness (n_paired = 1). Needs after-wash pairs.

## Correction after review 3 (08:50 UTC) — the earlier "held-out" after_wash number was leaked
`--exclude` dropped only the paired row; the pair's own after-wash photo was still in the unpaired pool. Fixed
(`denimtwin/prior.py`: LOO applies to both pools; unpaired samples of pairs that already have a paired run are
dropped; depths are px everywhere). Corrected LOO on pair1: **prior 17.4 px (n=2) vs measured 36.5 px** — under-
predicts by 2×. Cut-only pairs with cuffed hems now predict ≈0 (correct by rule). Nothing here is predictive; the
statement "not yet" stands, now on clean numbers.
