# PAIR — auto pipeline

flags: before: rotated -23.5° to upright
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2b0123d732_before_07ba40f3.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2b0123d732_after_cut_23fa579b.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 7.1 px from measured from after-photo (NOT a prediction); measured on after-photo: 7.1 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -13.7°, depth 1, right: angle 58.3°, depth 2
registration residual (leave-one-landmark-out): 108.85px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.672 | 52.1 | 16.5 | 0.051 |
| pred median | 0.673 | 51.5 | 16.5 | 0.150 |
| pred aggressive | 0.673 | 51.5 | 16.5 | 0.208 |
| null:no-op | 0.623 | 66.3 | 17.5 | 0.109 |
| null:crop-only | 0.671 | 52.5 | 16.2 | 0.000 |
