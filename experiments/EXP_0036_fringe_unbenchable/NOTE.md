# EXP_0036 — The fringe render rests on one garment

The backlog listed "fringe rendering is invisible in the bench" as open and unblocked: every
published run used `--wash none`, so the fringe depth was 0.0 px on every pair and the prediction
was the crop plus at most 256 px (EXP_0034). The obvious missing experiment was to turn wash on and
score it against an independent null. This does that, and finds the answer was structural.

## How many pairs can show a fringe at all

A fringe requires a **raw** cut edge (a cuffed or hemmed edge does not fray, whatever the wash) and
an **after-wash** capture (an after-cut photo was taken before the garment was ever washed). Of the
seven pairs the bench scores:

| | count |
|---|---|
| raw edge | **3** |
| after-wash capture | **1** |
| **both — can show a fringe** | **1** |

Six of the seven are structurally incapable of displaying a fringe. No amount of rendering work
changes their score, and no run of this bench can ever measure the fringe on them.

## What turning wash on does

`score_predict.py --wash median`, everything else unchanged, scored against the same ground truths
as the `--wash none` run:

| pair | wash none | wash median | difference |
|---|---|---|---|
| 2691c1a8d0 | 0.7192 | 0.7192 | 0.00000 |
| 26b1041d00 | 0.8769 | 0.8769 | 0.00000 |
| 2b0123d732 | 0.7802 | 0.7802 | 0.00000 |
| 443d1d4658 | 0.8515 | 0.8515 | 0.00000 |
| **4bfef03bd7** | 0.7887 | **0.7997** | **+0.01106** |
| 8d9f0df4ad | 0.8824 | 0.8824 | 0.00000 |
| e97924ad2d | 0.8636 | 0.8636 | 0.00000 |

Six pairs move by **exactly zero** — not "by a small amount", by nothing, which is what the
structural table above predicts. The whole effect is `4bfef03bd7`, the one after-wash raw-edge pair,
and its hem chamfer improves alongside (11.5 → 10.2 px).

## Is that one pair's gain real?

Paired against the same perturbed ground truths (EXP_0033's harness): **+0.01106 ± 0.00576**, which
is **1.9σ**. Suggestive, not significant. The bench mean moves +0.00158 ± 0.00082 — the same 1.9σ,
because it is the same single pair diluted by six zeros.

The cancellation factor is 37.1: high, because wash-on and wash-off masks are nearly the same
object, but well short of the 132 that flagged the crop-only null as degenerate (EXP_0034).

## What this means

The fringe renderer is **not benchable on the found-pair set**, and this is a property of the data,
not of the metric or the renderer. Its entire measurable evidence is one garment at 1.9σ.

That is worth stating as a limit rather than a to-do, because it cannot be worked around in code:

- **Six of seven pairs would have to be different garments.** Adding metrics, changing the renderer,
  or improving registration cannot make a cuffed hem fray.
- **The claim that would need support** — that the fringe render improves fidelity — currently rests
  on n=1. Any number quoted for it should say so.
- **What would settle it:** after-wash captures of **raw-edge** cuts. `CONTRIBUTING_PAIRS.md` already
  asks for after-wash photos; it should ask specifically for raw (unfinished) hems, since a cuffed
  contribution adds nothing to this question no matter how good the photograph is.

This does not retract anything. `--wash none` remains the right default for the headline bench: it
is the configuration in which six of seven pairs are meaningful, and turning wash on changes only
the one pair that can respond.


## Re-derived after two corrections (review 7)

Both corrections that review 7 forced were applied and this note's numbers survive them:

- **EXP_0038 regenerated `experiments/pairs`**, moving every pair's ground-truth inseam fraction.
- **The product path was not holding the fringe prior out.** `run_pair.py` has always excluded a
  pair from the prior that predicts it; `predict.py` passed `exclude=None`, and for the one
  fringe-capable pair the after-wash prior held exactly one paired row — `4bfef03bd7` itself — so
  its "predicted" depth was half its own measurement. Fixed; with the pair held out the prior for
  it is **n = 1** (a single unpaired sample), which is worth stating plainly.

Re-run with current pairs and a held-out prior on both arms: **+0.01104 ± 0.00577, still 1.9σ**,
still six pairs moving by exactly zero. The conclusion is unchanged, and it was not resting on the
leak.

## Files

- `reports/fringe_capable_pairs.json` — which pairs can show a fringe and why
- `reports/wash_effect_paired.json` — the paired A/B
- `experiments/pairs_predict_washmed/` — the wash-median run
- `tests/test_fringe_benchability.py`
