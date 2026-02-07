# PAIR — auto pipeline

flags: none
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
fringe depth used: 66.7 px from prior[after_wash] (n=8 after excluding self); measured on after-photo: 36.5 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -10.4°, depth 31, right: angle 4.5°, depth 15
registration residual (leave-one-landmark-out): 42.01px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.769 | 16.5 | 22.9 | 0.292 |
| pred median | 0.776 | 16.1 | 22.8 | 0.459 |
| pred aggressive | 0.768 | 21.5 | 22.7 | 0.462 |
| null:no-op | 0.286 | 503.4 | 20.5 | 0.038 |
| null:crop-only | 0.751 | 22.0 | 23.3 | 0.000 |
