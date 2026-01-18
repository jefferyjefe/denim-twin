# PAIR — auto pipeline

before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
hem fit: left: angle -16.9°, depth 2, right: angle 19.1°, depth 2
registration residual (landmarks, not held-out): 0.00px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.874 | 9.9 | 22.7 | 0.288 |
| pred median | 0.875 | 9.8 | 22.7 | 0.350 |
| pred aggressive | 0.876 | 9.7 | 22.7 | 0.436 |
| null:no-op | 0.335 | 120.6 | 28.8 | 0.012 |
| null:crop-only | 0.869 | 10.2 | 23.0 | 0.000 |
