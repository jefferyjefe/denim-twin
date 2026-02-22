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
