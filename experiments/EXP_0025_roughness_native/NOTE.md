# EXP_0025 — Scored where nothing resampled the boundary, the fray comparison has no signal to score against

> **Partly superseded by EXP_0034.** The native-resolution roughness result stands; any comparison
> here against the crop-only null does not — that null is built from the model's own keep mask.


EXP_0017 scored the fringe renderer on hem roughness against the real garment's, using the real mask **warped into
the prediction's frame**. EXP_0024 showed the warp manufactures exactly that quantity. Roughness is scale-free —
p90 divided by waist width — so the two sides never needed a shared frame. `run_pair` now keeps `amask_native.png`,
the after mask as segmented, and `compare.py` measures the real hem on it.

## What the real hems actually measure

| pair | real hem, native | real hem, warped | waist in the after photo |
|---|---|---|---|
| 2691c1a8d0 | **0.00000** | 0.00353 | 273 px |
| 26b1041d00 | **0.00000** | 0.00415 | 241 px |
| 2b0123d732 | **0.00000** | 0.00341 | 290 px |
| 443d1d4658 | **0.00000** | 0.00000 | 357 px |
| 4bfef03bd7 | 0.00299 | 0.00538 | 334 px |
| 8d9f0df4ad | **0.00000** | 0.00171 | 914 px |
| e97924ad2d | **0.00000** | 0.00000 | 389 px |

The warp inflates the real garment's measured roughness **six-fold** — mean 0.00043 native against 0.00260 warped,
rougher on 5 of the 7 pairs. And on **6 of 7 pairs the real frayed hem measures exactly zero**, which is not a
surprise: EXP_0016 established that roughness needs roughly 600–1000 px of waistband, and six of these photographs
have 241–389 px.

## The comparison, both ways

| real hem measured on | prediction | crop-only null | better / worse / tied | sign p |
|---|---|---|---|---|
| the warped mask (EXP_0017's method) | 0.00443 | 0.00356 | 2 / 2 / 3 | 1.000 |
| **the native mask** | 0.00376 | **0.00240** | 1 / 3 / 3 | 0.625 |

On the native measurement the ordering **reverses**: the fringe renderer is further from the real hem than a clean
cut is. That is the direction EXP_0024 predicted, and it is not the interesting part.

## The interesting part: there was never anything to score

Six of the seven real values are a hard zero — the floor of a statistic that cannot resolve fray at this resolution.
A comparison against a floor does not measure how well a system renders fray; it measures **which system renders less
texture**, and a clean cut renders none. Both EXP_0017's original ordering and its reversal here are that same
artefact seen from two sides.

**EXP_0017 is therefore retracted in full, for the second time and for a better reason.** The first retraction
(review 6) was because its numbers were not in its artefacts. This one is because the experiment has no measurable
quantity on its subjects: at 241–389 px of waistband the real hems are unresolvable, and the number the comparison
used instead was largely made by the registration warp.

## What would make it a real experiment
- an after-photo with ≥600 px of waistband, which is what `CONTRIBUTING_PAIRS.md` already asks for, or
- a hem close-up, which the issue form already asks for and which no contributed pair has yet supplied.

Until one exists, `hem_rough_*` is a diagnostic, not evidence, and every `metrics.json` says so
(`hem_rough_valid_for_fray: false` on the warped measurement).
