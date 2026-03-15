# Backlog

What is open, what is closed and why, and what each item is blocked on. Updated when an
experiment closes a line. Run `tools/verify.py` before and after any change here.

## The one question that matters now

**Can the pipeline choose an inseam fraction from the before photo and user intent, and beat
0.7278?** (Gate 1 restatement, EXP_0034.) No experiment in this repository has asked it. Every
product-path run so far has been handed the answer: the only per-garment input is the inseam
fraction, and `run_pair.py:263` measures it from the real after-photo.

Blocked on: nothing in code. Blocked on **judgement** — the inseam fraction is a style choice, and
with 7 pairs spanning 0.000–0.461 there is little reason to believe it is predictable *from the
garment*. The honest framing may be that it is a user input, not a prediction target, in which case
the product claim is "renders a supplied cut height well" (+0.0954, 4.8σ) and Gate 1 should be
rewritten rather than attempted. **Decide this before building a predictor** — fitting one on 7
style-driven samples would be overfitting with a number attached.

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

## Open, unblocked (code only)

- **`443d1d4658` bench regression** — two documented metrics (IoU 0.918→0.857, hem 8.9→27.7). The
  cheap waistband fix was ruled out (EXP_0026); what is named is an "is this line the waistband"
  test. This is the one pair the independent null *beats* the product path on (−0.0068, −3.6σ).
- **The eval-vs-product gap (0.857 vs 0.823)** — EXP_0028 showed handing the product path the exact
  cut region closes it (0.8735 vs 0.8750), so the gap is knowledge of where the cut goes, which is
  the same question as the one at the top. Not independently actionable.
- **Fringe rendering is invisible in the bench** — with `--wash none` the fringe is 0.0 px and the
  prediction is the crop plus ≤256 px. Any fringe claim needs a run with wash enabled *and* an
  independent null; none has been done.

## Blocked on data

- **Gate 1 repeatability** — needs a repeat capture of one garment. Nothing in the found-pair set
  is a re-capture.
- **Fray observables** — need an after-photo with ≥600 px of waistband. Found pairs give 241–389 px.
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
