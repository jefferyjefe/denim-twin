# PAIR — auto pipeline

flags: none
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
fringe depth used: 37.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 37.5 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 4.8°, depth 37, right: angle -3.1°, depth 0
registration residual (leave-one-landmark-out): 84.35px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.733 | 22.3 | 25.1 | 0.144 |
| pred median | 0.738 | 21.5 | 24.8 | 0.275 |
| pred aggressive | 0.739 | 22.2 | 24.5 | 0.344 |
| null:no-op | 0.280 | 528.7 | 22.8 | 0.035 |
| null:crop-only | 0.727 | 23.8 | 25.3 | 0.000 |
