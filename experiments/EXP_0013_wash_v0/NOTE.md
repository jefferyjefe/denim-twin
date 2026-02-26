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

## Part B — batch A/B, `--wash median` vs none, 11 usable pairs (experiments/pairs_wash vs experiments/pairs)
| metric | change | reading |
|---|---|---|
| sil IoU vs real | −0.01 … +0.01 | unchanged: 2% shrink is inside registration noise |
| hem error | −1.8 … +1.1 px | unchanged |
| ΔE kept region vs real (lighting-matched) | lower on 10/11 pairs, by 0.0–1.4 | weak, consistent; direction of the dye-loss prior is right but the effect is at the noise floor |
| SSIM kept vs real | +0.00 … +0.06 (10/11 up) | same weak signal |
| fringe IoU | −0.01 … +0.07 | fringe now grows from the shrunk edge; slightly better on 6 pairs |
| **SSIM kept vs before** | **1.00 → 0.26–0.87** | see below |

**Metric finding (plan §6.2):** the identity metrics compare the prediction to the *before* photo pixel-for-pixel, so any
legitimate global shrinkage reads as identity loss (SSIM 0.26 on the largest garment). Identity should be measured after
aligning the prediction to the reference (register, then SSIM/ΔE/feature retention), otherwise a correct wash model is
penalised and a no-op is rewarded. Until that change, `ssim_keep_vs_before` is only meaningful for `--wash none`.

**Decision:** wash v0 ships off-by-default as the interval-bearing placeholder the plan asks for; no parameter is tuned
(tuning rule, docs/GATES.md). Next: alignment-aware identity metrics; measurement of real shrinkage the moment a
coin-scaled contributed pair arrives (`tools/experiment_gate5.py` will pick it up).

## Part C — alignment-aware identity metrics (fix for the finding above)
`eval/identity.align_to_reference` estimates a **bounded affine** map from the prediction to the reference — initialised
from the two masks' second central moments (which recover anisotropic shrink directly), refined by ECC on masked
intensity, with every axis scale clipped to ±15% — and `aligned_identity` reports SSIM / ΔE / location-checked feature
retention after that map. Bounded on purpose: alignment must not be able to drag arbitrary content into place.

Synthetic check (`tests/test_aligned_identity.py`): a 2%/1% shrink scores naive SSIM 0.82 → **aligned 0.98** with the
recovered axis scales 1.0204 / 1.0102 (exactly 1/0.98 and 1/0.99); a blurred garment still scores 0.78 / feature
retention 0.06, and a 2× rescale is refused rather than "aligned".

On the 11 real pairs (`ssim_keep_vs_before` → `ssim_keep_vs_before_aligned`, median preset):

| run | naive | aligned | recovered scale |
|---|---|---|---|
| `--wash none` | 0.993 | 0.992 | 1.000 |
| `--wash median` | 0.522 | **0.935** | 1.015 (= 1/0.985, the applied shrink) |

Null baselines score 1.00 aligned, as they must (they change nothing). Both metrics are now reported for every system;
the strict pixel-copy check `ssim_keep_vs_before` remains the Gate 2 evidence for `--wash none`.

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
