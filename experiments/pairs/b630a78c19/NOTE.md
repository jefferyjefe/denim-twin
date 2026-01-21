# PAIR — auto pipeline

before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
hem fit: left: angle -5.1°, depth 54, right: angle 4.7°, depth 14
registration residual (leave-one-landmark-out): 11.02px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.874 | 64.5 | 14.3 | 0.083 |
| pred median | 0.878 | 60.9 | 14.2 | 0.187 |
| pred aggressive | 0.881 | 57.6 | 14.1 | 0.276 |
| null:no-op | 0.730 | 141.8 | 11.8 | 0.145 |
| null:crop-only | 0.871 | 67.1 | 14.4 | 0.000 |
