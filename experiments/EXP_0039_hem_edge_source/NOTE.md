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

## Files

- `reports/hem_edge_source_ab.json`
- `experiments/pairs_hemmask/` — the mask-edge arm, kept as evidence
