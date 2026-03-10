# EXP_0029 — Canonical space does not give the garment back

> **Corrected by EXP_0030.** The measurement below is right: the round trip is off by a median of 10.7 px over the
> garment. The *attribution* is wrong. **No production path uses the canonical→image direction** — `canon/cut2d.apply_cut`
> maps every garment pixel *forward* into canonical space and looks the cut up there, and neither `run_pair.py` nor
> `predict.py` calls `canon_to_image`, `points_to_image` or `image_to_canon` at all. Switching the inverse between
> approximate and corrected changes **zero pixels** of every rendered prediction. What does reach the pipeline is the
> **forward** map folding, which makes two garment pixels land on one canonical coordinate — 40.1% and 37.2% of the
> garment on two of the seven pairs, and those are exactly the two whose region does not survive. Read the section
> below headed "Why it matters here" as a measurement of the `--cut-canon-mask` instrument's own fidelity, not of the
> product path's representation.

`docs/PLAN_PROGRESS.md` has recorded `canon/warp.py` since Phase 1 as **"sub-pixel round-trip; exact per-pixel maps"**.
That is true, and it is true only at the landmarks.

`CanonicalMap` fits **two independent** thin-plate splines from the same correspondences — one image→canonical, one
canonical→image. Two independent fits agree exactly at the points they were fitted to, and nowhere in particular
between them. Everything this project expresses in canonical space is expressed between them: the cut line,
`inseam_fraction`, the parametric template, the wash.

## Image → canonical → image, on the seven usable pairs

| pair | error at the landmarks | median over the garment | p90 | worst | region round-trip IoU |
|---|---|---|---|---|---|
| e97924ad2d | 0.00 px | 0.33 px | 1.2 | 2.6 | 0.980 |
| 443d1d4658 | 0.00 | 1.77 | 4.8 | 14.9 | 0.947 |
| 2691c1a8d0 | 0.00 | 8.53 | 16.5 | 37.6 | 0.638 |
| 8d9f0df4ad | 0.00 | 10.72 | 28.5 | 60.8 | 0.890 |
| 26b1041d00 | 0.00 | 29.38 | 73.0 | 101.5 | 0.441 |
| 4bfef03bd7 | 0.44 | 67.27 | **449.0** | **834.6** | 0.179 |
| 2b0123d732 | 0.13 | 110.85 | 328.2 | 490.7 | **0.074** |

**Median 0.00 px at the landmarks and 10.7 px over the garment**, with a worst case of 835 px. Send the *removed
region* on the same journey and it comes back with a median IoU of **0.638** with itself; on 2b0123d732, **0.074** —
93% of it is gone.

## Why it matters here, and not just as a caveat

EXP_0028 concluded that handing the product path the fitted cut line recovers none of its gap to the evaluation path.
That conclusion inherits this: a 16-sample canonical polyline was the wrong instrument, because canonical space is
where the loss happens. Handing over the **exact canonical region** instead (`predict.py --cut-canon-mask`, an
evaluation instrument) and restricting to the two pairs whose region round-trip is faithful (IoU ≥ 0.90):

| | product path, given the exact cut region | evaluation path |
|---|---|---|
| 443d1d4658, e97924ad2d | **0.8735** | 0.8750 |

On the pairs where canonical space is faithful, the product path *matches* the evaluation path. e97924ad2d reproduces
it exactly — 0.893 against 0.893, hem error 1.3 px against 1.3 px. On the five where it is not, the same instrument
scores 0.348 to 0.792 against 0.807 to 0.899, and 4bfef03bd7's hem error is 509 px.

So the product path's gap is not what the user can say about the cut, and it is not the renderer. **It is that the
representation the cut is expressed in does not survive being used.**

## What is being corrected
- `docs/PLAN_PROGRESS.md`: "sub-pixel round-trip" now says where — at the landmarks — and what happens elsewhere.
- `tests/test_canon.py` measured the round trip at landmark points. `tests/test_canonical_roundtrip.py` measures it
  over the whole garment and over a region, and pins the numbers above as a ceiling so this cannot silently regress
  further.

## What would fix it
One TPS, inverted numerically, instead of two fitted independently — the inverse of a TPS has no closed form, but a
few Newton steps per pixel on the forward map is exact to any tolerance and is a well-understood method. That changes
every canonical coordinate in the project, so it is its own experiment with its own A/B, and it is the most valuable
one on the board: every downstream number is expressed in this space.
