# EXP_0038 — A garment that cannot fray was having its hem measured from a fringe

EXP_0037 confirmed uprighting caused `443d1d4658`'s bench regression and disconfirmed the stated
mechanism, leaving it unknown. Two further explanations were tested and died — the leg-split column
assignment (insensitive across ±60 px) and hem-fit instability under rotation (the response is
rigid, slope ≈ −1.0/degree). The mechanism turned out to be a branch, not a geometry.

## The mechanism

`estimate_hems` has three paths for locating the fabric edge, in priority order: a SAM **fringe
mask** if one is supplied, else a **colour split** of the registered after-image, else the **mask**
alone. Running the pair both ways and forcing each path shows the two arms were on different ones:

| arm | path actually taken | left hem angle | right hem angle |
|---|---|---|---|
| uprighting on | fringe mask | **25.4°** | −8.6° |
| uprighting off | colour split (no fringe mask produced) | 11.4° | −11.3° |
| uprighting on, forced onto the colour split | colour split | 15.7° | −7.2° |

Uprighting did not move the hem. It changed whether SAM produced a fringe mask at all, and that
switched `estimate_hems` onto a branch that puts the left leg's fitted line 14° away.

## Why that branch should never have run

`443d1d4658` is `edge_treatment: cuffed`. A cuffed hem does not fray — the project has held this
since EXP_0017, and `run_pair.py` says so in its own flags: *"no fringe rendered: edge_treatment
'cuffed' with no wash does not fray"*. Its NOTE simultaneously records *"SAM/hem-fit said 47.5px"*
of fringe on that same cuffed hem.

The `expects_fringe()` test was computed **after** `estimate_hems` and used only to suppress
**rendering**. So the fringe was correctly not drawn, and just as incorrectly still used to decide
where the fabric ends. A segmentation artefact on a garment that cannot fray was driving the
measurement.

This is a logic error, not a tuned threshold: the condition already existed and was applied to one
of the two things it governs.

## The fix

Compute `expects_fringe()` before the hem fit and pass `fringe_mask=fr_before if _expects else
None`, with a flag recording when a mask was ignored.

## A/B on all seven scored pairs (tuning rule)

| pair | gated | Δ silhouette IoU | Δ hem chamfer |
|---|---|---|---|
| 2691c1a8d0 | yes | −0.0027 | +0.97 px |
| 26b1041d00 | no | 0.0000 | 0.00 px |
| 2b0123d732 | yes | −0.0092 | +3.38 px |
| **443d1d4658** | yes | **+0.0419** | **-20.13 px** |
| 4bfef03bd7 | no | 0.0000 | 0.00 px |
| 8d9f0df4ad | yes | −0.0018 | +0.77 px |
| e97924ad2d | no | 0.0000 | 0.00 px |

**mean silhouette IoU 0.8566 → 0.8606 (+0.0040); mean hem chamfer 7.85 → 5.70 px (−2.15).**
Four pairs are gated, one improves, three worsen slightly, three are untouched.

The three regressions are real and should not be waved away: on those pairs SAM's spurious fringe
was accidentally landing closer to the true hem than the colour split does. That is a defect in the
**colour split**, now visible because the artefact that was masking it is gone. It is not a reason
to keep reading a fringe off a garment that cannot fray.

The whole bench is green for the first time — all 21 metrics within tolerance, including
`443d1d4658`, whose regression has been open since EXP_0022 — and **no baseline was re-frozen** to
achieve it. The three small regressions fall inside the existing tolerance, so they stay visible to
`tools/bench.py` rather than being absorbed into a new baseline.

## What this does not fix

`443d1d4658`'s silhouette IoU is 0.898 against the 0.918 that uprighting-off gives, so uprighting
still costs this pair something beyond the branch switch. The hem is now *better* than the
uprighting-off arm (7.54 px against 8.92), so whatever remains is not in the hem line.

## Files

- `tools/run_pair.py` — the gate
- `reports/fringe_gate_ab.json`, `experiments/pairs_prefringegate/` (the before arm, reproducible)
- `tests/test_fringe_gate.py`
