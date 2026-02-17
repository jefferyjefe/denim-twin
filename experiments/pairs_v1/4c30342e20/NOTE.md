# PAIR — auto pipeline

flags: none
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4c30342e20_before_ccfb944a.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4c30342e20_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 64.4 px from measured from after-photo (NOT a prediction); measured on after-photo: 64.4 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -15.2°, depth 70, right: angle -2.0°, depth 32
registration residual (leave-one-landmark-out): 103.36px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.858 | 43.0 | 22.9 | 0.142 |
| pred median | 0.872 | 34.9 | 22.1 | 0.302 |
| pred aggressive | 0.877 | 32.5 | 21.7 | 0.381 |
| null:no-op | 0.279 | 810.3 | 15.3 | 0.043 |
| null:crop-only | 0.845 | 51.7 | 24.1 | 0.000 |
