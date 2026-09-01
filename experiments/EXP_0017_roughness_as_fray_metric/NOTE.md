# EXP_0017 — RETRACTED TWICE: scoring the fringe renderer on hem roughness

> **Second retraction (EXP_0025).** Everything below scores each system against the real garment's hem roughness
> measured on the real mask **warped into the prediction's frame**. EXP_0024 showed that warp manufactures the
> quantity being measured — rotating a finished-hem control makes 12 of 12 read as frayed, at the same magnitude as
> this experiment's entire result. Measured on the mask as segmented, the real hems of **6 of the 7 usable pairs read
> exactly zero**: at 241–389 px of waistband they are below the resolution EXP_0016 established this statistic needs.
> The comparison therefore had no signal to score against, and the ordering below reverses when the artefact is
> removed. Nothing in this note is evidence. It is kept because the retraction is the result.

> **This experiment's original numbers were wrong and are withdrawn.** Review 6 checked every figure against the pair
> artefacts and found none of them there: the note claimed 11 usable pairs (7 were decidable), mean errors of
> 0.91/1.27/1.55 px (the artefacts gave 0.43/1.00/1.00), and a 6-3-2 split at p = 0.51 (4-1-2, p = 0.375). The
> arithmetic was right; the note had been written from a run whose artefacts were then regenerated under a rewritten
> metric and never recomputed. README and STATUS quoted two further different versions of the same result. All three
> are corrected to what follows.

## Recomputed step 17 (after the compactness gate was removed)
The restatement below was itself written between two changes and is superseded: with the gate gone, **all 10 usable
pairs are decidable**, not 2. The numbers are re-derived from the artefacts by `result.json` in this directory, and
`claims.json` checks this note against it in CI — the mechanism that exists precisely because this note has now drifted
twice.

| system | mean \|roughness error\| relative to waist width (n=10) |
|---|---|
| prediction (cut + procedural fringe) | **0.00194** |
| null: no-op (the uncut jeans) | 0.00214 |
| null: crop-only (a clean cut, no fringe) | 0.00231 |

Prediction beats crop-only on **4** pairs, loses on **1**, ties on **5**; sign test **p = 0.375**. The ordering is the
one we would want and the margin is 16% of the null's error, but five ties on ten pairs is not a result — a tie here
usually means both silhouettes have a hem that deviates on fewer than 10% of columns, which is the p90 floor rather
than agreement.

One false fray remains (`e97924ad2d`: predicted p90 1.0 against a real 0.0), down from three before `run_pair` started
consulting `modification.expects_fringe()`.

## What was measurable at the time of the retraction
`compare.py` now reports hem roughness **relative to waist width** (a pixel value ranks photo size: the same fray
photographed twice as large doubles it) together with `rough_fraction`, because a p90 of 0 means only "fewer than 10%
of hem columns deviate", not "this hem is smooth".

On the current artefacts, **8 of 10 usable pairs cannot be decided at all**: the predicted silhouette includes rendered
fringe, which breaks the solid-column requirement `hem_roughness` uses to avoid measuring speckle, so the metric
refuses. Of the 2 decidable pairs the prediction matches the real roughness exactly on one and ties on the other:

| system | mean \|roughness error\| (relative to waist width), n=2 |
|---|---|
| prediction | 0.00000 |
| null: crop-only | 0.00136 |
| null: no-op | 0.00136 |

Sign test: 1 win, 0 losses, 1 tie, **p = 1.0**. There is no evidence here either way, and n = 2 is not a result.

## The real finding of this experiment
Scoring the *rendered silhouette* was the wrong design. The renderer paints threads below the fabric edge, which is
exactly what the roughness metric treats as an unreliable boundary — so the better the fringe render, the less
measurable it becomes. Roughness should be computed on the predicted **fabric edge** (the cut line), with the fringe
compared separately, and that is a change to make deliberately rather than in the middle of a correction.

## What still stands from the original
Two things, both independently checked:
- the *ordering* the earlier run reported (prediction ≤ crop-only ≤ no-op) is the ordering the corrected numbers show
  on the pairs that can be decided;
- the failure mode it named is real and was fixed: the renderer used to fray hems the modification declared finished
  (`run_pair` now consults `modification.expects_fringe()`; false frays on real pairs went 3 → 1).
