# PAIR — auto pipeline

before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / prior_no_gap_jeans)
hem fit: left: angle -0.0°, depth 0, right: angle -0.0°, depth 0
registration residual (landmarks, not held-out): 0.01px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.508 | 106.0 | 54.4 | 1.000 |
| pred median | 0.508 | 106.0 | 54.4 | 1.000 |
| pred aggressive | 0.508 | 106.0 | 54.4 | 1.000 |
| null:no-op | 0.508 | 106.0 | 54.5 | 1.000 |
| null:crop-only | 0.508 | 105.8 | 54.5 | 0.000 |
