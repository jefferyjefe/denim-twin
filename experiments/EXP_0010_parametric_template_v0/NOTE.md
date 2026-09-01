# EXP_0010 — Parametric 2D jeans template v0 (Phase 3 start) — not yet better than heuristic landmarks

**Date:** 2026-02-13 07:25 UTC (Gate 2 recorded as passed the same day, which unlocks Phase 3).
**What:** `canon/template.py`: 11-parameter symmetric polygon (waist, hip, rise, thigh, knee, hem widths, leg length, spread)
fitted to a silhouette mask by Nelder–Mead on 1 − IoU, then with an added between-leg-gap IoU term and soft bounds.

| mask | silhouette IoU of fit | crotch error | landmark error vs reference |
|---|---|---|---|
| synthetic jeans | 0.94 (IoU-only) / 0.83 (+gap term) | 82 px / 104 px too high | — |
| Grailed 501 (SAM mask) | 0.78 / 0.60 | 548 / 261 px | 9.0% / 9.2% of width (heuristic autolm: 4.4%) |

## Read
Silhouette IoU under-constrains the crotch (the inner-leg region is a sliver of the area); the gap term helped the
Grailed crotch but hurt overall IoU, and the polygon's spread parameterisation cannot reproduce straight inner legs.
Conclusion per plan: do not add 3D/parametric complexity until it beats the 2D heuristic on measured landmark error.
Next for Phase 3 (when resumed): fit in canonical space with per-vertex offsets from a mean template (statistical
shape model), initialise from the heuristic landmarks, and optimise boundary Chamfer distance rather than area IoU.
Module kept as an experimental skeleton; test marked xfail with this reason.
