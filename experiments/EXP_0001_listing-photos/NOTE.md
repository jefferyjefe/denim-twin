# EXP_0001 — Can marketplace / retail listing photos feed the pipeline?

**Date:** 2026-01-07  **Code:** commit after "Manual landmark annotator"  **Data:** 1 Levi's retail photo set, 1 Grailed used listing

## Hypothesis
Listing photos (new retail + second-hand) are usable as (a) pipeline test inputs and (b) pretraining data for segmentation/landmarks.

## Setup
- Retail: levi.com 501 medium wash, product images pulled from the Scene7 CDN (site itself returns 403 to fetchers).
- Used: Grailed listing 24793141 (501, 31x34, 100% cotton, $75, seller measurements in text). eBay item pages returned a 1.8 KB bot-block; Grailed HTML fetched with a browser UA; one listing photo.
- Ran `check_capture.py --no-board`, then hand-estimated 14 landmarks on the Grailed photo and ran `run_baseline.py --inseam-frac 0.35`.

## Result
- Retail photos: on-model, standing, legs occluded by hands/shoes, perspective. Crotch/inseam/hem not cleanly visible. **Not usable** for flat-lay canonicalization; only as appearance priors.
- Grailed photo: seller cutout on pure white, flat-lay, front, 2000×2000, EXIF stripped. All 14 landmarks visible. Baseline: 1.26M of 2.05M garment px removed, `changed_outside_cut = 0.0`. Canonical warp and cut are visually correct (see used_panel.jpg).
- Bugs surfaced: (1) capture checker flags pure-white cutout backgrounds as "clipping" — rule needs a cutout exemption or a garment-only exposure stat; (2) GrabCut seeded from the landmark convex hull filled the between-leg gap — fixed to use the outline polygon.
- No metric scale (no fiducial, no EXIF), so cut position can only be expressed as inseam fraction, not cm — unless seller measurements are trusted.

## Interpretation
Second-hand flat-lay listings are **genuinely useful as pretraining/prior data** for segmentation + landmarks and as pipeline smoke tests; sellers often provide measurements and composition in text. They are **not** a substitute for paired before/after captures with a fiducial. Retail on-model photos add little. Access is the practical blocker: eBay and levi.com block fetchers; Grailed serves HTML but ToS still applies — use official APIs or DeepFashion2 for any volume.

## Next action
Fix checker cutout handling; test the same flow on the first real rig photo with the ChArUco board to get cm-scale cut placement.
