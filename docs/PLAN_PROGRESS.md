# Plan → implementation map (2026-08-29)

Every artefact traced to the section of the original plan it serves. "Evidence" = the experiment note with numbers.

| Plan section | Deliverable | Where | Status / evidence |
|---|---|---|---|
| §2 thesis, §3 north-star | falsifiable prediction vs reality | `tools/compare.py`, null baselines | EXP_0003/0004: cut geometry reproduced; fringe not yet (EXP_0008) |
| §4.1 capture | quality checker, ChArUco board, scale | `capture/quality.py`, `make_charuco_board.py`, `scale_from_grid.py`, `scale_from_coin.py` | checker tested; grid + coin scale tested; first metric pair (Kids Couture) |
| §4.2 segmentation + landmarks | SAM masks; mask-derived landmarks; manual override | `seg/sam.py`, `canon/autolm.py`, `annotate_landmarks.py` | autolm ≈4–7% width error on real photos; cut-invariant after review 2 |
| §4.3 Representation A (canonical 2D) | TPS canonical space | `canon/warp.py` | sub-pixel round-trip; exact per-pixel maps |
| §4.3 Representation B (parametric/mesh) | parametric template v0 | `canon/template.py` | EXP_0010: not yet better than heuristics; xfail |
| §4.5 modification representation | structured parameters, no free text | `modification.py` | tested; every run writes `modification.json` |
| §4.6 cutting | canonical cut, angled cut, image-space per-leg cut | `canon/cut2d.py`, `canon/hemfit.py` | tested; hem error 7–31 px on found pairs |
| §4.7 fraying (procedural base) | thread v0, density-band v1, SAM fringe split | `canon/rawedge.py`, `rawedge_v1.py`, `seg/sam.segment_fringe` | EXP_0004: beats crop-only on one fray pair; prior not predictive yet (EXP_0008) |
| §4.7 learned residual | — | — | gated (Phase 6); not started, by design |
| §4.8 identity-preserving render + diff map | pixel copy outside cut; diff.png | `run_pair.py` | changed_outside_cut = 0 on every pair (Gate 2 evidence) |
| §4.9 uncertainty | conservative/median/aggressive; 80% intervals | `rawedge_v1.PRESETS`, `run_pair` intervals | EXP_0009: over-confident, n tiny — labelled uncalibrated |
| §5 dataset program | garment records, schema, splits, sentinel | `data/garments`, `garment.schema.json`, `sentinel.py` | 2 owner garments registered; online-only amendment |
| §5 (online variant) | found pairs, contributions, unpaired samples | `tutorial_pairs.py`, `validate_pairs.py`, issue form, `fringe_unpaired.py` | 31 pages → 5 cut pairs, 1 fray pair; channel exhausted (EXP_0005) |
| §6.1 geometry metrics | silhouette IoU, hem profile error, chamfer | `eval/geometry.py` | reviewed twice; tests |
| §6.2 identity metrics | SSIM/ΔE/feature retention in kept region, lighting-normalised | `eval/identity.py` | tautological until a renderer alters pixels (judge report) |
| §6.3 fray metrics | fringe IoU (coverage>0.5), profile distance | `eval/geometry.py` | in use |
| §6.4 uncertainty metrics | coverage / calibration audit | `eval/uncertainty.py`, `calibration_audit.py` | run once (EXP_0009) |
| §6.5 human evaluation | blinded judge pre-screen; gallery | `judge_pairs.py`, `make_gallery.py`, `reports/judge/` | blinding broken by construction until renders alter pixels |
| §6.6 baselines | no-op, crop-only, blurred, v0/v1 | `null_baselines.py`, `compare.py` | in every report |
| §7 Phase 0/1/2 | charter, protocol, literature, 2D baseline | `docs/`, `protocol/`, `canon/` | gate_0 ✔, gate_2 ✔; gate_1 (repeat captures) needs a rig or contributors |
| §9 collaboration | advisor brief | `outreach/ADVISOR_BRIEF.md` | draft |
| §12 weekly cadence | weekly note | `notes/weekly/2026-W35.md` | written |
| §13/§14 risks, kill rules | tuning rule, benchmark, scope check | `docs/GATES.md`, `bench.py`, `scope_check.py` | enforced |
| §15 discovery | interview guide, outreach copy | `discovery/` | not yet run (owner action) |

Not on plan / deliberately absent: 3D meshes, cloth simulation, learned rendering, any chemical treatment.
