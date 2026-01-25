# PAIR — auto pipeline

before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
fringe depth used: 2.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 2.5 px
hem fit: left: angle 2.6°, depth 1, right: angle -2.0°, depth 4
registration residual (leave-one-landmark-out): 11.10px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.794 | 24.8 | 22.5 | 0.017 |
| pred median | 0.794 | 25.0 | 22.5 | 0.032 |
| pred aggressive | 0.793 | 25.5 | 22.5 | 0.041 |
| null:no-op | 0.345 | 458.2 | 24.9 | 0.002 |
| null:crop-only | 0.795 | 24.6 | 22.7 | 0.000 |
