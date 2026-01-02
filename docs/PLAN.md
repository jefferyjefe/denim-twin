# 12-Month Roadmap (from the source plan; unchanged)

| Phase | Weeks | Objective | Key deliverables |
|---|---|---|---|
| 0 Definition & recruitment | 1–4 | Freeze question, recruit advisors, protocols | Charter, literature map, protocol draft, outreach package, risk register |
| 1 Capture & dataset pilot | 5–8 | Rig, 5 pilot garments end to end | Dataset v0.1, capture checker, annotation guide, revised protocol |
| 2 Simple 2D baseline | 9–12 | Identity-preserving 2D cut | Interactive 2D prototype, baseline eval report, failure gallery, 5-user test |
| 3 Parametric geometry | 13–18 | Fit jeans template, correspondences | Fitted twins, reconstruction metrics, failure cases |
| 4 Mesh cutting & cloth | 19–24 | Topological cut, post-cut sim | Jorts generator, post-cut benchmark, mesh tests, 6-month demo |
| 5 Fray dataset & procedural | 25–30 | 20–30 garments, procedural fray | Dataset v0.5, fray simulator, parameter notebook |
| 6 Learned residual & render | 31–36 | Constrained photoreal refinement | Hybrid model, renderer, ablation report |
| 7 Scale, uncertainty, locked eval | 37–44 | 50 garments, calibrated ranges | Dataset v1.0, final results, calibration + human eval reports |
| 8 Release & prototype | 45–52 | Research + product package | Report, demo video, web UI, model/dataset cards, year-two rec |

Gates: see `GATES.md`. Kill/pivot rules: see `CHARTER.md` and source plan §14.

## First 90 days

- **Days 1–14**: freeze question ✔; mockup; 10 core papers; identify 2+2 researchers; protocol v0.1 ✔; acquire 5 jeans; repo/tracker/log ✔; define metrics.
- **Days 15–30**: build rig; capture 2 garments repeatedly; segmentation + manual correction; canonical 2D coords; digital cut line; cut first 2 garments; audit planned vs actual.
- **Days 31–60**: all 5 pilots; finalize wash protocol; procedural raw edge; side-by-side eval UI; identity metrics; present pilot; revise scope from failures.
- **Days 61–90**: toward 10 garments; first parametric fit; calibration + scale; cut line on digital rep; first predicted-vs-real demo; internal report.

## Dataset stages
Pilot 5 → Baseline 20 → Research v1 50 (35/5/10 train/val/locked test) → v2 100–150 → 300+.
Split by physical garment, never by image.

## Immediate next actions (source §18)
1. Name project ✔ (denim-twin)  2. Freeze question ✔  3. Advisor brief (draft ✔)
4. Acquire 5 jeans  5. Protocol (draft ✔, fill `[FILL]` fields)  6. Build rig
7. Capture one garment repeatedly  8. Measure consistency
9. Simplest 2D cut baseline  10. First physical cut + comparison  11. Approach collaborators with results
