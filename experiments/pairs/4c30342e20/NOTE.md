# PAIR — auto pipeline

flags: coin scale rejected: no coin-like circle found
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4c30342e20_before_ccfb944a.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4c30342e20_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 67.3 px from measured from after-photo (NOT a prediction); measured on after-photo: 67.3 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -1.9°, depth 72 px, right: angle -16.5°, depth 30 px
registration residual (leave-one-landmark-out): 56.91px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.852 | 46.0 | 22.7 | 0.117 |
| pred median | 0.857 | 44.7 | 22.2 | 0.236 |
| pred aggressive | 0.859 | 44.7 | 21.9 | 0.309 |
| null:no-op | 0.279 | 820.4 | 16.0 | 0.038 |
| null:crop-only | 0.846 | 48.4 | 23.6 | 0.000 |
