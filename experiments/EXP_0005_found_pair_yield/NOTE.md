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
