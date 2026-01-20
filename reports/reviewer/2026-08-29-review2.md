# Review 2 (local adversarial agent) — 12 findings, all fixed same day; reviewer tests adopted as tests/test_review2_*.py

| # | sev | finding | fix |
|---|---|---|---|
| 1 | critical | auto knees on the after (shorts) photo stretched the TPS to the jeans' knees | autolm emits knees only on jeans with leg ≥ 55% of height; run_pair drops auto knees; crotch/hips now waist-width-relative (cut-invariant) |
| 2 | high | fringe IoU aced by an opaque block (depth fitted from the real image) | predicted fringe = coverage > 0.5 only; new appearance metric `fringe_profile_distance` |
| 3 | high | abraded band painted along the whole outline (waistband, outseams) | band distance measured to the removed region only (both rawedge versions) |
| 4 | high | collage splitter discarded an off-centre single garment | split only if both halves contain garment mass |
| 5 | high | hanger in mask → waist/hips on the hanger | garment top = last horizontal width jump in top 30%; wide-kernel opening |
| 6 | med | tilted waistband clipped | top rule + fallback to first half-width row |
| 7 | med | hem chamfer averaged away over the outline | `hem_chamfer` = per-column bottom-profile error; whole-outline chamfer reported as `sil_chamfer` |
| 8 | med | null-baseline cut SSIM measured background | `cut_region_similarity` (SSIM + ΔE) over removed ∪ real-below-cut |
| 9 | med | one-leg hem fit cut silently | run_pair refuses unless both legs fit |
| 10 | med | GitHub `_No response_` stored as data | stripped |
| 11 | med | licences recorded, never enforced | validate requires `license_or_terms`; fetch skips non-open licences unless `--research-use` |
| 12 | low | uint8 0/255 mask wrapped to 0/1 | `(mask > 0)` before scaling |
Not fixed (noted): rawedge_v1 streak texture assumes image-vertical hanging; `rf < 0.05` gate rejects tiny trims; bmask refined after landmarks computed.
