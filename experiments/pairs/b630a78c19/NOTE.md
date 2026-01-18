# PAIR — auto pipeline

before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
hem fit: left: angle -0.5°, depth 14, right: angle 14.5°, depth 13
registration residual (landmarks, not held-out): 0.00px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.808 | 19.5 | 16.9 | 0.179 |
| pred median | 0.810 | 19.3 | 16.9 | 0.370 |
| pred aggressive | 0.812 | 19.1 | 16.9 | 0.521 |
| null:no-op | 0.760 | 28.1 | 16.7 | 0.133 |
| null:crop-only | 0.806 | 19.8 | 16.9 | 0.000 |
