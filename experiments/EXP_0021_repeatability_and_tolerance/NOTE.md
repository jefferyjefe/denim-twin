# EXP_0021 — Repeatability: the blocker moves from "we cannot segment" to "our measurements are frame-dependent"

Gate 1 asks for *repeated captures of the same garment that align consistently, with measurements reproducible within
tolerance*. EXP_0018 recorded it FAILED and named the cause: the only two photographs of one garment in the dataset
returned waist widths of 874 px and 191 px, because SAM segmented a back pocket at score 0.906. EXP_0019 showed
consensus segmentation returns the whole garment on that file but left it opt-in and unmeasured on repeatability.

Three parts, all reproducible from the artefacts: `tools/experiment_same_garment.py`, `tools/experiment_repeatability.py`,
`tools/experiment_landmark_rotation.py` → `reports/repeatability/`.

## Part A — the one same-garment pair, re-measured (n = 1 garment)

| statistic (front vs back view) | best-score | consensus |
|---|---|---|
| waist width | 874 px vs **191 px** (4.58x) | 874 px vs 953 px |
| rise / waist | 0.660 vs **1.424** (2.16x) | 0.660 vs 0.714 (**1.081x**) |
| height / waist | 0.819 vs 1.440 | 0.819 vs 0.871 (1.063x) |
| hip / waist | 1.197 vs 1.728 | 1.197 vs 1.226 (1.024x) |
| hem roughness p90 | 5.0 px vs **0.0 px** | 5.0 px vs 5.0 px |

The two methods return the *same* mask on the front view (IoU 1.000) and disagree completely on the back view
(IoU 0.110): best-score takes the pocket, consensus takes the garment. EXP_0018's failure is a segmentation failure
and it is fixed.

**This does not establish a tolerance.** A front view and a back view are not the same measurement — the back rise of
real trousers is longer than the front, pockets change the outline, and the two frames differ in distance and light.
The 8% rise/waist difference is an upper bound on measurement error *conflated with a real difference*, from n = 1
garment. Agreement here is necessary, not sufficient.

## Part B — 16 photos x 15 runs x 2 methods = 480 segmentations under simulated re-capture

The same photograph re-framed, re-exposed, re-compressed. Masks are compared after undoing the known transform, and
only inside the region that came from real pixels (`tests/test_repeatability_harness.py` drives the harness with a
synthetic perfect segmenter and requires IoU > 0.999, so the numbers below measure the segmenter, not the bookkeeping).

| family (n per method) | best-score | consensus |
|---|---|---|
| photometric — jpeg 40/15, ±20% exposure, warm white balance, blur (96) | **16 runs below IoU 0.8**, 4 below 0.5 | **0** below 0.8 |
| geometric — rot ±3°/+8°, zoom 0.85/1.15, 4% shift (96) | 25 below 0.8, 11 below 0.5 | 6 below 0.8, 2 below 0.5, **9 refusals** |
| combined re-capture (32) | 7 below 0.8 | 3 below 0.8, 1 refusal |
| **total (224 runs)** | **48 below 0.8, 17 below 0.5, 0 refusals** | **9 below 0.8, 3 below 0.5, 10 refusals** |

Under the photometric family the garment does not move at all: a JPEG re-encode or a 20% exposure change is enough to
make best-score SAM return a **different object** on 16 of 96 tries. Consensus never does. Median IoU per perturbation
for consensus is 0.990–0.999 — the mask is not merely stable, it is the same mask.

Consensus fails differently: it **refuses**. That is the better failure, and it is honest about it, but 7 of its 10
refusals are one perturbation — `zoom1.15` — and the cause is not disagreement at all. Six of those garments already
cover 0.57–0.72 of the frame; a 1.15x zoom takes them past the hard **75% area ceiling** and every candidate is
discarded before the vote. The refusal message said "prompt sets disagree", which is exactly wrong: the prompts agreed.
Fixed here — a refusal now names the filter that caused it (`tests/test_seg_consensus.py`), which matters because the
user's corrective action is "step back", not "re-shoot on a different background".

### What the measurements do under the same perturbations (consensus, median over 16 photos)
| perturbation | rise/waist | height/waist | hem roughness p90 | mask IoU |
|---|---|---|---|---|
| jpeg 40 | 0.2% | 0.2% | 16.3% | 0.997 |
| jpeg 15 | 0.4% | 0.3% | **79.9%** | 0.992 |
| exposure ±20%, white balance | ≤0.3% | ≤0.1% | 10–28% | 0.999 |
| blur | 0.2% | 0.2% | 39.7% | 0.998 |
| rot ±3° | 1.1–2.0% | 0.9–1.1% | 21–40% | 0.995 |
| **rot +8°** | **29.6%** | **32.1%** | 44.0% | 0.994 |
| zoom 0.85 / 1.15, 4% shift | 1.2–1.8% | ≤0.6% | 29–48% | 0.990–0.992 |
| combined re-captures | 2.1 / 6.8% | 3.3 / 10.2% | 39 / 80% | 0.991–0.992 |

Two results, and they point at different layers:

1. **Shape ratios are reproducible to ~1–2% under everything except tilt.** At 8° they move 30%, while the mask IoU is
   still 0.994. Segmentation is not the cause — see Part C.
2. **Hem roughness is not reproducible at all.** Re-encoding the same photograph at JPEG 15 changes it by 80% of its
   own value; nothing in the scene moved. The fray *verdict* (p90 > 0) is unstable on **6 of 16 photos**, and
   **2 of the 9 high-resolution finished-hem controls read "frayed" under at least one perturbation** (7b0a1ceaaf,
   dbde5e4083 — the same two photos EXP_0016's addendum caught under best-score segmentation). EXP_0016's headline
   "0 false positives on 9 controls" is a statement about one photograph each; it does not survive a re-encode.

**This is a simulated re-capture and it bounds repeatability from above.** It cannot move the fabric, change the
drape, or move the light. A real second photograph will be worse than every number here.

## Part C — the tilt sensitivity is in the landmarks, not the mask

Rotate a mask that is already correct. No SAM, no photograph, no confound (`experiment_landmark_rotation.py`).
`canon/autolm.landmarks_from_mask` measures axis-aligned extents — leftmost/rightmost pixel in a horizontal band, the
lowest pixel in a column — and those are not rotation-invariant.

| subject | first tilt where a ratio moves >5% | deviation at 8° |
|---|---|---|
| synthetic exact silhouette (shorts) | **5°** | 33% (rise/waist) |
| synthetic exact silhouette (jeans) | 8° | 18% |
| 16 real masks, rise/waist | median **8°**, and **6 of 16 at ≤5°** (one at 1°) | median 7.9%, max 51.8% |

`tools/predict.py` and `tools/run_pair.py` only rotate a photo upright when the estimated tilt is **≥ 8°** — at or
above the angle where a third of the subjects have already lost more than 5%, and the two synthetic silhouettes lose
18–33%. The threshold is on the wrong side of the effect. It is left unchanged in this commit: changing it alters
every rendered output and every bench number, so it belongs in its own A/B (`docs/GATES.md` tuning rule), and the
measured invariance above is now the test that A/B has to satisfy.

> **Superseded by EXP_0022** (same day): the A/B was run, the deadband is now 0.0, and the invariance above is pinned
> by `tests/test_upright.py`. EXP_0022 also measured the estimator itself — accurate to 0.41° in the band the deadband
> was skipping, and unreliable (up to 10.5°) in the large-tilt, near-isotropic band it was acting in.

## Gate 1

Still **not met**, and for a different reason than in EXP_0018 — which is the progress:

- object identity under re-capture is **solved for the photometric family and near-solved for the geometric one**
  (0 and 6 failures in 96 with consensus, against 16 and 25 with best-score);
- what fails now is the **measurement layer**: shape ratios lose >5% at 1–8° of camera tilt, and the fray verdict
  flips on a JPEG re-encode;
- and the tolerance itself is still unmeasured, because a simulated re-capture is not a re-capture. **Two photographs
  of one garment, taken twice with the phone picked up in between, would settle it** — that remains the ask in
  `CONTRIBUTING_PAIRS.md`.

## What changed in the code
- `tools/predict.py` gained `--seg consensus`: the product path could not use the segmentation that fixes
  catastrophic object-identity failures. Every prediction now records which segmentation produced it, and the default
  (`coarse`) carries a flag saying SAM's score does not detect a wrong object.
- consensus refusals name the filter that dropped the candidates (area ceiling / floor / frame border).
- `seg/validate.segment_garment_consensus` had a declared parameter, `agreement_slack`, that the body never read.
  `tests/test_no_dead_parameters.py` now walks the package and fails on any such parameter; it found four more,
  including `hem_chamfer(band_px=40)` — `tools/compare.py` computed a 15 mm band and passed it positionally for
  nothing on every pair report ever produced. All five removed.
