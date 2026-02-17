# PAIR — auto pipeline

flags: after: rotated -10.7° to upright
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 297.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 297.5 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 73.8°, depth 5, right: angle 3.5°, depth 82
registration residual (leave-one-landmark-out): 82.88px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.475 | 306.8 | 20.6 | 0.297 |
| pred median | 0.520 | 247.1 | 20.8 | 0.644 |
| pred aggressive | 0.538 | 252.2 | 20.4 | 0.768 |
| null:no-op | 0.528 | 296.3 | 13.9 | 0.641 |
| null:crop-only | 0.437 | 363.7 | 21.5 | 0.000 |
