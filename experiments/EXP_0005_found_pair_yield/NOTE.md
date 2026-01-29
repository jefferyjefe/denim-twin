# EXP_0005 — Yield of found tutorial pairs through the automatic pipeline

**Date:** 2026-08-29. **Input:** 14 pages found by the seed agent (95 images). **Tools:** validate_pairs.py (CLIP roles) → run_pairs_batch.py → run_pair.py (collage split, sanity gates, auto landmarks, hem fit, v1 fringe, scoring).

## Funnel
| stage | pages |
|---|---|
| found by agent | 14 |
| CLIP says whole-garment before AND after | 5 |
| pass pipeline sanity gates | 2 |
| genuinely usable on inspection | **1** (Thrifted & Taylor'd) |

The one that passes gates but is not usable (b630a78c19) is a legs-only crop of both images: no waistband, no crotch context.
CLIP's "whole garment" tag accepted it and the mask-shape gates cannot tell two touching legs from a garment.
Rejections were correct: cropped photos (garment touching the frame), a price sign, a hem macro, a folded pile.

## Numbers on the usable pair (auto, zero clicks)
sil IoU 0.88 (crop-only 0.87, no-op 0.33) · hem chamfer 10 px (crop 10) · edge ΔE 22.7 (crop 23.0) · fringe IoU 0.35 (no-op 0.01).
Units px; no scale reference.

## Read
- Found tutorial pairs are far noisier than hoped: ~7% yield. The finder now has a mandatory vision check, which should
  raise precision; volume will stay low (small blogs are the only productive source).
- Crowd-sourced pairs with a coin in frame (CONTRIBUTING_PAIRS.md) are the realistic path to tens of usable, scaled pairs.
- Pipeline is now one command per pair and refuses bad inputs with a reason, which is what a routine needs.

## Update after review 2 (cut-invariant landmarks, stricter metrics)
Same usable pair, fully automatic: sil IoU 0.81 (crop-only 0.82, no-op 0.35); hem profile error 16 px (crop 16);
edge ΔE 21.1 (crop 21.3); **fringe IoU 0.07** (no-op 0.00) — the earlier 0.35 was inflated by counting faint
haze as fringe (review finding #2). The honest statement today: the pipeline reproduces the *cut* of a found pair
automatically; its fringe prediction is barely distinguishable from crop-only at this resolution and with an
unfitted appearance model. b630a78c19 still passes gates but is a legs-only crop (known false positive).

## Update 05:50 UTC — pair 15 (Create/Enjoy, 2011 Blogger post), found manually
Whole jeans flat + whole shorts flat (cuffed hem: a cut-geometry pair, no fray). Needed two pipeline fixes to be
accepted: before-photo legs reaching the frame bottom is now a flag, not a rejection; jeans/shorts decided by leg
length vs waist width (spread-invariant) instead of bounding-box aspect.
Result (auto, zero clicks): **sil IoU 0.94** (crop 0.94, no-op 0.42), **hem error 8 px** (crop 9), fringe IoU 0.11 (no fray expected).
Funnel now: 15 found → 6 CLIP-usable → 3 pass gates → **2 genuinely usable** (+1 known legs-only false positive).
