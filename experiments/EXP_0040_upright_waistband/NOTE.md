# EXP_0040 — The waistband is the one region registration has no landmarks for, and it always lands low

> **Corrected by EXP_0041.** The headline sign test below — the registered after-garment's top
> lands below the prediction's on 7 of 7 pairs, p = 0.0156 — **does not survive matched
> segmentation**. It was measured with `before_lm.json` (from the coarse before mask) against masks
> derived from `bmask.png` (the refined one), and those two disagree by up to **45 px**. Recompute
> both from one segmentation and the offsets are 30, 14, 23, 0, **−1**, 10, 4: five positive, one
> negative, one zero, **p = 0.2188**. `4bfef03bd7`, the extreme case named throughout this note, is
> the pair that flips, and it is the pair with the largest provenance disagreement.
>
> What stands: the band decomposition (all of the uprighting loss is in band 0, −0.1951 against
> −0.0089 for the hem band) — that measurement never touched the landmark set. What does not stand:
> the sign test, its 14 px median, and the correlations built on the per-pair offsets. The lead this
> note ends on was acted on and closed negatively — the waistband sits 16.6 px from an existing
> landmark, so a correspondence there is redundant rather than missing (EXP_0041).

EXP_0038 left a residual: with uprighting **on**, `443d1d4658` scores IoU 0.898 against the 0.918
uprighting **off** gives, even though its hem is now *better* with uprighting on. Chasing that
turned up something bigger than the one pair.

## Where the loss is: one band, and it is not the hem

Four arms (uprighting on/off × the EXP_0038 fix on/off). Uprighting off is **identical** with and
without the fix — with no uprighting SAM produces no fringe mask, so the gate has nothing to gate —
which leaves uprighting as the only variable. Decomposing silhouette IoU into six vertical bands,
uprighting on minus off:

| band | 0 (waist) | 1 | 2 | 3 | 4 | 5 (hem) |
|---|---|---|---|---|---|---|
| Δ IoU | **-0.1951** | −0.0052 | +0.0045 | +0.0054 | +0.0119 | −0.0089 |

**Exactly one band is worse by more than 0.05**, and it is the top one. Bands 2–4 are slightly
*better* with uprighting on; the hem band moves by under a hundredth. All of the loss is in the
waistband.

## The systematic finding

Band 0 is not arbitrary. `register.SURVIVING` — the landmarks registration actually fits — is
`waist_left/center/right`, `hip_left/right`, `crotch`. The **topmost landmarks are the waist**, so
everything above them is thin-plate-spline *extrapolation*, constrained by no correspondence at all.
It is the only part of the garment registered by nothing.

Measuring where the registered after-garment's top lands relative to the prediction's, on all seven
scored pairs:

| | |
|---|---|
| pairs displaced **downward** | **7 of 7** |
| exact binomial sign test | **p = 0.0156** |
| median displacement | **+14 px** (range +1 to +30) |

Every pair, same direction. The registered ground truth systematically begins *below* the garment it
is being compared against, and nothing in this repository had measured it. It is not noise, and with
n=7 a sign test is one of the few things this sample size can establish properly.

It also behaves like registration error rather than like a segmentation quirk:

| correlation | r |
|---|---|
| leave-one-out registration residual vs \|top offset\| | **+0.781** |
| \|top offset\| vs band-0 IoU | **-0.646** |

So the chain is: registration quality → how far the after-garment's top is displaced → how bad the
waistband band scores. `4bfef03bd7` is the extreme — band-0 IoU **0.138**, with `real_only = 0` and
`pred_only = 12490` in that band, because the registered garment simply starts 28 rows lower and is
17% wider than the garment it should match.

## Two mechanisms for the magnitude, both dead

Having a real systematic effect is not having an explanation for its size. Two candidates were
tested and both fail:

- **Uprighting shifts the waistband landmark, unequally on the two photos.** Within `443d1d4658`
  this is well supported: uprighting pushes the detected waist line down (before 4.71% → 6.42% of
  garment height, after 6.67% → **10.50%**), and the shift is the same fraction of the predicted
  `width × sin θ` edge smear on two independent photos — **0.614** and **0.627** — which is what a
  detector firing partway through a smeared edge looks like. The waist correspondence error doubles,
  14 px → 29 px. But **across pairs it explains nothing**: r = **+0.177**, the wrong sign, and
  `4bfef03bd7` is simultaneously the pair with the smallest waist mismatch and the worst band-0 IoU.
- **More garment above the top landmark means more extrapolation means worse.** Also false:
  r = **-0.187**.

So: the effect is systematic and significant; the within-pair account for `443d1d4658` is supported
by a controlled toggle and three checked predictions; and the magnitude across pairs is
**unexplained**. Recorded that way deliberately — this project's recurring failure is a real
measurement published with an unchecked mechanism attached (EXP_0029, EXP_0033, EXP_0037, EXP_0039).

## What follows

Not a fix, and specifically not a `canon/autolm.py` change: a rotation-robust waistband detector is
under the tuning rule (`docs/GATES.md`), needs ≥5 pairs and an attached report, and EXP_0039 is the
cautionary case — a change better on 5 of 7 and worse on the mean.

The more interesting lead is the landmark set itself. Registration has **no landmark above the
waistband**, and the waistband is where it fails on every pair. A correspondence on the waistband
edge — the one garment feature that survives cutting unchanged and is trivially visible in both
photos — would put the failing region inside the landmark hull instead of outside it. That is a
change to `canon/register.SURVIVING`, testable with the existing A/B machinery, and it is the first
lead in a while that is unblocked and not obviously fitted to one pair.

## Files

- `tools/experiment_upright_waistband.py`, `reports/upright_waistband.json`
- `tests/test_upright_waistband.py`
