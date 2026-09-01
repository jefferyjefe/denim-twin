# EXP_0005 — Yield of found tutorial pairs through the automatic pipeline

**Date:** 2026-02-16. **Input:** 14 pages found by the seed agent (95 images). **Tools:** validate_pairs.py (CLIP roles) → run_pairs_batch.py → run_pair.py (collage split, sanity gates, auto landmarks, hem fit, v1 fringe, scoring).

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

## Update 06:10 UTC — second finder run (+8 vetted pages, 23 total)
Funnel: 23 found → 12 CLIP-usable → 5 pass gates → **3–4 genuinely usable** (Thrifted & Taylor'd fray pair; Create/Enjoy;
Create Kids Couture on a 1-inch grid mat, sil IoU 0.92 / hem 15 px; Under Peach Trees pending). Two new mechanisms were
needed and are principled, not tuning: per-image **manual crop boxes** in the manifest (second object in frame — the
dominant failure) and **upright normalisation** (PCA rotation before landmarks). Excluded with reasons: Mr Kate (tiny
collage tile), mom-jeans (ruler across the leg; would need a mask prompt), 51likes (overlapping shorts).
Fringe prior: n=3 usable geometry pairs, still < 5.

## Close-out 06:20 UTC
Final for today: **3 usable pairs** of 23 found (13%): 4bfef03bd7 (fray), 8d9f0df4ad (cut), 443d1d4658 (cut, grid mat).
Excluded with reasons in data/priors/exclude.txt: b630 (legs crop), 3082 (collage tile), 963f (ruler across leg),
f9c0 (overlapping shorts), d52a (diagonal on patterned rug). Rule reminder: today's pipeline changes were principled
(crop boxes, upright normalisation, denim-colour prior, crop-aware gates) but they were each triggered by one image;
they stand only if the next batch of pairs does not regress. `tools/report_pairs.py` is the arbiter.

## Update 06:35 UTC — third finder run (+6 pages, 29 total)
Funnel: 29 found → 17 CLIP-usable → 6 pass gates → 4 meet the prior's quality bar (sil IoU ≥ 0.75, hem ≤ 40 px):
4bfef03bd7 (fray), 8d9f0df4ad, 443d1d4658 (metric, grid mat), 26b1041d00 (Sewing Novice; a bermuda→shorter cut, flagged).
Two more ran but fail the bar (Bastelfrau 0.70; niftythrifty after-wash on a rug, hem err 113). Pipeline changes this
round: shorts threshold 0.6× waist width (toddler jeans have legs ≈1.5×), short 'before' garments allowed with a flag,
grid-mat scale detector (Kids Couture is the first metric pair, ~0.95 mm/px), backdrop-only inpainting of the removed
region, judge sets use the un-warped real photo. Fringe prior n=4 — one short of the threshold; only 2 of the 4 are
real fray pairs, which is what the prior actually needs.

## Update 06:55 UTC — fourth finder run (after-wash focus): +2 pages (31 total)
~45 pages screened in 9 languages → 1 genuine fray-after-wash sequence (Prudence & Austere: flat before → flat cut →
flat after one washer/dryer cycle) + 1 cut-only (Doodlecraft, sil IoU 0.90, hem 7 px). Finder's conclusion: search
results are saturated by the same ~10 large sites; almost nobody photographs the washed result flat. Found-pair
channel is effectively exhausted at **5 usable cut pairs + 2 fray sequences**. Next channel = contributions.
Prudence & Austere on inspection: after-wash shorts are cuffed once and knife-slashed — a distressing sample, not a
raw fringe hem; excluded from the fringe prior. Final fray pairs from the found channel: 1 (Thrifted & Taylor'd).

## Update 07:35 UTC — Wayback channel (1 run): +1 cut pair (Adventures in Dressmaking 2010, cuffed), 32 pages total
Verdict from the run: not worth continuing — wildcard CDX queries time out, archived Blogger images are 640 px inline
sizes, CDN step images were never archived, ~1 usable pair per 50 calls. The found-pair channel is closed at
**6 cut pairs + 1 fray pair**. Everything downstream now waits on contributed after-wash pairs.

## Contributor loop verified 07:50 UTC
A test issue (#1, closed) through the GitHub form → `ingest_submissions.py` (form parsing, `_No response_`, consent box,
pasted links) → fetch → CLIP validation → batch: end to end OK. Coin scale did not trigger (no coin in the test photos —
correct). The record is excluded from priors (two different garments). The channel is live: a real contributor pair
with a coin in frame would be scored and enter the prior automatically on the next daily run.
