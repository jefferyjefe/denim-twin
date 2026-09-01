# Backlog

What is open, what is closed and why, and what each item is blocked on. Updated when an
experiment closes a line. Run `tools/verify.py` before and after any change here.

## The one question that matters now

**Answered, negatively (EXP_0035).** Gate 1's restatement asked whether the pipeline could *choose*
an inseam fraction from the before photo and beat the constant baseline (0.7302 IoU). It cannot,
and the reason is not a modelling failure: the cut height is a style choice, not a property of the
garment. Six shape features, nested leave-one-out with the feature chosen inside the fold — MAE
0.3066 against a constant's 0.1804 (70% worse), and on the bench's own metric **0.6584 against
0.7302**, losing on 7 of 7 pairs. The seven folds pick four different features.

So the supportable product claim is EXP_0034's: given a cut height, the pipeline places and renders
it far better than not knowing it (**+0.0953, 4.7σ**), and the inseam fraction belongs in the
interface as a **user input** — which is how `score_predict.py`'s docstring already describes it.

**What is now open in its place:** converting *stated user intent* into a fraction ("just above the
knee", a length in mm, a line marked on the photo). That is not a garment feature and EXP_0035 says
nothing about it. It is a conversion problem with a checkable answer, and it needs the mm/px scale
most found pairs lack — so it is **blocked on data**, not on code.

## Closed

| line | verdict | where |
|---|---|---|
| Segmentation repeatability | fixed by consensus segmentation | EXP_0019 |
| Camera tilt | fixed; upright everything, near-vertical axis | EXP_0022/0023 |
| Canonical inverse wrong by 10.7 px | fixed by iteration; **no production path uses that direction**, 0 pixels changed | EXP_0030 |
| Canonical map folding | cause was coincident landmarks (legs photographed touching); `drop_degenerate` | EXP_0031 |
| Fringe **depth** as evidence | withdrawn; not measurable at found-pair resolution | EXP_0015/0016 |
| Hem roughness as a fray metric | does not survive re-capture; 6 of 7 real hems read exactly zero natively | EXP_0021/0025 |
| Registration TPS folding | does not fold (0.0000 on all 7); only 6 near-affine landmarks survive a cut | EXP_0033 |
| "Product path ties crop-only" | **void** — the null is built from the model's own keep mask | EXP_0034 |
| "The bench is too noisy to resolve the difference" | **wrong** — paired, it resolves to 0.00023 | EXP_0033 |
| Landmark consistency as a fold gate | rejected; degeneracy is one cause of folding, not the cause | EXP_0032 |
| Predicting the cut height from the garment | **not predictable**; worse than a constant on MAE and on IoU | EXP_0035 |
| Benching the fringe render | impossible on this data: 6 of 7 pairs cannot show a fringe | EXP_0036 |
| `443d1d4658` bench regression | fixed: a cuffed garment's hem was measured from a spurious fringe | EXP_0038 |
| Mask edge instead of the colour split | tested, **not adopted**; one pair decides it either way | EXP_0039 |
| Waistband edge as a registration landmark | tested, **not adopted**; outside the hull is fitted better than inside | EXP_0041 |

## Open, unblocked (code only)

- **`443d1d4658` bench regression** — ~~open~~ **closed** (EXP_0038). The mechanism was a branch,
  not a geometry: uprighting changed whether SAM produced a fringe mask, which switched
  `estimate_hems` onto its fringe-mask path and moved the left leg's fitted line 14°. The garment is
  `cuffed` and cannot fray, so that path should never have run — `expects_fringe()` was computed
  after the hem fit and gated only rendering. Gated now; the whole bench is green with **no baseline
  re-freeze**. Residual: this pair's IoU is 0.898 against the 0.918 uprighting-off gives, so
  uprighting still costs it something outside the hem line.
  Historical detail (EXP_0037), cause confirmed, mechanism was then unknown: Disabling
  uprighting on this pair reproduces the frozen baseline exactly (IoU 0.9180 / hem 8.92 against
  0.918 / 8.916). Three explanations are now dead: the waistband fix (EXP_0026), independent
  uprighting of before and after (r = +0.092), and hem-angle asymmetry (r = +0.213) — the last two
  both point at `2b0123d732`, which has nearly the best hem error in the set. Uprighting stays on;
  one pair does not outweigh a directly measured defect and a better mean. Still the one pair the
  independent null beats the product path on (−0.0068, −3.6σ).
- **The eval-vs-product gap (0.857 vs 0.823)** — EXP_0028 showed handing the product path the exact
  cut region closes it (0.8735 vs 0.8750), so the gap is knowledge of where the cut goes. EXP_0035
  now shows that knowledge cannot come from the garment, so this gap closes only with a user input,
  not with a better model. Not independently actionable.
- ~~**Fringe rendering is invisible in the bench**~~ — done, and the answer is structural
  (EXP_0036). With `--wash none` the prediction is the crop plus ≤256 px; turning wash on moves
  **six of seven pairs by exactly zero**: a fringe needs a raw
  edge *and* an after-wash capture, and only 1 of 7 pairs has both. That pair gains +0.01106 ±
  0.00576 (**1.9σ**, not significant). The fringe render is **not benchable on this data** and no
  code change alters that. Moved to "blocked on data".

## Blocked on data

- **Gate 1 repeatability** — needs a repeat capture of one garment. Nothing in the found-pair set
  is a re-capture.
- **Fray observables** — need an after-photo with ≥600 px of waistband. Found pairs give 241–389 px.
- **Any fringe-render claim** — needs after-wash captures of **raw-edge** cuts. Only 1 of 7 current
  pairs qualifies, so the claim rests on n=1 (EXP_0036). `CONTRIBUTING_PAIRS.md` now asks for raw
  edges specifically; a cuffed contribution cannot help here however good the photograph.
- **Predicting the cut height at all** — EXP_0035's negative result holds at n=7; a genuine
  r² ≈ 0.3 would need roughly 25 pairs to separate from noise.
- **Any heuristic threshold change** — the tuning rule (`docs/GATES.md`) requires ≥5 usable pairs
  with a report attached.
- **Found-pair channel is exhausted** (EXP_0005/0007): 32 tutorial pages → 6 cut pairs + 1 fray
  pair. Contributed after-wash photos with a coin in frame are the only lever
  (`CONTRIBUTING_PAIRS.md`).

## Guards that are currently not running

- **`tests/test_review4_wash_null_baselines.py` skips.** It compares the null baselines between
  `experiments/pairs` and `experiments/pairs_wash` to check that `--wash median` leaves them
  untouched. EXP_0038 regenerated `pairs` and not `pairs_wash`, and `pairs_wash/provenance.json`
  predates the `pipeline_sha256` field, so there is no way to tell whether the same code produced
  both. Re-running both with `tools/run_pairs_batch.py` is the fix and needs a full segmentation
  pass. This is the **only** skip in the suite, and `tests/test_guards_are_not_optional.py` now
  fails if a second one appears — a skip is a guard that stopped running, and review 7 found several
  that had.

## Environment hazards

- **`com.denimtwin.pairs-daily` regenerates the pair set and pushes, at 03:30, unattended, against
  the WORKING TREE.** The whole job is one inline shell command in the plist: pull --rebase, ingest,
  fetch, `run_pairs_batch.py`, `report_pairs.py`, `fit_fringe.py` (which rewrites the tracked prior),
  `make_gallery.py`, `bench.py`, then `git add … && git commit && git push`. It never runs
  `tools/verify.py`. In a later step it fired while `tools/run_pair.py` held an uncommitted change and
  regenerated eight pair directories with code that was not in any commit — the review-7 defect
  (artefacts whose producer is not in history), automated and self-pushing. It was stopped
  mid-batch and the tracked files restored; `experiments/pairs` verified byte-identical afterwards.
  **The job is currently unloaded.** `ops/pairs-daily.sh` is the same sequence with the two guards it
  needed: refuse to run when `git diff HEAD -- src tools` is non-empty, and refuse to commit when
  `verify.py` fails. Re-enable with
  `launchctl load ~/Library/LaunchAgents/com.denimtwin.pairs-daily.plist` after pointing the plist at
  that script.


- **Stale bytecode can silently mask a source edit.** `.venv/bin/python` here is macOS's system
  Python, which sets a `pycache_prefix` and writes `.pyc` files to
  `~/Library/Caches/com.apple.python/<absolute path>/` — outside the repository and outside any
  `__pycache__`, so `rm -rf src/**/__pycache__` does not clear it. Review 7 hit this live: a
  threshold edited back to 0.6 on disk kept importing as 0.9. Any experiment run in that state uses
  old code and reports it as current. `tests/test_tuning_rule_thresholds.py` now compares the
  imported defaults against an AST parse of the file and names the cache directory when they differ.

## Known defects accepted, not fixed

- **The before-photo landmarks and `bmask.png` come from different segmentations.** Measured
  (EXP_0041) and acted on (EXP_0042). `run_pair.py` refines the before mask with landmark prompts
  once `autolm` finds ≥14 landmarks and keeps the *coarse* landmarks; refinement **never shrinks the
  mask** (area ratio 1.0014–1.1161 on the five pairs it runs on), so the landmarks are anchored on a
  systematically smaller silhouette and end up as much as **45 px** from where the refined mask puts
  them. Matching the two is worth **+0.0316 silhouette IoU** on the treated pairs (1.42σ) and costs
  **+0.15 px** of hem error, so it is **not adopted** — `run_pair.py --refit-landmarks-after-refine`
  is off by default with the A/B attached. The reason the current behaviour was chosen is *not
  recoverable*: `run_pair.py` cites EXP_0004 for a claim that note does not make, on a pair that no
  longer exists. `landmarks.json` now records `before_landmark_source` either way.

- **`run_pair.py` writes `*_used.png` before the `sane()` gates** (line 110 vs 129), so a directory
  re-run and then rejected keeps fresh images beside stale masks. Two directories are in that state
  (`660bef67bf`, `85d48013a2`); both are rejected and nothing scores them
  (`score_predict.py:48`). Guarded by `tests/test_pair_dirs_consistent.py` for the case that would
  hurt — an *accepted* directory with disagreeing artefacts.
- **926 copyrighted derived images are in the pushed GitHub history.** Untracked going forward and
  ignored via `experiments/**/*.png|jpg|jpeg`; removing them from history is the owner's call.
- **`lmcheck`'s "crotch above the hips" rule is unreachable for auto landmarks** — `autolm` searches
  `range(hip_y, bot)`, so an auto crotch can never sit above the hips. Kept for manual landmarks.

## The waistband lead (EXP_0040 → EXP_0041): closed, and EXP_0040 corrected on the way

EXP_0040 measured that `register.SURVIVING` has no landmark above the waist, that the registered
after-garment's top lands below the prediction's on 7 of 7 pairs (p = 0.0156, median +14 px), and
that band 0 is where uprighting costs IoU. The lead was to add a waistband-edge correspondence.

EXP_0041 added it — three arms plus a displaced null, seven pairs,
`reports/waistband_landmark.json` — and the answer is no. Two of the three things that answer rests
on also overturn something:

- **EXP_0040's sign test does not survive matched segmentation.** It compared landmarks from the
  *coarse* before mask against masks derived from the *refined* one. Recompute both from one
  segmentation and the offsets are 30, 14, 23, 0, **-1**, 10, 4 — five positive, one negative, one
  zero, **p = 0.2188**. The pair that flips is `4bfef03bd7`, which is the pair with the largest
  provenance disagreement. EXP_0040's band decomposition stands; its headline does not.
- **The waistband is not an unconstrained region.** A held-out `SURVIVING` landmark sits a median of
  **136.0 px** from its nearest support; a waistband corner sits **16.6 px** from its. Matched on
  cardinality the waistband gap beats the leave-one-out error (12.03 px against 28.82, 7 of 7);
  matched on *reach* it loses by the same margin (**118.94 px**, 7 of 7). The correspondence is
  redundant with a landmark 16.6 px away, not missing from a region nothing constrains.
- **Neither treatment helps.** Δ IoU -0.00204 (−0.58σ) adding the corners, -0.00234 (−0.69σ) moving
  the waist landmarks onto them. On the prediction-independent residual, `add` is a coin flip
  (0.24σ, better on 4 of 7, sign reverses when normalised by garment height) and `replace` is
  genuinely worse (2.15σ, worse on 6 of 7). Displacing the correspondence costs **+12.134 px** of
  residual against `add`'s +1.586, so it is a real correspondence carrying no new information.
- **The band-0 column cannot carry a claim at all.** `pred_median_mask.png` is a strict pixel subset
  of `bmask.png` on 7 of 7 pairs and shares its top row on 7 of 7, so a correspondence read off
  `bmask.png` is read off the artefact defining the scoring target — `docs/GATES.md`'s baseline rule.

**Now open in its place:** the before photo is segmented twice and the two results differ by up to
45 px, with everything downstream mixing them. See the defect below.

## The hem edge source (EXP_0038 → EXP_0039)

EXP_0038 found that SAM's spurious fringe had been landing closer to the true hem than
`hemfit.fabric_vs_fringe`'s colour split does. The principled follow-up — a garment that cannot
fray has no fringe to exclude, so take the fabric edge from the mask — was tested on all seven
pairs and **not adopted** (EXP_0039): better on 5 of 7, but mean hem 5.70 → 7.85 px because
`2b0123d732` alone costs +20.08 px, the same size as EXP_0038's win. Neither edge source is right
in general and there is no principled per-garment rule available at n=7. **Blocked on data.**

## A pattern worth naming

Three causal claims in this project have survived their number and failed their explanation:
EXP_0029's canonical-inverse attribution, EXP_0033's reading of the null, and EXP_0037's uprighting
mechanism. In each the measurement was right and the story about *why* was wrong, and in each the
story was only caught because something downstream was checked against it. A real effect plus a
plausible mechanism is not a finding until the mechanism predicts something that is then tested.

## Standing rules

- `tools/verify.py` is the gate; CI runs it blocking (`--no-bench`).
- A baseline may not be derived from the model's own output (`docs/GATES.md`, baseline rule).
- Quote the **paired** uncertainty on a method difference, never the unpaired one; a cancellation
  factor in the hundreds means the two arms are the same object (EXP_0033/0034).
- Every number in a NOTE, the README or `docs/` is checked by `tools/check_claims.py`.
- A note whose conclusion has been overturned carries a banner naming the note that overturned it,
  and `experiments/README.md` (generated, gate-checked) flags it. Five notes were still asserting
  the voided crop-only comparison after EXP_0034; a test now enforces the pointer.
- State a mechanism only with a prediction it makes that has been checked; otherwise write
  "mechanism unknown" (EXP_0037). And check the prediction on CURRENT data — EXP_0037 disconfirmed a
  mechanism on a correlation that a later commit invalidated, and on a rotation column in which a
  refused tilt correction was indistinguishable from a straight photograph (review 7).
