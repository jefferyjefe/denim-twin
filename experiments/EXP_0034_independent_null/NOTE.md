# EXP_0034 — The null was built out of the model, so the tie meant nothing

The headline number this project has carried for months: product path **0.8232**, crop-only null
**0.8233**. A dead heat, reproduced across EXP_0027 through EXP_0031, and the reason four separate
lines of work were opened to explain why the model adds nothing. EXP_0033 sharpened it further by
showing the bench resolves that difference to ±0.00023 — a real null, not a noise floor.

The null is invalid.

## Where it comes from

`compare.py:42` builds `null:crop-only` out of the `--keep` mask it is handed. `score_predict.py`
hands it `{od}/keep_mask.png`, where `od` is **predict's own output directory**. The null therefore
crops the photograph at the cut line the model just predicted. It is not a baseline; it is the
model's own answer with the fringe switched off.

And the fringe *is* switched off. The bench runs `--wash none`, and every pair's `prediction.json`
records `fringe_depth.median = 0.0` with `below_render_resolution: true`. So the two masks cannot
differ by anything at all. Measured directly:

| | |
|---|---|
| median IoU(prediction, crop-only) | **0.99954** |
| pixels the null keeps that the prediction drops | **0** on every pair |
| most pixels the prediction adds | 256 |
| pairs where the two masks are bit-identical | **1** |
| median symmetric difference | 0.046% of the union |

The prediction is the crop-only mask plus, at most, a quarter-percent sliver. "The product path
ties the crop-only null" was a statement that a cut rendered without fringe equals the same cut
rendered without fringe.

EXP_0033's ±0.00023 was correct and is now explained: pairing cancelled **132×** of the
registration noise precisely *because* the two masks are the same object. In hindsight that
cancellation factor was the evidence, sitting in plain sight — a genuine comparison cannot cancel
that well.

## A null that does not see the model

Place the cut at the **leave-one-out median inseam fraction of the other six pairs** — the best
guess available with no information about the garment being scored — and score it against the same
ground truth:

| | mean IoU |
|---|---|
| product path | **0.8232** |
| leave-one-out null | **0.7278** |
| advantage | **+0.0954** |

Product wins on **6** of 7 pairs. Paired against the same perturbed ground truths (EXP_0033's
harness), the difference is **+0.09539 ± 0.01974** — **4.8σ**. Real.

The cancellation factor for this comparison is **1.5**, against 132 for crop-only. That is the
method checking itself: noise cancels almost perfectly between two identical masks and barely at
all between two genuinely different ones.

## What the advantage is not

It is not evidence that the system predicts where to cut. The product path's only per-garment input
is the inseam fraction, and `run_pair.py:263` computes that from the cut line **fitted to the real
after-photo**. The model is handed a measurement of the ground truth and asked to render it.

So the honest reading is narrower than the number looks:

- **Supported:** given a cut height, the pipeline places and renders that cut substantially better
  than not knowing it (+0.095, 4.8σ). Under this project's own framing — the inseam fraction is
  "what a user actually supplies" (`score_predict.py` docstring) — that is a legitimate product
  claim: the system correctly uses what the user asks for.
- **Not supported, and never yet benched:** that the system can choose the cut height itself. No
  experiment in this repository has asked that question, because every product-path run has been
  handed the answer.

`443d1d4658` is the one pair the null wins (−0.0068, −3.6σ). Its own fraction (0.246) is almost the
leave-one-out median (0.260), so there is nothing to gain there, and what is left is the rendering
regression already documented against that pair in the bench.

## Consequences

- The crop-only null stays (it catches a gamed metric, which is what it was written for) but it is
  no longer a baseline the product path can be said to "beat" or "tie". Reported alongside it now:
  the leave-one-out null.
- Gate 1's real question is restated: **can the pipeline choose an inseam fraction from the before
  photo and user intent, and beat 0.7278?** That is the first genuinely predictive question this
  bench has been able to pose.

## Files

- `tools/experiment_independent_null.py`, `reports/independent_null.json`
- `tools/experiment_paired_uncertainty.py --null-dir`, `reports/paired_uncertainty_loonull.json`
- `reports/prediction_vs_croponly_masks.json`
- `tests/test_independent_null.py`
