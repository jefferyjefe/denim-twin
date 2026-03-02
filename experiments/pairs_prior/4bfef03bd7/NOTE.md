# PAIR — auto pipeline

flags: fringe measured directly: 2.0px in the after frame (rel 0.0060, coverage 0.61); SAM/hem-fit said 36.5px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
fringe depth used: 2.7 px from prior[after_wash] (n=5 after excluding self); measured on after-photo: 2.2 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -10.4°, depth 31 px, right: angle 4.5°, depth 15 px
registration residual (leave-one-landmark-out): 42.01px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.751 | 20.7 | 23.4 | 0.013 |
| pred median | 0.753 | 20.2 | 23.4 | 0.033 |
| pred aggressive | 0.755 | 19.5 | 23.3 | 0.063 |
| null:no-op | 0.286 | 529.6 | 20.5 | 0.038 |
| null:crop-only | 0.751 | 21.0 | 23.3 | 0.000 |
