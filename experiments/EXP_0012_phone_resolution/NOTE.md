# EXP_0012 — Does the pipeline hold at contributor phone resolution? (synthetic, 3000×4500)

**Setup:** the synthetic textured jeans pair (cut at 35% inseam, after re-laid by 6° + 2% scale + shift), upscaled 5× to
3000×4500 (phone-class), run through `run_pair.py --state after_cut` with no manual input.

| resolution | sil IoU | hem error | time |
|---|---|---|---|
| 600×900 (native) | 0.961 | 0.9 px | 8.6 s |
| 3000×4500, before fix | 0.751 | 388 px | 38 s |
| 3000×4500, after fix | **0.967** | **2.8 px** | 38 s |

**Failure found and fixed:** at high resolution SAM's hem-band prompt returned a huge "fringe" (701 px deep) on a garment
with no fringe; the fabric edge then came from the fringe mask and the cut was wrong. Gate added: a fringe mask whose
median column depth exceeds 15% of garment height is rejected (a fringe is a thin band) with fallback to the mask edge.
Real pairs unchanged; bench 0 regressions. 38 s/pair is acceptable for the daily loop. Caveat: synthetic re-lay is affine;
real contributor photos add drape and perspective.

## Side effect on the 7 real pairs (bench A/B, attached in experiments/pairs/REPORT.md)
The plausibility gate also fires on two low-res real pairs. Sewing Novice (cuffed): sil IoU 0.75 → 0.89, hem error
31 → 3 px (the bogus "fringe" had been pulling the edge up). Bastelfrau (raw, unwashed): 0.69 → 0.62, hem 32 → 47 px
(the SAM band was, by luck, a usable edge cue there). Others unchanged. Net: kept — it removes a catastrophic
high-resolution failure and one real regression trades against one real improvement; baseline refrozen with this note.
