# PAIR — auto pipeline

before: /Users/jefferyhuang/denim-twin/data/external/pair_images/660bef67bf_before_55d52af6.jpg
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/660bef67bf_after_cut_66a745a0.jpg
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
hem fit: left: angle -15.8°, depth 9
registration residual (landmarks, not held-out): 0.00px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.269 | 67.5 | 46.4 | 0.115 |
| pred median | 0.269 | 67.4 | 46.9 | 0.176 |
| pred aggressive | 0.268 | 67.6 | 47.2 | 0.166 |
| null:no-op | 0.230 | 70.9 | 47.2 | 0.059 |
| null:crop-only | 0.268 | 67.4 | 45.8 | 0.000 |
