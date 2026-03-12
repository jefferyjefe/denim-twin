# EXP_0031 — The fold was two landmarks sitting on top of each other

EXP_0030 left the fold as the one canonical-layer defect that reaches the pipeline: on two of the seven usable pairs
the forward map turns space inside out over 37.2% and 40.1% of the garment, so two garment pixels land on one
canonical coordinate. This finds the cause, which is smaller and more fixable than "TPS folds sometimes".

## The cause

Take the landmark correspondences, remove the best similarity transform — the part the spline does *not* have to bend
— and look at which pairs of landmarks must still move relative to each other:

| pair | worst stretch | landmarks | image separation → canonical separation |
|---|---|---|---|
| 4bfef03bd7 | **135×** | `hem_left_inner` ↔ `hem_right_inner` | 1 px → 160 px |
| 4bfef03bd7 | 101× | `knee_left_inner` ↔ `knee_right_inner` | 1 px → 120 px |
| 2b0123d732 | **106×** | `hem_left_inner` ↔ `hem_right_inner` | 2 px → 160 px |
| 2b0123d732 | 80× | `knee_left_inner` ↔ `knee_right_inner` | 2 px → 120 px |
| e97924ad2d (does not fold) | 1.5× | `hem_left_inner` ↔ `hem_right_inner` | 240 px → 160 px |

Both garments were photographed **with their legs touching**. `canon/autolm.landmarks_from_mask` finds no gap, so it
puts the two legs' inner landmarks within a pixel or two of each other, and the canonical template wants them 160 px
apart. A thin-plate spline asked to pull two coincident points apart has one way to comply: tear.

Two points a pixel apart carry no information about how space should stretch between them. That is a degenerate
correspondence, not a measurement.

## The fix

`CanonicalMap(drop_degenerate=True)`, now the default: when a source landmark lies within 1% of the garment's span of
one already kept, it is dropped, and the map is fitted on what is left. The rule is a numerical-conditioning
condition, not a threshold chosen against outcomes — and it fires only where it should.

| pair | fold, all landmarks | fold, degenerate dropped | dropped |
|---|---|---|---|
| 4bfef03bd7 | 37.2% | **0.0%** | `hem_right_inner`, `knee_right_inner` |
| 2b0123d732 | 40.1% | **5.3%** | `hem_right_inner`, `knee_right_inner` |
| the other five | 0.0–3.1% | **unchanged**, nothing dropped | — |

And the canonical representation, across the three states:

| | round trip, median over the garment | region IoU with itself | pairs faithful (≥0.90) | worst point error |
|---|---|---|---|---|
| two independent TPS fits | 10.7 px | 0.638 | 2 of 7 | 835 px |
| + corrected inverse (EXP_0030) | 0.02 px | 0.972 | 5 of 7 | 835 px |
| + degenerate dropped (this) | **0.01 px** | **0.998** | **6 of 7** | **149 px** |

`4bfef03bd7` goes from a region round-trip IoU of 0.178 to **1.000**.

## And it changes nothing

Both A/Bs are identical, and this time checked at the pixel:

- evaluation path, 7 pairs: silhouette IoU 0.8566 both arms, hem 7.85 px both arms, **0 differing pixels** across all
  11 scored runs;
- product path: 0.8232 both arms, hem 20.9 px both arms.

The one visible consequence is a good one: `predict.py`'s fold refusal, which had been rejecting those two garments
outright (EXP_0030), now sees a maximum fold of 5.3% and **accepts all seven again**.

## The pattern worth keeping

That is the third canonical-layer fix in a row — the corrected inverse, the fold detector, and now the degenerate
correspondences — which is correct, measurable at the layer it fixes, and **invisible in the pair scores**. Together
they take the canonical representation from usable on 2 of 7 garments to 6 of 7, and move no pixel.

The honest reading is not that the work was wasted; it is that **the canonical layer was not what limited the
scores**, and three experiments were needed to establish that rather than assume it. The corollary is a warning about
the fold refusal: its 20% threshold was set before this fix, no pair now comes within 15 points of it, and it has
never been shown to prevent an actual error. It is insurance against a latent failure, and it should be described
that way rather than as a validated gate.

## What is left
`2b0123d732` still folds over 5.3% of itself and still has the worst region round trip (0.603), and it is the pair
whose landmark set puts the **crotch above the hips** — a physically impossible garment. That is a landmark-extraction
failure, not a mapping one, and `canon/autolm` should be able to say so: a garment whose crotch is above its hips is
one this pipeline cannot measure, and it is cheap to detect.
