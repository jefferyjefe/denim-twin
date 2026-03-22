# EXP_0039 — Should a garment that cannot fray use the mask edge? Tested, not adopted

EXP_0038 left a finding open: three pairs got slightly *worse* when a spurious SAM fringe was
removed from the hem fit, meaning the artefact had been landing closer to the true hem than
`hemfit.fabric_vs_fringe`'s colour split does.

There is a principled follow-up. The colour split exists to stop a **fringe** being counted as
fabric. On a garment that cannot fray there is no fringe to exclude, so the split has nothing to do
and can only invent an edge. The obvious change is to gate `real_img` exactly as EXP_0038 gates
`fringe_mask`: when `expects_fringe()` is false, take the fabric edge from the mask.

It was tested on all seven scored pairs. **It is not adopted.**

## The A/B

| pair | edge | hem, colour split | hem, mask | Δ |
|---|---|---|---|---|
| 2691c1a8d0 | raw | 12.45 | 11.44 | −1.01 |
| 26b1041d00 | cuffed | 3.00 | 2.97 | −0.03 |
| **2b0123d732** | cuffed | **7.20** | **27.27** | **+20.08** |
| 443d1d4658 | cuffed | 7.54 | 4.95 | −2.59 |
| 4bfef03bd7 | raw | 4.46 | 4.46 | 0.00 |
| 8d9f0df4ad | cuffed | 3.96 | 2.59 | −1.36 |
| e97924ad2d | raw | 1.32 | 1.27 | −0.05 |

**Better on 5 of 7 pairs. Mean hem chamfer 5.70 → 7.85 px — worse.** Median is unchanged at 4.46.
Mean silhouette IoU 0.8606 → 0.8592.

## Why it is not adopted

One pair carries the entire result in each direction. `2b0123d732` alone costs +20.08 px, which is
the same size as the win EXP_0038 delivered on `443d1d4658` (−20.13 px), and it is not a rounding
difference — the mask edge on that garment is 27 px from the true hem.

`2b0123d732` is the pair photographed with its legs touching (EXP_0031) and the one with a 54.9°
fitted right-hem angle. Its garment mask evidently extends past the true hem, and the colour split
is doing real work there — exactly the work it was written for, on a garment that supposedly has no
fringe to find.

So the honest reading is that neither edge source is right in general, and there is no principled
rule available for choosing between them per garment. Adopting the change would trade one pair's
20 px error for another's. That is the kind of swap the tuning rule exists to prevent: "better on
5 of 7" and "worse on the mean" are the same data, and picking whichever framing favours the change
is how a null becomes a result.

The experimental knob used to run this (a `HEM_EDGE` environment variable) was **reverted**, not
left in place behind a default. An undocumented switch nobody sets is a dead parameter, and this
repository has a test against those.

## What would settle it

A rule for when the garment mask can be trusted at the hem. `2b0123d732` fails it and the other six
pass, so the discriminator would need to be measured on far more than one negative example — and at
n=7 with one deciding pair, anything fitted here would be fitted to that pair. Blocked on data, like
most of what is left.


## Addendum — where the 20 px lives, and three explanations that do not

The regression is not spread across `2b0123d732`'s hem. Comparing the two arms' fitted cut lines
column by column, the shift is **≈0 px on six of seven pairs** and on `2b0123d732` is confined to
**78 columns, x = 281–363** — the middle of a garment spanning x = 156–425 — where the mask edge
sits up to **120 px** below the colour-split edge. Everywhere else on that garment the two agree.
(One isolated column on `2691c1a8d0` shifts 195 px; a single column is not a systematic shift, and
it moves that pair's score by 4 px at the 90th percentile.)

So the colour split is not generally better on this pair. It rescues one central band.

Three explanations for that band were tested and none survives:

- **The rolled cuff.** The garment is cuffed, and a cuff gives two candidate edges — the fold and
  the bottom. But the cuff is roughly 30 px of a 757 px frame, and the shift reaches 120 px.
- **The legs were photographed touching** (true of this pair, EXP_0031, and the cause of its
  canonical fold). But the between-leg gap is present on 74.5% of rows from crotch to hem, and near
  the hem specifically it is 21.4% — against 9.1% on `8d9f0df4ad` and **0.0%** on `2691c1a8d0`,
  neither of which shows the shift.
- **Gap fraction near the hem as a discriminator.** Directly falsified by the line above: the pair
  with the *least* gap near the hem has the *smallest* shift.

So the band is **localised but unexplained**. Recording it that way rather than attaching the most
appealing of three dead stories — the standing rule from EXP_0037.

This sharpens what "blocked on data" means here. There may well be a principled rule for when the
mask can be trusted at the hem, but the only positive example of it failing is 78 columns of one
garment, and nothing measured so far separates that garment from the six that are fine.

## Files

- `reports/hem_edge_source_ab.json`
- `experiments/pairs_hemmask/` — the mask-edge arm, kept as evidence
