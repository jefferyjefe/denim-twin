# PAIR — auto pipeline

before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 191.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 191.5 px (fabric/fringe split: SAM)
hem fit: left: angle 0.7°, depth 383, right: angle -9.9°, depth 0
registration residual (leave-one-landmark-out): 11.02px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.742 | 155.7 | 15.7 | 0.061 |
| pred median | 0.744 | 155.7 | 16.2 | 0.131 |
| pred aggressive | 0.745 | 156.3 | 16.2 | 0.180 |
| null:no-op | 0.730 | 141.8 | 14.1 | 0.411 |
| null:crop-only | 0.738 | 157.5 | 15.5 | 0.000 |
