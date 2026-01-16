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

## Update (same day) — raw edge v1 (density band) + fringe-aware metrics
`compare.py` previously never scored the fringe zone (silhouette = keep; edge band on the fabric side only), which is
why v0 presets tied crop-only. Fixed: predicted mask now includes fringe pixels; edge band spans ±15 mm both sides;
new `fringe_iou_vs_real` (predicted fringe pixels vs real garment pixels below the fabric edge).

| system | fringe IoU | edge-band ΔE | edge-band SSIM | sil IoU |
|---|---|---|---|---|
| null: crop-only | 0.000 | 27.5 | 0.164 | 0.782 |
| v0 median / aggressive (threads) | 0.027 / 0.087 | 26.8 / 26.2 | 0.156 / 0.154 | 0.78 |
| **v1 conservative 8 mm** | 0.121 | 26.6 | 0.156 | 0.782 |
| **v1 median 20 mm** | 0.253 | **25.5** | 0.153 | 0.780 |
| **v1 aggressive 35 mm** | **0.286** | 25.9 | 0.147 | 0.775 |
| v1 hand-tuned (30 mm, indigo 0.65) | 0.286 | 27.1 | 0.147 | 0.776 |

Reading: v1 is a measured improvement over v0 and crop-only on fringe coverage and edge colour, monotone in depth.
It plateaus at fringe IoU ≈ 0.29 regardless of depth — the ceiling is **geometric** (the real hem/fringe is angled and
hangs off-axis; my zone follows a flat cut), not appearance. Edge-band SSIM never beats crop-only: SSIM penalises any
texture that isn't pixel-aligned, so it is the wrong metric for a stochastic fringe — keep ΔE + fringe IoU + a
texture-statistics distance instead. Hand-tuning indigo up made ΔE worse: the pair's fringe reads blue in the
photo mostly because of shadow/bundling, not thread colour. One pair; nothing here is a fitted parameter yet.

## Update 2 — per-leg hem fit (image space) + colour-based fabric/fringe split
`canon/hemfit.py`: per column, edge = last *fabric* row (Lab distance to the garment body colour, Otsu), tip = last
garment row; RANSAC line per leg → image-space angled cut; fringe depth = median(tip − edge).
Fitted on this pair: left +11°, right −20° (the tutorial's diagonal), depth 39 / 15 mm* (asymmetric → classifier noise).

| system | sil IoU | chamfer (mm*) | edge-band ΔE | fringe IoU |
|---|---|---|---|---|
| null: crop-only (fitted cut) | 0.792 | 27.4 | 22.4 | 0.000 |
| v1 conservative (½ depth) | 0.805 | 25.7 | 22.0 | 0.301 |
| **v1 median (fitted depth)** | **0.810** | **25.0** | **21.8** | **0.457** |
| v1 aggressive (1.5× depth) | 0.807 | 25.4 | 21.8 | 0.474 |
| (previous flat cut, v1 median) | 0.780 | 29.9 | 25.5 | 0.253 |

Fringe IoU 0.25 → 0.46 from geometry alone (angled cut + correct depth); appearance unchanged. This is the ceiling
lift EXP_0003 predicted. Caveat: depth/angle were *estimated from the after-photo* — this is a fit of the cut input,
which a user would supply; the fringe appearance is still the only genuinely predicted quantity, and depth is here
taken from the same image (so depth is not a prediction on this pair either — it becomes one when fitted across
pairs and applied to held-out garments).
