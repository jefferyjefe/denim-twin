# PAIR — auto pipeline

flags: before: rotated -23.5° to upright
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2b0123d732_before_07ba40f3.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2b0123d732_after_cut_23fa579b.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 8.1 px from measured from after-photo (NOT a prediction); measured on after-photo: 8.1 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -20.0°, depth 1, right: angle 54.9°, depth 5
registration residual (leave-one-landmark-out): 76.77px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.847 | 11.0 | 15.7 | 0.154 |
| pred median | 0.847 | 11.4 | 15.8 | 0.317 |
| pred aggressive | 0.846 | 11.9 | 15.8 | 0.312 |
| null:no-op | 0.664 | 87.5 | 19.6 | 0.025 |
| null:crop-only | 0.847 | 11.1 | 15.5 | 0.000 |
