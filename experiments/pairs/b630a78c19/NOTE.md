# PAIR — auto pipeline

flags: after: rotated -10.7° to upright
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 60.2 px from measured from after-photo (NOT a prediction); measured on after-photo: 60.2 px (fabric/fringe split: SAM)
hem fit: left: angle -0.8°, depth 5, right: angle 72.4°, depth 116
registration residual (leave-one-landmark-out): 52.04px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.557 | 243.2 | 16.0 | 0.099 |
| pred median | 0.558 | 242.2 | 16.0 | 0.217 |
| pred aggressive | 0.559 | 241.5 | 16.0 | 0.302 |
| null:no-op | 0.534 | 295.9 | 15.1 | 0.173 |
| null:crop-only | 0.556 | 244.2 | 16.0 | 0.000 |
