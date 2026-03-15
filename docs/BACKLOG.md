# Backlog

What is open, what is closed and why, and what each item is blocked on. Updated when an
experiment closes a line. Run `tools/verify.py` before and after any change here.

## The one question that matters now

**Answered, negatively (EXP_0035).** Gate 1's restatement asked whether the pipeline could *choose*
an inseam fraction from the before photo and beat the constant baseline (0.7278 IoU). It cannot,
and the reason is not a modelling failure: the cut height is a style choice, not a property of the
garment. Six shape features, nested leave-one-out with the feature chosen inside the fold — MAE
0.2586 against a constant's 0.1690 (53% worse), and on the bench's own metric **0.6738 against
0.7278**, losing on 6 of 7 pairs. The seven folds pick four different features.

So the supportable product claim is EXP_0034's: given a cut height, the pipeline places and renders
it far better than not knowing it (**+0.0954, 4.8σ**), and the inseam fraction belongs in the
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

## Open, unblocked (code only)

- **`443d1d4658` bench regression** — two documented metrics (IoU 0.918→0.857, hem 8.9→27.7). The
  cheap waistband fix was ruled out (EXP_0026); what is named is an "is this line the waistband"
  test. This is the one pair the independent null *beats* the product path on (−0.0068, −3.6σ).
- **The eval-vs-product gap (0.857 vs 0.823)** — EXP_0028 showed handing the product path the exact
  cut region closes it (0.8735 vs 0.8750), so the gap is knowledge of where the cut goes. EXP_0035
  now shows that knowledge cannot come from the garment, so this gap closes only with a user input,
  not with a better model. Not independently actionable.
- **Fringe rendering is invisible in the bench** — with `--wash none` the fringe is 0.0 px and the
  prediction is the crop plus ≤256 px. Any fringe claim needs a run with wash enabled *and* an
  independent null; none has been done.

## Blocked on data

- **Gate 1 repeatability** — needs a repeat capture of one garment. Nothing in the found-pair set
  is a re-capture.
- **Fray observables** — need an after-photo with ≥600 px of waistband. Found pairs give 241–389 px.
- **Predicting the cut height at all** — EXP_0035's negative result holds at n=7; a genuine
  r² ≈ 0.3 would need roughly 25 pairs to separate from noise.
- **Any heuristic threshold change** — the tuning rule (`docs/GATES.md`) requires ≥5 usable pairs
  with a report attached.
- **Found-pair channel is exhausted** (EXP_0005/0007): 32 tutorial pages → 6 cut pairs + 1 fray
  pair. Contributed after-wash photos with a coin in frame are the only lever
  (`CONTRIBUTING_PAIRS.md`).

## Known defects accepted, not fixed

- **`run_pair.py` writes `*_used.png` before the `sane()` gates** (line 110 vs 129), so a directory
  re-run and then rejected keeps fresh images beside stale masks. Two directories are in that state
  (`660bef67bf`, `85d48013a2`); both are rejected and nothing scores them
  (`score_predict.py:48`). Guarded by `tests/test_pair_dirs_consistent.py` for the case that would
  hurt — an *accepted* directory with disagreeing artefacts.
- **926 copyrighted derived images are in the pushed GitHub history.** Untracked going forward and
  ignored via `experiments/**/*.png|jpg|jpeg`; removing them from history is the owner's call.
- **`lmcheck`'s "crotch above the hips" rule is unreachable for auto landmarks** — `autolm` searches
  `range(hip_y, bot)`, so an auto crotch can never sit above the hips. Kept for manual landmarks.

## Standing rules

- `tools/verify.py` is the gate; CI runs it blocking (`--no-bench`).
- A baseline may not be derived from the model's own output (`docs/GATES.md`, baseline rule).
- Quote the **paired** uncertainty on a method difference, never the unpaired one; a cancellation
  factor in the hundreds means the two arms are the same object (EXP_0033/0034).
- Every number in a NOTE, the README or `docs/` is checked by `tools/check_claims.py`.
