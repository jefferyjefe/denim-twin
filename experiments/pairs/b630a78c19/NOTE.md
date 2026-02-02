# PAIR — auto pipeline

flags: after: rotated -10.7° to upright
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 30.8 px from measured from after-photo (NOT a prediction); measured on after-photo: 30.8 px (fabric/fringe split: SAM)
hem fit: left: angle -0.7°, depth 6, right: angle -20.2°, depth 56
registration residual (leave-one-landmark-out): 41.30px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.459 | 366.0 | 15.9 | 0.007 |
| pred median | 0.460 | 363.3 | 16.3 | 0.017 |
| pred aggressive | 0.460 | 360.9 | 16.6 | 0.026 |
| null:no-op | 0.536 | 296.2 | 16.4 | 0.582 |
| null:crop-only | 0.459 | 367.7 | 17.4 | 0.000 |
