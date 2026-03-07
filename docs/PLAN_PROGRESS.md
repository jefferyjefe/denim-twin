# Plan → implementation map (2026-08-29)

Every artefact traced to the section of the original plan it serves. "Evidence" = the experiment note with numbers.

| Plan section | Deliverable | Where | Status / evidence |
|---|---|---|---|
| §2 thesis, §3 north-star | falsifiable prediction vs reality | `tools/compare.py`, null baselines | EXP_0003/0004: cut geometry reproduced; fringe not yet (EXP_0008) |
| §4.1 capture | quality checker, ChArUco board, scale | `capture/quality.py`, `make_charuco_board.py`, `scale_from_grid.py`, `scale_from_coin.py` | checker tested; grid + coin scale tested; first metric pair (Kids Couture) |
| §4.2 segmentation + landmarks | SAM masks; mask-derived landmarks; manual override | `seg/sam.py`, `canon/autolm.py`, `annotate_landmarks.py` | autolm ≈4–7% width error on real photos; cut-invariant after review 2. EXP_0021: consensus segmentation is repeatable (0/96 photometric failures vs 16/96 for best-score) but the landmarks are **not rotation-invariant** — >5% loss at 1–8° of tilt |
| §4.2 (repeatability) | simulated re-capture suite; same-garment test; tilt sensitivity | `tools/experiment_repeatability.py`, `experiment_same_garment.py`, `experiment_landmark_rotation.py` | EXP_0021: the first tolerance numbers; Gate 1 blocker moved from segmentation to the measurement layer |
| §4.2 (tilt) | one upright implementation + estimator study + pair A/B | `canon/upright.py`, `tools/experiment_upright.py`, `tools/compare_upright_ab.py` | EXP_0022: deadband 8° → 0°; estimator accurate to 0.41° below 3° of tilt, unreliable on near-isotropic silhouettes; A/B inconclusive, bench clean |
| §4.3 Representation A (canonical 2D) | TPS canonical space | `canon/warp.py` | sub-pixel round-trip; exact per-pixel maps |
| §4.3 Representation B (parametric/mesh) | parametric template v0 | `canon/template.py` | EXP_0010: not yet better than heuristics; xfail |
| §4.5 modification representation | structured parameters, no free text | `modification.py` | tested; every run writes `modification.json` |
| §4.6 cutting | canonical cut, angled cut, image-space per-leg cut | `canon/cut2d.py`, `canon/hemfit.py` | tested; hem error 7–31 px on found pairs |
| §4.7 wash appearance (shrink, hem roll, dye loss) | procedural wash v0, presets = interval | `canon/wash.py`, `run_pair.py --wash` | EXP_0013: priors only (shrinkage unmeasurable from found photos); ΔE vs real marginally better on 10/11 pairs; off by default |
| §4.7 fraying (procedural base) | thread v0, density-band v1, SAM fringe split | `canon/rawedge.py`, `rawedge_v1.py`, `seg/sam.segment_fringe` | EXP_0015: the measurement itself is invalid (SAM returns fabric; direct method fails its negative control) — no fringe number in the repo is evidence |
| §4.7 learned residual | — | — | gated (Phase 6); not started, by design |
| §4.8 identity-preserving render + diff map | pixel copy outside cut; diff.png | `run_pair.py` | changed_outside_cut = 0 on every pair (Gate 2 evidence) |
| §4.7 fringe measurement | direct thread measurement + negative control | `eval/fringe_measure.py`, `tools/compare_fringe_methods.py` | EXP_0015: SAM's mask measures fabric; the direct method fails its control — no validated fringe measurement exists |
| §4.9 uncertainty | conservative/median/aggressive; 80% LOO intervals | `rawedge_v1.PRESETS`, `prior.py`, `run_pair` intervals | EXP_0009 (corrected): coverage 0/10, n tiny — uncalibrated |
| §5 dataset program | garment records, schema, splits, sentinel | `data/garments`, `garment.schema.json`, `sentinel.py` | 2 owner garments registered; online-only amendment |
| §5 (online variant) | found pairs, contributions, unpaired samples | `tutorial_pairs.py`, `validate_pairs.py`, issue form, `fringe_unpaired.py` | 31 pages → 5 cut pairs, 1 fray pair; channel exhausted (EXP_0005) |
| §6.1 geometry metrics | silhouette IoU, hem profile error, chamfer | `eval/geometry.py` | reviewed twice; tests |
| §6.2 identity metrics | SSIM/ΔE/feature retention in kept region, lighting-normalised | `eval/identity.py` | strict version = Gate 2 evidence; alignment-aware version (`aligned_identity`) added for renders that legitimately move pixels (EXP_0013 Part C) |
| §6.3 fray metrics | fringe IoU (coverage>0.5), profile distance | `eval/geometry.py`, `eval/fringe_measure.py`, `eval/hem_texture.py` | depth fails its control (EXP_0015/0016); hem roughness passes its control on unresampled masks (0/9) but **measures the resampler** on warped ones — a rotation alone makes 12/12 finished hems read frayed (EXP_0024). EXP_0017 retracted in full: at 241–389 px of waistband 6 of 7 real hems read exactly zero, so there was no signal to score (EXP_0025) |
| §6.4 uncertainty metrics | coverage / calibration audit | `eval/uncertainty.py`, `calibration_audit.py` | run once (EXP_0009) |
| §6.5 human evaluation | blinded judge pre-screen; gallery | `judge_pairs.py`, `make_gallery.py`, `reports/judge/` | blinding broken by construction until renders alter pixels |
| §6.6 baselines | no-op, crop-only, blurred, v0/v1 | `null_baselines.py`, `compare.py` | in every report |
| §2/§3 the product itself | one photo + cut spec -> prediction with interval, no ground truth needed | `tools/predict.py`, `tools/score_predict.py` | end-to-end tested; scored on 11 pairs (EXP_0014): sil IoU 0.768 vs 0.819 evaluation path, 0.771 crop-only |
| §7 Phase 0/1/2 | charter, protocol, literature, 2D baseline | `docs/`, `protocol/`, `canon/` | gate_0 ✔, gate_2 ✔; gate_1 still unmet but for a stated, measured reason (EXP_0021) — a real repeat capture is the only thing that can close it |
| §9 collaboration | advisor brief | `outreach/ADVISOR_BRIEF.md` | draft |
| §12 weekly cadence | weekly note | `notes/weekly/2026-W35.md` | written |
| §13/§14 risks, kill rules | tuning rule, benchmark, scope check | `docs/GATES.md`, `bench.py`, `scope_check.py` | enforced |
| §15 discovery | interview guide, outreach copy | `discovery/` | not yet run (owner action) |

Not on plan / deliberately absent: 3D meshes, cloth simulation, learned rendering, any chemical treatment.
