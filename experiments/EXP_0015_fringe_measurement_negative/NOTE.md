# EXP_0015 — Fringe depth is not measurable from found photos. Both methods fail, for different reasons.

**Why this matters:** every fringe number in the project — the prior in `data/priors/fringe.json`, the "measured from
after-photo" values in each pair NOTE, EXP_0008's held-out comparison, the interval `predict.py` publishes — comes from
one measurement: SAM prompted with a band at the hem, the returned mask called "fringe". This experiment checks that
measurement against a second, independent one and against negative controls.

## Method A — SAM-prompted fringe mask (what everything used until today)
`tools/compare_fringe_methods.py` over every after-wash whole-garment photo it may use: **7 harvested unpaired + 1
paired** after-photo. (The census in the first version of this note was transposed; it counted one photograph twice,
because the contributor TEST submission had re-used a tutorial's image — that record is now deleted from the manifest;
and it ignored `exclude.txt`, which bans two more paired photos. All three faults came from review 5.)
SAM's fringe depth on these: **0.024–0.606 of waist width**, i.e. up to 24 cm of "fringe" on a 40 cm waistband; most
trip `run_pair`'s plausibility gate. The QA sheets (`reports/fringe_methods/sheet_*.jpg`, magenta) show
what it actually returns: **the bottom third of the fabric**, hem to mid-thigh. It is not measuring threads at all.

## Method B — direct thread measurement (`src/denimtwin/eval/fringe_measure.py`, new)
The threads lie *outside* the coarse garment mask, so measure them there: per column, below the fabric edge, a pixel is
thread if it is at least as light as the local backdrop (or clearly off-hue) and far from it — the lightness condition
is what excludes the garment's drop shadow, which inflated a first prototype by ~3×. Depth is the deepest such pixel
still connected to the edge. Verified on synthetic garments with known fringe depth (6/14/25 px recovered to ±2 px,
shadow rejected, scale-free — `tests/test_fringe_measure.py`), and by eye it hugs the real fringe (yellow in the
sheets) where SAM covers fabric.

| | SAM rel | direct rel |
|---|---|---|
| harvested unpaired (7 photos, all frayed and washed) | 0.024–0.606 | 0.0037–0.0341 |
| paired after-photo (1, the only one not excluded) | 0.099 | 0.0060 |

## The negative control kills both
Four of the paired garments have **finished hems** (cuffed) — they have no fringe by construction, so any depth measured
on them is the method's noise floor. Direct measurement:

| group | n | mean depth_rel | range |
|---|---|---|---|
| finished hem (cuffed) — **should be 0** | 4 | **0.0081** | 0.0033–0.0166 |
| frayed + washed (paired) | 3 | 0.0077 | 0.005–0.0121 |
| frayed + washed (harvested unpaired) | 4 | 0.0071 | 0.0037–0.0114 |

**A cuffed hem measures the same as a frayed one.** The floor comes from garment-mask boundary error: SAM's mask sits a
few pixels inside the true fabric edge, and those first rows are "not backdrop", so they count as threads. At these
image resolutions (fringe ≈ 2–20 px) the floor and the signal are the same size.

## Read
- SAM's fringe mask is **wrong, not noisy** — it measures fabric. Every number derived from it is void, including
  EXP_0008's "prior 17 px vs measured 37 px" and the depths in `data/priors/fringe.json`.
- The direct method is correct in what it paints but its scalar output has no discriminative power on this data.
- Therefore: **fringe depth has never been measured in this project.** The honest state is not "the prior is weak"
  (EXP_0008) but "there is no fringe measurement yet", and no prior can be fitted until there is one.

## Changes made
- `run_pair.py` now records the direct measurement as the fringe number (SAM's value kept alongside in a new
  `measure.json` per pair) — not because it is trustworthy, but because it is not measuring the wrong object.
- Consequence on the bench: fringe IoU drops on four pairs (0.317→0.100, 0.352→0.029, 0.311→0.064, 0.142→0.041) and
  one hem error rises (14.6→20.3 px). Those earlier scores came from rendering a 20–70 px "fringe" that matched SAM's
  fabric-mask; they were never evidence. Baseline refrozen with this note attached.
- No appearance parameter was tuned (docs/GATES.md tuning rule).

## What would fix it
A photo where the fringe is resolvable: contributed close-range shots (fringe ≥ 50 px), or a metric-scale photo with a
coin, where the floor (a few px of mask error) is small against the signal. The contributor form already asks for the
coin; it should also ask for one close-up of the hem. Until then `predict.py` should say the fringe depth is a
placeholder — it already prints "INSUFFICIENT (n<5)", which understates the problem, so the wording is now stronger.

## Rebuild of the prior on one method (2026-08-29, same day)
Every channel now measures the same way (`eval/fringe_measure.py`); the SAM-derived numbers are gone from
`data/priors/*`, and `fringe.json` carries `measurement_method`, `validated: false` and the control result as fields so
no consumer can quote it as evidence by accident.

| | before (SAM) | after (direct) |
|---|---|---|
| after-wash samples in the prior | 3 | **6** (1 paired + 5 unpaired) |
| after-wash mean depth_rel | 0.052 | **0.0071** |
| after-cut mean depth_rel | 0.0015 | 0.0020 |
| held-out error on the one fray pair | 15.2 px (predicted 17.4, measured 2.2) | **0.5 px** (predicted 2.7, measured 2.2) |
| 80% interval coverage | **0.09** (1 hit of 11) | 0.55 of 11, now 0.55 of 10 after the duplicate record was deleted (nominal 0.80 — still miscalibrated) |

The sample count rose because the harvested photos are no longer rejected by a gate that existed only to catch SAM's
broken masks: **5 of 7 candidates measure** (one is a whole pair of jeans, one has too narrow a waist in frame). The
two samples that used to come from the older pairs manifest were later removed for a different reason — their pages
describe *several* washes, and this project predicts one (review 5, finding 10).

**Do not read the improved held-out error as progress on fray prediction.** It is one pair, and the reason prediction
and measurement now agree is that both are small numbers near the method's noise floor. The apparent 3.6× separation
between after-wash (0.0072) and after-cut (0.0020) is also partly manufactured: `fit_fringe.py` forces finished hems
(cuffed/hemmed/serged) to depth 0 by rule, and four of the five after-cut pairs are cuffed. Measured without that rule,
the cuffed controls sit at 0.0081 — indistinguishable from the frayed group. The control result stands, and it is the
finding of record: **we cannot yet measure fray depth from these photos.**

Gate 5 verdict is unchanged: INSUFFICIENT (1 after-wash pair with a held-out prediction; needs ≥10).

## Part F — fifth adversarial review (2026-08-29): fringe DEPTH withdrawn as evidence
A reviewer agent attacked the direct measurement and the rebuilt prior with 22 failing tests. The important ones:

| # | finding | response |
|---|---|---|
| 1 | the measurement returns garment-mask boundary error 1 px for 1 px, with `coverage=1.00, ok=True` | **depth withdrawn as evidence**; every call now reports `sensitivity_px` (how far the answer moves when the mask shifts one pixel) and refuses when that is not small against the depth |
| 2 | the drop-shadow rejection only works when the shadow touches the hem; a 4–16 px offset is measured as fringe | recorded as an accepted limitation (`tests/test_fringe_measure_limitations.py`, strict xfail) — it is why depth is withdrawn, not a bug to patch |
| 3 | every `after_cut` depth in the prior was a hard-coded rule output, labelled as a measurement | rows now carry `depth_px_measured` and `rule_applied` alongside; `measurement_method` says "none — diagnostics, not evidence" |
| 4 | one photograph carried two pair ids (the contributor TEST submission re-used a tutorial's image), so leave-one-out could not exclude it | the TEST record is deleted from the manifest; `prior.aliases_for` now excludes by photograph, and `compare_fringe_methods.py` honours `exclude.txt` |
| 5 | a mottled backdrop alone produced 12–20 px of phantom fringe | **fixed** by the sensitivity check — kept as a live regression test |
| 6 | `prediction.json` presented the placeholder as a passing 8-sample prior, and its last warning switched itself off on a bigger photo | the prediction carries the prior's own `validated: false` and note, warns unconditionally, and `insufficient` is no longer recomputed from counts |
| 7 | `depth_rel` is not scale-free once threads resolve (fixed 3 px gap walk) | gap is now a fraction of waist width; the residual truncation is an accepted limitation |
| 8 | `coverage` silently dropped columns with no room below the garment | denominator fixed to all garment columns |
| 10 | the manifest unpaired channel had no hem-finish or wash-count gate; both its samples were multi-wash | gated; both dropped (this project predicts ONE wash) |
| 12 | a mask/image shape mismatch raised IndexError from inside the loop | returns `ok=False` with a reason |

Six numeric claims in this note were wrong; all corrected above, and `tests/test_exp0015_claims.py` now checks the
note against the artefacts it cites so they cannot drift again.

**Where the fray claim stands after five reviews:** depth is unmeasurable and no longer used as evidence anywhere;
the only sourced number is 12.7 mm from a tutorial that stitched a stop 1/2 in above the cut and reported the fray
reaching it after one wash; and hem *roughness* (EXP_0016/0017) is the one fray observable that passes a control.
