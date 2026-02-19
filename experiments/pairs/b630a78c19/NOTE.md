# PAIR — auto pipeline

flags: after: rotated -10.7° to upright
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 307.2 px from measured from after-photo (NOT a prediction); measured on after-photo: 307.2 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -0.7°, depth 6 px, right: angle -20.2°, depth 56 px
registration residual (leave-one-landmark-out): 41.30px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.464 | 231.6 | 17.9 | 0.076 |
| pred median | 0.474 | 210.2 | 18.2 | 0.179 |
| pred aggressive | 0.482 | 200.5 | 18.1 | 0.251 |
| null:no-op | 0.536 | 161.9 | 16.4 | 0.582 |
| null:crop-only | 0.459 | 260.9 | 17.4 | 0.000 |
