# EXP_0041 — The waistband correspondence is redundant, not missing; and EXP_0040's headline does not survive

EXP_0040 ended on a lead. `register.SURVIVING` tops out at the waist landmarks, `autolm` places those
2% of the garment height *below* the top edge, so the waistband is registered by pure thin-plate-spline
extrapolation — and the waistband is the one band uprighting costs IoU on (−0.1951, against −0.0089
for the hem band). The obvious move was to give the fit a correspondence it was missing.

It was given one, three ways, on seven pairs. It changes nothing. Establishing *why* it changes
nothing took two controls the first version of this experiment did not have, and both of them
overturned something — including EXP_0040's own headline number.

## 1. EXP_0040's 7-of-7 is a segmentation artefact

`before_lm.json` and `bmask.png` are **different segmentations of the same photograph**.
`run_pair.py:150` refines the before mask with landmark prompts once there are ≥14 landmarks and
deliberately keeps the landmarks from the *coarse* mask (the comment cites EXP_0004: recomputing
them on the refined mask regressed pair 1). So registration fits landmarks describing one
segmentation, while the prediction and every mask downstream live on another.

Nobody had measured the size of that. Over all six `SURVIVING` landmarks and both coordinates:

| | |
|---|---|
| largest before-photo disagreement | **45 px** (`4bfef03bd7`, crotch y; 32 px in x on the waist) |
| pairs with any disagreement | **5 of 7** |
| largest **after**-photo disagreement | **0 px** — the after mask is never refined |

Re-run EXP_0040's own statistic — the row where the registered after-garment's top lands, minus the
prediction's — with landmarks and mask taken from one segmentation instead of two:

| | per pair (px) | median | sign test |
|---|---|---|---|
| production landmarks (EXP_0040's configuration) | 30, 14, 24, 1, 28, 11, 4 | 14 | **7 of 7 positive, p = 0.0156** |
| landmarks and mask from the same segmentation | 30, 14, 23, 0, **−1**, 10, 4 | 10 | 5 positive, 1 negative, 1 zero, **p = 0.2188** |

`4bfef03bd7` — EXP_0040's extreme, "starts 28 rows lower", band-0 IoU 0.138 — goes to **−1**. It is
the pair with the 45 px provenance disagreement. **EXP_0040's headline result is not established at
n=7**; it was carried by a mismatch between two segmentations of the before photo, and the note now
carries a correction banner saying so.

## 2. The correspondence is 16.6 px from a landmark that already exists

The lead assumed the waistband is a region the fit reaches for. It is not. Distance from each
evaluated point to its nearest point in the fit's support:

| | median reach |
|---|---|
| a held-out `SURVIVING` landmark, under leave-one-out | **136.0 px** |
| a waistband corner, under the full six-landmark fit | **16.6 px** |

A number computed at 16.6 px of reach and a number computed at 136.0 px of reach are not the same
measurement. Matching the *cardinality* of the fit — the waistband gap re-derived under each
five-landmark jackknife, so both are predictions from five points — the gap wins:

| | median |
|---|---|
| waistband gap, matched cardinality | **12.03 px** |
| leave-one-out error of the landmarks the fit was given | **28.82 px** |
| pairs where the LOO error is the larger | **7 of 7** (p = 0.0078) |

Matching the *reach* instead — drop the three waist landmarks from the waistband's support, so the
corner faces the same denuded neighbourhood a held-out landmark does — the ordering **inverts**:

| | median |
|---|---|
| waistband gap, matched reach | **118.94 px** |
| pairs where it exceeds the LOO error | **7 of 7** (p = 0.0078) |

Both results are real and they answer different questions. What neither supports is the conclusion
the first draft of this note drew from the first table alone — that the outside of the landmark hull
is fitted better than the inside. The waistband is barely outside the hull at all. **That is the
finding: the correspondence is redundant with a landmark 16.6 px away, not missing from a region
nothing constrains.**

## 3. And the downward direction is mostly built in

`autolm` places the waist landmark `int(0.02 × h)` below the top edge of **each garment's own
height** (`autolm.py:36`), and the before garment is the taller one — it still has its legs. So the
before waist sits further below its top edge than the after waist does below its, and a *perfect*
map still lands the mapped corner low:

| | |
|---|---|
| median vertical displacement of the mapped corner | +3.21 px |
| median of the construction term alone (before depth − after depth) | **+2.00 px** |
| correlation between the two across pairs | **r = +0.821** |

Seven of seven are positive at p = 0.0156, but the null that test rejects — "displacement symmetric
about zero" — is false for a correct registration on this landmark definition. About two thirds of
the median is arithmetic. **The sign test is not evidence about registration**, and this note does
not use it as such.

## 4. The A/B: nothing, and worse than nothing

| arm | Δ IoU (paired) | σ | Δ held-out residual, common landmarks | σ | median | worse on |
|---|---|---|---|---|---|---|
| `add` | -0.00204 ± 0.00350 | −0.58 | +1.586 px ± 6.586 | **0.24** | **-4.76 px** | 3 of 7 |
| `replace` | -0.00234 ± 0.00341 | −0.69 | **+5.574 px** ± 2.598 | **2.15** | +2.97 px | **6 of 7** |

The residual is the one measurement that does not depend on the prediction: leave-one-out error over
the landmarks **no arm moves** (hips and crotch), with each arm's own top-of-garment points held in
support. Read it with its uncertainty, which the first draft did not:

- **`add` does nothing at all.** 0.24σ, better on the majority of pairs, and the mean is carried by
  the two tallest garments — normalised by garment height it changes sign (-0.26σ). Calling this
  "worse" was wrong; it is a coin flip.
- **`replace` is genuinely worse**, 2.15σ and worse on 6 of 7, and 2.33σ scale-free. Moving the waist
  landmarks onto the top edge costs the fit accuracy where that accuracy can be checked.

Neither moves silhouette IoU, both negatively and both under 1σ.

## 5. The null says the correspondence is real, and that the fit already had it

Displacing each waistband point by a random vector of the measured gap length:

| | Δ held-out residual vs control |
|---|---|
| `null` (displaced correspondence) | **+12.134 px** |
| `add` (true correspondence) | +1.586 px |
| `add` − `null` | **-10.549 px, −2.51σ, better on 7 of 7** |

So the waistband edge is a genuine correspondence — a wrong point in its place does real damage, and
the true one does not. It simply adds no information the six landmarks did not already carry. That
is a much more specific answer than "it did not help", and it is the one the reach measurement
predicts.

## 6. The band-0 column cannot carry a claim, in either run

`pred_median_mask.png` is a strict pixel **subset** of `bmask.png` on **7 of 7** pairs and shares its
**top row** on **7 of 7**. A correspondence read off `bmask.png` is therefore read off the artefact
that defines the scoring target's silhouette — the same structure `docs/GATES.md`'s baseline rule
bans for `null:crop-only`. It shows up exactly where you would expect:

| | `replace` Δ band-0 IoU |
|---|---|
| landmarks and correspondence from the same mask | **+0.02313** |
| production landmarks, correspondence off `bmask.png` | **+0.12004** |

and the second is **89% one pair** — `4bfef03bd7` alone contributes +0.6039 of the +0.6825 total
difference, and the three pairs with zero provenance disagreement produce identical deltas in both
runs. So the warning is narrower than "mixing segmentations inflates effects": it is that one pair
with a 45 px segmentation disagreement can carry a 1.6σ result on its own.

## Verdict

**Not adopted.** `register.SURVIVING` is unchanged. The tuning rule (`docs/GATES.md`) is satisfied —
seven usable pairs with the report attached — and the answer is no.

## What this closes and what it opens

- EXP_0040's **lead** is closed: the waistband is not an unconstrained region, it is 16.6 px from a
  landmark, and a correspondence there is redundant.
- EXP_0040's **headline** is corrected: 7 of 7 at p = 0.0156 becomes 5-of-7-with-a-negative at
  p = 0.2188 once the landmarks and the mask come from one segmentation. Its band-decomposition
  finding (all of the uprighting loss is in band 0) is untouched — that measurement never used the
  landmark set.
- **Newly open, and the more useful lead:** the before photo is segmented twice and the two results
  differ by up to 45 px, with everything downstream silently mixing them. That is not a registration
  problem and it is cheap to test: either refine the landmarks with the mask, or do not refine the
  mask. EXP_0004 chose the latter for a reason worth re-examining at n=7 rather than n=1.

## A note on how this experiment went wrong first

The first version of this note reported "extrapolating past the hull is more accurate than
interpolating inside it, on 7 of 7 pairs" and "the residual gets worse in both arms". Both came from
real numbers. The first compared two quantities computed at an 8× difference in reach; the second
read a 0.24σ difference as a result and did not notice its own scale-free form had the opposite sign.
Neither survived being asked what would have to be true for the comparison to mean what it said —
which is the check this project keeps rediscovering it needs (EXP_0029, EXP_0033, EXP_0037, EXP_0039,
and now the first draft of this one).

## Files

- `src/denimtwin/canon/waistband.py` — the top-edge rule moved out of `autolm` so both can use it,
  behaviour unchanged (`tests/test_waistband.py` re-derives every landmark on every stored mask)
- `tools/experiment_waistband_landmark.py`
- `reports/waistband_landmark.json`, `reports/waistband_landmark_production.json`
- `tests/test_waistband_landmark.py`, `tests/test_waistband.py`
