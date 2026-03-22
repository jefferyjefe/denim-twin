# EXP_0035 — The cut height is a style choice, not a garment property

EXP_0034 restated Gate 1: can the pipeline **choose** an inseam fraction, instead of being handed
one measured off the after-photo, and beat the leave-one-out median baseline (0.7302 IoU)? The
backlog said to decide whether that is even a prediction target before building a predictor on
seven samples. This decides it by measurement.

## What is available to predict from

Six features computable from the before mask and landmarks alone — no after-photo:
`aspect`, `waist_w_over_h`, `hip_over_waist`, `crotch_frac`, `leg_over_h`, `area_frac`.

Fitted on all seven pairs, the best is `area_frac` at **r² = 0.2523**. That number is the trap. With
7 points and 6 candidate features, the best in-sample r² is close to what noise alone produces, and
reporting it as a finding is the standard way a null result gets published as a discovery.

## The honest protocol

Nested leave-one-out: hold out a pair, then choose the feature **and** fit the line on the other
six. Choosing the feature on all seven leaks the held-out pair into the model selection.

| | mean absolute error on the fraction |
|---|---|
| predictor (feature chosen in-fold) | **0.3066** |
| predict the median of the other six | **0.1804** |

The predictor is **70%** worse than a constant. Its folds do not even agree on what to look at: over
seven folds they choose **four different features** (`area_frac` 3, `waist_w_over_h` 2,
`hip_over_waist` 1, `leg_over_h` 1). That disagreement is the signature — each fold is fitting its
own six points' noise.

## In the bench's own units

MAE is not what the gate is written in, so both were rendered and scored against the same ground
truth:

| baseline | mean IoU |
|---|---|
| constant: median fraction of the other six | **0.7302** |
| predictor: feature chosen and fitted in-fold | **0.6584** |

The predictor is **worse than a constant** on the metric the gate uses, losing on **7** of 7 pairs.
The one it improves (`4bfef03bd7`, 0.5286 → 0.5784) is the pair whose true fraction is 0.000 — a
garment cut at the crotch — which every method mispredicts.

## What this means

The inseam fraction is **not a property of the garment** at this sample size. It ranges 0.000–0.461
across seven pairs (sd 0.167) and none of the shape available in a flat-lay photograph anticipates
it. That is unsurprising once stated plainly: how short someone cuts their jeans is a decision about
how they want to look, not a fact about the jeans.

So Gate 1's restatement should not be attempted as posed. The supportable product claim is the one
EXP_0034 measured — given a cut height, the pipeline places and renders it far better than not
knowing it (**+0.0953, 4.7σ**) — and the inseam fraction belongs in the interface as a **user
input**, which is how `score_predict.py`'s own docstring already describes it ("what a user actually
supplies").

This is a negative result about *predictability*, not about the pipeline. It would be overturned by
either of:

- **More pairs.** Seven is too few to detect anything but a very strong relationship; a real
  r² ≈ 0.3 would need roughly 25 pairs to separate from noise. The found-pair channel is exhausted
  (EXP_0005/0007), so this is blocked on contributed pairs.
- **A different input.** Stated user intent ("just above the knee", a length in mm, a marked line on
  the photo) is not a garment feature and is not tested here. That is a conversion problem with a
  checkable answer, and it needs the mm/px scale that most found pairs lack.

## Files

- `tools/experiment_frac_predictable.py`, `reports/frac_predictable.json`
- `tools/experiment_independent_null.py --fracs-json`, `reports/frac_predictor_scored.json`
- `tests/test_frac_predictable.py`
