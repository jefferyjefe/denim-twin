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
