# EXP_0014 — How much of our cut accuracy comes from *looking at the answer*?

> **Superseded by EXP_0034.** The crop-only comparison below is void: the null is built from
> predict's own keep mask, so it crops at the cut line the model predicted. This note's own table
> says so — "crop-only null **on the product path's own mask**" — and the implication was not
> drawn for twenty experiments. Against a null that does not see the model the product path wins
> by +0.0954 (4.8σ).


**Question.** `run_pair.py` fits the cut by reading the real after-photo (per-leg hem lines, fabric/fringe split). That is
an evaluation path. A user of `predict.py` supplies one scalar — the inseam fraction — and the cut is placed in canonical
space. The headline "silhouette IoU 0.6–0.95" comes from the evaluation path. What does the *product* path score?

**Method** (`tools/score_predict.py`): for each of the 11 usable found pairs, run `predict.py` on the same before-photo
with the cut height the evaluation path fitted, then score the render against the same registered real after-photo with
the same `compare.py`. `--wash none` so only the cut is under test. Comparison is done in predict's own frame (it may
rotate the photo again), otherwise masks are silently mis-sized — the first version of this script crashed on one pair
and mis-scored another because of exactly that.

| condition | mean sil IoU | mean hem error |
|---|---|---|
| evaluation path (sees the after-photo) | **0.819** | **48.4 px** |
| product path, `inseam_fraction` as recorded by run_pair | 0.736 | 104.7 px |
| product path, canonically-defined cut height | 0.768 | 80.6 px |
| product path, canonical height + the fitted cut angle (outseam-higher sign) | 0.772 | 80.2 px |
| crop-only null on the product path's own mask | 0.771 | — |

*(all conditions re-run step 14 after review 4 fixed `apply_cut`, which had been discarding cut angles entirely)*

## Finding 1 (bug): the two paths do not mean the same thing by "inseam fraction"
`modification.py` documents `inseam_fraction` as *canonical* ("0 = crotch, 1 = original hem, canonical inseam
coordinate"), but `run_pair.py` computes it in **image** y between the crotch landmark and the hem landmarks. Measured
discrepancy on the 11 pairs (recorded vs the canonical fraction of the same fitted cut): 0.106→−0.085, 0.221→0.428,
0.396→0.344, 0.221→0.061, … — up to **0.21 of the leg**, and four pairs sit above the canonical crotch (negative), which
run_pair clips to 0. Feeding the canonical value recovers ~a third of the IoU gap and ~a quarter of the hem-error gap.
Fix belongs in run_pair (record the canonical fraction, or rename the field); not applied here because the file is
under adversarial review in parallel.

## Finding 2 (RETRACTED and re-measured): a global cut angle helps slightly
The original version of this finding — "a single global cut angle buys nothing" — was measured on code that never
applied an angle. `apply_cut` reduced any canonical removal mask to its topmost row, so every angled cut was rendered
as a flat cut (review 4, finding 1); `predict.py` was its only caller, so nothing else was affected. The angle also
pivoted about the inseam side, which made `+a` and `-a` nested rather than mirrored; it now pivots about the requested
cut height.

Re-measured with angles actually applied: no angle 0.768 / 80.6 px, outseam-higher angle **0.772 / 80.2 px**,
inseam-higher angle 0.761 / 85.5 px. So the angle carries a small real signal in the expected direction (tutorial cuts
are cut higher on the outseam) and the sign convention is now meaningful. It remains far short of the evaluation path,
and per-leg curvature would still need the polyline (`cut_path_canonical`, already in the schema).

## Finding 3: the honest headline
Given only what a user actually supplies, the cut prediction scores **0.768** (0.772 with a cut angle) where the
evaluation path scores 0.819 — and the crop-only null on the same mask scores 0.771, i.e. **the fringe render is invisible to silhouette IoU** —
a whole-garment metric cannot see a 7–40 px band. On the fringe-specific metric the render does beat the null (mean
fringe IoU 0.17 vs 0.00), but that is with the depth read off the after-photo; held out through the prior it is not
predictive (EXP_0008). The remaining 0.05 IoU / 32 px gap is genuine: a straight canonical
cut cannot reproduce a hand-cut hem's per-leg curvature. README and STATUS must quote the product-path number when
describing what the system can do for a user; the evaluation-path number describes only the scoring harness.
