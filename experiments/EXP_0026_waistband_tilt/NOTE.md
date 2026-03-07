# EXP_0026 — A better tilt estimator that makes the pipeline worse

EXP_0023 left one pair regressing past the bench tolerance: 443d1d4658, whose after-photo shows a pair of red shorts
on a cutting mat. The mat's grid says the garment is square; the principal-axis estimate says it is tilted 4.8°,
because one leg hangs lower and further right and that is what a second moment reads. Asymmetric leg splay is not a
camera tilt.

The waistband is the one part of a flat-laid garment that is straight by construction — a stiff band with a sewn edge
spanning most of the width. Fitting a line to the mask's top edge by RANSAC (`canon/upright.waistband_angle`) should
therefore be a better measure of which way is up.

## Measured against known rotations (16 real masks × 11 angles, `experiment_upright.py`)

| estimator | median \|error\| | p90 | >1° | >3° | answers |
|---|---|---|---|---|---|
| principal axis (in use) | 0.00° | 1.64° | 21 / 176 | 13 / 176 | always |
| **waistband edge** | 0.03° | **0.22°** | **0** | **0** | 109 / 176 (declines on 38%) |
| flattest-top search | 0.00° | 26.00° | 51 | 40 | always |
| waistband, falling back to the axis | 0.02° | 0.89° | 17 | 11 | always |

And on the one case with independent ground truth, the waistband estimator is right: **−1.9° against the principal
axis's +4.8°** on 443d1d4658.

## Wired into the pipeline it is worse

| metric (7 usable pairs) | principal axis | waistband first | better / worse / tied |
|---|---|---|---|
| silhouette IoU | **0.8582** | 0.8312 | 1 / 4 / 1 |
| hem chamfer (px) | **8.52** | 23.28 | 1 / 4 / 1 |
| edge-band ΔE | 18.67 | 18.70 | 2 / 3 / 1 |
| fringe IoU | 0.1097 | 0.2085 | 2 / 3 / 1 |

It does exactly what it was built to do on the pair it was built for — 443d1d4658 goes IoU 0.857 → **0.922** and hem
27.7 → **7.6 px**, better than before EXP_0023 touched it — and it breaks 2691c1a8d0 from 0.736 → **0.558** with hem
11.5 → **86.6 px**, by rotating a before-photo the principal axis had declined to touch at all (its axis lies at 40°,
past the correctable range). It also moved which pairs the pipeline accepts: 2b0123d732 dropped out, 22a5857a0c came in.

## Not adopted

`tilt_estimate(prefer_waistband=True)` exists, is tested, and is **off**. Being more precise when it answers is not
the same as answering about the waistband: on some photographs the straight line across the top of a mask is a fold,
a belt, or a shadow, and nothing in the fit can tell. Five of the seven pairs disagree with the rotation-study result,
and five pairs are what this project has.

There is also a second-order cost that showed up in the invariance study: because the estimator declines on 38% of
masks, a garment can be measured by the waistband in one photograph and by the principal axis in the next, and
switching estimators between two captures of one garment is itself a source of irreproducibility (f41d64c01b loses
9.0% of its rise/waist at 8° of tilt under the hybrid, against 4.4% under the axis alone).

**The 443d1d4658 regression therefore stands, and is still the honest state of the bench.** What this experiment
rules out is the cheap fix.

## What it leaves for next time
The estimator is right where it can identify the waistband and wrong where it cannot, and it does not know which case
it is in. A test for "is this line the waistband" — its length relative to the garment width, the fabric above and
below it, whether the two ends are the garment's widest points — is a real piece of work, not a threshold, and it is
what would make this estimator usable.
