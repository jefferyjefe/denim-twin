# EXP_0013 — Procedural wash appearance v0 (shrink + hem roll + dye loss): does it help, and can we measure it?

**Why:** the thesis is "cut AND washed once"; until now the only wash effect modelled was the fringe. `canon/wash.py`
adds the rest of a first laundering: anisotropic shrinkage (prior: 2% along / 1% across, textile-industry ranges for
sanforized cotton denim), a hem-roll shading strip on the fabric side of the cut, and a small lightness gain /
chroma loss. Presets conservative / median / aggressive; `none` is byte-identical. Off by default (`run_pair.py --wash`,
batch `PAIRS_WASH=`), so the bench baseline is untouched.

## Part A — can shrinkage be measured from found pairs? **No.**
Scale-free ratio crotch-depth / waist-width from the auto landmarks, before → after, on the 11 usable pairs:
0.48→0.98, 0.80→0.93, 0.45→0.97, 0.67→0.67, 0.60→0.81, 0.79→0.81, 0.70→0.79, 0.67→0.77, 0.73→0.45, 1.06→0.97, 1.15→0.80.
Cut-only pairs (no wash) move by up to ±0.5 — landmark noise on re-laid found photos is two orders of magnitude above a
1–3% shrinkage signal. Shrinkage parameters therefore stay **priors** until metric-scale contributed pairs (coin in frame,
same lay) exist; the contributor form already asks for exactly that.

## Part B — batch A/B, `--wash median` vs none, 11 usable pairs (RECOMPUTED 2026-08-29 after review 4)
The first version of this table was scored against a moving reference: `run_pair --wash` reassigned the garment/removed
masks to the *shrunk* ones, and those masks define `garment_before` in `compare.py`, i.e. the null baselines themselves
(review 4, finding 5 — null IoU drifted by up to 0.017, the same size as the effects being claimed). Scoring masks are
now pinned to the pre-wash garment; only the prediction's silhouette shrinks. Both batches were re-run. Null drift is
now exactly 0.000000 on every pair. The corrected deltas (wash − no-wash, prediction row):

| metric | range over 11 pairs | pairs improved | reading |
|---|---|---|---|
| sil IoU vs real | −0.010 … +0.011 | 5/11 | unchanged: a 2% shrink is inside registration noise |
| hem error | −1.36 … +7.86 px | 5/11 | unchanged except b630a78c19 (+7.9 px), the pair that fails anyway |
| ΔE kept region vs real | −0.52 … +1.03 | 2/11 | **worse on 9/11** — the earlier "better on 10/11" was the moving reference |
| SSIM kept vs real | −0.011 … +0.050 | 3/11 | mixed, at the noise floor |
| fringe IoU vs real | −0.196 … 0.000 | 0/11 | **worse on 10/11**: shrinking the edge moves the fringe off the real one |
| SSIM kept vs before | −0.755 … −0.173 | 0/11 | expected: the wash changes kept pixels by design (see Part C) |

**Read:** with the reference pinned, procedural wash v0 does not improve any metric on real found pairs and measurably
hurts fringe overlap. That is the expected outcome for parameters nobody fitted (Part D: they have no verified source),
and it is the reason the model ships **off by default** everywhere except `predict.py`, where the thesis question
("cut *and washed*") makes an explicit wash the honest default. No parameter was tuned in response to this table
(tuning rule, docs/GATES.md).

## Part C — alignment-aware identity metrics
`eval/identity.align_to_reference` estimates a **bounded affine** map from the prediction to the reference — initialised
from the two masks' second central moments, refined by ECC on masked intensity — and `aligned_identity` reports
SSIM / ΔE / location-checked feature retention after it. The bounds are the point, and review 4 (finding 2) showed the
first version had none that mattered: it tested only singular values, which are (1, 1) for **any** rotation, so a 15°
rotation scored 0.98 "aligned". Now each axis scale (±15%), the rotation (±2°) and the shear (±2°) are checked
separately from a proper decomposition; an out-of-bounds estimate is **refused** (recorded in `info["refused"]`,
`bound_hit`) and the metrics see the unaligned prediction.

Two further corrections from the same review: the score is computed over the **whole reference keep region**, with
pixels the prediction does not claim filled by the reference backdrop and their share reported as `claimed` — scoring
the intersection let a system raise its identity score by destroying fabric and not claiming it (finding 3); and
`axis_scales` is always `[scale_x, scale_y]` in image order rather than sorted singular values, so the anisotropy
direction — the entire point of an anisotropic shrink model — is recoverable (finding 6).

On the 11 real pairs (median preset, re-run after the fixes):

| run | naive SSIM vs before | aligned | recovered scale |
|---|---|---|---|
| `--wash none` | 0.993 | 0.991 | 1.000 |
| `--wash median` | 0.497 | 0.921 | 1.0149 (the applied shrink is 1/0.985 = 1.0152) |

Caveat recorded by the same review (finding 11): on the real-pairs path `compare.py` passes `sil & keep == keep` as
both masks, so the moment initialisation is the identity there and the whole recovery comes from ECC. The moment step
does its job in the synthetic tests, where the two masks genuinely differ.

## Part D — the shrinkage prior has no verified source behind its anisotropy (2026-08-29)
The module says "~1–3% warp, ~0.5–2% weft" for sanforized denim. Searching for the primary evidence found exactly one
verifiable measurement paper (LITERATURE.md entry 14, Talu 2021): a printed 50 cm square photographed before and after
washing, six denim types × five samples, dimensional change 0.04–5.0% in one direction and 0.04–1.3% in the other, with
a ±0.33–0.5% measurement precision. It is **industrial roll washing, not one home cycle on a made-up garment**, and its
results table does not label the directions warp/weft — and the larger changes are in the *width* direction, i.e. it
does not support the warp-dominant anisotropy `canon/wash.py` assumes. The commonly quoted "1–3% sanforized" figure
traces only to trade/SEO pages, not to a study we could read.

Consequence: `shrink_along_frac` / `shrink_across_frac` stay unsupported priors, the wash model stays off by default,
and the honest statement is "we do not know the anisotropy". A single contributed pair with a coin in frame would
measure it directly at ~0.5% precision — the same precision the published vision method achieves.

## Part E — fourth adversarial review (2026-08-29): 8 code bugs, 6 documentation overclaims
A reviewer agent was pointed at everything written today and told to write failing tests, not fixes. It found:

| # | bug | consequence | fixed in |
|---|---|---|---|
| 1 | `apply_cut` collapsed any canonical removal mask to its topmost row | **every angled cut was rendered flat**; EXP_0014's angle finding was measured on code that ignored angles | `canon/cut2d.py` (per-column lookup), `predict.py` (angle pivots about the cut height so ±a mirror) |
| 2 | alignment bounded only singular values, which are (1,1) for any rotation | a 15° rotated garment scored aligned SSIM 0.98 | `eval/identity.py` (`_decompose`, separate scale/rotation/shear bounds, explicit refusal) |
| 3 | aligned identity scored the intersection of the masks | destroying fabric and not claiming it *raised* the score (0.968 vs 0.926) | score the whole reference keep region; unclaimed pixels filled with backdrop; `claimed` reported |
| 4 | `predict.py` floored the rendered fringe depth but published the unfloored interval | a tile labelled "aggressive (15 px)" contained a 19 px fringe | render exactly lo/median/hi |
| 5 | `--wash` reassigned the masks that define the null baselines | the A/B in Part B was against a moving reference (null drift up to 0.017) | scoring masks pinned pre-wash; nulls now drift 0.000000 |
| 6 | `axis_scales` was sorted singular values on one path, `[x, y]` on the other | anisotropy direction — the point of the shrink model — was unrecoverable | always `[scale_x, scale_y]` |
| 7 | the presentation (texture) backdrop fill fed scored images | `dE_edge_band` moved with a presentation RNG seed alone | `predict.py` scores the deterministic fill; texture only in `panel.jpg`; invariant tested |
| 8 | a "hem roll 5 mm" flag in runs with no metric scale | the rendered strip was 5 **px**, ~8× off at phone scale | flag states px and says so |

Documentation overclaims, all corrected: Part B's hem-error range was wrong and omitted the worst pair; "a 2× rescale
is refused" was false (it was clipped and applied — now genuinely refused with `bound_hit`); "moment initialisation
recovers anisotropic shrink" does not apply on the real-pairs path (both masks are identical there — recorded in
Part C); `experiment_gate5.py` does not and will not pick up a shrinkage measurement; Gate 2's "by construction"
wording did not cover `predict.py --wash median`, which alters kept pixels by design (`docs/GATES_STATUS.json` now
scopes the gate, and every `prediction.json` reports `changed_fraction_of_kept_region`); README's test count was stale.

All 10 reviewer tests now pass, as do the 3 restated ones for finding 7 (the original pair asserted a property the
helper cannot have in isolation — the invariant is that scored images never come from it). Suite: 102 + 1 xfail.
