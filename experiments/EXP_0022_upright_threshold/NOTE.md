# EXP_0022 — The tilt correction was switched off exactly where it was needed and reliable

EXP_0021 Part C showed that `canon/autolm.landmarks_from_mask` is not rotation-invariant: on a geometrically exact
silhouette a **5° tilt already moves every shape ratio by more than 5%**, and 8° moves them 18–33%, while the
segmentation mask is still right (IoU 0.994). `run_pair.py` and `predict.py` corrected tilt only **above 8°**. This
asks the two questions that follow: is the tilt estimate good enough to act on at small angles, and does acting on it
change anything on the pairs?

## Part A — the estimator, measured against a known rotation

Rotate an already-correct mask by a known amount and ask each estimator to recover it. No SAM, no photograph, no
confound (`tools/experiment_upright.py`; 16 real masks + 2 synthetic silhouettes × 11 angles).

| estimator | median \|error\| | p90 | >3° | correcting made it worse than doing nothing |
|---|---|---|---|---|
| **principal axis** (the one in use) | **0.00°** | **1.64°** | 13 / 176 | **0 / 176** |
| top-edge line fit (waistband) | 5.94° | 21.48° | 120 / 176 | 135 / 176 |
| flattest-top search | 0.00° | 26.00° | 40 / 176 | 30 / 176 |

The principal axis wins, and the two "physically motivated" alternatives are much worse — the waistband edge is not
straight enough in these photographs, and the flattest-top search locks onto a leg hem when the waistband is short.

Where the principal axis fails is exactly where the physics says it should: a **near-isotropic silhouette**.

| | tilt 0–3° | tilt 5° | tilt 8° | tilt 15° |
|---|---|---|---|---|
| elongation ≥ 1.2 (n=16 each) | max 0.02° | max 0.01° | max 0.13° | max 0.81° |
| elongation < 1.2 — squat shorts (n=16 each) | max **0.41°** | max 2.03° | max **4.67°** | max **10.45°** |

**The 8° deadband was backwards.** It skipped correction in the band where the estimate is accurate to 0.41° and the
measurement error from *not* correcting is already >5%, and it acted in the band where a squat silhouette's principal
axis can be wrong by 5–10°.

## Part B — the A/B on the pairs (the tuning rule's requirement)

Two full batch runs of the same code, `--upright-deadband 8.0` against `0.0`, 7 usable pairs after `exclude.txt`
(`tools/compare_upright_ab.py` → `result.json`). Three pairs are rotated only in the candidate arm (443d1d4658 by
−3.6°, 4bfef03bd7 by 0.5°, e97924ad2d by −1.9°); the other four are untouched and score identically.

| metric | deadband 8° | always upright | better / worse / tied | sign p |
|---|---|---|---|---|
| silhouette IoU | 0.8372 | 0.8365 | 2 / 1 / 4 | 1.000 |
| hem chamfer (px) | 13.35 | 13.31 | 2 / 1 / 4 | 1.000 |
| edge-band ΔE | 18.67 | 18.60 | 1 / 2 / 4 | 1.000 |
| fringe IoU | 0.0570 | **0.0746** | 3 / 0 / 4 | 0.250 |

**This A/B is inconclusive and is not the reason for the change.** Three affected pairs cannot resolve anything; the
fringe-IoU improvement is directionally consistent (it improves on every pair it touches and degrades none) but
p = 0.25. What the A/B establishes is the absence of harm: no metric moves beyond the bench tolerances
(`data/bench/baseline.json`: IoU ±0.03, hem ±5 px, fringe IoU ±0.05), and the largest single-pair loss is 0.009 IoU.

## The change made

`--upright-deadband` defaults to **0.0** in `run_pair.py` and `predict.py` (pass `8.0` to reproduce the old
behaviour). The justification is Part A plus EXP_0021 Part C — a measured defect and a measured-reliable correction —
with Part B as evidence that it costs nothing downstream. A near-isotropic silhouette tilted 5° or more now carries a
flag saying the estimate is unreliable there, because that is the regime the old threshold was quietly acting in.

What this does **not** do is make the measurements *true*: uprighting to "principal axis vertical" is a
canonicalisation, not a measurement of the garment's real orientation. It makes repeated measurements of one garment
agree, which is what Gate 1 asks for, and nothing more.
