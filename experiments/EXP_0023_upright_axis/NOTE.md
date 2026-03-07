# EXP_0023 — Uprighting read the wrong axis, so it did nothing on the garment this project is about

EXP_0022 turned the upright deadband off and claimed the tilt problem solved. Re-measuring EXP_0021's own numbers with
uprighting switched on says otherwise: on 8 of 16 photographs the shape ratios still moved exactly as much as before.

The cause is one line. `tilt_angle` returned the angle of the silhouette's **long** axis from vertical. A pair of
shorts laid flat is usually **wider than tall** — 9 of the 16 photographs have height/width 0.60–0.85 — so its long
axis runs left-to-right and the function returned ~±88°, outside `max_correctable_tilt`, and uprighting silently did
nothing. It worked on full-length jeans and skipped the shorts.

Reading whichever principal axis is closer to vertical turns those same nine photographs into tilts of −3.4° to +2.6°,
which is what they are.

## Part A — the invariance, re-measured (`experiment_landmark_rotation.py --upright`)

Deviation of a scale-free shape ratio when the same mask is rotated, and the number of subjects that lose more than 5%.

| statistic | raw mask (EXP_0021) | uprighted, long axis (EXP_0022) | uprighted, near-vertical axis |
|---|---|---|---|
| rise / waist | 6 of 16 lose >5% by 5°; median 7.9% at 8°, max 51.8% | 8 of 16 unchanged | **0 of 16 by 5°; 11 of 16 never exceed 5% up to 20°; median 0.2% at 8°, max 3.6%** |
| height / waist | 6 of 16; median 7.3%, max 53.3% | — | 0 of 16; 12 of 16 never; median 0.3%, max 1.4% |
| hip / waist | 5 of 16; median 2.6%, max 46.4% | — | 0 of 16; 13 of 16 never; median 0.2%, max 0.9% |

## Part B — the same, through SAM on 16 photographs × 14 simulated re-captures

| perturbation | rise/waist, raw | rise/waist, uprighted | height/waist, raw | uprighted |
|---|---|---|---|---|
| rot +3° | 2.0% | 0.4% | 1.1% | 0.3% |
| **rot +8°** | **29.6%** | **0.5%** | **32.1%** | **0.5%** |
| combined re-capture b | 6.8% | 0.7% | 10.2% | 0.7% |
| every photometric perturbation | ≤0.4% | ≤0.6% | ≤0.3% | ≤0.6% |

The tilt term is gone: every geometric perturbation now moves the ratios by at most 1.5%.

## Part C — the pair A/B (`compare_upright_ab.py`, 7 pairs after `exclude.txt`)

| metric | long axis | near-vertical axis | better / worse / tied | sign p |
|---|---|---|---|---|
| silhouette IoU | 0.8365 | **0.8566** | 4 / 2 / 1 | 0.688 |
| hem chamfer (px) | 13.31 | **7.85** | 3 / 3 / 1 | 1.000 |
| edge-band ΔE | 18.60 | 18.23 | 4 / 2 / 1 | 0.688 |
| fringe IoU | 0.0746 | **0.1004** | 4 / 2 / 1 | 0.688 |

Three pairs gain a lot — 2691c1a8d0 IoU 0.615 → 0.736 with hem error 47.5 → 11.5 px, 4bfef03bd7 0.756 → 0.807 with
20.9 → 4.5 px, 8d9f0df4ad 8.8 → 3.2 px — and in each the change is that the AFTER photo (the shorts) is uprighted for
the first time.

**One pair regresses past the bench tolerance, and it is recorded rather than tuned away.** 443d1d4658 loses 0.052 of
IoU and gains 19.6 px of hem error. Its after photo is a pair of red shorts on a cutting mat; the mat's grid shows the
garment is already square, and the estimate says 4.8°. The silhouette's two second moments are nearly equal there
(elongation 1.10), which is the regime EXP_0022 measured as unreliable — the existing flag fires at ≥5° and this is
4.8°. The before photo is uprighted by −3.6° and the after by +4.8°, so the two frames end up 8.4° apart and
registration pays for it.

`tools/bench.py` therefore reports a regression on this pair, and **the baseline is not re-frozen to hide it**. The
right fix is not a threshold: it is for `run_pair` to put the after photo in the *before photo's* frame — which the
registration step already estimates — instead of uprighting the two photographs independently. That is the next
experiment, and this note is the reason it exists.

## What changed
- `canon/upright.tilt_angle` reads the near-vertical principal axis. A consequence worth knowing: |angle| is now at
  most 45° by construction, so a garment truly lying at 50° reads as −40°, and the silhouette alone cannot tell them
  apart.
- `tests/test_upright.py` gains a wide-garment fixture (wider than tall, like the real subjects) and pins both the
  invariance and the 45° ceiling.
