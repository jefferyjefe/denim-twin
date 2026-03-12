# EXP_0033 — How well can this bench measure anything? (and a wrong answer I nearly published)

Every number this project reports is a comparison against `real_mask.png`: the real after-photo's garment mask
warped into the before frame by `register.warp_after_to_before`. Three consecutive canonical-layer fixes
(EXP_0029, 0030, 0031) were each correct and each changed **zero pixels** of the pair scores. The product path
sits at 0.823 against a crop-only null at 0.823. Before hunting for a fourth fix, the question worth asking is
whether the ruler can read the difference at all.

Nobody had measured the map that makes the ruler.

## The registration TPS does not fold

`warp_after_to_before` fits its own thin-plate spline, before-coords → after-coords, **directly** — not through
canonical space (`register.py:26`). A TPS has no injectivity guarantee here either, and a fold would mean two
before-pixels sampling one after-pixel: duplicated garment in the ground truth itself.

It never folds. **0.0000 on all 7 scored pairs**, with **0** of them over 20%. The reason is structural: only six landmarks
survive a cut garment (`waist_left/center/right`, `hip_left/right`, `crotch`) — auto knees are dropped as
meaningless on a cut garment — and six well-separated upper-garment points give a near-affine spline with nothing
to tear. The canonical map folds because it is asked to bend 10–14 landmarks onto a fixed template; this one is
not asked to bend at all.

## But its landmarks miss badly

The leave-one-out residual — refit without a landmark, then predict it — is **7.9 to 76.8 px, median 27.9 px**
across the seven pairs. On garments a few hundred pixels tall that is several percent of the garment. The ground
truth is not a fixed mask. It is a mask with an error bar.

## Resampling that error bar

Perturb each before-frame landmark by its *own* held-out error, random direction, refit, re-warp the real mask,
rescore the same unchanged prediction. Null control first: at `--scale 0` every pair reproduces its baseline IoU
with **SD 0.0000**, so the harness adds no noise of its own.

| perturbation | median per-pair IoU SD | SD of the bench mean |
|---|---|---|
| quarter scale | 0.0169 | **0.0106** |
| half scale | 0.0378 | 0.0180 |
| full scale | 0.0688 | **0.0298** |

Leave-one-out overstates the fitted map's error (the fitted map sees all six landmarks), so full scale is an upper
bound and quarter scale a conservative floor.

## The wrong conclusion

The obvious reading: a single bench number is uncertain to ±0.03, the product-vs-crop difference is 0.0001, so the
bench is 100–300× too blunt to resolve what it is being asked to resolve, and the whole product-path line is
unfalsifiable at this sample size.

**That is wrong, and it is wrong in a way worth recording.** The two methods are scored against the *same* ground
truth. The registration error is common to both and cancels in the difference. An unpaired spread is not the error
bar on a paired comparison.

## The paired test

Perturb the ground truth once per draw; rescore **both** the product prediction and the crop-only null against
that same perturbed truth; take the difference.

| | SD of the bench difference |
|---|---|
| unpaired (wrong) | 0.03041 |
| **paired (correct)** | **0.00023** |

Pairing cancels **132×** of the registration noise. So:

**product − crop-only = -0.00010 ± 0.00023.**

The bench is not blunt. It resolves method differences to about 0.0005 at 2σ — and against that ruler, the product
path being no better than cropping is a **real, precisely measured null**, not a measurement floor. Every pair
individually agrees: the largest per-pair difference is 0.00066, and four of seven favour the null.

This kills the hypothesis that better registration would reveal a hidden product-path advantage. There is nothing
hiding under 0.0002. The product path does not beat cropping because it does not differ from cropping — on these
seven garments its predicted mask and the crop-only mask are near-identical objects, which is a statement about
the prediction, not about the measurement.

What the ±0.03 figure *does* bound is any claim about a **single** pair's absolute IoU, or any comparison between
runs registered from different landmark sets. Those need the unpaired number.

## Files

- `tools/experiment_registration_fold.py`, `reports/registration_fold.json`
- `tools/experiment_groundtruth_uncertainty.py` (`--scale 0` is the null control),
  `reports/groundtruth_uncertainty.json`, `reports/groundtruth_uncertainty_quarter.json`
- `tools/experiment_paired_uncertainty.py`, `reports/paired_uncertainty.json`
- `tests/test_registration_uncertainty.py`
