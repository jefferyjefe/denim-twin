# PAIR — auto pipeline

before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 13.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 13.5 px
hem fit: left: angle -5.5°, depth 18, right: angle -8.5°, depth 9
registration residual (leave-one-landmark-out): 11.02px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.882 | 59.3 | 13.7 | 0.043 |
| pred median | 0.883 | 58.0 | 13.7 | 0.098 |
| pred aggressive | 0.884 | 57.1 | 13.6 | 0.142 |
| null:no-op | 0.730 | 141.8 | 12.5 | 0.114 |
| null:crop-only | 0.881 | 60.2 | 13.7 | 0.000 |
