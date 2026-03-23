# EXP_0032 — A garment whose crotch is above its hips, and two directories that were lying

EXP_0031 ended by naming the next step: `2b0123d732`'s landmark set "puts the **crotch above the hips** — a
physically impossible garment ... and it is cheap to detect." This builds that detector, measures it, and finds
that the sentence which motivated it was wrong in an instructive way.

## The detector

`canon/lmcheck.check_landmarks` walks nine orderings a real pair of jeans cannot violate (waist left of waist
right, hips below the waist, crotch below the hips, hems below the crotch, each leg's outer edge outside its
inner edge, legs not swapped) and reports two severities:

- **inverted** — the ordering is reversed. Nothing downstream can repair it; the set describes a garment that
  does not exist.
- **degenerate** — the two landmarks coincide, within 1% of the set's bounding diagonal. The garment is fine;
  the extractor collapsed a region to zero extent. The tolerance is `warp.py`'s `min_sep_frac`, so what this
  reports is exactly what `warp.py` would drop.

## What it finds

On the 14 landmark sets belonging to the seven pairs the bench actually scores:

| | count |
|---|---|
| inverted | **0** |
| degenerate | **4** |
| clean | **10** |

**No landmark set is inverted.** The `2b0123d732` crotch is not *above* its hips — it is *exactly on* them, and it
could not have been otherwise: `autolm.landmarks_from_mask` searches for the crotch gap in `range(yh, bot)`,
starting at the hip row, so the crotch it returns can never have a smaller `y` than the hips. The "physically
impossible garment" of EXP_0031 was equality read as inversion. What it means is real but different: the hip line
was placed *below* the true crotch, so the search began past the thing it was looking for and returned its own
first row.

That makes the `crotch above the hips` rule **structurally unreachable for automatic landmarks**.

> **Corrected by review 7 — this undercounts badly.** It is not one rule, it is **eight of the nine**.
> Most of these landmarks come from `_row_extent`, which returns `(min_x, max_x)` in that order, so
> every left/right and inside-out ordering is true by construction too. Measured
> (`tools/experiment_lmcheck_reachability.py`): over 400 fuzzed garments **no rule fires at all**, and
> only one — `left hem above the crotch` — can be made to fire by a deliberately constructed case
> (shorts with no between-leg gap and a short left leg, so the crotch falls back to the longer leg's
> tip). The right-hem twin stays unreachable because `autolm` slices the left leg as `slice(0, cyx)`
> and the right as `slice(cyx, W)`, so the right sub-mask absorbs the crotch column and takes the
> longer leg's hem row.
>
> So `lmcheck`'s "inverted" severity is **1-of-9 live on the auto path**. The rules are kept for
> manual landmarks (`--before-lm`), where a mis-click can genuinely invert any of them, but counting
> nine rules as coverage of the automatic path was wrong. What actually does the work on that path is
> the `degenerate` severity, which fires on real data.

A check that cannot fail on the path it is aimed at is worth stating plainly rather than counting as coverage.

## It is not a fold gate

The tempting next move is to refuse any garment the check flags. The numbers do not support it:

| | median fold | after `warp.py` drops degenerates |
|---|---|---|
| flagged sets | **0.3863** | 0.0263 |
| clean sets | 0.0157 | 0.0157 |

A 25× separation — but the tails ruin it as a gate. `e97924ad2d after` is flagged and folds **0.0000**; a *clean*
set (`26b1041d00 after`) folds **0.502**; and the worst fold left after the drop, **0.8207**, belongs to a flagged
set (`4bfef03bd7 after`) where dropping `hem_right_inner` barely moved it. Degeneracy is one cause of folding, not
the cause. So `lmcheck` is adopted as a **diagnostic**, not a gate — no refusal threshold, no change to any
pipeline decision, and no pixel changes anywhere.

Those `after` fold numbers describe a map the pipeline never builds, which is worth saying before anyone acts on
them: `register.warp_after_to_before` fits a TPS from before-coords to after-coords **directly** (`register.py:26`),
not through canonical space, so `CanonicalMap` is never constructed for an after photo. EXP_0029 was wrong in
exactly this way and it was checked for here before writing, not after. Whether the map that *is* built folds is
EXP_0033.

## Two directories that were lying

Auditing whether every stored artefact in a pair directory has a shape consistent with its neighbours turned up
**16 of 104 shape pairings disagreeing, all inside two directories**: `660bef67bf` and `85d48013a2`. In both, only
`before_used.png` / `after_used.png` disagree; every measurement artefact agrees with every other.

The cause is an ordering in `run_pair.py`: `*_used.png` is written at line 110, and the `sane()` gates that can
`FAIL` the pair run at line 129. A pair that is rejected on a later re-run therefore leaves *fresh* `_used` images
next to *stale* masks and predictions from an earlier accepted run. Both directories are marked
`# PAIR — rejected`.

Nothing consumed them: `score_predict.py:48` skips any directory whose NOTE begins `rejected`, and neither has a
`modification.json` to score. **No published number is affected.** The invariant is now a test rather than a
one-off audit, because the next such directory might not be rejected.

## Files

- `src/denimtwin/canon/lmcheck.py` — the check
- `tools/experiment_landmark_consistency.py` — `--usable-only` restricts to the seven scored pairs
- `tests/test_lmcheck.py`, `tests/test_pair_dirs_consistent.py`
- `reports/landmark_consistency.json`
