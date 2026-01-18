# EXP_0004 — pair1 through run_pair.py fully automatically (no clicks)

before: /private/tmp/claude-501/-Users-jefferyhuang/1ef3f3da-1382-4ef0-b947-af045629cb8c/scratchpad/pair1/before.png
after: /private/tmp/claude-501/-Users-jefferyhuang/1ef3f3da-1382-4ef0-b947-af045629cb8c/scratchpad/pair1/after.png
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
hem fit: left: angle -6.2°, depth 3, right: angle 19.2°, depth 2
registration residual (landmarks, not held-out): 0.00px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.875 | 10.1 | 23.2 | 0.327 |
| pred median | 0.875 | 10.1 | 23.2 | 0.377 |
| pred aggressive | 0.873 | 10.3 | 23.1 | 0.375 |
| null:no-op | 0.333 | 121.1 | 30.2 | 0.006 |
| null:crop-only | 0.873 | 10.2 | 23.5 | 0.000 |

## Read
Zero clicks: coarse SAM garment pick (candidate selection with border/area priors) → mask landmarks (crotch via
gap scan; jeans/shorts by aspect ratio) → registration → per-leg hem fit → v1 fringe → scoring.
Geometry is *better* than the hand-clicked run (sil IoU 0.875 vs 0.80; chamfer 10 px vs ~20). Fringe depth
estimate (2–3 px) is far too small — the colour classifier under-calls fringe in this lighting — so fringe IoU
0.38 comes mostly from the hem-band placement. Units are px (no scale reference in found images).
Caveats: registration residual is not held-out; hanger merges into the waist mask; one pair.
