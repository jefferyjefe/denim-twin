# PAIR — auto pipeline

before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
hem fit: left: angle 28.2°, depth 3, right: angle 2.5°, depth 6
registration residual (leave-one-landmark-out): 11.10px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.815 | 16.2 | 21.1 | 0.030 |
| pred median | 0.815 | 16.5 | 21.1 | 0.073 |
| pred aggressive | 0.814 | 16.9 | 21.1 | 0.095 |
| null:no-op | 0.345 | 458.2 | 24.0 | 0.003 |
| null:crop-only | 0.815 | 16.1 | 21.3 | 0.000 |
