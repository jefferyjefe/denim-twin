# EXP_0003 — First found before/after pair through the full pipeline

**Date:** 2026-08-29. **Pair:** Thrifted & Taylor'd "DIY Denim Shorts" (thrifted Levi's; front panels of the
before/after collages; same wooden hanger in both). Source: data/external/pairs.jsonl, page 4bfef03bd7.
**Scale:** none in the images; **1.33 mm/px is a placeholder** (hanger bar assumed 40 cm) — all mm numbers are provisional.
**Cut input:** the tutorial's cut isn't recorded, so the fabric hem was estimated from the registered after-photo
(row where ≥50% of the leg width is intact fabric) → inseam fraction 0.187. Only the fray is "predicted".

## Pipeline
landmarks (14 before / 6 after, by eye) → SAM masks (0.988 / 0.959) → canonical TPS → flat cut → raw edge ×3 presets
→ register after→before on 6 surviving landmarks → compare.py.

## Result (metrics.md)
| | sil IoU vs real | hem chamfer (mm*) | SSIM kept vs real | ΔE kept | SSIM edge band vs real |
|---|---|---|---|---|---|
| prediction (median) | 0.78 | 30 | 0.20 | 15.2 | 0.21 |
| null: crop-only | 0.78 | 30 | 0.20 | 15.2 | 0.22 |
| null: no-op | 0.44 | 133 | 0.20 | 15.2 | 0.22 |

## What this says (honest)
1. **Cutting works; fray prediction is currently worthless on this pair.** All three presets tie crop-only
   (or lose slightly). Two reasons: (a) at ~1.3 mm/px a 1-px thread is invisible — v0 renders individual threads,
   the real hem is a **~27 mm dense fringe** (hand-pulled then washed) that reads as a texture band;
   (b) presets top out at 11 mm.
2. **The tutorial cut was diagonal** (outer edge higher). `cut_mask_canon_angled` was added, but estimating the
   two heights from the after-photo failed on this pair (legs hang together on the hanger, so canonical leg
   columns don't line up). Estimator needs per-leg image-space hem fitting.
3. **Registration is usable but coarse**: pockets/fly align; SSIM 0.20 and ΔE 15 in the kept region are
   dominated by fine-texture misalignment and lighting differences, not garment changes. The "0.00 px residual"
   is meaningless with 6 landmarks (TPS interpolates exactly) — need held-out landmarks or feature-based residual.
4. **Confounds of found pairs**: added thigh distressing (excluded by nothing yet), hanging not flat, JPEG collage.
5. **Emmy Lou Styles pair is not a pair** (before = stack of many jeans; after = styled flat-lay). Finder needs a
   same-garment check.

## Next
- Raw edge v1: render fray as a density/colour band + coarse thread clumps parameterised by fringe depth
  (5–40 mm) so it registers at found-image resolution; fit depth from after_wash images.
- Per-leg hem estimator in image space (fabric edge + fringe tip per leg → depth + angle).
- Registration residual on held-out landmarks; lighting normalisation (match kept-region colour stats before SSIM).
- Pair finder: add a same-garment sanity check.
