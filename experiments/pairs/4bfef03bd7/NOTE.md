# PAIR — auto pipeline

flags: none
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
fringe depth used: 23.0 px from measured from after-photo (NOT a prediction); measured on after-photo: 23.0 px (fabric/fringe split: SAM)
hem fit: left: angle -10.4°, depth 31, right: angle 4.5°, depth 15
registration residual (leave-one-landmark-out): 42.01px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.759 | 19.3 | 18.9 | 0.123 |
| pred median | 0.767 | 16.8 | 19.5 | 0.265 |
| pred aggressive | 0.771 | 16.1 | 19.9 | 0.338 |
| null:no-op | 0.286 | 503.4 | 20.5 | 0.038 |
| null:crop-only | 0.751 | 22.0 | 23.3 | 0.000 |
