# Weekly step log

## Hypothesis
Gate 1 was recorded as failed because segmentation was not repeatable (EXP_0018). If consensus segmentation fixes
that (EXP_0019), the pipeline should now measure one garment consistently — and the tolerance that Gate 1 asks for
should be measurable, even without a second photograph of anything.

## Setup
Three instruments, all reproducible from artefacts in `reports/repeatability/`:
- the one same-garment pair in the dataset (a front and a back view of one pair of cut-offs), re-measured;
- 16 photographs × 14 *simulated* re-captures (re-framed, re-exposed, re-compressed) × 2 segmentation methods;
- rotations of masks that are already correct, which isolate the landmark heuristic from segmentation entirely.

## Result
Segmentation is fixed and something behind it was not. Consensus never changes object under a photometric
perturbation (0 of 96 runs below IoU 0.8, against 16 for SAM's best-scoring mask) and refuses rather than guessing
when it is unsure. But the *measurements* were frame-dependent: a 5° camera tilt moved every shape ratio by more
than 5%, and the pipeline only corrected tilt above 8°. Chasing that produced four more experiments:

- **EXP_0022** the deadband was on the wrong side of the effect (the estimate is accurate to 0.41° in the band it
  was skipping); set to 0.
- **EXP_0023** and it still did nothing on this project's own subject, because it read the silhouette's *long* axis
  and a flat-laid pair of shorts is wider than tall. Reading the near-vertical axis: tilt term in the repeatability
  suite **29.6% → 0.5%**, pairs IoU 0.837 → 0.857, hem error 13.3 → 7.8 px. One pair regresses past the bench
  tolerance and is left visible.
- **EXP_0024** hem roughness — the only fray observable that ever passed a control — **measures the resampler**.
  Rotate a finished-hem control by 8° and 12 of 12 read as frayed, at the size of EXP_0017's entire result.
- **EXP_0025** measured where nothing resampled the boundary, **6 of 7 real frayed hems read exactly zero** at
  241–389 px of waistband. EXP_0017 retracted in full: there was no signal to score against.
- **EXP_0026** a waistband-edge tilt estimator that is better on every measurement of the estimator (p90 0.22° vs
  1.64°) and worse in the pipeline (IoU 0.858 → 0.831). Not adopted.
- **EXP_0027** the product path, recomputed on the pairs `exclude.txt` allows: **0.8026 against a crop-only null of
  0.8026**. A dead heat.

## Interpretation
Two of this week's results are corrections to numbers the README was leading with, and both came from asking what a
metric does when nothing about the garment changes. That question — *perturb the input, not the model* — found more
in a day than any amount of scoring did: a segmentation that flips object on a JPEG re-encode, a landmark heuristic
that loses 30% at 8° of tilt, a fray metric that reads its own resampler, and a product path that ties with cropping.

The honest state of the thesis is narrower than it was on Monday. The cut geometry is reproduced well when the
system may look at the answer (0.857 IoU, 7.8 px hem) and no better than a crop when it may not. Fray has no
measurable observable at found-pair resolution. Both of those are now stated with the experiment that establishes
them.

## Next action
Two photographs of one garment with the phone picked up in between — the only thing that turns a simulated tolerance
into a real one — and an after-photo with ≥600 px of waistband, without which fray cannot be scored at all. Both
asks are now in `CONTRIBUTING_PAIRS.md` and the issue form. On the code side: a test for "is this line the
waistband" (EXP_0026), and closing the 0.857-vs-0.803 gap, which is the actual research problem.

<!-- weekly-scribe:begin -->
## Generated summary (weekly_scribe.py — edits here are overwritten)

## Commits this week
- Step 1 EXP_0027: the product path is a dead heat with cropping the photograph
- Step 2 EXP_0026: a better tilt estimator that makes the pipeline worse, and is therefore not adopted
- Step 3 EXP_0025: scored where nothing resampled the boundary, the fray comparison has no signal — EXP_0017 retracted in full
- Step 4 EXP_0023/0024: uprighting read the wrong axis, and hem roughness measures the resampler
- Step 5 EXP_0022: the tilt correction was switched off exactly where it was needed and reliable
- Step 6 Untrack every derived image under experiments/: 2035 renders of photographs we may not redistribute
- Step 7 EXP_0021: repeatability — the Gate 1 blocker moves from segmentation to the measurement layer
- Step 8 EXP_0017 recomputed after the gate removal: all 10 pairs decidable, prediction 0.00194 vs crop-only 0.00231 (4-1-5, p=0.375); claims now checked against result.json
- Step 9 Claim-checking infrastructure: every annotated experiment number is re-derived from its artefact in CI
- Step 10 EXP_0020: the sixth review's findings, the cost of the tightened evidence gate, and what survived
- Step 11 Claim test accepts the singular verb form
- Step 12 Review 6: remove the compactness gate (a garment-shape statistic that refused jeans), retract EXP_0017, correct EXP_0016 for excluded pairs, require explicit single-wash evidence (7 samples -> 1), drop rule outputs from the prior pool, canonicalise image URLs for leave-one-out, untrack copyrighted controls
- Step 13 Untrack the harvested control images: all-rights-reserved retailer photos must never be committed (review 6, finding 11) — derived numbers only
- Step 14 Consensus segmentation: keep it opt-in, document the studio-backdrop failure, refuse to tune the fix on 16 photos
- Step 15 EXP_0019: consensus segmentation (agreement across prompts) fixes all five known mask failures; 0/9 control false positives with no gate
- Step 16 EXP_0018: segmentation is the bottleneck — same-garment repeatability fails on confidently wrong masks; human mask verification now gates the prior; Gate 1 recorded as failed with evidence
- Step 17 EXP_0016 addendum: high-resolution controls confirm 0 false positives, but only behind a mask-quality gate (2 of 9 were broken masks reading as fray)
- Step 18 STATUS: mark the superseded n=3 line
- Step 19 README/STATUS: fray status after five reviews
- Step 20 Review 5: withdraw fringe depth as evidence (mask error, shadows, backdrops all read as fringe); exclude by photograph not page id; gate the manifest channel to one wash; prior carries rules and a sourced assumption; six EXP_0015 numbers corrected
- Step 21 EXP_0017: score the fringe renderer on hem roughness (6-3-2 vs crop-only, p=0.51); roughness reported for every system
- Step 22 EXP_0016: resolution does not rescue fringe depth (the floor scales too); hem roughness separates frayed from finished with 0/14 false positives
- Step 23 Weekly note: review 4 and the fringe-measurement negative
- Step 24 The null-baseline regression test skips where the pair artefacts are absent (CI has no scored runs)
- Step 25 Unpaired samples carry pairs.jsonl ids (LOO exclusion works across channels); flag sub-resolution fringe intervals instead of publishing three identical renders
- Step 26 Rebuild every fringe channel on one measurement method; prior carries validated:false and the control result
- Step 27 EXP_0015: fringe depth has never been measured — SAM's mask returns fabric, the new direct thread measurement fails its negative control; run_pair records both, docs and contributor form updated, bench refrozen
- Step 28 Adopt the review-4 tests now that all findings are fixed (they pass)
- Step 29 Review 4: fix 8 bugs (angled cuts discarded, unbounded alignment, gameable identity zone, published-vs-rendered interval, moving null baselines, sorted axis scales, seeded fill in scored images, unbacked mm claim); correct EXP_0013/0014 and gate scope
- Step 30 Weekly note addendum for this step
- Step 31 Untrack review-4 tests until their findings are triaged (they fail by design)
- Step 32 Literature 14-15 (denim shrinkage measurement, laundering edge abrasion); EXP_0013 Part D: our anisotropy prior is unsupported
- Step 33 Unpaired after-wash channel: ingest tool with evidence-gated validation; experiment dirs renamed to convention
- Step 34 Precision: the fringe is invisible to silhouette IoU but beats the null on the fringe metric
- Step 35 README: quote the product-path number, not the evaluation-path number
- Step 36 EXP_0014: score the product path against the found pairs; inseam_fraction definition mismatch found
- Step 37 predict.py: the product path (one photo + cut spec -> renders + interval); texture backdrop for presentation renders; README/status refresh
- Step 38 Alignment-aware identity metrics (bounded affine, moments+ECC); EXP_0013 Part C
- Step 39 Procedural wash v0 (shrink, hem roll, dye loss) with presets; EXP_0013 A/B and shrinkage-measurability negative
- Step 40 EXP_0012: bench A/B for the fringe gate; baseline refrozen with report
- Step 41 Rejected-run detection by title line only (flag text false-matched); reports refreshed
- Step 42 experiment_gate5: honour exclusions
- Step 43 EXP_0012 phone-resolution readiness; experiment_gate5.py (one-command Gate 5 evidence)
- Step 44 run_pair: plausibility gate on the SAM fringe mask (thin band only); phone-resolution synthetic pair verified
- Step 45 STATUS/PLAN_PROGRESS: review 3 and corrected numbers
- Step 46 Review 3 fixes (14): LOO prior module, px units, state always passed, manual-landmark transform, masked coin detection, bench guards, hem metric columns, consent check, grid/coin acceptance, modification ranges; EXP_0008/0009 corrected; baseline refrozen
- Step 47 Advisor brief: real status and specific questions
- Step 48 weekly W35 addendum
- Step 49 EXP_0011 verdict: template_v1 mixed, opt-in only
- Step 50 Template v1 (boundary Chamfer fit from heuristic landmarks) as optional refinement; EXP_0011 A/B on found pairs
- Step 51 Contributor loop verified; test record excluded; STATUS
- Step 52 Contributor dry run with valid image links
- Step 53 ingest: accept any link in photo sections; contributor dry run
- Step 54 ingest: accept any link in photo sections; contributor dry run through the batch
- Step 55 Contributor loop dry run: ingest accepts pasted image links; bench refrozen (7 pairs); STATUS
- Step 56 pairs: +1 (Wayback, cuffed cut pair; channel closed); batch/report/bench/gallery refresh
- Step 57 pairs-daily: batch, report, prior
- Step 58 docs: plan → implementation map
- Step 59 EXP_0010: parametric template v0 (not better than heuristics; xfail); STATUS gates/tools
- Step 60 EXP_0009: first calibration audit (over-confident, n too small; machinery verified)
- Step 61 Plan §4.9: prediction intervals for fringe depth per pair; first calibration audit run (n tiny)
- Step 62 Batch regenerated with diff maps; daily loop builds gallery + bench
- Step 63 Gate 2 passed with evidence; evaluation gallery + failure gallery generator (plan Phase 2 deliverables)
- Step 64 run_pair: fix indentation
- Step 65 Plan §4.5 structured modification representation (+tests); §4.8 difference map output; run_pair records the modification it evaluated
- Step 66 coins util module; coin_key test; batch imports it
- Step 67 batch: coin-based scale for contributor pairs (scale_ref coin + free-text coin name)
- Step 68 Coin-based scale detector for contributor photos; tests for coin/grid scale; agents README: routines disabled, CI added
- Step 69 bench: skip rejected runs; baseline refrozen
- Step 70 GitHub Actions test workflow; regression benchmark over usable pairs (baseline frozen)
- Step 71 Exclude Prudence & Austere (cuffed after wash); EXP_0005 final line
- Step 72 EXP_0005 fourth run; STATUS; cut->washed run for Prudence & Austere
- Step 73 fit_fringe: fix raw-cut tuple bug
- Step 74 pairs: +2 (31), incl. one genuine fray-after-wash pair (Prudence & Austere); batch refresh
- Step 75 EXP_0008 update; raw unwashed cuts contribute ~0 depth
- Step 76 hem_finish in manifest (cuffed => depth 0 in prior); depth measured in the after-photo frame; batches rerun
- Step 77 EXP_0008: held-out fringe prior — not predictive yet (n, cuff artefacts, measurement frame)
- Step 78 State-conditional fringe prior (after_cut vs after_wash); LOO batch rerun
- Step 79 Leave-one-out prior batch (experiments/pairs_prior)
- Step 80 Unpaired fringe samples: sanity filters; prior blends paired + unpaired; run_pair --prior uses the blend
- Step 81 fringe_unpaired.py: scale-free fringe depth from unpaired after-wash photos (SAM fringe mask)
- Step 82 exclude niftythrifty pair (before unusable); note after-wash as unpaired fringe sample
- Step 83 test: backdrop fill uses background colour, touches nothing else
- Step 84 EXP_0005/STATUS: third run, n=4
- Step 85 Short 'before' garments allowed (flag); exclusions for two cropped pages; batch refresh
- Step 86 autolm: shorts threshold 0.6x waist width (toddler jeans); batch refresh
- Step 87 pairs: +6 vetted pages (29); batch/report/prior refresh
- Step 88 Fix name shadowing: backdrop_fill
- Step 89 Backdrop-only background fill (inpaint whole garment, composite kept fabric back)
- Step 90 run_pair: inpainted fill; waistband gate on opened mask (hanger clips); judge sets regenerated
- Step 91 Judge pre-screen report (blinding broken by flat fill); inpainted background fill for the removed region; judge uses un-warped real photo
- Step 92 Grid-mat scale detector; per-image mm_per_px in manifest → batch; first metric pair (Kids Couture); judge set over pair runs
- Step 93 Close-out: exclude d52a with reason; EXP_0005/STATUS final for the day
- Step 94 upright: elongation-dependent rotation cap
- Step 95 coarse garment pick: denim-colour prior + more prompt sets (busy rugs)
- Step 96 upright: cap at 30° (wide shorts must not be rotated)
- Step 97 Batch refresh: 3 usable pairs; EXP_0005 update
- Step 98 Upright normalisation (PCA) before landmarks; tighter crop; exclusions for two unusable pages
- Step 99 Manual crop boxes in pairs manifest; batch applies them; crop-edge contact is a flag
- Step 100 pairs: +8 vetted pages (23); fringe prior quality bar; batch refresh
- Step 101 EXP_0005/STATUS: pair 15 usable (2/15)
- Step 102 autolm: spread-invariant jeans/shorts rule with too-low-gap fallback; batch/report refresh (2 usable pairs)
- Step 103 Pair 15 (Create/Enjoy, cut-geometry pair); before-image bottom-edge contact is a flag not a rejection
- Step 104 STATUS: SAM fringe result
- Step 105 fringe prior: exclusion list for known-bad pairs
- Step 106 run_pair --exclude for leave-one-out prior; batch honours PAIRS_USE_PRIOR
- Step 107 EXP_0004: SAM fringe result; batch/report/prior refresh
- Step 108 hemfit: with a fringe mask, edge = first fringe row per column
- Step 109 hemfit: scan from hip row; crotch prior 0.6x waist width; SAM fringe mask in hem fit (pair1 hem error 6 px)
- Step 110 tests for report/prior scripts; agents README harvester disabled
- Step 111 docs/STATUS.md
- Step 112 EXP_0007: CC harvest has no garments for the task (negative); curator throttled to daily
- Step 113 harvester: polite Commons download rate, honour Retry-After on 429
- Step 114 Outreach copy; README status section
- Step 115 Local repro report (43 pass); EXP_0006 fringe measurement negative result; measure_fringe marked experimental
- Step 116 pairs REPORT.md from daily-loop dry run
- Step 117 Local pairs-daily launchd job; agents README status; tuning rule in GATES
- Step 118 fit_fringe.py: scale-free fringe prior with leave-one-out; run_pair --prior makes depth a held-out prediction
- Step 119 CLIP gate demoted to info; weekly note W35
- Step 120 report_pairs: skip rejected runs, None-safe; mask-based fringe profile distance
- Step 121 CLIP whole-garment gate in run_pair; report_pairs.py aggregate with null deltas
- Step 122 EXP_0004: stop-tuning note
- Step 123 hemfit robustness (hip-midpoint leg split, mask fallback, min points); keep coarse-mask landmarks after refinement
- Step 124 rawedge_v1 streaks follow the cut's hanging direction; run_pair: 1% trim allowed, landmarks recomputed after mask refinement
- Step 125 Batch refresh after review 2; EXP_0005 update (fringe IoU honest at 0.07)
- Step 126 Review 2 fixes (12): cut-invariant landmarks, fringe/hem/cut metrics, band-to-cut distance, collage guard, licence gate, ingest cleanup; reviewer tests adopted
- Step 127 EXP_0004: registration quality notes
- Step 128 register_feat: affine-RANSAC inlier pass on SIFT matches
- Step 129 register_feat: min-separation filter, landmark-only held-out residual; test
- Step 130 Feature-augmented registration (SIFT matches consistent with landmark warp); pair1 held-out residual 158 -> 48 px
- Step 131 Leave-one-landmark-out registration residual (pair1: 157px, exposes underdetermined TPS on shorts); lighting normalisation on kept region before scoring; tests
- Step 132 EXP_0005: found-pair yield (1/14 usable), funnel and read
- Step 133 run_pair: score against the split (used) images, not the original collage paths
- Step 134 run_pair: waistband gate at widest top row
- Step 135 run_pair: collage splitting (side-by-side/stacked), input sanity gates (edge contact, size, waistband, degenerate cut, registration overlap); batch summary
- Step 136 Pair validator (CLIP roles, 5/14 usable); batch runner over usable pages; finder routine now requires a vision check
- Step 137 EXP_0004: pair1 fully automatic
- Step 138 Coarse garment segmentation (candidate selection, border/area priors); shorts-vs-jeans rule for crotch; test tolerance
- Step 139 Mask-based landmark heuristic (autolm) + tests; run_pair.py: one-command pair pipeline (auto landmarks, hem fit, fringe presets, scoring, panel)
- Step 140 EXP_0003 update 3: hem-zone restriction regression noted
- Step 141 hemfit: restrict fringe class to hem zone
- Step 142 Per-leg hem fit (image-space angled cut, colour-based fabric/fringe split, fringe depth); tests; EXP_0003 update 2
- Step 143 Fix v1 depth test to count fringe-zone pixels only
- Step 144 Raw edge v1: fringe as density band (depth 5-40mm); compare.py scores the fringe zone (pred mask incl. fringe, two-sided edge band, fringe IoU); EXP_0003 update
- Step 145 EXP_0003: first found pair end-to-end (honest negative result on fray); angled cut primitive + tests
- Step 146 pairs: seed 14 tutorial pages (95 images, 4 with after-wash)
- Step 147 Docs: pair finder in agents README; online-data pointers in README
- Step 148 Crowd-sourced pairs: GitHub issue form, ingest script, contributor guide
- Step 149 Charter amendment: online-only data variant; tutorial-pair manifest tool
- Step 150 null_baselines: use real/removed masks for silhouette instead of gray>0
- Step 151 Registration of real after-captures into the before frame (TPS on surviving landmarks) + compare.py scoring CLI with null baselines; test
- Step 152 EXP_0002: raw-edge v0 qualitative note + panel
- Step 153 Procedural raw edge v0 (2D baseline): jagged edge, abraded band, hanging weft threads; conservative/median/aggressive presets; tests
- Step 154 Agents README: routine IDs
- Step 155 Agent support: sentinel, null-baseline enforcer, protocol audit, scope check, weekly scribe, arXiv watch, blinded judge, calibration audit, capture-QA watcher, harvest curator, interview coder; launchd plists; agents README
- Step 156 Fix cut-position test: check boundary at leg columns against the map (tilted line), keep loose inseam check
- Step 157 Review fixes: true CIE76 dE, exact TPS maps, cut of out-of-raster pixels, SSIM leak, location-checked feature retention, Otsu/Lab foreground, repo-relative tool paths, SAM fallback, Openverse page_size + license normalisation + atomic manifest; schema conventions + strictness; protocol cut definition/measurement/fray/offcut clarifications
- Step 158 SAM segmentation prompted from landmarks (box + positive/negative points); baseline uses it by default
- Step 159 Capture checker: exposure stats on garment pixels only; cutout-background flag; foreground-size check; tests
- Step 160 Harvester for CC-licensed jeans images (Openverse + Commons) with manifest
- Step 161 Protocol §7: offcut swatches; Evisu wash decision
- Step 162 Fill measurements: Our Legacy from retailer size chart; Evisu tag + photo-proportion estimate
- Step 163 Web-verified specs: Our Legacy Third Cut Digital Denim Print (100% cotton, printed); Evisu size-code note
- Step 164 Register DENIM_0001 (Evisu) and DENIM_0002 (Our Legacy) from owner photos + labels
- Step 165 EXP_0001: listing-photo feasibility; seed GrabCut from outline polygon
- Step 166 Manual landmark annotator and baseline runner for real photos
- Step 167 Literature map (13 verified papers, component mapping, gaps)
- Step 168 Canonical 2D garment space (TPS on landmarks), 2D cut baseline, tests
- Step 169 Customer discovery interview guide and log
- Step 170 Evaluation metrics (§6): geometry, identity preservation, fray, uncertainty; tests
- Step 171 Widen board exclusion pad
- Step 172 Capture subsystem: ChArUco board generator, board detection + metric scale, capture-quality checker
- Step 173 Pilot acquisition list and auxiliary data note
- Step 174 Add roadmap summary
- Step 175 Phase 0: project skeleton, charter, protocol draft, schema, tools

## Experiments on record
- EXP_0001_listing-photos
- EXP_0002_rawedge_v0
- EXP_0003_first_found_pair
- EXP_0004_auto_pipeline_pair1
- EXP_0005_found_pair_yield
- EXP_0006_fringe_measurement
- EXP_0007_cc_harvest_value
- EXP_0008_heldout_fringe_prior
- EXP_0009_calibration_first
- EXP_0010_parametric_template_v0
- EXP_0011_template_v1
- EXP_0012_phone_resolution
- EXP_0013_wash_v0
- EXP_0014_product_path_score
- EXP_0015_fringe_measurement_negative
- EXP_0016_resolution_threshold
- EXP_0017_roughness_as_fray_metric
- EXP_0018_segmentation_is_the_bottleneck
- EXP_0019_consensus_segmentation
- EXP_0020_review6_response
- EXP_0021_repeatability_and_tolerance
- EXP_0022_upright_threshold
- EXP_0023_upright_axis
- EXP_0024_resampling_floor
- EXP_0025_roughness_native
- EXP_0026_waistband_tilt
- EXP_0027_product_path_recomputed

## Sentinel
```
manifest: 788 records checked
records: 2 (0 locked)
sentinel: OK
```
## Protocol audit
```
soft: 14 unfilled [FILL] fields in PROTOCOL.md: `[FILL: N standard filler towels]`, `[FILL: brand]`, `[FILL: fabric shears model]`, `[FILL: make/model, location]`, `[FILL: make/model]`, `[FILL: model/setting]`, `[FILL: name]`, `[FILL: phone model]`
soft: DENIM_0001: waist_cm=97.0 has no measurement_readings (source=mixed)
soft: DENIM_0001: front_rise_cm=33.0 has no measurement_readings (source=mixed)
soft: DENIM_0001: original_inseam_cm=76.2 has no measurement_readings (source=mixed)
soft: DENIM_0001: leg_opening_cm=60.0 has no measurement_readings (source=mixed)
soft: DENIM_0002: waist_cm=96.5 has no measurement_readings (source=web_size_chart)
soft: DENIM_0002: front_rise_cm=33.7 has no measurement_readings (source=web_size_chart)
soft: DENIM_0002: original_inseam_cm=76.2 has no measurement_readings (source=web_size_chart)
soft: DENIM_0002: leg_opening_cm=52.0 has no measurement_readings (source=web_size_chart)
soft: DENIM_0002: thigh_cm=36.2 has no measurement_readings (source=web_size_chart)
```
## Scope check
```
gates passed: ['gate_0', 'gate_2']
SCOPE VIOLATIONS:
 - src/denimtwin/canon/wash.py: mentions year-two-banned treatment (dye)
 - src/denimtwin/modification.py: mentions year-two-banned treatment (bleach)
```

## Review questions (fill in)
- What measurable uncertainty did we reduce this week?
- Which assumption failed?
- Physical matching improved, or only attractiveness?
- Is the next experiment testing one clear hypothesis?
- Are data and results reproducible?
- Is scope expanding without evidence?

## Next action
<!-- weekly-scribe:end -->
