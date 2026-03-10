# EXP_0030 — The inverse is fixed, nothing uses it, and the thing that does matter is the fold

EXP_0029 found the image → canonical → image round trip off by a median of 10.7 px over the garment and concluded
that the product path's gap to the evaluation path "is that the representation the cut is expressed in does not
survive being used". **That conclusion is wrong, and this note corrects it.** The measurement was right; the
attribution was not.

## The fix, which works

`CanonicalMap(exact=True)` — now the default — stops trusting the second, independently fitted TPS as the
canonical→image map and refines it against the forward map, which is the one that is actually defined. Per-point
backtracking, because without it the iteration **diverges** exactly where the two fits disagree most: on two real
pairs it ran to 9.5 million pixels before the line search went in.

| | before | after |
|---|---|---|
| point round trip, median over the garment | 10.7 px | **0.02 px** |
| region round trip, median IoU with itself | 0.638 | **0.972** |
| pairs whose region survives (IoU ≥ 0.90) | 2 of 7 | **5 of 7** |

## And nothing in the pipeline uses it

Grep every caller of the canonical→image direction (`canon_to_image`, `points_to_image`) and of the raster warp that
samples through it (`image_to_canon`): `tools/run_baseline.py`, which writes a canonical visualisation, the
measurement tools written for EXP_0029/0030, and tests. **Neither `run_pair.py` nor `predict.py` is on that list.**

`canon/cut2d.apply_cut` maps every garment pixel *forward* into canonical space and looks the cut up there. It never
asks where a canonical point came from. So:

- the evaluation-path A/B is identical on all 7 pairs, and
- the product-path A/B is identical to the **pixel** on all 5 it can score — `--canonical-inverse approx` against
  `exact`, 0 differing pixels in every rendered prediction, with the flag verifiably recorded as False and True in
  the respective `prediction.json`s.

The fix is correct and free, and it is invisible to the thing EXP_0029 blamed it for. What EXP_0029's `--cut-canon-mask`
instrument actually measured is its own fidelity: it builds the cut region by warping a raster into canonical space,
which *does* go through the inverse. Where that instrument was faithful the product path matched the evaluation path
(0.8735 against 0.8750) — a real and useful result, but it says the product path renders a given cut correctly, not
that its representation is lossy.

## What does reach the pipeline: the forward map folds

A thin-plate spline through landmarks is not guaranteed to be injective. Where the **forward** map folds, two garment
pixels land on the same canonical coordinate, and `apply_cut`'s lookup answers for one of them — so the fold hits the
product path directly, inverse or no inverse. `CanonicalMap.fold_fraction` measures it by the sign of the Jacobian
determinant:

| pairs | fraction of the garment where the map folds | region round trip |
|---|---|---|
| 2691c1a8d0, 443d1d4658, 8d9f0df4ad, e97924ad2d | 0.0% | 0.967 – 1.000 |
| 26b1041d00 | 3.1% | 0.972 |
| **4bfef03bd7** | **37.2%** | 0.178 |
| **2b0123d732** | **40.1%** | 0.077 |

The two that fold are exactly the two whose region does not survive, and correcting the inverse does not help them,
because there is no inverse to find.

## The product change, stated plainly

`predict.py` now **refuses** a garment whose canonical map folds over more than 20% of it, with a reason the user can
act on — "the landmarks are wrong: usually a garment photographed folded, at a steep angle, or with the legs crossed;
re-shoot it laid flat and square to the camera" — flags above 2%, and records `canonical_map.fold_fraction` in every
prediction. On the found-pair set that is **2 of 7 garments refused outright**.

That is the honest behaviour and it is also a real reduction in what the product accepts. It is why the A/B above
scores 5 pairs and not 7, and why its evaluation-path baseline reads 0.8685 rather than the 0.8566 of the 7-pair set:
the two refused garments are the two hardest ones. **Numbers from this A/B are not comparable with EXP_0027/0028's
seven-pair means**, and the mistake of comparing them was made once here before it was caught.

## What is still open
The fold is a property of the landmark set, not of the garment. A garment photographed flat and square does not fold;
these two are a folded before-photo and a pair shot at an angle. Whether the fix is better landmarks, a regularised
TPS constrained to stay injective, or a different representation for such garments is the next question — and it is
now a well-posed one, with a detector that says which garments have the problem.
