# EXP_0027 — The product path, recomputed: it is a dead heat with cropping the photograph

EXP_0014 answered "how much of our cut accuracy comes from looking at the answer?" and published mean silhouette IoU
0.768 for the product path against 0.819 for the evaluation path and 0.771 for the crop-only null, **over 11 pairs**.
Two things have changed since: the tilt correction was fixed (EXP_0022/0023), and — the reason this is a correction
rather than an update — **four of those eleven pairs are banned by `data/priors/exclude.txt`** and were scored anyway.
`tools/score_predict.py` never read that file. It is the third experiment in this repo caught doing it.

## Recomputed on the seven pairs `exclude.txt` allows

| condition | mean silhouette IoU | mean hem error |
|---|---|---|
| evaluation path (reads the real after-photo) | **0.857** | **7.8 px** |
| product path (one photo + a cut height, canonically defined) | 0.803 | 32.2 px |
| crop-only null, on the product path's own mask | 0.803 | — |

| pair | product | evaluation | crop-only |
|---|---|---|---|
| 2691c1a8d0 | 0.719 | 0.736 | 0.719 |
| 26b1041d00 | 0.877 | 0.899 | 0.877 |
| 2b0123d732 | 0.647 | 0.847 | 0.648 |
| 443d1d4658 | 0.850 | 0.857 | 0.850 |
| 4bfef03bd7 | 0.798 | 0.807 | 0.799 |
| 8d9f0df4ad | 0.881 | 0.958 | 0.881 |
| e97924ad2d | 0.845 | 0.893 | 0.844 |

## What this says

**The product path scores 0.8026 against the null's 0.8026.** It beats the null on 2 pairs and loses on 4, by
thousandths either way. On silhouette IoU — the metric the README leads with — *what a user gets is
indistinguishable from cropping their photograph at the same height*. That was already true in EXP_0014 (0.768
against 0.771, i.e. marginally worse than the null); the correction does not change the conclusion, it sharpens it.

This is not a surprise, and it is not a bug. Silhouette IoU is dominated by the kept region, which both systems copy
pixel-for-pixel, and the only thing the renderer adds below the cut is a few pixels of fringe. It is the wrong metric
for the thing the product actually does. It is, however, the number that has been quoted as the headline.

**The evaluation path did improve**, and by a lot: 0.819 → 0.857 IoU and 48.4 → 7.8 px of hem error. Most of that is
the tilt fix (EXP_0023) and the rest is no longer scoring pairs that were banned for having two garments in the
photograph.

## What follows
- The README's headline numbers are corrected to these.
- The gap that matters is the 0.857 vs 0.803 between reading the after-photo and predicting without it — 54 IoU
  points and 24 px of hem, entirely attributable to fitting the cut line to the real garment. That is the actual
  research problem, and it is bigger than any appearance work downstream of it.
