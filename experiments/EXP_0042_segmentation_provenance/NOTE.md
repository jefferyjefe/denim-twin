# EXP_0042 — The before photograph is segmented twice, and matching the two is worth +0.03 IoU

`run_pair.py` segments the before photo coarsely, derives landmarks from that mask, and then — only
if `autolm` found **≥ 14** landmarks — re-segments with those landmarks as prompts, keeps the
**refined** mask, and keeps the **coarse** landmarks. So registration fits landmarks describing one
segmentation while the cut, the prediction and the scoring all use another.

EXP_0041 found this while looking for something else, and measured that the two disagree by up to
45 px. This is the experiment: what the second segmentation actually does, and what matching the two
is worth on the bench.

## The gate first, because it is the denominator

Refinement is not applied to every pair. It runs only above 14 landmarks, and two of the seven
scored pairs are under it:

| pair | 2691c1a8d0 | 26b1041d00 | 2b0123d732 | 443d1d4658 | 4bfef03bd7 | 8d9f0df4ad | e97924ad2d |
|---|---|---|---|---|---|---|---|
| landmarks | **12** | **10** | 14 | 14 | 14 | 14 | 14 |
| refined | no | no | yes | yes | yes | yes | yes |

The first draft of this note reported "identical on 2 of 7" as evidence that refinement is nearly a
no-op. It is not evidence of that: nothing re-segmented those two. The denominator is **5**, and the
two untreated pairs are bit-identical *by construction* — which makes them a useful control and a
misleading average.

## What the second segmentation does

On the five treated pairs, reconstructing the coarse mask (`segment_garment_coarse` on
`before_native.png`, uprighted the same way) and comparing:

| | |
|---|---|
| IoU(coarse, refined), median / min | 0.9878 / **0.7857** |
| area ratio refined/coarse, range | **1.0014 – 1.1161** |
| pairs where refinement **shrank** the mask | **0 of 5** |
| shift in the row `autolm` anchors landmarks on | −4, −1, **−31**, −2, 0 px |
| largest landmark displacement (both coordinates) | 28, 2, **45**, 3, 2 px |

**Refinement never shrinks the mask.** That one-sidedness is the mechanism, and the first draft of
this experiment did not report it: the coarse landmarks are anchored on a systematically *smaller*
silhouette than everything downstream uses, so they sit low and inside. The anchor row moves up by
as much as 31 px, and the landmarks with it.

## The A/B

Both arms through the real pipeline — `run_pairs_batch.py`, same code, one env var apart — and
scored by the bench's own metric.

| | control | refit | Δ (treated only) | σ | better / worse / tied |
|---|---|---|---|---|---|
| silhouette IoU | 0.8606 | **0.8832** | **+0.0316** | 1.42 | 4 / 1 / 2 |
| hem chamfer (px) | 5.7026 | 5.8107 | +0.1513 | 1.32 | 1 / 4 / 2 |

Per pair, silhouette IoU:

| pair | control | refit | Δ |
|---|---|---|---|
| 2691c1a8d0 | 0.7328 | 0.7328 | **0.0000** |
| 26b1041d00 | 0.8993 | 0.8993 | **0.0000** |
| 2b0123d732 | 0.8378 | 0.8753 | +0.0375 |
| 443d1d4658 | 0.8984 | 0.8962 | −0.0022 |
| 4bfef03bd7 | 0.8065 | **0.9223** | **+0.1157** |
| 8d9f0df4ad | 0.9563 | 0.9566 | +0.0003 |
| e97924ad2d | 0.8929 | 0.8996 | +0.0067 |

**The two exact ties are exactly the two pairs the refinement gate skips.** Not approximately —
bit-identical, and the report asserts the set equality rather than leaving it to the eye. Where the
two segmentations are the same object, the two arms are the same run. That is the mechanism check
this result rests on, and it is stronger than the 1.42σ.

The two largest gains are the two pairs with a material disagreement: `4bfef03bd7` (45 px landmark
displacement, 31 px anchor shift) and `2b0123d732` (28 px, area ×1.116). The effect tracks the size
of the defect across pairs, which a coincidence would not.

`4bfef03bd7` is worth naming. It is the pair EXP_0040 built its account on — band-0 IoU 0.138, "the
registered garment starts 28 rows lower and is 17% wider" — and the pair whose provenance gap
EXP_0041 showed had carried EXP_0040's headline sign test. Matching the segmentations moves it
**0.8065 → 0.9223**. Its anomaly was, in large part, this.

## Not adopted, and what would settle it

`--refit-landmarks-after-refine` exists on `run_pair.py`, **off by default**, with this report
attached. The evidence favours turning it on and does not establish it:

- **For:** a directly measured, one-sided defect; a mechanism confirmed by two exact ties and a
  dose-response across the other five; +0.0316 IoU, the largest single-pair gain in this project
  since uprighting.
- **Against:** 1.42σ at n=5 is not significance, and the hem gets **worse** — +0.15 px, on 4 of the
  5 treated pairs. `docs/GATES.md`'s precedent (EXP_0022) allows a change to rest on a measured
  defect plus *the absence of any regression*, and there is a regression here, small as it is.

What would settle it: more pairs, or an account of why matching the segmentations should cost hem
accuracy at all. The hem is fitted on the before mask, which neither arm changes — so the cost has
to come through the landmarks, and that is checkable.

## Two things found on the way

- **The reason for the current behaviour is not recoverable.** `run_pair.py` cites EXP_0004 for
  "recomputing them on the refined mask regressed pair1". `experiments/EXP_0004_auto_pipeline_pair1/NOTE.md`
  does not contain that claim, mentions neither refinement nor recomputed landmarks, and its pair
  was a file under `/private/tmp` that no longer exists. The behaviour may well have been right when
  it was chosen; nothing in the repository says why.
- **Nothing records which segmentation a landmark came from.** `landmarks.json` now writes
  `before_landmark_source` and the coarse set beside the used one, so a pair directory can answer
  the question that took a full re-segmentation to answer here.

## What this note does not claim

The first version of this experiment had four measurements that could not support what they were
asked to. They are removed rather than caveated, and named here so the next person does not rebuild
them:

- a landmark-to-mask-boundary "fit" metric — minimised by matching provenance in *either*
  direction, so an arm that recomputed nothing reproduced 97% of the "improvement" (r = 0.99);
- a leave-one-out registration residual compared *across* arms whose evaluated landmarks move — the
  same confound EXP_0041 built `loo_common` to avoid, and not fixable here: a common evaluated set
  exists on only 1 of the 5 treated pairs;
- a third "coarse-consistent" arm, which is the production arm for every statistic that does not
  read the mask, and so returned a tautological zero;
- an anchor-shift diagnostic read off the raw mask instead of `top_edge_row(clean_mask(·))`, which
  pointed at the wrong pair (+55 px on a garment whose anchor moved 4 px).

The reconstruction is checked on **points**: `landmarks_from_mask` on the reconstructed coarse mask
reproduces `before_lm.json` exactly on 7 of 7 pairs, and on the 2 untreated pairs the mask itself is
bit-identical to `bmask.png`. On the 5 treated pairs the mask has no independent check.

## Files

- `tools/experiment_segmentation_provenance.py`, `reports/segmentation_provenance.json`
- `tools/run_pair.py --refit-landmarks-after-refine`, `PAIRS_REFIT_LM=1` for the batch
- A/B arms: `experiments/pairs_lmprov_control`, `experiments/pairs_lmprov_refit` (gitignored;
  regenerate with `PAIRS_OUT=<dir> [PAIRS_REFIT_LM=1] tools/run_pairs_batch.py`)
- `tests/test_segmentation_provenance.py`
