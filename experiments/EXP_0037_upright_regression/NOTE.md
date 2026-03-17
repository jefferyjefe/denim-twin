# EXP_0037 — The regression is uprighting's fault; the reason given for it is not

`443d1d4658` is the last unblocked item on the backlog: two bench metrics past tolerance
(IoU 0.918 → 0.857, hem 8.9 → 27.7 px) and the one pair where the independent null beats the product
path (−0.0068, −3.6σ). The README says it regressed "because before and after are uprighted
independently — recorded, not tuned away, and the named next step". This takes the next step.

The attribution to uprighting is correct. The mechanism is not.

## Cause: confirmed exactly

Re-running the pair with uprighting disabled (`--upright-deadband 90`), everything else identical:

| arm | silhouette IoU | hem chamfer | left hem angle | right hem angle |
|---|---|---|---|---|
| uprighting on (current) | 0.8566 | 27.67 px | 25.4° | −8.6° |
| **uprighting off** | **0.9180** | **8.92 px** | 11.4° | −11.3° |
| frozen bench baseline | 0.918 | 8.916 px | | |

Uprighting off reproduces the frozen baseline to three decimals on both metrics. There is no
ambiguity about what changed this pair's score.

Note the hem angles. Flat-laid, the two legs should be cut at near mirror-image angles, and with
uprighting off they are: **11.4° and −11.3°**. With uprighting on they are 25.4° and −8.6°, and the
per-leg fringe depths swap character too (1 px / 16 px against 14 px / 2 px).

## Mechanism: not supported

"Because before and after are uprighted independently" predicts a dose-response — the more the two
photos are rotated *relative to each other*, the worse the registration and the worse the hem. It
does not hold:

| pair | before° | after° | \|difference\| | hem px |
|---|---|---|---|---|
| **2b0123d732** | −23.5 | 0.0 | **23.5** | **3.8** |
| 2691c1a8d0 | 0.0 | −8.8 | 8.8 | 11.5 |
| **443d1d4658** | −3.6 | 4.8 | 8.4 | **27.7** |
| 4bfef03bd7 | 0.5 | −4.8 | 5.3 | 4.5 |
| e97924ad2d | −1.9 | 2.2 | 4.1 | 1.3 |
| 8d9f0df4ad | −1.2 | 1.1 | 2.3 | 3.2 |
| 26b1041d00 | 0.0 | 2.1 | 2.1 | 3.0 |

**r = +0.092.** The pair with the largest independent rotation by a factor of nearly three
(`2b0123d732`, 23.5°) has the second-*best* hem error in the set. Whatever is wrong with
`443d1d4658` at 8.4° is not a thing that 23.5° does more of.

## A diagnostic that would have been useful, and does not work either

The angle symmetry above looks like a ground-truth-free way to catch a bad hem fit: score
|left + right| and flag the outliers. It fails on the same pair:

| pair | left | right | \|sum\| | hem px |
|---|---|---|---|---|
| **2b0123d732** | −20.0 | 54.9 | **34.9** | **3.8** |
| 443d1d4658 | 25.4 | −8.6 | 16.8 | 27.7 |
| 2691c1a8d0 | −20.9 | 6.5 | 14.4 | 11.5 |
| 26b1041d00 | 12.6 | −9.5 | 3.1 | 3.0 |

**r = +0.213**, and the most asymmetric fit in the set is again the pair with nearly the best hem.
Both candidate diagnostics point at `2b0123d732`, which is fine, and neither points at
`443d1d4658`, which is not.

The hem fit is also not unstable in the obvious way: rotating the real mask through ±6° moves the
fitted angles smoothly at a slope of ≈ −1.0 per degree on both legs, which is the rigid response a
correct fit should give. Whatever uprighting does to this pair, it is not knocking a bistable fit
into the wrong basin.

## What follows

**Not** "turn uprighting off". Uprighting is justified by a directly measured defect — shape ratios
swing 29.6% → 0.5% at 8° of tilt (EXP_0021 Part C / EXP_0023) — and it improves the pair mean
(0.8365 → 0.8566). One pair regressing does not outweigh that, and the tuning rule
(`docs/GATES.md`) exists precisely so a single pair cannot drive a threshold change.

What follows is that the README's causal sentence should be corrected: the cause is uprighting, the
stated mechanism is disconfirmed, and the mechanism is **currently unknown**. Two cheap explanations
were tested and both died. That is where this stands, and saying so is better than leaving a
plausible-sounding reason in the most-read document in the repository.

This is the third causal claim in this project to survive the number and fail the explanation
(EXP_0029's canonical-inverse attribution, EXP_0033's null interpretation, this one). The pattern is
worth naming: a real effect plus a plausible mechanism is not a finding until the mechanism itself
predicts something that is then checked.

## Files

- `tools/experiment_upright_regression.py`, `reports/upright_regression.json`
- `tests/test_upright_regression.py`
